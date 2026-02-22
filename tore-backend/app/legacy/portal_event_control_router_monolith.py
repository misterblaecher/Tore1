from __future__ import annotations

from datetime import datetime, timedelta
import csv
import io
import json
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from sqlalchemy import func
from db import now_utc
from models import Bet, BetDispute, Event, EventCostSimple, EventCostSimpleIdempotency, EventCreateIdempotency, EventQrPackIdempotency, EventQrToken, EventRuntimeState, EventStaffAssignment, EventStaffAssignmentIdempotency, Order, OrderItem, PartnerUser
from partner_auth import current_identity, require_role
from app.services.authz_service import ensure_partner_role
from app.schemas.event_modules import EventModulesOut, EventModulesUpdateIn
from app.schemas.orga_events import EventTemplateOut, OrgaEventCreateIn, OrgaEventOut, QrPackOut
from app.schemas.profitability import ProfitabilityCostsIn, ProfitabilityCostsOut, ProfitabilityOut
from app.schemas.wallet_admin import WalletAdminLogOut, WalletAdminLogPageOut, WalletAdminTopupIn, WalletAdminTopupOut
from app.services.audit_service import write_audit_log
from app.services.entry_service import get_owned_event_or_403
from app.services.event_modules_service import get_or_create_event_modules, update_event_modules
from app.services.wallet_admin_service import admin_topup, list_wallet_admin_logs
from app.services.qr_pack_service import create_staff_qr_token, generate_qr_pack
from app.services.rate_limit_service import enforce_rate_limit
from app.services.wallet_service import get_or_create_wallet
from app.services.p3_common import effective_module_state, ensure_event_action_allowed, get_event_runtime_state, is_event_live

router = APIRouter(prefix="/partner/portal", tags=["portal-event-control"])

MODULE_FIELDS = [
    "orders_enabled",
    "market_enabled",
    "battles_enabled",
    "hunt_enabled",
    "polymarket_enabled",
    "entry_enabled",
    "checkins_enabled",
    "wifi_enabled",
    "safety_enabled",
]


WIZARD_MODULE_MAP = {
    "menu": "orders_enabled",
    "wallet": "orders_enabled",
    "ticker": "market_enabled",
    "entry": "entry_enabled",
    "broadcast": "checkins_enabled",
    "music": "checkins_enabled",
    "vote": "battles_enabled",
    "polymarket": "polymarket_enabled",
    "hunt": "hunt_enabled",
    "battles": "battles_enabled",
    "wifi": "wifi_enabled",
    "safety": "safety_enabled",
}

DEFAULT_MODULES_ON = {
    "menu": True,
    "wallet": True,
    "ticker": True,
    "entry": False,
    "broadcast": False,
    "music": False,
    "vote": False,
    "polymarket": False,
    "hunt": False,
    "battles": False,
    "wifi": False,
    "safety": False,
    "map": False,
}


STAFF_ROLES = {"ENTRY", "BAR", "MANAGER"}


def _staff_status(*, revoked_at, expires_at: datetime | None) -> str:
    if revoked_at is not None:
        return "REVOKED"
    if expires_at is not None and expires_at <= now_utc():
        return "EXPIRED"
    return "ACTIVE"


def _serialize_staff_assignment(assignment: EventStaffAssignment, token: EventQrToken | None) -> dict:
    token_payload = None
    if token is not None:
        token_payload = {
            "tokenId": token.token_id,
            "type": token.qr_type,
            "payload": token.payload,
            "expiresAt": token.expires_at,
            "revokedAt": token.revoked_at,
            "status": _staff_status(revoked_at=token.revoked_at, expires_at=token.expires_at),
            "role": token.role,
        }
    status = token_payload["status"] if token_payload else _staff_status(revoked_at=assignment.revoked_at, expires_at=None)
    return {
        "id": assignment.id,
        "eventId": assignment.event_id,
        "role": assignment.role,
        "label": assignment.label,
        "createdBy": assignment.created_by_user_id,
        "createdAt": assignment.created_at,
        "revokedAt": assignment.revoked_at,
        "status": status,
        "token": token_payload,
    }


