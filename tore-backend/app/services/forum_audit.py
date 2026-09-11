from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from db import now_utc
from models import AuditLog
from app.forum_models import StructureAuditContext


def write_structure_audit(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: Optional[str],
    actor_role: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str],
    before: Optional[dict[str, Any]] = None,
    after: Optional[dict[str, Any]] = None,
    context: Optional[dict[str, Any]] = None,
    event_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
) -> AuditLog:
    """Append a structure-scoped audit record.

    No update/delete API is exposed for these records.  In production the DB role
    used by the application should additionally be denied UPDATE/DELETE on the
    audit tables.
    """
    payload = {
        "structure_id": organization_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        **(context or {}),
    }
    row = AuditLog(
        ts=now_utc(),
        actor_partner_id=None,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        entity_type=resource_type,
        entity_id=resource_id,
        event_id=event_id,
        committee_id=None,
        bar_id=None,
        idempotency_key=idempotency_key,
        payload_json=payload,
    )
    db.add(row)
    db.flush()
    db.add(StructureAuditContext(
        audit_log_id=row.id,
        organization_id=organization_id,
        before_json=before,
        after_json=after,
        context_json=context or {},
        created_at=now_utc(),
    ))
    return row
