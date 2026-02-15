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
    ensure_identity_consent_columns(engine)
    ensure_order_client_qr_scan_table(engine)
    ensure_orders_zone_id(engine)
    ensure_event_join_tables(engine)
    ensure_event_wizard_tables(engine)
    ensure_staff_management_tables(engine)
    ensure_broadcast_tables(engine)
    ensure_incidents_tables(engine)
    ensure_profitability_tables(engine)


def ensure_profitability_tables(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_costs_simple (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                costs_tickets INTEGER DEFAULT 0 NOT NULL,
                breakdown_json JSON,
                notes TEXT,
                updated_by INTEGER,
                updated_at DATETIME,
                CONSTRAINT uq_event_costs_simple_event UNIQUE (event_id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_costs_simple_event_id ON event_costs_simple (event_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_costs_simple_updated_at ON event_costs_simple (updated_at)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_costs_simple_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                idempotency_key VARCHAR(120) NOT NULL,
                response_json JSON,
                created_at DATETIME,
                CONSTRAINT uq_event_costs_simple_idem UNIQUE (event_id, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_costs_simple_idempotency_event_id ON event_costs_simple_idempotency (event_id)"))


def ensure_identity_consent_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bar_privacy_settings (
                id INTEGER NOT NULL PRIMARY KEY,
                bar_id INTEGER NOT NULL,
                staff_identity_consent_required BOOLEAN DEFAULT 0,
                updated_at DATETIME,
                CONSTRAINT uq_bar_privacy_settings_bar UNIQUE (bar_id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_bar_privacy_settings_bar_id ON bar_privacy_settings (bar_id)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS app_user_privacy_settings (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                show_identity_to_staff BOOLEAN DEFAULT 0,
                updated_at DATETIME,
                CONSTRAINT uq_app_user_privacy_settings_user UNIQUE (user_id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_app_user_privacy_settings_user_id ON app_user_privacy_settings (user_id)"))


def ensure_order_client_qr_scan_table(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS order_client_qr_scans (
                id INTEGER NOT NULL PRIMARY KEY,
                bar_id INTEGER NOT NULL,
                order_id INTEGER NOT NULL,
                event_id INTEGER,
                staff_user_id INTEGER,
                idempotency_key VARCHAR(120) NOT NULL,
                scanned_at DATETIME,
                CONSTRAINT uq_order_client_qr_scan_bar_idem UNIQUE (bar_id, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_order_client_qr_scans_bar ON order_client_qr_scans (bar_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_order_client_qr_scans_order ON order_client_qr_scans (order_id)"))


def ensure_order_items_market_item_id(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    order_item_cols = _table_columns(engine, "order_items")
    with engine.begin() as conn:
        if "market_item_id" not in order_item_cols:
            conn.execute(text("ALTER TABLE order_items ADD COLUMN market_item_id INTEGER"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_order_items_market_item_id ON order_items (market_item_id)"))


def ensure_orders_zone_id(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    order_cols = _table_columns(engine, "orders")
    with engine.begin() as conn:
        if "zone_id" not in order_cols:
            conn.execute(text("ALTER TABLE orders ADD COLUMN zone_id INTEGER"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_zone_id ON orders (zone_id)"))


def ensure_event_join_tables(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    event_cols = _table_columns(engine, "events")
    with engine.begin() as conn:
        if "event_code" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN event_code VARCHAR(16)"))
        if "charter_enabled" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN charter_enabled BOOLEAN DEFAULT 0"))
        if "charter_version" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN charter_version VARCHAR(32)"))
        if "charter_text" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN charter_text TEXT"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_events_event_code ON events (event_code)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_joins (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                user_id VARCHAR NOT NULL,
                device_id VARCHAR(120),
                joined_at DATETIME,
                idempotency_key VARCHAR(128),
                accepted_charter_version VARCHAR(32),
                CONSTRAINT uq_event_joins_event_user UNIQUE (event_id, user_id),
                CONSTRAINT uq_event_joins_event_idempotency UNIQUE (event_id, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_joins_event_id ON event_joins (event_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_joins_user_id ON event_joins (user_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_charter_acceptances (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                user_id VARCHAR NOT NULL,
                charter_version VARCHAR(32) NOT NULL,
                accepted_at DATETIME,
                CONSTRAINT uq_event_charter_acceptance UNIQUE (event_id, user_id, charter_version)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_charter_acceptances_event_id ON event_charter_acceptances (event_id)"))

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



def ensure_staff_management_tables(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_staff_assignments (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                role VARCHAR(24) NOT NULL,
                label VARCHAR(120),
                created_by_user_id INTEGER NOT NULL,
                created_at DATETIME,
                revoked_at DATETIME
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_staff_assignments_event_id ON event_staff_assignments (event_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_staff_assignments_role ON event_staff_assignments (role)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_staff_assignment_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                idempotency_key VARCHAR(120) NOT NULL,
                assignment_id INTEGER NOT NULL,
                response_json JSON,
                created_at DATETIME,
                CONSTRAINT uq_event_staff_assignment_idem UNIQUE (event_id, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_staff_assignment_idem_event_id ON event_staff_assignment_idempotency (event_id)"))

    qr_cols = _table_columns(engine, "event_qr_tokens")
    with engine.begin() as conn:
        if "role" not in qr_cols:
            conn.execute(text("ALTER TABLE event_qr_tokens ADD COLUMN role VARCHAR(24)"))
        if "assignment_id" not in qr_cols:
            conn.execute(text("ALTER TABLE event_qr_tokens ADD COLUMN assignment_id INTEGER"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_qr_tokens_role ON event_qr_tokens (role)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_qr_tokens_assignment_id ON event_qr_tokens (assignment_id)"))


def ensure_event_wizard_tables(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    event_cols = _table_columns(engine, "events")
    with engine.begin() as conn:
        if "venue" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN venue VARCHAR(180)"))
        if "timezone" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN timezone VARCHAR(64) DEFAULT 'Europe/Brussels'"))
        if "event_state" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN event_state VARCHAR(24) DEFAULT 'LIVE'"))
        if "modules_on" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN modules_on JSON"))
        if "rules_flags" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN rules_flags JSON"))
        if "created_by" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN created_by VARCHAR(120)"))
        if "last_state_updated_at" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN last_state_updated_at DATETIME"))
        if "last_updated_at" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN last_updated_at DATETIME"))

        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_event_state ON events (event_state)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_create_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                bar_id INTEGER NOT NULL,
                idempotency_key VARCHAR(120) NOT NULL,
                event_id INTEGER NOT NULL,
                created_at DATETIME
            )
        """))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_event_create_idempotency ON event_create_idempotency (bar_id, idempotency_key)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_qr_tokens (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                qr_type VARCHAR(32) NOT NULL,
                token_id VARCHAR(64) NOT NULL,
                nonce VARCHAR(64) NOT NULL,
                payload TEXT NOT NULL,
                signature VARCHAR(128) NOT NULL,
                issued_at DATETIME,
                expires_at DATETIME,
                revoked_at DATETIME,
                created_by_user_id INTEGER
            )
        """))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_event_qr_tokens_token_id ON event_qr_tokens (token_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_qr_tokens_event ON event_qr_tokens (event_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_qr_pack_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                idempotency_key VARCHAR(120) NOT NULL,
                pack_json JSON,
                created_at DATETIME
            )
        """))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_event_qr_pack_idempotency ON event_qr_pack_idempotency (event_id, idempotency_key)"))


def ensure_broadcast_tables(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_broadcasts (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                message VARCHAR(240) NOT NULL,
                level VARCHAR(16) DEFAULT 'info' NOT NULL,
                expires_at DATETIME,
                idempotency_key VARCHAR(120) NOT NULL,
                created_at DATETIME,
                CONSTRAINT uq_event_broadcast_idem UNIQUE (event_id, author_id, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_broadcasts_event_created ON event_broadcasts (event_id, created_at)"))


def ensure_incidents_tables(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_incidents (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                title VARCHAR(180),
                description TEXT NOT NULL DEFAULT '',
                severity VARCHAR(16) NOT NULL DEFAULT 'info',
                status VARCHAR(16) NOT NULL DEFAULT 'open',
                location VARCHAR(180),
                created_by INTEGER NOT NULL,
                assigned_to_staff_assignment_id INTEGER,
                assigned_to_role VARCHAR(24),
                created_at DATETIME,
                updated_at DATETIME
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_incidents_event_id ON event_incidents (event_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_incidents_severity ON event_incidents (severity)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_incidents_status ON event_incidents (status)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_incident_logs (
                id INTEGER NOT NULL PRIMARY KEY,
                incident_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                action_type VARCHAR(24) NOT NULL,
                payload JSON,
                actor_id INTEGER NOT NULL,
                created_at DATETIME
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_incident_logs_incident_id ON event_incident_logs (incident_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_incident_logs_event_id ON event_incident_logs (event_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_incident_logs_action_type ON event_incident_logs (action_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_incident_logs_incident_created ON event_incident_logs (incident_id, created_at)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_incident_create_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                idempotency_key VARCHAR(120) NOT NULL,
                incident_id INTEGER NOT NULL,
                response_json JSON,
                created_at DATETIME,
                CONSTRAINT uq_event_incident_create_idem UNIQUE (event_id, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_incident_create_idem_event_id ON event_incident_create_idempotency (event_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_incident_action_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                incident_id INTEGER NOT NULL,
                action_type VARCHAR(24) NOT NULL,
                idempotency_key VARCHAR(120) NOT NULL,
                response_json JSON,
                created_at DATETIME,
                CONSTRAINT uq_event_incident_action_idem UNIQUE (incident_id, action_type, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_incident_action_idem_incident_id ON event_incident_action_idempotency (incident_id)"))