EVENT_TEMPLATES = [
    {
        "id": "chapi",
        "name": "Chapi",
        "defaultModulesOn": {**DEFAULT_MODULES_ON, "entry": True, "broadcast": True},
        "defaultRules": {"charter_enabled": True, "require_charter_accept": True, "minors_policy": "restricted"},
        "durationPreset": "6h",
    },
    {
        "id": "bar-night",
        "name": "Bar night",
        "defaultModulesOn": {**DEFAULT_MODULES_ON, "entry": True, "wifi": True},
        "defaultRules": {"charter_enabled": True, "require_charter_accept": False, "minors_policy": "allowed"},
        "durationPreset": "8h",
    },
    {
        "id": "comite",
        "name": "Comité",
        "defaultModulesOn": {**DEFAULT_MODULES_ON, "entry": True, "battles": True, "hunt": True},
        "defaultRules": {"charter_enabled": True, "require_charter_accept": True, "minors_policy": "restricted"},
        "durationPreset": "10h",
    },
]


def _serialize_orga_event(event: Event) -> dict:
    return {
        "id": event.id,
        "name": event.name,
        "venue": event.venue,
        "startAt": event.starts_at,
        "endAt": event.ends_at,
        "timezone": event.timezone or "Europe/Brussels",
        "eventState": event.event_state or "LIVE",
        "modulesOn": event.modules_on or DEFAULT_MODULES_ON.copy(),
        "rulesFlags": event.rules_flags or {},
        "createdBy": event.created_by,
        "lastStateUpdatedAt": event.last_state_updated_at or event.starts_at,
        "lastUpdatedAt": event.last_updated_at or event.starts_at,
    }


def _materialize_modules(payload: dict[str, bool]) -> dict[str, bool]:
    merged = DEFAULT_MODULES_ON.copy()
    for key, value in (payload or {}).items():
        if key in merged:
            merged[key] = bool(value)
    return merged


def _template_defaults(template_id: str | None) -> tuple[dict[str, bool], dict]:
    if not template_id:
        return DEFAULT_MODULES_ON.copy(), {}
    for item in EVENT_TEMPLATES:
        if item["id"] == template_id:
            return dict(item["defaultModulesOn"]), dict(item["defaultRules"])
    return DEFAULT_MODULES_ON.copy(), {}


def get_db() -> Iterator[Session]:
    from app.legacy.monolith import get_db as _get_db

    yield from _get_db()


def _get_or_create_runtime_state(db: Session, event_id: int) -> EventRuntimeState:
    row = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
    if row:
        return row
    row = EventRuntimeState(event_id=event_id, state="LIVE")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _require_orga_identity(identity=Depends(current_identity)):
    ensure_partner_role(identity, {"manager", "bartender"})
    return identity


def _require_orga_manager_identity(identity=Depends(current_identity)):
    ensure_partner_role(identity, {"manager", "owner"})
    return identity


