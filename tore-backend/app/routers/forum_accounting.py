"""Capability-protected accounting reads for the Structures Forum.

Operational attendance statistics stay on the existing ``/stats`` surface.
Financial values are exposed separately and the backend remains the security
boundary: UI visibility never substitutes for ``finance.read``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import AppUser, Event, EventCost, Order
from app.core.security.user_auth import get_current_user
from app.deps.db import get_db
from app.routers.forum import _structure_or_404
from app.services.structure_rbac import require_capability
from app.models.accounting import StructureBudget, BudgetCategory, AccountingEntry
from app.services.audit_service import write_audit_log


router = APIRouter(prefix="/forum", tags=["forum-accounting"])

class BudgetIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    period: str = Field(default="ANNUAL", max_length=32)
    notes: str | None = Field(default=None, max_length=5000)

class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    budget_cents: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=2000)

class EntryIn(BaseModel):
    budget_id: int | None = None
    event_id: int | None = None
    category: str = Field(min_length=1, max_length=120)
    entry_type: str = Field(pattern="^(INCOME|EXPENSE|FORECAST)$")
    amount_cents: int = Field(ge=0)
    entry_date: datetime | None = None
    notes: str | None = Field(default=None, max_length=5000)
    attachment_url: str | None = Field(default=None, max_length=1000)

def _budget(db, org_id, budget_id):
    row = db.get(StructureBudget, budget_id)
    if row is None or row.organization_id != org_id:
        raise HTTPException(404, "Budget not found")
    return row

def _assert_mutable(budget):
    if budget.status == "LOCKED":
        raise HTTPException(409, detail={"reason": "ACCOUNTING_LOCKED"})

def _entry_payload(row):
    return {"id": row.id, "budgetId": row.budget_id, "eventId": row.event_id, "category": row.category, "entryType": row.entry_type, "amountCents": row.amount_cents, "entryDate": row.entry_date.isoformat(), "notes": row.notes, "attachmentUrl": row.attachment_url}


def _event_accounting(db: Session, event: Event) -> dict:
    revenue = int(db.scalar(
        select(func.coalesce(func.sum(Order.total_cents), 0)).where(Order.event_id == event.id)
    ) or 0)
    costs = int(db.scalar(
        select(func.coalesce(func.sum(EventCost.amount_cents), 0)).where(EventCost.event_id == event.id)
    ) or 0)
    return {
        "event": {
            "id": event.id,
            "name": event.name,
            "startsAt": event.starts_at.isoformat() if event.starts_at else None,
            "endsAt": event.ends_at.isoformat() if event.ends_at else None,
            "venue": event.venue,
        },
        "revenueCents": revenue,
        "costsCents": costs,
        "resultCents": revenue - costs,
    }


@router.get("/structures/{slug}/accounting-summary")
def get_accounting_summary(
    slug: str,
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _structure_or_404(db, slug)
    membership = require_capability(db, org.id, user, "finance.read")
    events = db.query(Event).filter(
        Event.host_type == "orga",
        Event.host_id == str(org.id),
    ).order_by(Event.starts_at.desc(), Event.id.desc()).limit(24).all()
    rows = [_event_accounting(db, event) for event in events]
    totals = {
        "revenueCents": sum(row["revenueCents"] for row in rows),
        "costsCents": sum(row["costsCents"] for row in rows),
        "resultCents": sum(row["resultCents"] for row in rows),
    }
    return {
        "role": membership.role,
        "currency": "EUR",
        "privateByDefault": True,
        "latest": rows[0] if rows else None,
        "history": rows,
        "totals": totals,
    }

@router.get("/structures/{slug}/accounting")
def accounting_workspace(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug)
    require_capability(db, org.id, user, "finance.read")
    budgets = db.query(StructureBudget).filter_by(organization_id=org.id).order_by(StructureBudget.created_at.desc()).all()
    return {"budgets": [{"id": b.id, "name": b.name, "period": b.period, "status": b.status, "notes": b.notes} for b in budgets], "entries": [_entry_payload(e) for e in db.query(AccountingEntry).filter_by(organization_id=org.id).order_by(AccountingEntry.entry_date.desc()).limit(500).all()]}

@router.post("/structures/{slug}/accounting/budgets")
def create_budget(slug: str, payload: BudgetIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); require_capability(db, org.id, user, "finance.write")
    row = StructureBudget(organization_id=org.id, name=payload.name.strip(), period=payload.period, notes=payload.notes, created_by_user_id=user.id)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "period": row.period, "status": row.status}

@router.post("/structures/{slug}/accounting/budgets/{budget_id}/categories")
def create_category(slug: str, budget_id: int, payload: CategoryIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); require_capability(db, org.id, user, "finance.write"); budget = _budget(db, org.id, budget_id); _assert_mutable(budget)
    row = BudgetCategory(budget_id=budget.id, name=payload.name.strip(), budget_cents=payload.budget_cents, notes=payload.notes); db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "name": row.name, "budgetCents": row.budget_cents, "notes": row.notes}

@router.post("/structures/{slug}/accounting/entries")
def create_entry(slug: str, payload: EntryIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); require_capability(db, org.id, user, "finance.write")
    budget = _budget(db, org.id, payload.budget_id) if payload.budget_id else None
    if budget: _assert_mutable(budget)
    row = AccountingEntry(organization_id=org.id, created_by_user_id=user.id, entry_date=payload.entry_date or datetime.utcnow(), **payload.model_dump(exclude={"entry_date"}))
    db.add(row); db.flush(); write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=None, action="forum.accounting.entry.create", entity_type="accounting_entry", entity_id=str(row.id), event_id=payload.event_id, committee_id=None, bar_id=None, payload={"organization_id": org.id, "entry_type": row.entry_type, "amount_cents": row.amount_cents}); db.commit(); return _entry_payload(row)

@router.post("/structures/{slug}/accounting/budgets/{budget_id}/lifecycle")
def transition_budget(slug: str, budget_id: int, status: str, reason: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); budget = _budget(db, org.id, budget_id)
    target = status.upper(); current = budget.status.upper()
    transitions = {"COLLECTING": {"REVIEW"}, "REVIEW": {"REVIEWED"}, "REVIEWED": {"LOCKED"}, "LOCKED": set()}
    if target == "COLLECTING" and current == "LOCKED":
        require_capability(db, org.id, user, "finance.lock")
        if len(reason.strip()) < 5: raise HTTPException(400, "Unlock reason required")
    elif target == "LOCKED":
        require_capability(db, org.id, user, "finance.lock")
        if len(reason.strip()) < 5: raise HTTPException(400, "Lock reason required")
    else:
        require_capability(db, org.id, user, "finance.review")
    if target not in transitions.get(current, set()) and not (current == "LOCKED" and target == "COLLECTING"):
        raise HTTPException(409, detail={"reason": "INVALID_ACCOUNTING_TRANSITION"})
    budget.status = target; budget.updated_at = datetime.utcnow(); budget.locked_at = datetime.utcnow() if target == "LOCKED" else None
    write_audit_log(db, actor_partner_id=None, actor_user_id=user.id, actor_role=None, action="forum.accounting.lifecycle", entity_type="structure_budget", entity_id=str(budget.id), event_id=None, committee_id=None, bar_id=None, payload={"from": current, "to": target, "reason": reason})
    db.commit(); return {"id": budget.id, "status": budget.status}

@router.get("/structures/{slug}/accounting/export.csv")
def export_accounting(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); require_capability(db, org.id, user, "finance.export")
    rows = db.query(AccountingEntry).filter_by(organization_id=org.id).order_by(AccountingEntry.entry_date.asc()).all()
    body = "date,type,category,amount_cents,notes\n" + "\n".join(f"{r.entry_date.isoformat()},{r.entry_type},{r.category},{r.amount_cents},{(r.notes or '').replace(',', ' ')}" for r in rows) + "\n"
    return Response(content=body, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=accounting.csv"})
