from __future__ import annotations

import io
import json
from typing import Iterator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from db import now_utc
from models import (
    EventIncident,
    EventIncidentActionIdempotency,
    EventIncidentCreateIdempotency,
    EventIncidentLog,
    EventRuntimeState,
    EventStaffAssignment,
)
from partner_auth import current_identity
from app.services.authz_service import ensure_partner_role
from app.services.audit_service import write_audit_log
from app.services.entry_service import get_owned_event_or_403
from app.services.event_modules_service import get_or_create_event_modules
from app.services.rate_limit_service import enforce_rate_limit

router = APIRouter(prefix="/partner/portal", tags=["incidents"])

SEVERITIES = {"info", "warn", "critical"}
STATUSES = {"open", "assigned", "resolved", "canceled"}
ASSIGNMENT_ROLES = {"ENTRY", "BAR", "MANAGER"}


def get_db() -> Iterator[Session]:
    from app.legacy.monolith import get_db as _get_db

    yield from _get_db()


def _require_orga_identity(identity=Depends(current_identity)):
    ensure_partner_role(identity, {"manager", "bartender"})
    return identity


def _required_idempotency(key: Optional[str]) -> str:
    idem = (key or "").strip()
    if not idem:
        raise HTTPException(status_code=400, detail={"reason": "missing_idempotency", "message": "Idempotency key required"})
    return idem


def _incident_out(db: Session, incident: EventIncident, *, json_safe: bool = False) -> dict:
    assigned_label = None
    if incident.assigned_to_staff_assignment_id:
        assignment = db.get(EventStaffAssignment, incident.assigned_to_staff_assignment_id)
        if assignment is not None:
            assigned_label = assignment.label or f"{assignment.role}#{assignment.id}"
    elif incident.assigned_to_role:
        assigned_label = incident.assigned_to_role
    created_at = incident.created_at.isoformat() if json_safe and incident.created_at else incident.created_at
    updated_at = incident.updated_at.isoformat() if json_safe and incident.updated_at else incident.updated_at
    return {
        "id": incident.id,
        "eventId": incident.event_id,
        "title": incident.title,
        "description": incident.description,
        "severity": incident.severity,
        "status": incident.status,
        "location": incident.location,
        "createdBy": incident.created_by,
        "assignedToStaffAssignmentId": incident.assigned_to_staff_assignment_id,
        "assignedToRole": incident.assigned_to_role,
        "assignedLabel": assigned_label,
        "createdAt": created_at,
        "updatedAt": updated_at,
    }


def _log_incident(db: Session, incident: EventIncident, action_type: str, actor_id: int, payload: dict) -> EventIncidentLog:
    row = EventIncidentLog(
        incident_id=incident.id,
        event_id=incident.event_id,
        action_type=action_type,
        payload=payload,
        actor_id=actor_id,
        created_at=now_utc(),
    )
    db.add(row)
    return row


def _get_incident_for_identity(db: Session, incident_id: int, bar_id: int) -> EventIncident:
    incident = db.get(EventIncident, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    get_owned_event_or_403(db, incident.event_id, bar_id)
    return incident


@router.get("/orga/events/{event_id}/incidents")
def list_incidents(event_id: int, identity=Depends(_require_orga_identity), db: Session = Depends(get_db)):
    get_owned_event_or_403(db, event_id, identity["bar_id"])
    enforce_rate_limit("orga_incidents.list", str(identity["user_id"]))
    rows = (
        db.query(EventIncident)
        .filter(EventIncident.event_id == event_id)
        .order_by(desc(EventIncident.created_at), desc(EventIncident.id))
        .all()
    )
    return {"items": [_incident_out(db, row) for row in rows]}


@router.post("/orga/events/{event_id}/incidents")
def create_incident(
    event_id: int,
    payload: dict,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(_require_orga_identity),
    db: Session = Depends(get_db),
):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    enforce_rate_limit("orga_incidents.create", str(identity["user_id"]))
    idem = _required_idempotency(idempotency_key)

    existing = (
        db.query(EventIncidentCreateIdempotency)
        .filter(EventIncidentCreateIdempotency.event_id == event_id, EventIncidentCreateIdempotency.idempotency_key == idem)
        .first()
    )
    if existing:
        return existing.response_json

    description = str(payload.get("description") or "").strip()
    if not description:
        raise HTTPException(status_code=422, detail={"reason": "invalid_description", "message": "description required"})
    severity = str(payload.get("severity") or "").strip().lower() or "info"
    if severity not in SEVERITIES:
        raise HTTPException(status_code=422, detail={"reason": "invalid_severity", "message": "invalid severity"})

    incident = EventIncident(
        event_id=event_id,
        title=(str(payload.get("title") or "").strip() or None),
        description=description,
        severity=severity,
        status="open",
        location=(str(payload.get("location") or "").strip() or None),
        created_by=identity["user_id"],
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(incident)
    db.flush()

    _log_incident(db, incident, "created", identity["user_id"], {"severity": severity})
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity.get("role"),
        action="orga.incident.create",
        entity_type="event_incident",
        entity_id=str(incident.id),
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"severity": severity, "location": incident.location},
    )

    response = {"incident": _incident_out(db, incident, json_safe=True)}
    db.add(EventIncidentCreateIdempotency(event_id=event_id, idempotency_key=idem, incident_id=incident.id, response_json=response))
    db.commit()
    return response


