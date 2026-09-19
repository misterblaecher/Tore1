"""Development/bootstrap schema compatibility and demo seed.

This preserves the historical SQLite bootstrap behavior without importing the
legacy runtime. Production PostgreSQL normally uses Alembic and does not run
this module unless TORE_AUTO_DB_BOOTSTRAP is explicitly enabled.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select, text

from app.db.sqlite_compat import ensure_sqlite_compat
from db import Base, engine, get_session, now_utc
from models import Bar, Drink, Event, EventDrink, PriceHistory


def _ensure_orders_payment_columns() -> None:
    if engine.dialect.name != "sqlite":
        return
    s = get_session()
    try:
        columns = {row[1] for row in s.execute(text("PRAGMA table_info(orders)")).fetchall()}
        if "total_tickets" not in columns:
            s.execute(text("ALTER TABLE orders ADD COLUMN total_tickets INTEGER DEFAULT 0"))
        if "payment_status" not in columns:
            s.execute(text("ALTER TABLE orders ADD COLUMN payment_status VARCHAR(20) DEFAULT 'UNPAID'"))
        s.commit()
    finally:
        s.close()


def _ensure_market_tick_columns() -> None:
    if engine.dialect.name != "sqlite":
        return
    s = get_session()
    try:
        columns = {row[1] for row in s.execute(text("PRAGMA table_info(drink_price_ticks)")).fetchall()}
        if "ref_order_id" not in columns:
            s.execute(text("ALTER TABLE drink_price_ticks ADD COLUMN ref_order_id INTEGER"))
            s.execute(text("CREATE INDEX IF NOT EXISTS ix_drink_price_ticks_ref_order_id ON drink_price_ticks (ref_order_id)"))
        s.commit()
    finally:
        s.close()


def _ensure_polymarket_v1_columns() -> None:
    if engine.dialect.name != "sqlite":
        return
    s = get_session()
    try:
        bet_columns = {row[1] for row in s.execute(text("PRAGMA table_info(polymarket_bets)")).fetchall()}
        if "dispute_window_minutes" not in bet_columns:
            s.execute(text("ALTER TABLE polymarket_bets ADD COLUMN dispute_window_minutes INTEGER DEFAULT 60"))
        if "resolved_at" not in bet_columns:
            s.execute(text("ALTER TABLE polymarket_bets ADD COLUMN resolved_at DATETIME"))
        if "finalized_at" not in bet_columns:
            s.execute(text("ALTER TABLE polymarket_bets ADD COLUMN finalized_at DATETIME"))

        s.execute(text("""
            CREATE TABLE IF NOT EXISTS polymarket_disputes (
                id INTEGER NOT NULL PRIMARY KEY,
                bet_id INTEGER NOT NULL,
                user_id VARCHAR NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                created_at DATETIME,
                CONSTRAINT uq_polymarket_dispute_bet_user UNIQUE (bet_id, user_id),
                FOREIGN KEY(bet_id) REFERENCES polymarket_bets (id)
            )
        """))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_polymarket_disputes_bet_id ON polymarket_disputes (bet_id)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_polymarket_disputes_user_id ON polymarket_disputes (user_id)"))
        s.commit()
    finally:
        s.close()


def _ensure_wallet_indexes() -> None:
    s = get_session()
    try:
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_wallet_txs_user_ts ON wallet_txs (user_id, created_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_wallet_ledger_event_ts ON wallet_ledger_entries (event_id, created_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_wallet_gifts_from_ts ON wallet_gifts (from_user_id, created_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_wallet_gifts_to_ts ON wallet_gifts (to_user_id, created_at)"))
        s.commit()
    finally:
        s.close()


def _ensure_app_user_privacy_columns() -> None:
    if engine.dialect.name != "sqlite":
        return
    s = get_session()
    try:
        columns = {row[1] for row in s.execute(text("PRAGMA table_info(app_users)")).fetchall()}
        if "email" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN email VARCHAR(255)"))
            s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_email ON app_users (email)"))
        if "phone" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN phone VARCHAR(64)"))
            s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_phone ON app_users (phone)"))
        if "is_deleted" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
            s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_is_deleted ON app_users (is_deleted)"))
        if "deleted_at" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN deleted_at DATETIME"))
        if "anonymized_at" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN anonymized_at DATETIME"))
        if "account_mode" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN account_mode VARCHAR(16) DEFAULT 'user'"))
        if "first_name" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN first_name VARCHAR(120)"))
        if "last_name" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN last_name VARCHAR(120)"))
        if "nickname" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN nickname VARCHAR(120)"))
        if "password_hash" not in columns:
            s.execute(text("ALTER TABLE app_users ADD COLUMN password_hash VARCHAR(255)"))
        s.execute(text("UPDATE app_users SET account_mode='user' WHERE account_mode IS NULL OR account_mode = ''"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_account_mode ON app_users (account_mode)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_deleted_at ON app_users (deleted_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_app_users_anonymized_at ON app_users (anonymized_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_user_ts ON audit_logs (actor_user_id, ts)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_logs_committee_ts ON audit_logs (committee_id, ts)"))
        s.commit()
    finally:
        s.close()


def _ensure_auth_otp_columns() -> None:
    s = get_session()
    try:
        if engine.dialect.name == "sqlite":
            columns = {row[1] for row in s.execute(text("PRAGMA table_info(auth_otp_codes)")).fetchall()}
            if "last_attempt_at" not in columns:
                s.execute(text("ALTER TABLE auth_otp_codes ADD COLUMN last_attempt_at DATETIME"))
            if "request_id" not in columns:
                s.execute(text("ALTER TABLE auth_otp_codes ADD COLUMN request_id VARCHAR(120)"))
            if "user_id" not in columns:
                s.execute(text("ALTER TABLE auth_otp_codes ADD COLUMN user_id VARCHAR"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_otp_email_created_at ON auth_otp_codes (email, created_at DESC)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_otp_email_used_at ON auth_otp_codes (email, used_at)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_auth_otp_expires_at ON auth_otp_codes (expires_at)"))
        s.commit()
    finally:
        s.close()


def _ensure_role_upgrade_requests_table() -> None:
    if engine.dialect.name != "sqlite":
        return
    s = get_session()
    try:
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS role_upgrade_requests (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                requested_mode VARCHAR(16) NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                created_at DATETIME,
                reviewed_at DATETIME,
                reviewed_by VARCHAR(120),
                note TEXT
            )
        """))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_role_upgrade_requests_user_id ON role_upgrade_requests (user_id)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_role_upgrade_requests_status ON role_upgrade_requests (status)"))
        s.execute(text("CREATE INDEX IF NOT EXISTS ix_role_upgrade_requests_mode ON role_upgrade_requests (requested_mode)"))
        s.commit()
    finally:
        s.close()