def _mask_partner_name(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = name.strip()
    if len(cleaned) <= 2:
        return cleaned[0] + "*"
    return cleaned[:2] + "***"


def _profitability_snapshot(db: Session, event_id: int) -> ProfitabilityOut:
    orders_count = db.query(func.count(Order.id)).filter(Order.event_id == event_id).scalar() or 0
    items_count = db.query(func.coalesce(func.sum(OrderItem.qty), 0)).join(Order, Order.id == OrderItem.order_id).filter(Order.event_id == event_id).scalar() or 0
    gross_tickets = db.query(func.coalesce(func.sum(Order.total_tickets), 0)).filter(Order.event_id == event_id).scalar() or 0
    last_updated = db.query(func.max(Order.updated_at)).filter(Order.event_id == event_id).scalar() or now_utc()

    costs = db.query(EventCostSimple).filter(EventCostSimple.event_id == event_id).first()
    costs_tickets = costs.costs_tickets if costs else 0
    updated_by = None
    if costs and costs.updated_by:
        actor = db.get(PartnerUser, costs.updated_by)
        updated_by = _mask_partner_name(actor.display_name if actor else None)

    return ProfitabilityOut(
        ordersCount=int(orders_count),
        itemsCount=int(items_count),
        grossRevenueTickets=int(gross_tickets),
        grossRevenueEuro=None,
        avgOrderValueTickets=(float(gross_tickets) / float(orders_count) if orders_count else 0.0),
        lastUpdatedAt=last_updated,
        costs=ProfitabilityCostsOut(
            costsTickets=int(costs_tickets),
            notes=costs.notes if costs else None,
            breakdown=(costs.breakdown_json or {}) if costs else {},
            updatedBy=updated_by,
            updatedAt=costs.updated_at if costs else None,
        ),
        netEstimateTickets=int(gross_tickets - costs_tickets),
    )



@router.get("/event/{event_id}/modules", response_model=EventModulesOut)
def get_event_modules(
    event_id: int,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    cfg = get_or_create_event_modules(db, event_id)
    return cfg


@router.get("/event/{event_id}/status")
def get_event_status(
    event_id: int,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    cfg = get_or_create_event_modules(db, event_id)
    return {
        "event_id": event_id,
        "live": is_event_live(db, event_id),
        "modules": {field: getattr(cfg, field) for field in MODULE_FIELDS},
    }


@router.get("/event/{event_id}/state-snapshot")
def event_state_snapshot(
    event_id: int,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    cfg = get_or_create_event_modules(db, event_id)
    runtime = _get_or_create_runtime_state(db, event_id)
    event_state = get_event_runtime_state(db, event_id)
    modules = {}
    warnings = []
    for field in MODULE_FIELDS:
        effective, reason = effective_module_state(db, event_id, field)
        enabled = bool(getattr(cfg, field))
        modules[field] = {"configured_enabled": enabled, "effective_state": effective, "reason": reason}
        if effective in {"READ_ONLY", "OFF"}:
            warnings.append(f"{field}:{effective}:{reason}")
    return {
        "event_id": event_id,
        "event_state": event_state,
        "runtime_reason": runtime.reason,
        "modules": modules,
        "warnings": warnings,
        "priority_rule": "event_state_overrides_module_toggle",
    }


@router.post("/event/{event_id}/state")
def set_event_runtime_state(
    event_id: int,
    payload: dict,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    state = str(payload.get("state") or "").upper()
    if state not in {"LIVE", "PAUSE", "MENU_ONLY", "DEGRADED", "FROZEN", "CLOSED"}:
        return {"ok": False, "code": "INVALID_STATE", "message": "Etat event invalide."}
    runtime = _get_or_create_runtime_state(db, event_id)
    before = {"state": runtime.state, "reason": runtime.reason}
    reason = (payload.get("reason") or "").strip()[:180]
    if runtime.state != state and not reason:
        raise HTTPException(status_code=400, detail={"reason": "reason_required", "message": "Reason is required for runtime state change"})
    runtime.state = state
    runtime.reason = reason or None
    runtime.updated_by_user_id = identity["user_id"]
    runtime.updated_at = now_utc()
    db.add(runtime)
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="event_state.update",
        entity_type="event",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"before": before, "after": {"state": runtime.state, "reason": runtime.reason}},
    )
    db.commit()
    return {"ok": True, "event_id": event_id, "state": runtime.state, "reason": runtime.reason}



@router.get("/orga/event_templates", response_model=list[EventTemplateOut])
def list_event_templates(
    identity=Depends(_require_orga_identity),
):
    return EVENT_TEMPLATES


@router.post("/orga/events", response_model=OrgaEventOut)
def create_orga_event(
    payload: OrgaEventCreateIn,
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(_require_orga_identity),
    db: Session = Depends(get_db),
):
    key = (idempotency_header or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency key required"})
    if payload.endAt <= payload.startAt:
        raise HTTPException(status_code=400, detail={"reason": "invalid_dates", "message": "endAt must be after startAt"})

    existing = db.query(EventCreateIdempotency).filter(EventCreateIdempotency.bar_id == identity["bar_id"], EventCreateIdempotency.idempotency_key == key).first()
    if existing:
        event = db.get(Event, existing.event_id)
        if not event:
            raise HTTPException(status_code=409, detail={"reason": "stale_idempotency", "message": "Idempotency points to missing event"})
        return _serialize_orga_event(event)

    tpl_modules, tpl_rules = _template_defaults(payload.templateId)
    modules_on = _materialize_modules({**tpl_modules, **(payload.modulesOn or {})})
    rules_flags = {**tpl_rules, **(payload.rulesFlags or {})}

    now = now_utc()
    event = Event(
        bar_id=identity["bar_id"],
        name=payload.name.strip(),
        venue=payload.venue.strip(),
        starts_at=payload.startAt,
        ends_at=payload.endAt,
        timezone=payload.timezone,
        event_state="LIVE",
        modules_on=modules_on,
        rules_flags=rules_flags,
        created_by=f"partner:{identity['user_id']}",
        last_state_updated_at=now,
        last_updated_at=now,
        charter_enabled=bool(rules_flags.get("charter_enabled", False)),
    )
    db.add(event)
    db.flush()

    idem = EventCreateIdempotency(bar_id=identity["bar_id"], idempotency_key=key, event_id=event.id)
    db.add(idem)

    runtime = EventRuntimeState(event_id=event.id, state="LIVE", updated_by_user_id=identity["user_id"], updated_at=now)
    db.add(runtime)

    cfg = get_or_create_event_modules(db, event.id)
    update_payload = {}
    for module_key, field in WIZARD_MODULE_MAP.items():
        if field in MODULE_FIELDS:
            update_payload[field] = bool(modules_on.get(module_key, False))
    cfg = update_event_modules(db, cfg, update_payload, identity["user_id"])

    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="orga.event.create",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        bar_id=event.bar_id,
        payload={"name": event.name, "modules_on": modules_on, "rules_flags": rules_flags, "template_id": payload.templateId},
    )
    db.commit()
    db.refresh(event)
    return _serialize_orga_event(event)


@router.post("/orga/events/{event_id}/qr_pack", response_model=QrPackOut)
def create_orga_qr_pack(
    event_id: int = Path(..., ge=1),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(_require_orga_identity),
    db: Session = Depends(get_db),
):
    key = (idempotency_header or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency key required"})

    event = get_owned_event_or_403(db, event_id, identity["bar_id"])

    existing = db.query(EventQrPackIdempotency).filter(EventQrPackIdempotency.event_id == event_id, EventQrPackIdempotency.idempotency_key == key).first()
    if existing:
        return {"eventId": event_id, "items": existing.pack_json or []}

    pack_items = generate_qr_pack(db, event=event, actor_user_id=identity["user_id"])
    idem = EventQrPackIdempotency(event_id=event_id, idempotency_key=key, pack_json=pack_items)
    db.add(idem)

    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="orga.qr_pack.generate",
        entity_type="event",
        entity_id=str(event.id),
        event_id=event.id,
        bar_id=event.bar_id,
        payload={"types": [item["type"] for item in pack_items], "idempotency_key": key},
    )
    db.commit()
    return {"eventId": event_id, "items": pack_items}


@router.get("/orga/events/{event_id}/profitability", response_model=ProfitabilityOut)
def get_profitability(
    event_id: int = Path(..., ge=1),
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
):
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    return _profitability_snapshot(db, event_id)


@router.put("/orga/events/{event_id}/costs", response_model=ProfitabilityOut)
def put_event_costs_simple(
    payload: ProfitabilityCostsIn,
    event_id: int = Path(..., ge=1),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
):
    key = (idempotency_header or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency-Key required"})

    get_owned_event_or_403(db, event_id, identity["bar_id"])
    runtime = get_event_runtime_state(db, event_id)
    if runtime == "DEGRADED":
        raise HTTPException(status_code=423, detail={"reason": "event_degraded", "message": "Write blocked while event is degraded"})

    existing = db.query(EventCostSimpleIdempotency).filter(
        EventCostSimpleIdempotency.event_id == event_id,
        EventCostSimpleIdempotency.idempotency_key == key,
    ).first()
    if existing:
        return ProfitabilityOut(**(existing.response_json or _profitability_snapshot(db, event_id).model_dump(mode="json")))

    row = db.query(EventCostSimple).filter(EventCostSimple.event_id == event_id).first()
    if not row:
        row = EventCostSimple(event_id=event_id)
    before = {"costsTickets": row.costs_tickets if row.id else 0, "notes": row.notes if row.id else None, "breakdown": row.breakdown_json if row.id else {}}
    row.costs_tickets = int(payload.costsTickets)
    row.notes = (payload.notes or "").strip() or None
    row.breakdown_json = payload.breakdown or {}
    row.updated_by = identity["user_id"]
    row.updated_at = now_utc()
    db.add(row)
    db.flush()

    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="orga.profitability.costs.update",
        entity_type="event_costs_simple",
        entity_id=str(row.id),
        event_id=event_id,
        bar_id=identity["bar_id"],
        payload={"before": before, "after": {"costsTickets": row.costs_tickets, "notes": row.notes, "breakdown": row.breakdown_json}, "idempotency_key": key},
    )

    snapshot = _profitability_snapshot(db, event_id)
    db.add(EventCostSimpleIdempotency(event_id=event_id, idempotency_key=key, response_json=snapshot.model_dump(mode="json")))
    db.commit()
    return snapshot


@router.get("/orga/events/{event_id}/profitability/export.csv")
def export_profitability_csv(
    event_id: int = Path(..., ge=1),
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
):
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    snapshot = _profitability_snapshot(db, event_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["event_id", "timestamp", "ordersCount", "grossTickets", "costsTickets", "netTickets", "notes"])
    writer.writerow([
        event_id,
        now_utc().isoformat(),
        snapshot.ordersCount,
        snapshot.grossRevenueTickets,
        snapshot.costs.costsTickets,
        snapshot.netEstimateTickets,
        snapshot.costs.notes or "",
    ])
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="profitability_event_{event_id}.csv"'},
    )


@router.get("/orga/events/{event_id}/profitability/export.json")
def export_profitability_json(
    event_id: int = Path(..., ge=1),
    identity=Depends(_require_orga_manager_identity),
    db: Session = Depends(get_db),
):
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    snapshot = _profitability_snapshot(db, event_id)
    return {
        "event_id": event_id,
        "timestamp": now_utc(),
        "snapshot": snapshot.model_dump(mode="json"),
    }




@router.get("/orga/events/{event_id}/staff")
def list_event_staff_assignments(
    event_id: int = Path(..., ge=1),
    identity=Depends(_require_orga_identity),
    db: Session = Depends(get_db),
):
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    assignments = (
        db.query(EventStaffAssignment)
        .filter(EventStaffAssignment.event_id == event_id)
        .order_by(EventStaffAssignment.created_at.desc())
        .all()
    )
    assignment_ids = [row.id for row in assignments]
    token_by_assignment: dict[int, EventQrToken] = {}
    if assignment_ids:
        tokens = (
            db.query(EventQrToken)
            .filter(EventQrToken.assignment_id.in_(assignment_ids))
            .order_by(EventQrToken.issued_at.desc())
            .all()
        )
        for token in tokens:
            if token.assignment_id is None or token.assignment_id in token_by_assignment:
                continue
            token_by_assignment[token.assignment_id] = token

    items = [_serialize_staff_assignment(item, token_by_assignment.get(item.id)) for item in assignments]
    return {"eventId": event_id, "items": items}


@router.post("/orga/events/{event_id}/staff")
def create_event_staff_assignment(
    payload: dict,
    event_id: int = Path(..., ge=1),
    idempotency_header: str | None = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(_require_orga_identity),
    db: Session = Depends(get_db),
):
    key = (idempotency_header or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency key required"})

    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    existing = (
        db.query(EventStaffAssignmentIdempotency)
        .filter(EventStaffAssignmentIdempotency.event_id == event_id, EventStaffAssignmentIdempotency.idempotency_key == key)
        .first()
    )
    if existing:
        return existing.response_json

    role = str(payload.get("role") or "").strip().upper()
    if role not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail={"reason": "invalid_role", "message": "Role must be ENTRY/BAR/MANAGER"})

    label = (payload.get("label") or "").strip()
    expires_at = payload.get("expiresAt")
    if expires_at:
        try:
            expires_value = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"reason": "invalid_expiry", "message": "expiresAt invalid"}) from exc
    else:
        expires_value = (event.ends_at or now_utc()) + timedelta(hours=6)

    assignment = EventStaffAssignment(
        event_id=event_id,
        role=role,
        label=label or None,
        created_by_user_id=identity["user_id"],
        created_at=now_utc(),
    )
    db.add(assignment)
    db.flush()

    qr_item = create_staff_qr_token(
        db,
        event=event,
        staff_role=role,
        created_by_user_id=identity["user_id"],
        assignment_id=assignment.id,
        expires_at=expires_value,
    )

    response = {
        "assignment": _serialize_staff_assignment(
            assignment,
            db.query(EventQrToken).filter(EventQrToken.assignment_id == assignment.id).order_by(EventQrToken.issued_at.desc()).first(),
        ),
        "qr": {"raw": qr_item["payload"], "deepLink": qr_item["payload"], "tokenId": qr_item["tokenId"], "type": qr_item["type"]},
    }

    serialized_response = json.loads(json.dumps(response, default=str))
    db.add(EventStaffAssignmentIdempotency(event_id=event_id, idempotency_key=key, assignment_id=assignment.id, response_json=serialized_response))
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="orga.staff.create",
        entity_type="event_staff_assignment",
        entity_id=str(assignment.id),
        event_id=event.id,
        bar_id=event.bar_id,
        payload={"role": role, "label": assignment.label, "token_id": qr_item["tokenId"], "idempotency_key": key},
    )
    db.commit()
    return response