@router.post("/orga/incidents/{incident_id}/assign")
def assign_incident(
    incident_id: int,
    payload: dict,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(_require_orga_identity),
    db: Session = Depends(get_db),
):
    enforce_rate_limit("orga_incidents.assign", str(identity["user_id"]))
    incident = _get_incident_for_identity(db, incident_id, identity["bar_id"])
    idem = _required_idempotency(idempotency_key)

    existing = (
        db.query(EventIncidentActionIdempotency)
        .filter(
            EventIncidentActionIdempotency.incident_id == incident.id,
            EventIncidentActionIdempotency.action_type == "assigned",
            EventIncidentActionIdempotency.idempotency_key == idem,
        )
        .first()
    )
    if existing:
        return existing.response_json

    assignment_id = payload.get("assignmentId")
    role = str(payload.get("role") or "").strip().upper() or None
    if not assignment_id and not role:
        raise HTTPException(status_code=422, detail={"reason": "missing_assignee", "message": "assignmentId or role required"})

    assigned_label = None
    if assignment_id:
        assignment = db.get(EventStaffAssignment, int(assignment_id))
        if assignment is None or assignment.event_id != incident.event_id or assignment.revoked_at is not None:
            raise HTTPException(status_code=404, detail={"reason": "assignment_not_found", "message": "assignment not found"})
        incident.assigned_to_staff_assignment_id = assignment.id
        incident.assigned_to_role = None
        assigned_label = assignment.label or f"{assignment.role}#{assignment.id}"
    else:
        if role not in ASSIGNMENT_ROLES:
            raise HTTPException(status_code=422, detail={"reason": "invalid_role", "message": "invalid role"})
        incident.assigned_to_role = role
        incident.assigned_to_staff_assignment_id = None
        assigned_label = role

    incident.status = "assigned"
    incident.updated_at = now_utc()
    log_payload = {"assignmentId": incident.assigned_to_staff_assignment_id, "role": incident.assigned_to_role, "reason": payload.get("reason")}
    _log_incident(db, incident, "assigned", identity["user_id"], log_payload)
    event = get_owned_event_or_403(db, incident.event_id, identity["bar_id"])
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity.get("role"),
        action="orga.incident.assign",
        entity_type="event_incident",
        entity_id=str(incident.id),
        event_id=incident.event_id,
        bar_id=event.bar_id,
        payload=log_payload,
    )
    response = {"incident": _incident_out(db, incident, json_safe=True), "assignedLabel": assigned_label}
    db.add(EventIncidentActionIdempotency(incident_id=incident.id, action_type="assigned", idempotency_key=idem, response_json=response))
    db.commit()
    return response


@router.post("/orga/incidents/{incident_id}/escalate")
def escalate_incident(
    incident_id: int,
    payload: dict,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(_require_orga_identity),
    db: Session = Depends(get_db),
):
    enforce_rate_limit("orga_incidents.escalate", str(identity["user_id"]))
    incident = _get_incident_for_identity(db, incident_id, identity["bar_id"])
    idem = _required_idempotency(idempotency_key)

    existing = (
        db.query(EventIncidentActionIdempotency)
        .filter(
            EventIncidentActionIdempotency.incident_id == incident.id,
            EventIncidentActionIdempotency.action_type == "escalated",
            EventIncidentActionIdempotency.idempotency_key == idem,
        )
        .first()
    )
    if existing:
        return existing.response_json

    to_severity = str(payload.get("severity") or "").strip().lower()
    reason = str(payload.get("reason") or "").strip()
    if to_severity not in SEVERITIES:
        raise HTTPException(status_code=422, detail={"reason": "invalid_severity", "message": "invalid severity"})
    if not reason:
        raise HTTPException(status_code=422, detail={"reason": "missing_reason", "message": "reason required"})

    from_severity = incident.severity
    incident.severity = to_severity
    incident.status = "assigned" if incident.status == "open" else incident.status
    incident.updated_at = now_utc()
    log_payload = {"fromSeverity": from_severity, "toSeverity": to_severity, "reason": reason}
    _log_incident(db, incident, "escalated", identity["user_id"], log_payload)
    event = get_owned_event_or_403(db, incident.event_id, identity["bar_id"])
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity.get("role"),
        action="orga.incident.escalate",
        entity_type="event_incident",
        entity_id=str(incident.id),
        event_id=incident.event_id,
        bar_id=event.bar_id,
        payload=log_payload,
    )
    response = {"incident": _incident_out(db, incident, json_safe=True)}
    db.add(EventIncidentActionIdempotency(incident_id=incident.id, action_type="escalated", idempotency_key=idem, response_json=response))
    db.commit()
    return response


