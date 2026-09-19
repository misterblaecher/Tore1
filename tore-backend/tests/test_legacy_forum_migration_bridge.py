from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text


ROOT = Path(__file__).resolve().parents[1]


def _config(database: Path, monkeypatch) -> Config:
    url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _version(database: Path) -> str:
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def _head(config: Config) -> str:
    return ScriptDirectory.from_config(config).get_current_head()


def test_empty_database_upgrades_to_single_head(tmp_path, monkeypatch):
    database = tmp_path / "fresh.db"
    config = _config(database, monkeypatch)
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_revision("0014_forum_p1").down_revision == "0013_forum_backend_foundation"
    assert scripts.get_revision("0013_forum_backend_foundation").down_revision == "0012_discussion_workspace"

    command.upgrade(config, "head")

    assert _version(database) == _head(config) == "0029_legacy_workspace_parity"


def test_0024_upgrades_to_head(tmp_path, monkeypatch):
    database = tmp_path / "from_0024.db"
    config = _config(database, monkeypatch)
    command.upgrade(config, "0024_versioned_folklore_pages")
    assert _version(database) == "0024_versioned_folklore_pages"

    command.upgrade(config, "head")

    assert _version(database) == _head(config)
    assert {"structure_planning_items", "structure_planning_assignees"}.issubset(
        inspect(create_engine(f"sqlite:///{database.as_posix()}")).get_table_names()
    )


def test_retired_public_event_revision_upgrades_to_head(tmp_path, monkeypatch):
    database = tmp_path / "retired_public_event_revision.db"
    config = _config(database, monkeypatch)
    command.upgrade(config, "0012_discussion_workspace")

    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS structure_discussion_reactions"))
        connection.execute(text("DROP TABLE IF EXISTS structure_notifications"))
        connection.execute(text("ALTER TABLE structure_discussion_posts DROP COLUMN document_ids"))
        connection.execute(text("ALTER TABLE structure_discussion_posts DROP COLUMN parent_id"))
        connection.execute(text("DELETE FROM alembic_version"))
        connection.execute(
            text("INSERT INTO alembic_version(version_num) VALUES ('0013_public_event_recap')")
        )

    command.upgrade(config, "head")

    assert _version(database) == _head(config)
    assert "forum_event_pages" in inspect(engine).get_table_names()
    assert "structure_discussion_reactions" in inspect(engine).get_table_names()
    assert "structure_notifications" in inspect(engine).get_table_names()
    assert {"parent_id", "document_ids"}.issubset(
        {column["name"] for column in inspect(engine).get_columns("structure_discussion_posts")}
    )


def _replace_with_representative_legacy_schema(database: Path) -> None:
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        for table in (
            "structure_membership_roles",
            "structure_role_capabilities",
            "structure_capabilities",
            "structure_invitations",
            "structure_claims",
            "event_structures",
            "structure_roles",
        ):
            connection.execute(text(f'DROP TABLE IF EXISTS "{table}"'))

        connection.execute(text("""
            CREATE TABLE structure_roles (
                id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, name VARCHAR(80) NOT NULL,
                system_role BOOLEAN NOT NULL DEFAULT 0, audience_level VARCHAR(16) NOT NULL DEFAULT 'MEMBERS',
                permissions_json JSON NOT NULL DEFAULT '[]', created_by_user_id VARCHAR,
                created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE structure_role_assignments (
                id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, membership_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL, assigned_by_user_id VARCHAR, created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE structure_claims (
                id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, requested_by_user_id VARCHAR NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'PENDING', reason TEXT, created_at DATETIME NOT NULL,
                reviewed_at DATETIME, reviewed_by_user_id VARCHAR
            )
        """))
        connection.execute(text("""
            CREATE TABLE structure_invitations (
                id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, email VARCHAR(255) NOT NULL,
                role_id INTEGER NOT NULL, token_hash VARCHAR(64) NOT NULL, expires_at DATETIME NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'PENDING', invited_by_user_id VARCHAR NOT NULL,
                created_at DATETIME NOT NULL, accepted_at DATETIME, accepted_by_user_id VARCHAR
            )
        """))
        connection.execute(text("""
            CREATE TABLE event_structures (
                id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, organization_id INTEGER NOT NULL,
                role VARCHAR(16) NOT NULL DEFAULT 'HOST', created_at DATETIME NOT NULL
            )
        """))
        connection.execute(text("""
            INSERT INTO structure_roles
            VALUES (701, 41, 'Bureau legacy', 1, 'BUREAU',
                    '["structure.read","members.manage","events.publish","accounting.manage"]',
                    'legacy-owner', '2026-01-01', '2026-01-02')
        """))
        connection.execute(text("""
            INSERT INTO structure_role_assignments
            VALUES (702, 41, 703, 701, 'legacy-owner', '2026-01-03', '2026-01-03')
        """))
        connection.execute(text("""
            INSERT INTO structure_claims
            VALUES (704, 41, 'claimant', 'APPROVED', 'historical proof', '2026-01-04', '2026-01-05', 'reviewer')
        """))
        connection.execute(text("""
            INSERT INTO structure_invitations
            VALUES (705, 41, 'legacy@example.test', 701, 'legacy-token', '2027-01-01',
                    'ACCEPTED', 'legacy-owner', '2026-01-06', '2026-01-07', 'invitee')
        """))
        connection.execute(text("""
            INSERT INTO event_structures VALUES (706, 81, 41, 'HOST', '2026-01-08')
        """))
        connection.execute(text("DELETE FROM alembic_version"))
        connection.execute(text("INSERT INTO alembic_version(version_num) VALUES ('0014_forum_p1')"))


