"""Add independent visibility keys for every public structure block.

The settings live in the existing JSON column; this migration normalizes legacy
portal switches so deployments can roll forward without a client-side fallback.
"""
from alembic import op
import json
import sqlalchemy as sa

revision = "0022_forum_per_block_visibility"
down_revision = "0021_event_structure_cohosting"
branch_labels = None
depends_on = None

DEFAULTS = {
    "about": "PUBLIC", "history": "PUBLIC", "partners": "PUBLIC",
    "services": "PUBLIC", "announcement": "PUBLIC", "team": "STRUCTURE_MEMBERS",
    "events": "PUBLIC", "albums": "PUBLIC", "documents": "STRUCTURE_MEMBERS",
    "stats": "ADMINS", "contact": "PUBLIC", "folklore": "PUBLIC",
}
ALIASES = {"gallery": "albums", "memory": "history", "description": "about"}

def upgrade():
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, visibility_settings_json, public_content_json FROM organizations")).mappings()
    for row in rows:
        raw = json.loads(row["visibility_settings_json"] or "{}") if isinstance(row["visibility_settings_json"], str) else (row["visibility_settings_json"] or {})
        content = json.loads(row["public_content_json"] or "{}") if isinstance(row["public_content_json"], str) else (row["public_content_json"] or {})
        settings = {**DEFAULTS, **{k: str(v).upper() for k, v in raw.items() if k in DEFAULTS}}
        portal = content.get("portal", {}) if isinstance(content, dict) else {}
        for legacy in portal.get("hidden_blocks", []) if isinstance(portal, dict) else []:
            key = ALIASES.get(str(legacy), str(legacy))
            if key in settings and key not in raw:
                settings[key] = "HIDDEN"
        bind.execute(sa.text("UPDATE organizations SET visibility_settings_json = :settings WHERE id = :id"), {"id": row["id"], "settings": json.dumps(settings)})

def downgrade():
    pass
