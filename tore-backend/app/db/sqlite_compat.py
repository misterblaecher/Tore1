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
        if "status" not in battle_cols:
            conn.execute(text("ALTER TABLE battles ADD COLUMN status VARCHAR(16) DEFAULT 'OPEN'"))
        if "joined_at" not in participant_cols:
            conn.execute(text("ALTER TABLE battle_participants ADD COLUMN joined_at DATETIME"))


def ensure_sqlite_compat(engine: Engine) -> None:
    ensure_battles_tables(engine)
    ensure_order_items_market_item_id(engine)
    ensure_entry_token_columns(engine)
    ensure_audit_log_indexes(engine)
    ensure_event_module_columns(engine)
    ensure_p3_tables(engine)


def ensure_order_items_market_item_id(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    order_item_cols = _table_columns(engine, "order_items")
    with engine.begin() as conn:
        if "market_item_id" not in order_item_cols:
            conn.execute(text("ALTER TABLE order_items ADD COLUMN market_item_id INTEGER"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_order_items_market_item_id ON order_items (market_item_id)"))


def ensure_entry_token_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    scan_cols = _table_columns(engine, "entry_scan_logs")
    with engine.begin() as conn:
        if "token_id" not in scan_cols:
            conn.execute(text("ALTER TABLE entry_scan_logs ADD COLUMN token_id INTEGER"))
        if "token_hash" not in scan_cols:
            conn.execute(text("ALTER TABLE entry_scan_logs ADD COLUMN token_hash VARCHAR(64)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_entry_scan_logs_token_id ON entry_scan_logs (token_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_entry_scan_logs_token_hash ON entry_scan_logs (token_hash)"))


def ensure_audit_log_indexes(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_event_id ON audit_logs (event_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_bar_id ON audit_logs (bar_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action)"))


def ensure_event_module_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    cols = _table_columns(engine, "event_module_configs")
    with engine.begin() as conn:
        if "checkins_enabled" not in cols:
            conn.execute(text("ALTER TABLE event_module_configs ADD COLUMN checkins_enabled BOOLEAN DEFAULT 0"))
        if "wifi_enabled" not in cols:
            conn.execute(text("ALTER TABLE event_module_configs ADD COLUMN wifi_enabled BOOLEAN DEFAULT 0"))
        if "safety_enabled" not in cols:
            conn.execute(text("ALTER TABLE event_module_configs ADD COLUMN safety_enabled BOOLEAN DEFAULT 0"))


def ensure_p3_tables(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS battle_submits (
                id INTEGER NOT NULL PRIMARY KEY,
                battle_id INTEGER NOT NULL,
                actor_user_id VARCHAR NOT NULL,
                scan_id VARCHAR(120) NOT NULL,
                target_user_id VARCHAR,
                points INTEGER DEFAULT 1 NOT NULL,
                validated_at DATETIME,
                validated_by_partner_id INTEGER,
                created_at DATETIME,
                CONSTRAINT uq_battle_submit_scan UNIQUE (battle_id, scan_id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_battle_submits_battle_id ON battle_submits (battle_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_battle_submits_actor_user_id ON battle_submits (actor_user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_battle_submits_created_at ON battle_submits (created_at)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS drink_checkins (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                drink_id INTEGER,
                name_snapshot VARCHAR(180) NOT NULL,
                rating INTEGER,
                comment TEXT,
                event_id INTEGER,
                bar_id INTEGER,
                ts DATETIME
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_drink_checkins_user_ts ON drink_checkins (user_id, ts DESC, id DESC)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_drink_checkins_event_ts ON drink_checkins (event_id, ts DESC, id DESC)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_drink_checkins_drink_ts ON drink_checkins (drink_id, ts DESC, id DESC)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS wifi_configs (
                id INTEGER NOT NULL PRIMARY KEY,
                bar_id INTEGER NOT NULL,
                event_id INTEGER,
                ssid VARCHAR(120) NOT NULL,
                password_enc TEXT NOT NULL,
                note TEXT,
                created_by INTEGER NOT NULL,
                updated_by INTEGER NOT NULL,
                updated_at DATETIME,
                created_at DATETIME,
                CONSTRAINT uq_wifi_scope UNIQUE (bar_id, event_id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_wifi_configs_bar_id ON wifi_configs (bar_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_wifi_configs_event_id ON wifi_configs (event_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS safety_buddy_sessions (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER,
                user_id VARCHAR NOT NULL,
                buddy_user_id VARCHAR NOT NULL,
                status VARCHAR(16) NOT NULL,
                started_at DATETIME,
                expires_at DATETIME,
                ended_at DATETIME
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_safety_buddy_sessions_user ON safety_buddy_sessions (user_id, status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_safety_buddy_sessions_event ON safety_buddy_sessions (event_id, status)"))
