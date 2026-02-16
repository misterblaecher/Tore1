from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from models import AuditLog


def write_audit_log(
    db: Session,
    *,
    actor_partner_id: Optional[int],
    actor_user_id: Optional[str] = None,
    actor_role: Optional[str],
    action: str,
    entity_type: str,
    entity_id: Optional[str],
    event_id: Optional[int],
    committee_id: Optional[int] = None,
    bar_id: Optional[int],
    idempotency_key: Optional[str] = None,
    payload: dict[str, Any],
) -> None:
    payload_safe = dict(payload or {})
    if idempotency_key and "idempotency_key" not in payload_safe:
        payload_safe["idempotency_key"] = idempotency_key
    row = AuditLog(
        actor_partner_id=actor_partner_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        event_id=event_id,
        committee_id=committee_id,
        bar_id=bar_id,
        idempotency_key=idempotency_key,
        payload_json=payload_safe,
    )
    db.add(row)
