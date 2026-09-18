"""Convert the legacy Forum P1 contracts before the modern Forum lineage.

Revision ID: 0015_legacy_forum_bridge
Revises: 0014_forum_p1

The legacy database used the same table names as the modern RBAC, claim,
invitation and cohost models, but with incompatible columns.  The original
tables are renamed and retained as immutable migration archives.  Canonical
tables are then recreated and populated without discarding legacy rows.
"""

from __future__ import annotations

from datetime import datetime
import re

from alembic import op
import sqlalchemy as sa


revision = "0015_legacy_forum_bridge"
down_revision = "0014_forum_p1"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _rename_legacy(
    table: str,
    archive: str,
    legacy_marker: str,
    modern_marker: str | None = None,
) -> bool:
    tables = _tables()
    if archive in tables:
        return False
    columns = _columns(table)
    if table in tables and legacy_marker in columns and (modern_marker is None or modern_marker not in columns):
        op.rename_table(table, archive)
        return True
    return False


def _role_code(value: str) -> str:
    code = re.sub(r"[^A-Z0-9]+", "_", (value or "MEMBER").upper()).strip("_")
    return (code or "MEMBER")[:64]


def _create_rbac_tables() -> None:
    tables = _tables()
    if "structure_roles" not in tables:
        op.create_table(
            "structure_roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
            sa.Column("scope_key", sa.String(180), nullable=False),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_legacy", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("scope_key", name="uq_structure_roles_scope_key"),
        )
        op.create_index("ix_structure_roles_organization_id", "structure_roles", ["organization_id"])
        op.create_index("ix_structure_roles_scope_key", "structure_roles", ["scope_key"], unique=True)
        op.create_index("ix_structure_roles_code", "structure_roles", ["code"])
        op.create_index("ix_structure_roles_is_system", "structure_roles", ["is_system"])
        op.create_index("ix_structure_roles_is_legacy", "structure_roles", ["is_legacy"])
    if "structure_membership_roles" not in _tables():
        op.create_table(
            "structure_membership_roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("membership_id", sa.Integer(), sa.ForeignKey("organization_memberships.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role_id", sa.Integer(), sa.ForeignKey("structure_roles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("assigned_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("membership_id", "role_id", name="uq_structure_membership_role"),
        )
        op.create_index("ix_structure_membership_roles_membership_id", "structure_membership_roles", ["membership_id"])
        op.create_index("ix_structure_membership_roles_role_id", "structure_membership_roles", ["role_id"])


def _copy_legacy_rbac() -> None:
    bind = op.get_bind()
    if "legacy_forum_structure_roles" not in _tables():
        return
    old_roles = sa.Table("legacy_forum_structure_roles", sa.MetaData(), autoload_with=bind)
    roles = sa.Table("structure_roles", sa.MetaData(), autoload_with=bind)
    existing = set(bind.execute(sa.select(roles.c.id)).scalars())
    for row in bind.execute(sa.select(old_roles)).mappings():
        if row["id"] in existing:
            continue
        bind.execute(roles.insert().values(
            id=row["id"],
            organization_id=row["organization_id"],
            scope_key=f"legacy-foundation:{row['organization_id']}:{row['id']}",
            code=_role_code(row["name"]),
            name=row["name"],
            is_system=False,
            is_legacy=True,
            created_by_user_id=row.get("created_by_user_id"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        ))
    if "legacy_forum_structure_role_assignments" not in _tables():
        return
    old_assignments = sa.Table("legacy_forum_structure_role_assignments", sa.MetaData(), autoload_with=bind)
    assignments = sa.Table("structure_membership_roles", sa.MetaData(), autoload_with=bind)
    existing_pairs = set(bind.execute(sa.select(assignments.c.membership_id, assignments.c.role_id)).all())
    for row in bind.execute(sa.select(old_assignments)).mappings():
        pair = (row["membership_id"], row["role_id"])
        if pair in existing_pairs:
            continue
        bind.execute(assignments.insert().values(
            membership_id=row["membership_id"],
            role_id=row["role_id"],
            assigned_by_user_id=row.get("assigned_by_user_id"),
            created_at=row["created_at"],
        ))


def _create_claims() -> None:
    if "structure_claims" in _tables():
        return
    op.create_table(
        "structure_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("structure_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("claimant_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("reviewer_user_id", sa.String(), sa.ForeignKey("app_users.id")),
        sa.Column("review_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("decided_at", sa.DateTime()),
        sa.Column("cancelled_at", sa.DateTime()),
    )
    op.create_index("ix_structure_claims_structure_status", "structure_claims", ["structure_id", "status"])
    op.create_index("ix_structure_claims_claimant_status", "structure_claims", ["claimant_user_id", "status"])
    op.create_index("ix_structure_claims_created_at", "structure_claims", ["created_at"])


def _copy_claims() -> None:
    bind = op.get_bind()
    if "legacy_forum_structure_claims" not in _tables():
        return
    old = sa.Table("legacy_forum_structure_claims", sa.MetaData(), autoload_with=bind)
    new = sa.Table("structure_claims", sa.MetaData(), autoload_with=bind)
    existing = set(bind.execute(sa.select(new.c.id)).scalars())
    for row in bind.execute(sa.select(old)).mappings():
        if row["id"] in existing:
            continue
        reviewed = row.get("reviewed_at")
        status = str(row.get("status") or "PENDING").upper()
        bind.execute(new.insert().values(
            id=row["id"], structure_id=row["organization_id"], claimant_user_id=row["requested_by_user_id"],
            reason=row.get("reason") or "Legacy claim", evidence_json={}, status=status,
            reviewer_user_id=row.get("reviewed_by_user_id"), review_notes=None,
            created_at=row["created_at"], updated_at=reviewed or row["created_at"], reviewed_at=reviewed,
            decided_at=reviewed if status in {"APPROVED", "REJECTED"} else None,
            cancelled_at=reviewed if status == "CANCELLED" else None,
        ))


def _create_invitations() -> None:
    if "structure_invitations" in _tables():
        return
    op.create_table(
        "structure_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("structure_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("invited_role", sa.String(64), nullable=False, server_default="MEMBER"),
        sa.Column("invited_role_id", sa.Integer(), sa.ForeignKey("structure_roles.id")),
        sa.Column("invited_by", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime()),
        sa.Column("declined_at", sa.DateTime()),
        sa.Column("revoked_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_structure_invitations_structure_email", "structure_invitations", ["structure_id", "email"])
    op.create_index("ix_structure_invitations_token_hash", "structure_invitations", ["token_hash"], unique=True)


def _copy_invitations() -> None:
    bind = op.get_bind()
    if "legacy_forum_structure_invitations" not in _tables():
        return
    old = sa.Table("legacy_forum_structure_invitations", sa.MetaData(), autoload_with=bind)
    new = sa.Table("structure_invitations", sa.MetaData(), autoload_with=bind)
    roles = sa.Table("structure_roles", sa.MetaData(), autoload_with=bind)
    role_codes = dict(bind.execute(sa.select(roles.c.id, roles.c.code)).all())
    existing = set(bind.execute(sa.select(new.c.id)).scalars())
    for row in bind.execute(sa.select(old)).mappings():
        if row["id"] in existing:
            continue
        status = str(row.get("status") or "PENDING").upper()
        bind.execute(new.insert().values(
            id=row["id"], structure_id=row["organization_id"], email=row["email"], token_hash=row["token_hash"],
            invited_role=role_codes.get(row.get("role_id"), "MEMBER"), invited_role_id=row.get("role_id"),
            invited_by=row["invited_by_user_id"], expires_at=row["expires_at"], accepted_at=row.get("accepted_at"),
            declined_at=row.get("created_at") if status == "DECLINED" else None,
            revoked_at=row.get("created_at") if status == "REVOKED" else None, created_at=row["created_at"],
        ))


def _create_event_structures() -> None:
    if "event_structures" in _tables():
        return
    op.create_table(
        "event_structures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="COHOST"),
        sa.Column("can_edit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_publish", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_staff", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_documents", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_finance", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_recap", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("app_users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_id", "organization_id", name="uq_event_structures_event_org"),
    )
    op.create_index("ix_event_structures_org_role", "event_structures", ["organization_id", "role"])
    op.create_index("ix_event_structures_event_id", "event_structures", ["event_id"])


def _copy_event_structures() -> None:
    bind = op.get_bind()
    if "legacy_forum_event_structures" not in _tables():
        return
    old = sa.Table("legacy_forum_event_structures", sa.MetaData(), autoload_with=bind)
    new = sa.Table("event_structures", sa.MetaData(), autoload_with=bind)
    existing = set(bind.execute(sa.select(new.c.event_id, new.c.organization_id)).all())
    for row in bind.execute(sa.select(old)).mappings():
        pair = (row["event_id"], row["organization_id"])
        if pair in existing:
            continue
        owner = str(row.get("role") or "HOST").upper() == "HOST"
        stamp = row.get("created_at") or datetime.utcnow()
        bind.execute(new.insert().values(
            id=row["id"], event_id=row["event_id"], organization_id=row["organization_id"],
            role="OWNER" if owner else "COHOST", can_edit=owner, can_publish=owner, can_staff=owner,
            can_documents=owner, can_finance=owner, can_recap=owner, created_by_user_id=None,
            created_at=stamp, updated_at=stamp,
        ))


def upgrade() -> None:
    _rename_legacy("structure_role_assignments", "legacy_forum_structure_role_assignments", "organization_id")
    _rename_legacy("structure_invitations", "legacy_forum_structure_invitations", "organization_id")
    _rename_legacy("structure_roles", "legacy_forum_structure_roles", "system_role")
    _rename_legacy("structure_claims", "legacy_forum_structure_claims", "organization_id")
    event_structures_renamed = _rename_legacy(
        "event_structures", "legacy_forum_event_structures", "created_at", modern_marker="can_edit"
    )
    if event_structures_renamed:
        indexes = {
            index.get("name")
            for index in sa.inspect(op.get_bind()).get_indexes("legacy_forum_event_structures")
        }
        if "ix_event_structures_org_role" in indexes:
            op.drop_index("ix_event_structures_org_role", table_name="legacy_forum_event_structures")

    _create_rbac_tables()
    _copy_legacy_rbac()
    _create_claims()
    _copy_claims()
    _create_invitations()
    _copy_invitations()
    _create_event_structures()
    _copy_event_structures()


def downgrade() -> None:
    # Downstream modern downgrades remove the canonical replacements before this
    # revision is reached.  Restore retained legacy tables only when they exist;
    # a fresh/current installation has no archives and therefore needs no work.
    pairs = (
        ("legacy_forum_structure_roles", "structure_roles"),
        ("legacy_forum_structure_role_assignments", "structure_role_assignments"),
        ("legacy_forum_structure_claims", "structure_claims"),
        ("legacy_forum_structure_invitations", "structure_invitations"),
        ("legacy_forum_event_structures", "event_structures"),
    )
    for archive, canonical in pairs:
        tables = _tables()
        if archive not in tables:
            continue
        if canonical in tables:
            raise RuntimeError(f"Cannot restore {archive}: {canonical} still exists")
        op.rename_table(archive, canonical)
