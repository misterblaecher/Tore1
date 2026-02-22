"""SQLite compatibility patch helpers extracted from legacy main module."""

from main import (
    _ensure_app_user_privacy_columns,
    _ensure_market_tick_columns,
    _ensure_orders_payment_columns,
    _ensure_polymarket_v1_columns,
    _ensure_role_upgrade_requests_table,
    _ensure_wallet_indexes,
)

__all__ = [
    "_ensure_orders_payment_columns",
    "_ensure_market_tick_columns",
    "_ensure_polymarket_v1_columns",
    "_ensure_wallet_indexes",
    "_ensure_app_user_privacy_columns",
    "_ensure_role_upgrade_requests_table",
]
