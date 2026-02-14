from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from models import AuditLog


def write_audit_log(
    db: Session,
    *,
    actor_partner_id: Optional[int],
    actor_role: Optional[str],
    action: str,
    entity_type: str,
    entity_id: Optional[str],
    event_id: Optional[int],
    bar_id: Optional[int],
    payload: dict[str, Any],
) -> None:
    row = AuditLog(
        actor_partner_id=actor_partner_id,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        event_id=event_id,
        bar_id=bar_id,
        payload_json=payload,
    )
    db.add(row)
