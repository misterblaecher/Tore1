from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text


def _config(database: Path, monkeypatch) -> tuple[Config, str]:
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config, database_url


def test_operational_access_migration_fresh_database(tmp_path: Path, monkeypatch):
    config, url = _config(tmp_path / "fresh-v4.db", monkeypatch)
    command.upgrade(config, "head")
    db_engine = create_engine(url)
    invite_columns = {column["name"] for column in inspect(db_engine).get_columns("event_staff_invite_codes")}
    access_columns = {column["name"] for column in inspect(db_engine).get_columns("partner_bar_access")}
    assert {"token_hash", "target_user_id", "actions_json", "max_uses", "used_count", "accepted_at"} <= invite_columns
    assert {"status", "actions_json", "starts_at", "expires_at", "source", "revoked_at"} <= access_columns
    with db_engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == ScriptDirectory.from_config(config).get_current_head()


def test_upgrade_from_0008_preserves_legacy_rows(tmp_path: Path, monkeypatch):
    config, url = _config(tmp_path / "from-v3.db", monkeypatch)
    command.upgrade(config, "0008_unified_profile_affiliations")
    db_engine = create_engine(url)
    with db_engine.begin() as connection:
        connection.execute(text("INSERT INTO bars (name, city, partner_code, partner_status, public_visibility, public_modules) VALUES ('Legacy', 'Paris', 'LEGACYV4', 'ACTIVE', 'PUBLIC', '{}')"))
        connection.execute(text("INSERT INTO partner_users (display_name, pin_hash, is_active, created_at) VALUES ('Legacy', 'hash', 1, CURRENT_TIMESTAMP)"))
        bar_id = connection.execute(text("SELECT id FROM bars WHERE partner_code='LEGACYV4'")).scalar_one()
        partner_id = connection.execute(text("SELECT id FROM partner_users WHERE display_name='Legacy'")).scalar_one()
        connection.execute(text(
            "INSERT INTO partner_bar_access "
            "(partner_user_id, bar_id, role, is_active, status, actions_json, source, created_at, updated_at) "
            "VALUES (:partner, :bar, 'manager', 1, 'ACTIVE', '[]', 'PARTNER_ADMIN', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ), {"partner": partner_id, "bar": bar_id})

    command.upgrade(config, "head")
    with db_engine.connect() as connection:
        row = connection.execute(text("SELECT status, source FROM partner_bar_access WHERE partner_user_id=:partner"), {"partner": partner_id}).one()
        assert row == ("ACTIVE", "PARTNER_ADMIN")


def test_downgrade_to_0008_is_supported(tmp_path: Path, monkeypatch):
    config, url = _config(tmp_path / "rollback-v4.db", monkeypatch)
    command.upgrade(config, "head")
    command.downgrade(config, "0008_unified_profile_affiliations")
    db_engine = create_engine(url)
    assert "token_hash" not in {column["name"] for column in inspect(db_engine).get_columns("event_staff_invite_codes")}
    assert "status" not in {column["name"] for column in inspect(db_engine).get_columns("partner_bar_access")}
    with db_engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0008_unified_profile_affiliations"
