"""Introduce capability-based Structure RBAC with a retro-compatible role backfill."""

from datetime import datetime, timezone
import re

from alembic import op
import sqlalchemy as sa

from app.services.structure_rbac import STRUCTURE_CAPABILITIES, SYSTEM_ROLE_CAPABILITIES


revision = "0014_structure_capability_rbac"
down_revision = "0013_structure_lifecycle_private_defaults"
branch_labels = None
depends_on = None


LEGACY_ROLE_RANK = {
    "FOLLOWER": 0,
    "ANCIEN": 0,
    "MEMBER": 1,
    "STAFF": 2,
    "COMMUNICATION": 2,
    "ARCHIVIST": 2,
    "TREASURER": 3,
    "TRESORIER": 3,
    "SECRETARY": 3,
    "BUREAU": 4,
    "VICE_PRESIDENT": 4,
    "PRESIDENT": 4,
    "MANAGER": 4,
    "ADMIN": 5,
    "OWNER": 6,
}

LEGACY_BASE = {
    "structure.read", "member.read", "discussion.read", "discussion.write", "event.read",
    "document.read", "album.read", "page.read", "planning.read", "stats.read",
}
LEGACY_MANAGER = LEGACY_BASE | {
    "structure.edit", "structure.publish",
    "member.invite", "member.manage", "member.role.manage", "member.mandate.manage",
    "discussion.manage", "channel.create", "channel.manage",
    "event.create", "event.manage", "event.publish", "event.recap.manage",
    "document.manage", "document.publish", "album.manage", "album.publish",
    "page.manage", "page.publish", "planning.manage", "visibility.manage",
    "audit.read", "export.create",
}


def _legacy_caps(role: str) -> set[str]:
    normalized = (role or "MEMBER").upper()
    if normalized == "OWNER":
        # OWNER was the ultimate authority in the legacy model and must not lose
        # access to capabilities introduced by this migration.
        return set(STRUCTURE_CAPABILITIES)
    rank = LEGACY_ROLE_RANK.get(normalized, 0)
    if rank < 1:
        return set()
    result = set(LEGACY_BASE)
    if rank >= 3:
        result.add("finance.read")
    if rank >= 4:
        result |= LEGACY_MANAGER
    if rank >= 6:
        result |= {"ownership.transfer", "ownership.recover"}
    return result


