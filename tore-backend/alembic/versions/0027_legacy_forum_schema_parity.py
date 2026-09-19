"""Align indexes after converting legacy Forum tables to current contracts."""

from alembic import op
import sqlalchemy as sa


revision = "0027_legacy_forum_schema_parity"
down_revision = "0026_finalize_legacy_forum_bridge"
branch_labels = None
depends_on = None


INDEXES = {
    "structure_roles": {
        "ix_structure_roles_created_by_user_id": ["created_by_user_id"],
        "ix_structure_roles_created_at": ["created_at"],
        "ix_structure_roles_updated_at": ["updated_at"],
    },
    "structure_role_capabilities": {
        "ix_structure_role_capabilities_created_at": ["created_at"],
    },
    "structure_membership_roles": {
        "ix_structure_membership_roles_assigned_by_user_id": ["assigned_by_user_id"],
        "ix_structure_membership_roles_created_at": ["created_at"],
    },
    "structure_claims": {
        "ix_structure_claims_structure_id": ["structure_id"],
        "ix_structure_claims_claimant_user_id": ["claimant_user_id"],
        "ix_structure_claims_status": ["status"],
        "ix_structure_claims_reviewer_user_id": ["reviewer_user_id"],
        "ix_structure_claims_updated_at": ["updated_at"],
        "ix_structure_claims_reviewed_at": ["reviewed_at"],
        "ix_structure_claims_decided_at": ["decided_at"],
        "ix_structure_claims_cancelled_at": ["cancelled_at"],
    },
    "structure_invitations": {
        "ix_structure_invitations_structure_id": ["structure_id"],
        "ix_structure_invitations_email": ["email"],
        "ix_structure_invitations_invited_role": ["invited_role"],
        "ix_structure_invitations_invited_role_id": ["invited_role_id"],
        "ix_structure_invitations_invited_by": ["invited_by"],
        "ix_structure_invitations_expires_at": ["expires_at"],
        "ix_structure_invitations_accepted_at": ["accepted_at"],
        "ix_structure_invitations_declined_at": ["declined_at"],
        "ix_structure_invitations_revoked_at": ["revoked_at"],
        "ix_structure_invitations_created_at": ["created_at"],
    },
    "event_structures": {
        "ix_event_structures_organization_id": ["organization_id"],
        "ix_event_structures_role": ["role"],
        "ix_event_structures_created_at": ["created_at"],
        "ix_event_structures_updated_at": ["updated_at"],
    },
}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    index_owner = {
        item.get("name"): table
        for table in tables
        for item in inspector.get_indexes(table)
        if item.get("name")
    }
    for table, indexes in INDEXES.items():
        if table not in tables:
            continue
        existing = {item.get("name") for item in inspector.get_indexes(table)}
        for name, columns in indexes.items():
            if name not in existing:
                owner = index_owner.get(name)
                if owner and owner.startswith("legacy_forum_"):
                    op.drop_index(name, table_name=owner)
                op.create_index(name, table, columns)


def downgrade() -> None:
    # Some indexes predate this parity revision on fresh ORM-created schemas.
    # Keeping them during downgrade is safe and avoids deleting baseline indexes.
    pass