@router.post("/orga/staff/{assignment_id}/revoke")
def revoke_event_staff_assignment(
    payload: dict,
    assignment_id: int = Path(..., ge=1),
    identity=Depends(_require_orga_identity),
    db: Session = Depends(get_db),
):
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail={"reason": "reason_required", "message": "Reason is required"})

    assignment = db.get(EventStaffAssignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail={"reason": "staff_not_found"})
    event = get_owned_event_or_403(db, assignment.event_id, identity["bar_id"])

    now = now_utc()
    if assignment.revoked_at is None:
        assignment.revoked_at = now
    tokens = db.query(EventQrToken).filter(EventQrToken.assignment_id == assignment.id, EventQrToken.revoked_at.is_(None)).all()
    revoked_token_ids = []
    for token in tokens:
        token.revoked_at = now
        revoked_token_ids.append(token.token_id)

    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="orga.staff.revoke",
        entity_type="event_staff_assignment",
        entity_id=str(assignment.id),
        event_id=event.id,
        bar_id=event.bar_id,
        payload={"reason": reason, "tokens": revoked_token_ids},
    )
    db.commit()
    return {"ok": True, "assignmentId": assignment.id, "revokedAt": assignment.revoked_at}


@router.post("/orga/qr/{token_id}/revoke")
def revoke_qr_token(
    token_id: str,
    payload: dict,
    identity=Depends(_require_orga_identity),
    db: Session = Depends(get_db),
):
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail={"reason": "reason_required", "message": "Reason is required"})

    token = db.query(EventQrToken).filter(EventQrToken.token_id == token_id).first()
    if not token:
        raise HTTPException(status_code=404, detail={"reason": "token_not_found"})
    event = get_owned_event_or_403(db, token.event_id, identity["bar_id"])

    if token.revoked_at is None:
        token.revoked_at = now_utc()
    if token.assignment_id:
        assignment = db.get(EventStaffAssignment, token.assignment_id)
        if assignment and assignment.revoked_at is None:
            assignment.revoked_at = token.revoked_at

    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="orga.qr.revoke",
        entity_type="event_qr_token",
        entity_id=token.token_id,
        event_id=event.id,
        bar_id=event.bar_id,
        payload={"reason": reason, "assignment_id": token.assignment_id},
    )
    db.commit()
    return {"ok": True, "tokenId": token.token_id, "revokedAt": token.revoked_at}