@router.post("/orga/incidents/{incident_id}/set_status")
def set_incident_status(
    incident_id: int,
    payload: dict,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    identity=Depends(_require_orga_identity),
    db: Session = Depends(get_db),
):
    enforce_rate_limit("orga_incidents.status", str(identity["user_id"]))
    incident = _get_incident_for_identity(db, incident_id, identity["bar_id"])
    idem = _required_idempotency(idempotency_key)

    existing = (
        db.query(EventIncidentActionIdempotency)
        .filter(
            EventIncidentActionIdempotency.incident_id == incident.id,
            EventIncidentActionIdempotency.action_type == "status_changed",
            EventIncidentActionIdempotency.idempotency_key == idem,
        )
        .first()
    )
    if existing:
        return existing.response_json

    to_status = str(payload.get("status") or "").strip().lower()
    if to_status not in STATUSES:
        raise HTTPException(status_code=422, detail={"reason": "invalid_status", "message": "invalid status"})

    from_status = incident.status
    incident.status = to_status
    incident.updated_at = now_utc()
    log_payload = {"fromStatus": from_status, "toStatus": to_status, "reason": payload.get("reason")}
    _log_incident(db, incident, "status_changed", identity["user_id"], log_payload)
    event = get_owned_event_or_403(db, incident.event_id, identity["bar_id"])
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity.get("role"),
        action="orga.incident.status",
        entity_type="event_incident",
        entity_id=str(incident.id),
        event_id=incident.event_id,
        bar_id=event.bar_id,
        payload=log_payload,
    )
    response = {"incident": _incident_out(db, incident, json_safe=True)}
    db.add(EventIncidentActionIdempotency(incident_id=incident.id, action_type="status_changed", idempotency_key=idem, response_json=response))
    db.commit()
    return response


@router.get("/orga/incidents/{incident_id}/logs")
def incident_logs(incident_id: int, identity=Depends(_require_orga_identity), db: Session = Depends(get_db)):
    incident = _get_incident_for_identity(db, incident_id, identity["bar_id"])
    rows = (
        db.query(EventIncidentLog)
        .filter(EventIncidentLog.incident_id == incident.id)
        .order_by(EventIncidentLog.created_at.asc(), EventIncidentLog.id.asc())
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "incidentId": row.incident_id,
                "eventId": row.event_id,
                "actionType": row.action_type,
                "payload": row.payload or {},
                "actor": f"partner-{row.actor_id}",
                "createdAt": row.created_at,
            }
            for row in rows
        ]
    }


@router.get("/orga/events/{event_id}/incidents/export")
def export_incidents(event_id: int, identity=Depends(_require_orga_identity), db: Session = Depends(get_db)):
    event = get_owned_event_or_403(db, event_id, identity["bar_id"])
    incidents = (
        db.query(EventIncident)
        .filter(EventIncident.event_id == event_id)
        .order_by(desc(EventIncident.created_at), desc(EventIncident.id))
        .all()
    )
    incident_ids = [row.id for row in incidents]
    logs = (
        db.query(EventIncidentLog)
        .filter(EventIncidentLog.event_id == event_id, EventIncidentLog.incident_id.in_(incident_ids if incident_ids else [-1]))
        .order_by(EventIncidentLog.created_at.asc(), EventIncidentLog.id.asc())
        .all()
    )

    runtime = db.query(EventRuntimeState).filter(EventRuntimeState.event_id == event_id).first()
    module_cfg = get_or_create_event_modules(db, event_id)
    payload = {
        "generatedAt": now_utc().isoformat(),
        "event": {
            "id": event.id,
            "name": event.name,
            "barId": event.bar_id,
            "eventState": event.event_state,
            "runtimeState": runtime.state if runtime else event.event_state,
            "runtimeReason": runtime.reason if runtime else None,
            "modules": {
                "orders_enabled": bool(module_cfg.orders_enabled),
                "market_enabled": bool(module_cfg.market_enabled),
                "battles_enabled": bool(module_cfg.battles_enabled),
                "hunt_enabled": bool(module_cfg.hunt_enabled),
                "polymarket_enabled": bool(module_cfg.polymarket_enabled),
                "entry_enabled": bool(module_cfg.entry_enabled),
                "checkins_enabled": bool(module_cfg.checkins_enabled),
                "wifi_enabled": bool(module_cfg.wifi_enabled),
                "safety_enabled": bool(module_cfg.safety_enabled),
            },
        },
        "incidents": [_incident_out(db, row) for row in incidents],
        "logs": [
            {
                "id": row.id,
                "incidentId": row.incident_id,
                "actionType": row.action_type,
                "payload": row.payload or {},
                "actor": f"partner-{row.actor_id}",
                "createdAt": row.created_at.isoformat() if row.created_at else None,
            }
            for row in logs
        ],
    }

    if incidents:
        _log_incident(db, incidents[0], "exported", identity["user_id"], {"count": len(incidents)})
    write_audit_log(
        db,
        actor_partner_id=identity["user_id"],
        actor_role=identity.get("role"),
        action="orga.incident.export",
        entity_type="event",
        entity_id=str(event_id),
        event_id=event_id,
        bar_id=event.bar_id,
        payload={"incidents": len(incidents), "logs": len(logs)},
    )
    db.commit()

    encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(encoded),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="incidents-event-{event_id}.json"'},
    )
