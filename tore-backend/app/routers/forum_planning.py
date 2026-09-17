from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from models import AppUser
from app.legacy.monolith import get_current_user, get_db
from app.routers.forum import _structure_or_404
from app.services.structure_rbac import require_capability
from app.models.planning import StructurePlanningItem, StructurePlanningAssignee

router = APIRouter(prefix="/forum", tags=["forum-planning"])
KINDS = {"MEETING", "DEADLINE", "SHIFT", "EVENT", "REHEARSAL", "REMINDER", "OTHER"}
class PlanningIn(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    kind: str = "OTHER"
    starts_at: datetime
    ends_at: datetime | None = None
    recurrence: str | None = Field(default=None, pattern="^(DAILY|WEEKLY|MONTHLY)$")
    reminder_minutes: int | None = Field(default=None, ge=0, le=10080)
    event_id: int | None = None
    notes: str | None = Field(default=None, max_length=5000)
    assignee_user_ids: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.ends_at and self.ends_at < self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self

def _item(db, org_id, item_id):
    row = db.get(StructurePlanningItem, item_id)
    if row is None or row.organization_id != org_id: raise HTTPException(404, "Planning item not found")
    return row
def _out(db, row):
    assignees = db.query(StructurePlanningAssignee).filter_by(planning_item_id=row.id).all()
    return {"id": row.id, "title": row.title, "kind": row.kind, "startsAt": row.starts_at.isoformat(), "endsAt": row.ends_at.isoformat() if row.ends_at else None, "recurrence": row.recurrence, "reminderMinutes": row.reminder_minutes, "eventId": row.event_id, "notes": row.notes, "archived": row.archived, "assigneeUserIds": [a.user_id for a in assignees]}

@router.get("/structures/{slug}/planning")
def list_planning(slug: str, from_date: datetime | None = None, to_date: datetime | None = None, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); require_capability(db, org.id, user, "planning.read")
    query = db.query(StructurePlanningItem).filter_by(organization_id=org.id, archived=False)
    if from_date: query = query.filter(StructurePlanningItem.starts_at >= from_date)
    if to_date: query = query.filter(StructurePlanningItem.starts_at <= to_date)
    return {"items": [_out(db, row) for row in query.order_by(StructurePlanningItem.starts_at.asc()).all()]}

@router.post("/structures/{slug}/planning")
def create_planning(slug: str, payload: PlanningIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); require_capability(db, org.id, user, "planning.manage")
    if payload.kind not in KINDS: raise HTTPException(422, "Unknown planning kind")
    row = StructurePlanningItem(organization_id=org.id, created_by_user_id=user.id, **payload.model_dump(exclude={"assignee_user_ids", "kind"}), kind=payload.kind)
    db.add(row); db.flush()
    for uid in payload.assignee_user_ids: db.add(StructurePlanningAssignee(planning_item_id=row.id, user_id=uid))
    db.commit(); return _out(db, row)

@router.patch("/structures/{slug}/planning/{item_id}")
def update_planning(slug: str, item_id: int, payload: PlanningIn, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); require_capability(db, org.id, user, "planning.manage"); row = _item(db, org.id, item_id)
    if payload.kind not in KINDS: raise HTTPException(422, "Unknown planning kind")
    for key, value in payload.model_dump(exclude={"assignee_user_ids"}).items(): setattr(row, key, value)
    db.query(StructurePlanningAssignee).filter_by(planning_item_id=row.id).delete();
    for uid in payload.assignee_user_ids: db.add(StructurePlanningAssignee(planning_item_id=row.id, user_id=uid))
    row.updated_at = datetime.now(timezone.utc); db.commit(); return _out(db, row)

@router.delete("/structures/{slug}/planning/{item_id}")
def archive_planning(slug: str, item_id: int, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); require_capability(db, org.id, user, "planning.manage"); row = _item(db, org.id, item_id); row.archived = True; db.commit(); return {"id": row.id, "archived": True}

@router.get("/structures/{slug}/planning.ics")
def export_planning(slug: str, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = _structure_or_404(db, slug); require_capability(db, org.id, user, "planning.read")
    rows = db.query(StructurePlanningItem).filter_by(organization_id=org.id, archived=False).all()
    def stamp(value): return value.replace(tzinfo=timezone.utc).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    def escape(value): return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    events = "".join(f"BEGIN:VEVENT\r\nUID:tore-planning-{r.id}@tore\r\nDTSTAMP:{stamp(r.created_at)}\r\nDTSTART:{stamp(r.starts_at)}\r\nDTEND:{stamp(r.ends_at or r.starts_at)}\r\nSUMMARY:{escape(r.title)}\r\nDESCRIPTION:{escape(r.notes)}\r\nEND:VEVENT\r\n" for r in rows)
    body = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//TORE//Planning//EN\r\nCALSCALE:GREGORIAN\r\n" + events + "END:VCALENDAR\r\n"
    return Response(content=body, media_type="text/calendar", headers={"Content-Disposition": "attachment; filename=planning.ics"})