@router.get("/orga/events/active")
def get_active_event_for_orga(
    identity=Depends(_require_orga_identity),
    db: Session = Depends(get_db),
):
    now = now_utc()
    event = (
        db.query(Event)
        .filter(Event.bar_id == identity["bar_id"], Event.starts_at <= now, Event.ends_at >= now)
        .order_by(Event.starts_at.desc())
        .first()
    )
    if not event:
        event = (
            db.query(Event)
            .filter(Event.bar_id == identity["bar_id"])
            .order_by(Event.starts_at.desc())
            .first()
        )
    if not event:
        raise HTTPException(status_code=404, detail={"reason": "event_not_found", "message": "No event for this bar"})
    cfg = get_or_create_event_modules(db, event.id)
    runtime = _get_or_create_runtime_state(db, event.id)
    return {
        "event": {"id": event.id, "name": event.name, "starts_at": event.starts_at, "ends_at": event.ends_at},
        "event_state": runtime.state,
        "runtime_reason": runtime.reason,
        "modulesOn": {field: bool(getattr(cfg, field)) for field in MODULE_FIELDS},
    }


@router.post("/event/{event_id}/modules", response_model=EventModulesOut)
def update_modules(
    event_id: int,
    payload: EventModulesUpdateIn,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    cfg = get_or_create_event_modules(db, event_id)
    before = {k: getattr(cfg, k) for k in MODULE_FIELDS}
    cfg = update_event_modules(db, cfg, payload.model_dump(), identity["user_id"])
    after = {k: getattr(cfg, k) for k in MODULE_FIELDS}
    if before != after:
        write_audit_log(
            db,
            actor_partner_id=identity["user_id"],
            actor_role=identity["role"],
            action="event_modules.update",
            entity_type="event",
            entity_id=str(event_id),
            event_id=event_id,
            bar_id=event.bar_id,
            payload={"before": before, "after": after},
        )
        db.commit()
    return cfg


@router.post("/wallet/topup", response_model=WalletAdminTopupOut)
@router.post("/wallet/admin/topup", response_model=WalletAdminTopupOut)
def wallet_admin_topup(
    payload: WalletAdminTopupIn,
    idempotency_header: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, payload.event_id, identity["bar_id"])
    ensure_event_action_allowed(db, payload.event_id, "wallet_enabled", write=True)
    target_user_id = (payload.target_user_id or payload.user_id or "").strip()
    if not target_user_id:
        raise HTTPException(status_code=400, detail={"reason": "invalid_target", "message": "target_user_id is required"})
    amount = payload.amount_cents if payload.amount_cents is not None else payload.amount_tickets
    if amount is None or amount < 1:
        raise HTTPException(status_code=400, detail={"reason": "invalid_amount", "message": "amount must be >= 1"})
    reason_code = (payload.reason_code or "wallet_topup").strip()
    reason = (payload.reason_text or payload.note or payload.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=422, detail={"reason": "missing_reason", "message": "reason_text required"})
    idempotency_key = (idempotency_header or "").strip()
    if len(idempotency_key) < 1:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency-Key header required"})
    enforce_rate_limit("wallet_topup", f"{identity['user_id']}:{idempotency_key}")
    ledger, idempotent = admin_topup(
        db,
        event_id=payload.event_id,
        user_id=target_user_id,
        amount_tickets=amount,
        reason=reason,
        idempotency_key=idempotency_key,
        actor_user_id=identity["user_id"],
    )
    if not idempotent:
        write_audit_log(
            db,
            actor_partner_id=identity["user_id"],
            actor_role=identity["role"],
            action="wallet.topup",
            entity_type="wallet_ledger_entry",
            entity_id=str(ledger.id),
            event_id=payload.event_id,
            bar_id=event.bar_id,
            payload={"user_id": target_user_id, "amount_tickets": amount, "reason_code": reason_code, "reason_text": reason},
        )
        write_audit_log(
            db,
            actor_partner_id=identity["user_id"],
            actor_role=identity["role"],
            action="wallet_admin.topup",
            entity_type="wallet_ledger_entry",
            entity_id=str(ledger.id),
            event_id=payload.event_id,
            bar_id=event.bar_id,
            payload={"user_id": target_user_id, "amount_tickets": amount, "reason_code": reason_code, "reason_text": reason},
        )
    db.commit()
    wallet = get_or_create_wallet(db, target_user_id)
    return WalletAdminTopupOut(
        ledger_id=ledger.id,
        event_id=ledger.event_id,
        user_id=ledger.user_id,
        amount_tickets=ledger.amount_tickets,
        reason=ledger.reason,
        balance_tickets=wallet.balance_tickets,
        idempotent=idempotent,
        created_at=ledger.created_at,
    )


@router.get("/wallet/logs", response_model=WalletAdminLogPageOut)
@router.get("/wallet/admin/logs", response_model=WalletAdminLogPageOut)
def wallet_admin_logs(
    event_id: int,
    user_id: Optional[str] = Query(default=None),
    after: Optional[datetime] = Query(default=None),
    before: Optional[datetime] = Query(default=None),
    min_delta: Optional[int] = Query(default=None),
    max_delta: Optional[int] = Query(default=None),
    idempotency_key: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    ensure_event_action_allowed(db, event_id, "wallet_enabled", write=False)
    rows, next_cursor = list_wallet_admin_logs(
        db,
        event_id=event.id,
        user_id=user_id,
        after=after,
        before=before,
        min_delta=min_delta,
        max_delta=max_delta,
        idempotency_key=idempotency_key,
        query=q,
        tx_type=type,
        cursor=cursor,
        limit=limit,
    )
    return WalletAdminLogPageOut(
        items=[WalletAdminLogOut(id=r.id, event_id=r.event_id, user_id=r.user_id, amount_tickets=r.amount_tickets, reason=r.reason, idempotency_key=r.idempotency_key, created_at=r.created_at) for r in rows],
        next_cursor=next_cursor,
    )


@router.get("/wallet/logs/export.csv")
def wallet_admin_logs_export(
    event_id: int,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    ensure_event_action_allowed(db, event_id, "wallet_enabled", write=False)
    rows, _ = list_wallet_admin_logs(
        db,
        event_id=event.id,
        user_id=None,
        after=None,
        before=None,
        min_delta=None,
        max_delta=None,
        idempotency_key=None,
        query=None,
        tx_type=None,
        cursor=None,
        limit=10000,
    )
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity["role"],
        action="wallet.export",
        entity_type="wallet_ledger_entry",
        entity_id=None,
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"rows": len(rows)},
    )
    db.commit()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ts", "user_id", "type", "amount", "note", "ref_id"])
    for row in rows:
        writer.writerow([row.created_at.isoformat(), row.user_id, "topup", row.amount_tickets, row.reason, row.idempotency_key])

    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=wallet_logs_event_{event_id}.csv"})


@router.get("/polymarket/event/{event_id}")
def portal_polymarket_event_view(
    event_id: int,
    identity=Depends(require_role("manager")),
    db: Session = Depends(get_db),
):
    from app.services.polymarket_service import list_bets

    get_owned_event_or_403(db, event_id, identity["bar_id"])
    bets = list_bets(db, scope="EVENT", event_id=event_id, status=None, kind=None, limit=200, offset=0)
    dispute_rows = (
        db.query(BetDispute.bet_id, func.count(BetDispute.id))
        .join(Bet, Bet.id == BetDispute.bet_id)
        .filter(Bet.event_id == event_id)
        .group_by(BetDispute.bet_id)
        .all()
    )
    dispute_map = {bet_id: int(count or 0) for bet_id, count in dispute_rows}
    for bet in bets:
        status = bet.get("status")
        bet["status_compat"] = "RESOLVED" if status == "FINALIZED" else status
        bet["disputes_count"] = dispute_map.get(bet.get("id"), 0)
    return {"event_id": event_id, "bets": bets}
