"""unify profiles, privacy, affiliations and effective roles

Revision ID: 0008_unified_profile_affiliations
Revises: 0007_public_content_branding
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0008_unified_profile_affiliations"
down_revision = "0007_public_content_branding"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def _add_missing(table_name: str, columns: list[sa.Column]) -> None:
    existing = _columns(table_name)
    for column in columns:
        if column.name not in existing:
            op.add_column(table_name, column)


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def _add_index(table_name: str, name: str, columns: list[str], *, unique: bool = False) -> None:
    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns, unique=unique)


def _ensure_alembic_version_capacity() -> None:
    """Allow descriptive revision IDs on PostgreSQL.

    Alembic creates ``alembic_version.version_num`` as VARCHAR(32) by default.
    This revision ID is longer than 32 chars, so PostgreSQL rejects Alembic's
    bookkeeping UPDATE after the migration body completes. SQLite does not
    enforce that length, which is why the issue can be invisible in SQLite CI.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE alembic_version "
        "ALTER COLUMN version_num TYPE VARCHAR(128)"
    )


def upgrade() -> None:
    # Must happen before Alembic records this revision name at the end of the
    # migration transaction.
    _ensure_alembic_version_capacity()

    _add_missing("app_users", [
        sa.Column("username", sa.String(length=40), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("account_status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("global_role", sa.String(length=16), nullable=False, server_default="USER"),
        sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.false()),
    ])
    op.execute("UPDATE app_users SET updated_at = COALESCE(updated_at, created_at)")
    # A legacy profile is never made public by this migration.
    op.execute("UPDATE app_users SET profile_visibility = 'PRIVATE'")
    _add_index("app_users", "ix_app_users_username", ["username"], unique=True)
    _add_index("app_users", "ix_app_users_updated_at", ["updated_at"])
    _add_index("app_users", "ix_app_users_account_status", ["account_status"])
    _add_index("app_users", "ix_app_users_global_role", ["global_role"])
    _add_index("app_users", "ix_app_users_is_guest", ["is_guest"])

    _add_missing("app_user_privacy_settings", [
        sa.Column("photo_visibility", sa.String(length=16), nullable=False, server_default="PRIVATE"),
        sa.Column("bio_visibility", sa.String(length=16), nullable=False, server_default="PRIVATE"),
        sa.Column("affiliations_visibility", sa.String(length=16), nullable=False, server_default="PRIVATE"),
        sa.Column("badges_visibility", sa.String(length=16), nullable=False, server_default="PRIVATE"),
        sa.Column("event_history_visibility", sa.String(length=16), nullable=False, server_default="PRIVATE"),
        sa.Column("participations_visibility", sa.String(length=16), nullable=False, server_default="PRIVATE"),
        sa.Column("gamification_visibility", sa.String(length=16), nullable=False, server_default="PRIVATE"),
        sa.Column("event_history_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("participations_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("gamification_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
    ])
    op.execute("UPDATE app_user_privacy_settings SET visibility = 'PRIVATE'")

    _add_missing("organization_memberships", [
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("mandate_label", sa.String(length=120), nullable=True),
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="PRIVATE"),
        sa.Column("validation_source", sa.String(length=32), nullable=False, server_default="LEGACY"),
        sa.Column("validated_by_user_id", sa.String(), nullable=True),
        sa.Column("validated_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by_user_id", sa.String(), nullable=True),
        sa.Column("revoke_reason", sa.String(length=280), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
    ])
    op.execute("UPDATE organization_memberships SET starts_at = COALESCE(starts_at, joined_at)")
    _add_index("organization_memberships", "ix_organization_memberships_starts_at", ["starts_at"])
    _add_index("organization_memberships", "ix_organization_memberships_ends_at", ["ends_at"])
    _add_index("organization_memberships", "ix_organization_memberships_visibility", ["visibility"])
    _add_index("organization_memberships", "ix_organization_memberships_validation_source", ["validation_source"])
    _add_index("organization_memberships", "ix_organization_memberships_validated_by_user_id", ["validated_by_user_id"])
    _add_index("organization_memberships", "ix_organization_memberships_revoked_at", ["revoked_at"])

    _add_missing("event_staff", [sa.Column("expires_at", sa.DateTime(), nullable=True)])
    _add_index("event_staff", "ix_event_staff_expires_at", ["expires_at"])

    _add_missing("partner_users", [sa.Column("app_user_id", sa.String(), nullable=True)])
    _add_index("partner_users", "ix_partner_users_app_user_id", ["app_user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_partner_users_app_user_id", table_name="partner_users")
    with op.batch_alter_table("partner_users") as batch:
        batch.drop_column("app_user_id")
    op.drop_index("ix_event_staff_expires_at", table_name="event_staff")
    with op.batch_alter_table("event_staff") as batch:
        batch.drop_column("expires_at")
    for name in [
        "ix_organization_memberships_revoked_at",
        "ix_organization_memberships_validated_by_user_id",
        "ix_organization_memberships_validation_source",
        "ix_organization_memberships_visibility",
        "ix_organization_memberships_ends_at",
        "ix_organization_memberships_starts_at",
    ]:
        op.drop_index(name, table_name="organization_memberships")
    with op.batch_alter_table("organization_memberships") as batch:
        for name in [
            "metadata_json", "revoke_reason", "revoked_by_user_id", "revoked_at",
            "validated_at", "validated_by_user_id", "validation_source", "visibility",
            "mandate_label", "ends_at", "starts_at",
        ]:
            batch.drop_column(name)
    with op.batch_alter_table("app_user_privacy_settings") as batch:
        for name in [
            "gamification_opt_in", "participations_opt_in", "event_history_opt_in",
            "gamification_visibility", "participations_visibility", "event_history_visibility",
            "badges_visibility", "affiliations_visibility", "bio_visibility", "photo_visibility",
        ]:
            batch.drop_column(name)
    for name in [
        "ix_app_users_is_guest", "ix_app_users_global_role", "ix_app_users_account_status",
        "ix_app_users_updated_at", "ix_app_users_username",
    ]:
        op.drop_index(name, table_name="app_users")
    with op.batch_alter_table("app_users") as batch:
        for name in ["is_guest", "global_role", "account_status", "updated_at", "city", "username"]:
            batch.drop_column(name)