def _schema_signature(database: Path, tables: set[str]) -> dict[str, dict]:
    inspector = inspect(create_engine(f"sqlite:///{database.as_posix()}"))
    return {
        table: {
            "columns": {
                column["name"]: (str(column["type"]), column["nullable"], column.get("primary_key", 0))
                for column in inspector.get_columns(table)
            },
            "foreign_keys": sorted(
                (
                    tuple(item["constrained_columns"]),
                    item["referred_table"],
                    tuple(item["referred_columns"]),
                    item.get("options", {}).get("ondelete"),
                )
                for item in inspector.get_foreign_keys(table)
            ),
            "uniques": sorted({
                tuple(item["column_names"])
                for item in inspector.get_unique_constraints(table)
            } | {
                tuple(item["column_names"])
                for item in inspector.get_indexes(table)
                if item["unique"]
            }),
            "indexes": sorted(
                (tuple(item["column_names"]), bool(item["unique"]))
                for item in inspector.get_indexes(table)
            ),
        }
        for table in tables
    }


def test_representative_legacy_0014_upgrades_without_data_loss(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy.db"
    config = _config(legacy, monkeypatch)
    command.upgrade(config, "0012_discussion_workspace")
    _replace_with_representative_legacy_schema(legacy)

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{legacy.as_posix()}")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM legacy_forum_structure_roles")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM legacy_forum_structure_role_assignments")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM legacy_forum_structure_claims")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM legacy_forum_structure_invitations")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM legacy_forum_event_structures")).scalar_one() == 1
        assert connection.execute(text("SELECT name FROM structure_roles WHERE id=701")).scalar_one() == "Bureau legacy"
        assert connection.execute(text("SELECT COUNT(*) FROM structure_membership_roles WHERE role_id=701")).scalar_one() == 1
        assert connection.execute(text("SELECT status FROM structure_claims WHERE id=704")).scalar_one() == "APPROVED"
        assert connection.execute(text("SELECT accepted_at FROM structure_invitations WHERE id=705")).scalar_one() is not None
        assert connection.execute(text("SELECT role FROM event_structures WHERE id=706")).scalar_one() == "OWNER"
        mapped = set(connection.execute(text("""
            SELECT c.key FROM structure_capabilities c
            JOIN structure_role_capabilities rc ON rc.capability_id=c.id
            WHERE rc.role_id=701
        """)).scalars())
        assert {"structure.read", "member.manage", "event.publish", "finance.write"}.issubset(mapped)

    fresh = tmp_path / "comparison.db"
    fresh_config = _config(fresh, monkeypatch)
    command.upgrade(fresh_config, "head")
    functional_tables = {
        "organization_lifecycle_states", "structure_capabilities", "structure_roles",
        "structure_role_capabilities", "structure_membership_roles", "stored_files",
        "structure_claims", "structure_invitations", "structure_channel_acls",
        "structure_channel_acl_grants", "structure_ownership", "structure_ownership_transfers",
        "structure_recovery_requests", "event_structures", "event_manager_settings",
        "forum_event_pages", "structure_budgets", "accounting_entries",
        "structure_page_revisions", "structure_planning_items", "structure_planning_assignees",
        "structure_notifications",
    }
    legacy_schema = _schema_signature(legacy, functional_tables)
    fresh_schema = _schema_signature(fresh, functional_tables)
    for table in functional_tables:
        assert legacy_schema[table]["columns"] == fresh_schema[table]["columns"]
        assert legacy_schema[table]["foreign_keys"] == fresh_schema[table]["foreign_keys"]
        assert legacy_schema[table]["uniques"] == fresh_schema[table]["uniques"]
        # Retained compatibility indexes are allowed; every canonical fresh
        # index must still be present on the upgraded legacy schema.
        assert set(fresh_schema[table]["indexes"]).issubset(legacy_schema[table]["indexes"])


def test_orm_create_all_bootstrap_and_repeated_upgrade_are_idempotent(tmp_path, monkeypatch):
    database = tmp_path / "orm_bootstrap.db"
    config = _config(database, monkeypatch)
    from db import Base
    import models  # noqa: F401

    engine = create_engine(f"sqlite:///{database.as_posix()}")
    Base.metadata.create_all(engine)
    command.upgrade(config, "head")
    before = set(inspect(engine).get_table_names())

    command.upgrade(config, "head")

    assert _version(database) == _head(config)
    assert set(inspect(engine).get_table_names()) == before
