from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_public_content_migration_preserves_legacy_rows(tmp_path: Path, monkeypatch):
    database = tmp_path / "legacy.db"
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE bars (id INTEGER PRIMARY KEY, name VARCHAR, city VARCHAR, partner_code VARCHAR(16))"))
        connection.execute(text("CREATE TABLE events (id INTEGER PRIMARY KEY, bar_id INTEGER, name VARCHAR)"))
        connection.execute(
            text("INSERT INTO bars (name, city, partner_code) VALUES ('Legacy Bar', 'Liège', 'LEGACY01')")
        )
        bar_id = connection.execute(text("SELECT id FROM bars WHERE partner_code='LEGACY01'")).scalar_one()
        connection.execute(
            text("INSERT INTO events (bar_id, name) VALUES (:bar_id, 'Legacy Event')"),
            {"bar_id": bar_id},
        )

    command.stamp(config, "0006_music_committee_v1_tables")
    command.upgrade(config, "head")
    columns = {column["name"] for column in inspect(engine).get_columns("events")}
    assert {"banner_url", "capacity", "currency", "access_type"}.issubset(columns)
    with engine.connect() as connection:
        legacy = connection.execute(
            text("SELECT name, currency, banner_url FROM events WHERE name='Legacy Event'")
        ).one()
        bar = connection.execute(
            text("SELECT name, partner_status, public_visibility FROM bars WHERE partner_code='LEGACY01'")
        ).one()
    assert legacy == ("Legacy Event", "EUR", None)
    assert bar == ("Legacy Bar", "ACTIVE", "PUBLIC")
