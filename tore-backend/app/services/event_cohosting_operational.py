from __future__ import annotations

from sqlalchemy import or_
from db import now_utc
from models import Event, EventStructure, OrganizationMembership
from app.services.event_cohosting_service import cohost_capability_actions


def install_cohost_operational_access():
    from app.services import operational_access_service as operational
    if getattr(operational, "_forum_cohost_installed", False):
        return
    original = operational.event_capabilities

    def wrapped(db, user, *, at=None):
        stamp = at or now_utc()
        items = list(original(db, user, at=stamp))
        by_event = {int(item["event_id"]): item for item in items}
        memberships = db.query(OrganizationMembership).filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == "ACTIVE",
            OrganizationMembership.revoked_at.is_(None),
            or_(OrganizationMembership.starts_at.is_(None), OrganizationMembership.starts_at <= stamp),
            or_(OrganizationMembership.ends_at.is_(None), OrganizationMembership.ends_at > stamp),
        ).all()
        by_org = {row.organization_id: row for row in memberships}
        if by_org:
            rows = db.query(EventStructure, Event).join(Event, Event.id == EventStructure.event_id).filter(EventStructure.organization_id.in_(list(by_org))).all()
            for relation, event in rows:
                if (relation.role or "").upper() != "COHOST" or (event.ends_at is not None and event.ends_at <= stamp):
                    continue
                actions = cohost_capability_actions(relation)
                if not actions:
                    continue
                membership = by_org[relation.organization_id]
                expires = event.ends_at
                if membership.ends_at and (expires is None or membership.ends_at < expires): expires = membership.ends_at
                candidate = {
                    "id": f"event:{event.id}:cohost:{relation.id}", "type":"EVENT", "scope":f"event:{event.id}",
                    "event_id":event.id, "bar_id":event.bar_id, "organization_id":relation.organization_id,
                    "role":"MANAGER", "actions":sorted(actions), "source":"EVENT_COHOST",
                    "activated_at": relation.created_at.isoformat() if relation.created_at else None,
                    "expires_at": expires.isoformat() if expires else None, "status":"ACTIVE",
                    "updated_at": relation.updated_at.isoformat() if relation.updated_at else None,
                    "event":{"id":event.id,"name":event.name,"state":(event.event_state or "LIVE").upper(),"starts_at":event.starts_at.isoformat() if event.starts_at else None,"ends_at":event.ends_at.isoformat() if event.ends_at else None},
                }
                current = by_event.get(event.id)
                if current is None:
                    items.append(candidate); by_event[event.id]=candidate
                else:
                    current["actions"] = sorted(set(current.get("actions",[])) | actions)
                    current["sources"] = sorted(set(current.get("sources",[current.get("source")])) | {"EVENT_COHOST"})
                    if current.get("source") == "EVENT_COHOST" or not current.get("source"): current["source"]="EVENT_COHOST"
        return sorted(items, key=lambda item: item["event_id"])

    operational.event_capabilities = wrapped
    operational._forum_cohost_installed = True