def _code(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", (value or "MEMBER").upper()).strip("_")
    return normalized[:64] or "MEMBER"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "structure_capabilities" not in tables:
        op.create_table(
            "structure_capabilities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("key", sa.String(length=96), nullable=False),
            sa.Column("description", sa.String(length=280), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("key", name="uq_structure_capabilities_key"),
        )
        op.create_index("ix_structure_capabilities_key", "structure_capabilities", ["key"], unique=True)
        op.create_index("ix_structure_capabilities_created_at", "structure_capabilities", ["created_at"])

    if "structure_roles" not in tables:
        op.create_table(
            "structure_roles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
            sa.Column("scope_key", sa.String(length=180), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
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

    if "structure_role_capabilities" not in tables:
        op.create_table(
            "structure_role_capabilities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("role_id", sa.Integer(), sa.ForeignKey("structure_roles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("capability_id", sa.Integer(), sa.ForeignKey("structure_capabilities.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("role_id", "capability_id", name="uq_structure_role_capability"),
        )
        op.create_index("ix_structure_role_capabilities_role_id", "structure_role_capabilities", ["role_id"])
        op.create_index("ix_structure_role_capabilities_capability_id", "structure_role_capabilities", ["capability_id"])

    if "structure_membership_roles" not in tables:
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

    stamp = datetime.now(timezone.utc).replace(tzinfo=None)
    capability = sa.table(
        "structure_capabilities",
        sa.column("id", sa.Integer()), sa.column("key", sa.String()),
        sa.column("description", sa.String()), sa.column("created_at", sa.DateTime()),
    )
    role = sa.table(
        "structure_roles",
        sa.column("id", sa.Integer()), sa.column("organization_id", sa.Integer()),
        sa.column("scope_key", sa.String()), sa.column("code", sa.String()), sa.column("name", sa.String()),
        sa.column("is_system", sa.Boolean()), sa.column("is_legacy", sa.Boolean()),
        sa.column("created_by_user_id", sa.String()), sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    role_cap = sa.table(
        "structure_role_capabilities",
        sa.column("id", sa.Integer()), sa.column("role_id", sa.Integer()),
        sa.column("capability_id", sa.Integer()), sa.column("created_at", sa.DateTime()),
    )
    member_role = sa.table(
        "structure_membership_roles",
        sa.column("id", sa.Integer()), sa.column("membership_id", sa.Integer()),
        sa.column("role_id", sa.Integer()), sa.column("assigned_by_user_id", sa.String()),
        sa.column("created_at", sa.DateTime()),
    )
    memberships = sa.table(
        "organization_memberships",
        sa.column("id", sa.Integer()), sa.column("organization_id", sa.Integer()), sa.column("role", sa.String()),
    )

    existing_caps = {key: cid for cid, key in bind.execute(sa.select(capability.c.id, capability.c.key)).all()}
    for key in STRUCTURE_CAPABILITIES:
        if key not in existing_caps:
            bind.execute(capability.insert().values(key=key, description=None, created_at=stamp))
    existing_caps = {key: cid for cid, key in bind.execute(sa.select(capability.c.id, capability.c.key)).all()}

    for code, cap_keys in SYSTEM_ROLE_CAPABILITIES.items():
        scope = f"system:{code}"
        role_id = bind.execute(sa.select(role.c.id).where(role.c.scope_key == scope)).scalar_one_or_none()
        if role_id is None:
            result = bind.execute(role.insert().values(
                organization_id=None,
                scope_key=scope,
                code=code,
                name=code.replace("_", " ").title(),
                is_system=True,
                is_legacy=False,
                created_by_user_id=None,
                created_at=stamp,
                updated_at=stamp,
            ))
            role_id = result.inserted_primary_key[0]
        existing_links = set(bind.execute(sa.select(role_cap.c.capability_id).where(role_cap.c.role_id == role_id)).scalars().all())
        for key in cap_keys:
            cap_id = existing_caps[key]
            if cap_id not in existing_links:
                bind.execute(role_cap.insert().values(role_id=role_id, capability_id=cap_id, created_at=stamp))

    # Historical memberships are copied to per-Structure immutable-meaning legacy roles.
    # This freezes their old effective access instead of making future system-role changes retroactive.
    for membership_id, organization_id, legacy_role in bind.execute(
        sa.select(memberships.c.id, memberships.c.organization_id, memberships.c.role)
    ).all():
        already = bind.execute(sa.select(member_role.c.id).where(member_role.c.membership_id == membership_id)).first()
        if already:
            continue
        legacy_code = _code(legacy_role or "MEMBER")
        scope = f"legacy:{organization_id}:{legacy_code}"
        role_id = bind.execute(sa.select(role.c.id).where(role.c.scope_key == scope)).scalar_one_or_none()
        if role_id is None:
            result = bind.execute(role.insert().values(
                organization_id=organization_id,
                scope_key=scope,
                code=f"LEGACY_{legacy_code}"[:64],
                name=f"Legacy {legacy_code.replace('_', ' ').title()}",
                is_system=False,
                is_legacy=True,
                created_by_user_id=None,
                created_at=stamp,
                updated_at=stamp,
            ))
            role_id = result.inserted_primary_key[0]
            for key in _legacy_caps(legacy_role or "MEMBER"):
                bind.execute(role_cap.insert().values(
                    role_id=role_id,
                    capability_id=existing_caps[key],
                    created_at=stamp,
                ))
        bind.execute(member_role.insert().values(
            membership_id=membership_id,
            role_id=role_id,
            assigned_by_user_id=None,
            created_at=stamp,
        ))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table_name in (
        "structure_membership_roles",
        "structure_role_capabilities",
        "structure_roles",
        "structure_capabilities",
    ):
        if table_name in tables:
            op.drop_table(table_name)
