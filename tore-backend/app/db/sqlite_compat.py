from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _table_columns(engine: Engine, table_name: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def ensure_battles_tables(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS battles (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER,
                title VARCHAR DEFAULT 'Battle' NOT NULL,
                mode VARCHAR DEFAULT '1v1' NOT NULL,
                join_code VARCHAR NOT NULL,
                created_at DATETIME,
                ended BOOLEAN DEFAULT 0 NOT NULL,
                winner_user_id VARCHAR,
                created_by_user_id VARCHAR,
                ended_at DATETIME
            )
        """))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_battles_join_code ON battles (join_code)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_battles_event_id ON battles (event_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS battle_participants (
                id INTEGER NOT NULL PRIMARY KEY,
                battle_id INTEGER NOT NULL,
                user_id VARCHAR NOT NULL,
                display_name VARCHAR DEFAULT '' NOT NULL,
                wins INTEGER DEFAULT 0 NOT NULL,
                losses INTEGER DEFAULT 0 NOT NULL,
                joined_at DATETIME,
                FOREIGN KEY(battle_id) REFERENCES battles (id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_battle_participants_battle_id ON battle_participants (battle_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_battle_participants_user_id ON battle_participants (user_id)"))

    battle_cols = _table_columns(engine, "battles")
    participant_cols = _table_columns(engine, "battle_participants")

    with engine.begin() as conn:
        if "created_by_user_id" not in battle_cols:
            conn.execute(text("ALTER TABLE battles ADD COLUMN created_by_user_id VARCHAR"))
        if "ended_at" not in battle_cols:
            conn.execute(text("ALTER TABLE battles ADD COLUMN ended_at DATETIME"))
        if "joined_at" not in participant_cols:
            conn.execute(text("ALTER TABLE battle_participants ADD COLUMN joined_at DATETIME"))


def ensure_sqlite_compat(engine: Engine) -> None:
    ensure_battles_tables(engine)
