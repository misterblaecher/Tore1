from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _config(database: Path, monkeypatch) -> tuple[Config, str]:
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config, database_url


def test_unified_profile_migration_fresh_database(tmp_path: Path, monkeypatch):
    config, url = _config(tmp_path / "fresh.db", monkeypatch)
    command.upgrade(config, "head")
    engine = create_engine(url)
    assert "username" in {column["name"] for column in inspect(engine).get_columns("app_users")}
    assert "event_history_opt_in" in {
        column["name"] for column in inspect(engine).get_columns("app_user_privacy_settings")
    }
    assert "validation_source" in {
        column["name"] for column in inspect(engine).get_columns("organization_memberships")
    }
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0009_scoped_operational_access"


def test_upgrade_from_0007_keeps_legacy_private_and_unknown_visibility_private(tmp_path: Path, monkeypatch):
    config, url = _config(tmp_path / "from-0007.db", monkeypatch)
    command.upgrade(config, "0007_public_content_branding")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO app_users (id, created_at, updated_at, display_name, profile_visibility, account_mode, "
            "show_address, show_avatar, is_deleted, account_status, global_role, is_guest) "
            "VALUES ('legacy-user', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'Legacy', 'PUBLIC', 'organizer', "
            "0, 1, 0, 'ACTIVE', 'USER', 0)"
        ))
        connection.execute(text(
            "INSERT INTO app_user_privacy_settings (user_id, visibility, show_identity_to_staff, show_identity_in_bar, updated_at, "
            "photo_visibility, bio_visibility, affiliations_visibility, badges_visibility, event_history_visibility, "
            "participations_visibility, gamification_visibility, event_history_opt_in, participations_opt_in, gamification_opt_in) "
            "VALUES ('legacy-user', 'mystery', 0, 0, CURRENT_TIMESTAMP, 'PRIVATE', 'PRIVATE', 'PRIVATE', 'PRIVATE', "
            "'PRIVATE', 'PRIVATE', 'PRIVATE', 0, 0, 0)"
        ))
        connection.execute(text(
            "INSERT INTO organizations (name, slug, visibility, join_mode, created_by_user_id, created_at) "
            "VALUES ('Legacy Org', 'legacy-org', 'PUBLIC', 'OPEN_MEMBERSHIP', 'legacy-user', CURRENT_TIMESTAMP)"
        ))
        org_id = connection.execute(text("SELECT id FROM organizations WHERE slug='legacy-org'")).scalar_one()
        connection.execute(text(
            "INSERT INTO organization_memberships (organization_id, user_id, role, status, joined_at, updated_at, created_at, "
            "created_by_user_id, visibility, validation_source, metadata_json) "
            "VALUES (:org, 'legacy-user', 'free text president', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, "
            "'legacy-user', 'PRIVATE', 'LEGACY', '{}')"
        ), {"org": org_id})

    command.upgrade(config, "head")
    with engine.connect() as connection:
        user = connection.execute(text(
            "SELECT profile_visibility, global_role, account_mode FROM app_users WHERE id='legacy-user'"
        )).one()
        privacy = connection.execute(text(
            "SELECT visibility, event_history_opt_in FROM app_user_privacy_settings WHERE user_id='legacy-user'"
        )).one()
        membership = connection.execute(text(
            "SELECT role, visibility, validation_source FROM organization_memberships WHERE user_id='legacy-user'"
        )).one()
    assert user == ("PRIVATE", "USER", "organizer")
    assert privacy == ("PRIVATE", 0)
    assert membership == ("free text president", "PRIVATE", "LEGACY")


def test_downgrade_to_0007_is_supported(tmp_path: Path, monkeypatch):
    config, url = _config(tmp_path / "rollback.db", monkeypatch)
    command.upgrade(config, "head")
    command.downgrade(config, "0007_public_content_branding")
    engine = create_engine(url)
    assert "username" not in {column["name"] for column in inspect(engine).get_columns("app_users")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0007_public_content_branding"
