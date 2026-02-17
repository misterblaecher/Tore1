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




def ensure_event_battles_v1_tables(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_battle_rounds (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                title VARCHAR(180) DEFAULT '' NOT NULL,
                kind VARCHAR(24) DEFAULT 'PARTICIPATION' NOT NULL,
                optionA_label VARCHAR(120),
                optionB_label VARCHAR(120),
                status VARCHAR(16) DEFAULT 'IDLE' NOT NULL,
                starts_at DATETIME,
                ends_at DATETIME,
                locked_at DATETIME,
                created_by VARCHAR(120) DEFAULT '' NOT NULL,
                created_at DATETIME,
                winner VARCHAR(12) DEFAULT 'NONE' NOT NULL,
                winner_count_a INTEGER DEFAULT 0 NOT NULL,
                winner_count_b INTEGER DEFAULT 0 NOT NULL
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_battle_rounds_event_id ON event_battle_rounds (event_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_battle_rounds_status ON event_battle_rounds (status)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_battle_votes (
                id INTEGER NOT NULL PRIMARY KEY,
                round_id INTEGER NOT NULL,
                user_id VARCHAR NOT NULL,
                choice VARCHAR(16) DEFAULT 'PARTICIPATE' NOT NULL,
                created_at DATETIME,
                CONSTRAINT uq_event_battle_vote_round_user UNIQUE (round_id, user_id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_battle_votes_round_id ON event_battle_votes (round_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_battle_votes_user_id ON event_battle_votes (user_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_battle_scores (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                user_id VARCHAR NOT NULL,
                score INTEGER DEFAULT 0 NOT NULL,
                last_updated_at DATETIME,
                CONSTRAINT uq_event_battle_score_event_user UNIQUE (event_id, user_id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_battle_scores_event_id ON event_battle_scores (event_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_battle_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                action_type VARCHAR(32) NOT NULL,
                actor_id VARCHAR(120) NOT NULL,
                idempotency_key VARCHAR(120) NOT NULL,
                response_json JSON,
                created_at DATETIME,
                CONSTRAINT uq_event_battle_idem UNIQUE (event_id, action_type, actor_id, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_battle_idempotency_event_id ON event_battle_idempotency (event_id)"))

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
    ensure_menu_admin_columns(engine)
    ensure_event_battles_v1_tables(engine)
    ensure_event_safety_v1_tables(engine)
    ensure_organization_tables(engine)
    ensure_auth_tables(engine)


def ensure_auth_tables(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS auth_magic_links (
                id INTEGER NOT NULL PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                token_hash VARCHAR(64) NOT NULL,
                expires_at DATETIME NOT NULL,
                used_at DATETIME,
                request_ip VARCHAR(64),
                request_device VARCHAR(180),
                created_at DATETIME
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_magic_links_email ON auth_magic_links (email)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_magic_links_token_hash ON auth_magic_links (token_hash)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_magic_links_expires_at ON auth_magic_links (expires_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_magic_links_used_at ON auth_magic_links (used_at)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                token_hash VARCHAR(64) NOT NULL,
                expires_at DATETIME NOT NULL,
                revoked_at DATETIME,
                created_at DATETIME,
                CONSTRAINT uq_refresh_tokens_token_hash UNIQUE (token_hash)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_expires_at ON refresh_tokens (expires_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_revoked_at ON refresh_tokens (revoked_at)"))


def ensure_organization_tables(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER NOT NULL PRIMARY KEY,
                name VARCHAR(140) NOT NULL,
                slug VARCHAR(160) NOT NULL,
                description TEXT,
                city VARCHAR(120),
                org_type VARCHAR(64),
                website_url VARCHAR(255),
                instagram_handle VARCHAR(64),
                visibility VARCHAR(16) DEFAULT 'PUBLIC' NOT NULL,
                created_by_user_id VARCHAR NOT NULL,
                created_at DATETIME,
                CONSTRAINT uq_organizations_slug UNIQUE (slug)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organizations_name ON organizations (name)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organizations_city_type ON organizations (city, org_type)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS organization_memberships (
                id INTEGER NOT NULL PRIMARY KEY,
                organization_id INTEGER NOT NULL,
                user_id VARCHAR NOT NULL,
                role VARCHAR(16) DEFAULT 'MEMBER' NOT NULL,
                status VARCHAR(16) DEFAULT 'ACTIVE' NOT NULL,
                joined_at DATETIME,
                updated_at DATETIME,
                created_at DATETIME,
                created_by_user_id VARCHAR NOT NULL,
                CONSTRAINT uq_organization_memberships_org_user UNIQUE (organization_id, user_id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organization_memberships_user_role ON organization_memberships (user_id, role)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organization_memberships_org ON organization_memberships (organization_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS organization_invite_codes (
                id INTEGER NOT NULL PRIMARY KEY,
                organization_id INTEGER NOT NULL,
                code VARCHAR(16) NOT NULL,
                role VARCHAR(16) DEFAULT 'MEMBER' NOT NULL,
                max_uses INTEGER DEFAULT 100 NOT NULL,
                used_count INTEGER DEFAULT 0 NOT NULL,
                expires_at DATETIME,
                created_by_user_id VARCHAR NOT NULL,
                created_at DATETIME,
                CONSTRAINT uq_organization_invite_codes_code UNIQUE (code)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organization_invite_codes_org_expires ON organization_invite_codes (organization_id, expires_at)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS organization_write_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                actor_user_id VARCHAR NOT NULL,
                action VARCHAR(48) NOT NULL,
                idempotency_key VARCHAR(120) NOT NULL,
                response_json JSON,
                created_at DATETIME,
                CONSTRAINT uq_organization_write_idem UNIQUE (actor_user_id, action, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organization_write_idem_actor ON organization_write_idempotency (actor_user_id)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS organization_posts (
                id INTEGER NOT NULL PRIMARY KEY,
                organization_id INTEGER NOT NULL,
                author_user_id VARCHAR NOT NULL,
                text TEXT NOT NULL,
                image_url VARCHAR(512),
                pinned BOOLEAN DEFAULT 0 NOT NULL,
                deleted_at DATETIME,
                created_at DATETIME
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organization_posts_feed ON organization_posts (organization_id, deleted_at, pinned, created_at)"))



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
        cols = _table_columns(engine, "app_user_privacy_settings")
        if "visibility" not in cols:
            conn.execute(text("ALTER TABLE app_user_privacy_settings ADD COLUMN visibility VARCHAR(16) DEFAULT 'public'"))
        if "show_identity_in_bar" not in cols:
            conn.execute(text("ALTER TABLE app_user_privacy_settings ADD COLUMN show_identity_in_bar BOOLEAN DEFAULT 0"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ticket_transfers (
                id INTEGER NOT NULL PRIMARY KEY,
                from_user_id VARCHAR NOT NULL,
                to_user_id VARCHAR NOT NULL,
                amount INTEGER NOT NULL,
                event_id INTEGER,
                reason VARCHAR(255),
                created_at DATETIME
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ticket_transfers_from_ts ON ticket_transfers (from_user_id, created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ticket_transfers_to_ts ON ticket_transfers (to_user_id, created_at)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ticket_transfer_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                from_user_id VARCHAR NOT NULL,
                idempotency_key VARCHAR(128) NOT NULL,
                transfer_id INTEGER NOT NULL,
                response_json JSON,
                created_at DATETIME,
                CONSTRAINT uq_ticket_transfer_sender_idem UNIQUE (from_user_id, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ticket_transfer_idempotency_sender ON ticket_transfer_idempotency (from_user_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_gift_codes (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                code VARCHAR(16) NOT NULL,
                created_at DATETIME,
                updated_at DATETIME,
                CONSTRAINT uq_user_gift_codes_code UNIQUE (code),
                CONSTRAINT uq_user_gift_codes_user UNIQUE (user_id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_gift_codes_code ON user_gift_codes (code)"))


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
    cols = _table_columns(engine, "audit_logs")
    with engine.begin() as conn:
        if "actor_user_id" not in cols:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN actor_user_id VARCHAR"))
        if "committee_id" not in cols:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN committee_id INTEGER"))
        if "idempotency_key" not in cols:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN idempotency_key VARCHAR(128)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_event_id ON audit_logs (event_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_bar_id ON audit_logs (bar_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_user_id ON audit_logs (actor_user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_committee_id ON audit_logs (committee_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_idempotency_key ON audit_logs (idempotency_key)"))


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

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_staff_invite_codes (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                role VARCHAR(24) NOT NULL,
                code VARCHAR(24) NOT NULL,
                label VARCHAR(120),
                expires_at DATETIME NOT NULL,
                created_by VARCHAR NOT NULL,
                status VARCHAR(16) DEFAULT 'ACTIVE',
                created_at DATETIME,
                revoked_at DATETIME,
                revoked_reason VARCHAR(280)
            )
        """))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_event_staff_invite_event_code ON event_staff_invite_codes (event_id, code)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_staff_invite_event_id ON event_staff_invite_codes (event_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_staff_invite_status ON event_staff_invite_codes (status)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_staff_invite_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                action VARCHAR(64) NOT NULL,
                actor_user_id VARCHAR NOT NULL,
                idempotency_key VARCHAR(120) NOT NULL,
                invite_id INTEGER,
                response_json JSON,
                created_at DATETIME,
                CONSTRAINT uq_event_staff_invite_idem UNIQUE (event_id, action, actor_user_id, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_staff_invite_idem_event_id ON event_staff_invite_idempotency (event_id)"))


        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_staff_backup_codes (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                role VARCHAR(24) NOT NULL,
                code_hash VARCHAR(128) NOT NULL,
                suffix4 VARCHAR(4) NOT NULL,
                expires_at DATETIME NOT NULL,
                status VARCHAR(16) DEFAULT 'ACTIVE',
                created_by VARCHAR NOT NULL,
                created_at DATETIME,
                used_at DATETIME,
                used_by VARCHAR,
                revoked_at DATETIME,
                revoked_reason VARCHAR(280)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_staff_backup_event_id ON event_staff_backup_codes (event_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_staff_backup_role ON event_staff_backup_codes (role)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_staff_backup_code_hash ON event_staff_backup_codes (code_hash)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_staff_backup_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                action VARCHAR(64) NOT NULL,
                actor_user_id VARCHAR NOT NULL,
                idempotency_key VARCHAR(120) NOT NULL,
                code_id INTEGER,
                response_json JSON,
                created_at DATETIME,
                CONSTRAINT uq_event_staff_backup_idem UNIQUE (event_id, action, actor_user_id, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_staff_backup_idem_event_id ON event_staff_backup_idempotency (event_id)"))

    invite_cols = _table_columns(engine, "event_staff_invite_codes")
    with engine.begin() as conn:
        if "label" not in invite_cols:
            conn.execute(text("ALTER TABLE event_staff_invite_codes ADD COLUMN label VARCHAR(120)"))
        if "status" not in invite_cols:
            conn.execute(text("ALTER TABLE event_staff_invite_codes ADD COLUMN status VARCHAR(16) DEFAULT 'ACTIVE'"))
        if "revoked_at" not in invite_cols:
            conn.execute(text("ALTER TABLE event_staff_invite_codes ADD COLUMN revoked_at DATETIME"))
        if "revoked_reason" not in invite_cols:
            conn.execute(text("ALTER TABLE event_staff_invite_codes ADD COLUMN revoked_reason VARCHAR(280)"))

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
        if "host_type" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN host_type VARCHAR(16) DEFAULT 'user'"))
        if "host_id" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN host_id VARCHAR(120)"))
        if "host_display_name" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN host_display_name VARCHAR(180)"))
        if "visibility" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN visibility VARCHAR(16) DEFAULT 'PRIVATE'"))
        if "publication_status" not in event_cols:
            conn.execute(text("ALTER TABLE events ADD COLUMN publication_status VARCHAR(16) DEFAULT 'DRAFT'"))

        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_event_state ON events (event_state)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_host_type ON events (host_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_host_id ON events (host_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_visibility ON events (visibility)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_publication_status ON events (publication_status)"))

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

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_app_write_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                actor_user_id VARCHAR(64) NOT NULL,
                action VARCHAR(64) NOT NULL,
                idempotency_key VARCHAR(120) NOT NULL,
                event_id INTEGER,
                response_json JSON,
                created_at DATETIME,
                CONSTRAINT uq_event_app_write_idem UNIQUE (actor_user_id, action, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_app_write_idem_actor ON event_app_write_idempotency (actor_user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_app_write_idem_event ON event_app_write_idempotency (event_id)"))


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


def ensure_menu_admin_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    cols = _table_columns(engine, "menu_items")
    with engine.begin() as conn:
        if "stock_status" not in cols:
            conn.execute(text("ALTER TABLE menu_items ADD COLUMN stock_status VARCHAR(8) DEFAULT 'IN'"))
        if "version" not in cols:
            conn.execute(text("ALTER TABLE menu_items ADD COLUMN version INTEGER DEFAULT 1"))
        if "last_price_change_at" not in cols:
            conn.execute(text("ALTER TABLE menu_items ADD COLUMN last_price_change_at DATETIME"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS menu_admin_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                idempotency_key VARCHAR(120) NOT NULL,
                response_json JSON,
                created_at DATETIME,
                CONSTRAINT uq_menu_admin_idempotency UNIQUE (event_id, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_menu_admin_idempotency_event_id ON menu_admin_idempotency (event_id)"))



def ensure_event_safety_v1_tables(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_safety_settings (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                enabled BOOLEAN DEFAULT 1 NOT NULL,
                orga_phone VARCHAR(64),
                message_hint TEXT,
                updated_at DATETIME,
                updated_by INTEGER,
                CONSTRAINT uq_event_safety_settings_event UNIQUE (event_id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_safety_settings_event_id ON event_safety_settings (event_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_safety_buddies (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                user_id VARCHAR NOT NULL,
                buddy_user_id VARCHAR NOT NULL,
                created_at DATETIME,
                CONSTRAINT uq_event_safety_buddy_user UNIQUE (event_id, user_id)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_safety_buddies_event_user ON event_safety_buddies (event_id, user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_safety_buddies_event_buddy ON event_safety_buddies (event_id, buddy_user_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_safety_checkins (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                user_id VARCHAR NOT NULL,
                type VARCHAR(16) NOT NULL,
                created_at DATETIME,
                resolved_at DATETIME,
                resolved_by INTEGER,
                resolve_reason VARCHAR(240),
                assigned_to_user_id INTEGER
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_safety_checkins_event_created ON event_safety_checkins (event_id, created_at DESC, id DESC)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_safety_checkins_event_type_resolved ON event_safety_checkins (event_id, type, resolved_at)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS event_safety_idempotency (
                id INTEGER NOT NULL PRIMARY KEY,
                event_id INTEGER NOT NULL,
                action VARCHAR(32) NOT NULL,
                actor_scope VARCHAR(16) NOT NULL,
                actor_id VARCHAR(64) NOT NULL,
                idempotency_key VARCHAR(120) NOT NULL,
                response_json JSON,
                created_at DATETIME,
                CONSTRAINT uq_event_safety_idem UNIQUE (event_id, action, actor_scope, actor_id, idempotency_key)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_event_safety_idempotency_event_id ON event_safety_idempotency (event_id)"))