def ensure_seed() -> None:
    Base.metadata.create_all(engine)
    _ensure_orders_payment_columns()
    _ensure_market_tick_columns()
    _ensure_polymarket_v1_columns()
    _ensure_wallet_indexes()
    _ensure_app_user_privacy_columns()
    _ensure_auth_otp_columns()
    _ensure_role_upgrade_requests_table()
    ensure_sqlite_compat(engine)

    s = get_session()
    try:
        bar_count = s.scalar(select(func.count()).select_from(Bar)) or 0
        if bar_count != 0:
            return

        b1 = Bar(name="TORÈ Test Bar", city="Liège", partner_code="TORE_TEST_LIEGE")
        b2 = Bar(name="Dow'n Drinks", city="Bruxelles", partner_code="DOWN_BRUX")
        s.add_all([b1, b2])
        s.flush()

        e1 = Event(
            bar_id=b1.id,
            name="Baptême — Soirée Marché",
            starts_at=now_utc(),
            ends_at=now_utc() + timedelta(hours=8),
            entry_price_cents=500,
            ticket_mode=True,
            ticket_value_cents=200,
            allow_self_ticket_adjust=True,
        )
        e2 = Event(
            bar_id=b1.id,
            name="Afond Night (gratuit)",
            starts_at=now_utc(),
            ends_at=now_utc() + timedelta(hours=6),
            entry_price_cents=0,
            ticket_mode=False,
            ticket_value_cents=200,
            allow_self_ticket_adjust=True,
        )
        s.add_all([e1, e2])
        s.flush()

        drinks = [
            Drink(name="Pils", type="beer"),
            Drink(name="Jupiler", type="beer"),
            Drink(name="Shot", type="shot"),
            Drink(name="Cocktail", type="cocktail"),
            Drink(name="Soft", type="soft"),
        ]
        s.add_all(drinks)
        s.flush()

        base_prices = [250, 280, 220, 650, 200]
        for event in (e1, e2):
            for drink, price in zip(drinks, base_prices):
                s.add(
                    EventDrink(
                        event_id=event.id,
                        drink_id=drink.id,
                        base_price_cents=price,
                        current_price_cents=price,
                        last_price_update=now_utc(),
                    )
                )
                s.add(
                    PriceHistory(
                        event_id=event.id,
                        drink_id=drink.id,
                        price_cents=price,
                        ts=now_utc(),
                    )
                )
        s.commit()
    finally:
        s.close()


__all__ = ["ensure_seed"]
