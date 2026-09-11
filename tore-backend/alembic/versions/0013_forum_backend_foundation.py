"""Forum backend production foundation.

Revision ID: 0013_forum_backend_foundation
Revises: 0012_discussion_workspace
Create Date: 2026-09-11
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0013_forum_backend_foundation"
down_revision = "0012_discussion_workspace"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _create(name: str, *columns, **kwargs) -> None:
    if name not in _tables():
        op.create_table(name, *columns, **kwargs)


def upgrade() -> None:
    _create(
        "structure_governance",
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), primary_key=True),
        sa.Column("owner_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("seo_title", sa.String(180), nullable=True),
        sa.Column("seo_description", sa.String(320), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('REQUESTED','SETUP','ACTIVE','LOCKED','ARCHIVED')", name="ck_structure_governance_status"),
    )
    op.create_index("ix_structure_governance_owner", "structure_governance", ["owner_user_id"])
    op.create_index("ix_structure_governance_status", "structure_governance", ["status"])

    _create(
        "structure_public_pages",
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("seo_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("indexable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('DRAFT','PUBLISHED','HIDDEN','SUSPENDED','ARCHIVED')", name="ck_structure_public_page_status"),
    )
    op.create_index("ix_structure_public_pages_status", "structure_public_pages", ["status"])

    _create(
        "structure_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("system_role", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("audience_level", sa.String(16), nullable=False, server_default="MEMBERS"),
        sa.Column("permissions_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_structure_roles_org_name"),
        sa.CheckConstraint("audience_level IN ('PUBLIC','TORE','MEMBERS','STAFF','BUREAU','TREASURY','PRIVATE')", name="ck_structure_role_audience"),
    )
    op.create_index("ix_structure_roles_org_system", "structure_roles", ["organization_id", "system_role"])

    _create(
        "structure_role_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("membership_id", sa.Integer(), sa.ForeignKey("organization_memberships.id"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("structure_roles.id"), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("membership_id", name="uq_structure_role_assignment_membership"),
    )
    op.create_index("ix_structure_role_assignments_org_role", "structure_role_assignments", ["organization_id", "role_id"])

    _create(
        "structure_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("structure_roles.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("invited_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("accepted_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
        sa.CheckConstraint("status IN ('PENDING','ACCEPTED','EXPIRED','REVOKED')", name="ck_structure_invitation_status"),
    )
    op.create_index("ix_structure_invitations_org_status", "structure_invitations", ["organization_id", "status"])
    op.create_index("ix_structure_invitations_email", "structure_invitations", ["email"])

    _create(
        "structure_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
        sa.CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','CANCELLED')", name="ck_structure_claim_status"),
    )
    op.create_index("ix_structure_claims_org_status", "structure_claims", ["organization_id", "status"])
    op.create_index("ix_structure_claims_requester_status", "structure_claims", ["requested_by_user_id", "status"])

    _create(
        "structure_visibility_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("resource_type", sa.String(48), nullable=False),
        sa.Column("resource_id", sa.String(80), nullable=False, server_default="__section__"),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("updated_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "resource_type", "resource_id", name="uq_structure_visibility_policy_resource"),
        sa.CheckConstraint("level IN ('PUBLIC','TORE','MEMBERS','STAFF','BUREAU','TREASURY','PRIVATE')", name="ck_structure_visibility_policy_level"),
    )
    op.create_index("ix_structure_visibility_policy_lookup", "structure_visibility_policies", ["organization_id", "resource_type", "resource_id"])

    _create(
        "event_structures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="HOST"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_id", "organization_id", name="uq_event_structures_event_org"),
        sa.CheckConstraint("role IN ('HOST','CO_HOST')", name="ck_event_structure_role"),
    )
    op.create_index("ix_event_structures_org_role", "event_structures", ["organization_id", "role"])

    _create(
        "forum_event_lifecycle",
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"),
        sa.Column("updated_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('DRAFT','PUBLISHED','SYNCED_TO_APP','LIVE','CLOSED','RECAP_DRAFT','RECAP_PUBLISHED','ARCHIVED')", name="ck_forum_event_lifecycle_status"),
    )
    op.create_index("ix_forum_event_lifecycle_org_status", "forum_event_lifecycle", ["organization_id", "status"])

    _create(
        "event_public_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False, unique=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("entries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scans", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("occupancy_percent", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("published_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
    )
    op.create_index("ix_event_public_summaries_org", "event_public_summaries", ["organization_id", "published_at"])

    _create(
        "structure_accounting_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("entry_type", sa.String(16), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("label", sa.String(180), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("supplier", sa.String(180), nullable=True),
        sa.Column("paid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("locked_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=True),
        sa.CheckConstraint("entry_type IN ('INCOME','EXPENSE')", name="ck_structure_accounting_type"),
        sa.CheckConstraint("status IN ('DRAFT','VALIDATED','LOCKED')", name="ck_structure_accounting_status"),
    )
    op.create_index("ix_structure_accounting_org_event", "structure_accounting_entries", ["organization_id", "event_id"])
    op.create_index("ix_structure_accounting_org_status", "structure_accounting_entries", ["organization_id", "status"])

    _create(
        "structure_document_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("structure_documents.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False, unique=True),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(160), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("document_id", "version_number", name="uq_structure_document_version_number"),
    )
    op.create_index("ix_structure_document_versions_document_created", "structure_document_versions", ["document_id", "created_at"])

    _create(
        "structure_media_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(160), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_structure_media_assets_org_created", "structure_media_assets", ["organization_id", "created_at"])

    _create(
        "structure_album_media_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("album_id", sa.Integer(), sa.ForeignKey("structure_albums.id"), nullable=False),
        sa.Column("media_id", sa.Integer(), sa.ForeignKey("structure_media_assets.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_cover", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("album_id", "media_id", name="uq_structure_album_media_link"),
    )
    op.create_index("ix_structure_album_media_position", "structure_album_media_links", ["album_id", "position"])

    _create(
        "structure_page_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("page_id", sa.Integer(), sa.ForeignKey("structure_pages.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("visibility", sa.String(24), nullable=False),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("page_id", "version_number", name="uq_structure_page_version_number"),
    )
    op.create_index("ix_structure_page_versions_page_created", "structure_page_versions", ["page_id", "created_at"])

    _create(
        "organization_post_publications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("organization_posts.id"), nullable=False, unique=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("media_id", sa.Integer(), sa.ForeignKey("structure_media_assets.id"), nullable=True),
        sa.Column("title", sa.String(180), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="PUBLIC"),
        sa.Column("publish_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('DRAFT','SCHEDULED','PUBLISHED','ARCHIVED')", name="ck_organization_post_publication_status"),
        sa.CheckConstraint("visibility IN ('PUBLIC','TORE','MEMBERS','STAFF','BUREAU','TREASURY','PRIVATE')", name="ck_organization_post_publication_visibility"),
    )
    op.create_index("ix_organization_post_publications_org_schedule", "organization_post_publications", ["organization_id", "status", "publish_at"])

    _create(
        "structure_audit_contexts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("audit_log_id", sa.Integer(), sa.ForeignKey("audit_logs.id"), nullable=False, unique=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_structure_audit_contexts_org_audit", "structure_audit_contexts", ["organization_id", "audit_log_id"])

    _backfill_existing()


def _backfill_existing() -> None:
    bind = op.get_bind()
    stamp = datetime.utcnow()
    metadata = sa.MetaData()
    roles = sa.Table("structure_roles", metadata, autoload_with=bind)
    assignments = sa.Table("structure_role_assignments", metadata, autoload_with=bind)
    governance = sa.Table("structure_governance", metadata, autoload_with=bind)
    public_pages = sa.Table("structure_public_pages", metadata, autoload_with=bind)
    visibility = sa.Table("structure_visibility_policies", metadata, autoload_with=bind)
    event_structures = sa.Table("event_structures", metadata, autoload_with=bind)
    lifecycles = sa.Table("forum_event_lifecycle", metadata, autoload_with=bind)
    page_versions = sa.Table("structure_page_versions", metadata, autoload_with=bind)
    post_publications = sa.Table("organization_post_publications", metadata, autoload_with=bind)

    permission_sets = {
        "Owner": ("PRIVATE", ["structure.read","structure.manage","structure.admin","ownership.transfer","members.view","members.manage","roles.manage","visibility.manage","events.view","events.manage","events.publish","stats.view","accounting.view","accounting.manage","accounting.unlock","channels.read","channels.post","channels.manage","documents.view","documents.download","documents.manage","albums.view","albums.manage","folklore.view","folklore.manage","publications.manage","audit.view","search.view"]),
        "Bureau": ("BUREAU", ["structure.read","structure.manage","members.view","members.manage","roles.manage","visibility.manage","events.view","events.manage","events.publish","stats.view","channels.read","channels.post","channels.manage","documents.view","documents.download","documents.manage","albums.view","albums.manage","folklore.view","folklore.manage","publications.manage","audit.view","search.view"]),
        "Trésorerie": ("TREASURY", ["structure.read","members.view","events.view","stats.view","accounting.view","accounting.manage","channels.read","channels.post","documents.view","documents.download","albums.view","folklore.view","audit.view","search.view"]),
        "Staff": ("STAFF", ["structure.read","members.view","events.view","stats.view","channels.read","channels.post","documents.view","documents.download","albums.view","folklore.view","search.view"]),
        "Membre": ("MEMBERS", ["structure.read","members.view","events.view","channels.read","channels.post","documents.view","documents.download","albums.view","folklore.view","search.view"]),
    }
    role_aliases = {"OWNER":"Owner","ADMIN":"Bureau","PRESIDENT":"Bureau","VICE_PRESIDENT":"Bureau","BUREAU":"Bureau","SECRETARY":"Bureau","MANAGER":"Bureau","TREASURER":"Trésorerie","TRESORIER":"Trésorerie","STAFF":"Staff","COMMUNICATION":"Staff","ARCHIVIST":"Staff","MEMBER":"Membre"}
    defaults = {"presentation":"PUBLIC","events":"PUBLIC","members":"PUBLIC","albums":"PUBLIC","folklore":"PUBLIC","contact":"PUBLIC","publications":"PUBLIC","documents":"MEMBERS","stats":"PRIVATE"}

    org_rows = bind.execute(sa.text("SELECT id, created_by_user_id, visibility, visibility_settings_json FROM organizations")).mappings().all()
    for org in org_rows:
        owner = bind.execute(sa.text("SELECT user_id FROM organization_memberships WHERE organization_id=:oid AND status='ACTIVE' AND revoked_at IS NULL AND role='OWNER' ORDER BY id LIMIT 1"), {"oid": org["id"]}).scalar()
        owner = owner or org["created_by_user_id"]
        if not owner:
            continue
        bind.execute(governance.insert().values(organization_id=org["id"], owner_user_id=owner, status="ACTIVE", created_at=stamp, updated_at=stamp))
        is_public = str(org["visibility"] or "PRIVATE").upper() == "PUBLIC"
        bind.execute(public_pages.insert().values(organization_id=org["id"], status="PUBLISHED" if is_public else "DRAFT", seo_enabled=True, indexable=True, published_at=stamp if is_public else None, created_at=stamp, updated_at=stamp))
        role_ids = {}
        for name, (audience, permissions) in permission_sets.items():
            result = bind.execute(roles.insert().values(organization_id=org["id"], name=name, system_role=True, audience_level=audience, permissions_json=permissions, created_by_user_id=owner, created_at=stamp, updated_at=stamp))
            role_ids[name] = result.inserted_primary_key[0]
        members = bind.execute(sa.text("SELECT id, user_id, role FROM organization_memberships WHERE organization_id=:oid"), {"oid": org["id"]}).mappings().all()
        for member in members:
            role_name = "Owner" if member["user_id"] == owner else role_aliases.get(str(member["role"] or "MEMBER").upper(), "Membre")
            bind.execute(assignments.insert().values(organization_id=org["id"], membership_id=member["id"], role_id=role_ids[role_name], assigned_by_user_id=owner, created_at=stamp, updated_at=stamp))
        legacy = org["visibility_settings_json"] if isinstance(org["visibility_settings_json"], dict) else {}
        legacy_map = {"description":"presentation","events":"events","members":"members","albums":"albums","folklore":"folklore","contact":"contact","documents":"documents","stats":"stats"}
        aliases = {"TORE_USERS":"TORE","STRUCTURE_MEMBERS":"MEMBERS","OFFICE":"BUREAU","ADMINS":"PRIVATE"}
        for section, default in defaults.items():
            legacy_key = next((k for k, v in legacy_map.items() if v == section), None)
            raw = str(legacy.get(legacy_key, default)).upper() if legacy_key else default
            level = aliases.get(raw, raw)
            if level not in {"PUBLIC","TORE","MEMBERS","STAFF","BUREAU","TREASURY","PRIVATE"}:
                level = default
            bind.execute(visibility.insert().values(organization_id=org["id"], resource_type=section, resource_id="__section__", level=level, updated_by_user_id=owner, created_at=stamp, updated_at=stamp))

    event_rows = bind.execute(sa.text("SELECT id, host_id, publication_status FROM events WHERE host_type='orga' AND host_id IS NOT NULL")).mappings().all()
    valid_org_ids = {row["id"] for row in org_rows}
    for event in event_rows:
        try:
            oid = int(event["host_id"])
        except (TypeError, ValueError):
            continue
        if oid not in valid_org_ids:
            continue
        bind.execute(event_structures.insert().values(event_id=event["id"], organization_id=oid, role="HOST", created_at=stamp))
        bind.execute(lifecycles.insert().values(event_id=event["id"], organization_id=oid, status="PUBLISHED" if str(event["publication_status"] or "DRAFT").upper() == "PUBLISHED" else "DRAFT", updated_by_user_id=None, created_at=stamp, updated_at=stamp))

    for page in bind.execute(sa.text("SELECT id, organization_id, version, title, content, category, visibility, created_by_user_id, created_at FROM structure_pages")).mappings().all():
        bind.execute(page_versions.insert().values(organization_id=page["organization_id"], page_id=page["id"], version_number=page["version"] or 1, title=page["title"], content=page["content"] or "", category=page["category"] or "OTHER", visibility=page["visibility"] or "MEMBERS", created_by_user_id=page["created_by_user_id"], created_at=page["created_at"] or stamp))

    for post in bind.execute(sa.text("SELECT id, organization_id, created_at FROM organization_posts WHERE deleted_at IS NULL")).mappings().all():
        bind.execute(post_publications.insert().values(organization_id=post["organization_id"], post_id=post["id"], title="", status="PUBLISHED", visibility="PUBLIC", publish_at=post["created_at"], published_at=post["created_at"], updated_at=post["created_at"] or stamp))


def downgrade() -> None:
    for table in [
        "structure_audit_contexts",
        "organization_post_publications",
        "structure_page_versions",
        "structure_album_media_links",
        "structure_media_assets",
        "structure_document_versions",
        "structure_accounting_entries",
        "event_public_summaries",
        "forum_event_lifecycle",
        "event_structures",
        "structure_visibility_policies",
        "structure_claims",
        "structure_invitations",
        "structure_role_assignments",
        "structure_roles",
        "structure_public_pages",
        "structure_governance",
    ]:
        if table in _tables():
            op.drop_table(table)
