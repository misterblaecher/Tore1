"""Finalize preserved legacy role permissions after capability catalog creation."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "0026_finalize_legacy_forum_bridge"
down_revision = ("0025_structure_planning", "0015_legacy_forum_bridge")
branch_labels = None
depends_on = None


PERMISSION_MAP = {
    "structure.read": {"structure.read"},
    "structure.manage": {"structure.edit", "structure.publish"},
    "structure.admin": {"structure.edit", "structure.publish", "visibility.manage", "audit.read", "export.create"},
    "ownership.transfer": {"ownership.transfer"},
    "members.view": {"member.read"},
    "members.manage": {"member.invite", "member.manage", "member.role.manage", "member.mandate.manage"},
    "roles.manage": {"member.role.manage"},
    "visibility.manage": {"visibility.manage"},
    "events.view": {"event.read"},
    "events.manage": {"event.create", "event.manage", "event.recap.manage"},
    "events.publish": {"event.publish"},
    "stats.view": {"stats.read"},
    "accounting.view": {"finance.read"},
    "accounting.manage": {"finance.write", "finance.review", "finance.export"},
    "accounting.unlock": {"finance.lock"},
    "channels.read": {"discussion.read"},
    "channels.post": {"discussion.write"},
    "channels.manage": {"discussion.manage", "channel.create", "channel.manage"},
    "documents.view": {"document.read"},
    "documents.download": {"document.read"},
    "documents.manage": {"document.manage", "document.publish"},
    "albums.view": {"album.read"},
    "albums.manage": {"album.manage", "album.publish"},
    "folklore.view": {"page.read"},
    "folklore.manage": {"page.manage", "page.publish"},
    "publications.manage": {"structure.publish"},
    "audit.view": {"audit.read"},
    "search.view": {"structure.read"},
}


def _permissions(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return []
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    return []


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    required = {"legacy_forum_structure_roles", "structure_capabilities", "structure_role_capabilities"}
    if not required.issubset(tables):
        return
    old_roles = sa.Table("legacy_forum_structure_roles", sa.MetaData(), autoload_with=bind)
    capabilities = sa.Table("structure_capabilities", sa.MetaData(), autoload_with=bind)
    links = sa.Table("structure_role_capabilities", sa.MetaData(), autoload_with=bind)
    cap_ids = dict(bind.execute(sa.select(capabilities.c.key, capabilities.c.id)).all())
    existing = set(bind.execute(sa.select(links.c.role_id, links.c.capability_id)).all())
    for row in bind.execute(sa.select(old_roles.c.id, old_roles.c.permissions_json)).mappings():
        mapped: set[str] = set()
        for permission in _permissions(row["permissions_json"]):
            mapped.update(PERMISSION_MAP.get(permission, set()))
        for key in mapped:
            cap_id = cap_ids.get(key)
            pair = (row["id"], cap_id)
            if cap_id is not None and pair not in existing:
                bind.execute(links.insert().values(
                    role_id=row["id"], capability_id=cap_id,
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                ))
                existing.add(pair)


def downgrade() -> None:
    # Capability links may have been edited after migration; removing them is
    # not distinguishable from deleting user changes.
    pass
