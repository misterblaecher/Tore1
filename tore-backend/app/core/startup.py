"""Startup/bootstrap helpers."""

from app.legacy.monolith import _startup, _startup_sanity_checks, ensure_seed, run_migrations_on_startup


def run_startup(app) -> None:
    """Compatibility wrapper used by app factory."""
    _ = app


__all__ = ["_startup", "_startup_sanity_checks", "run_migrations_on_startup", "ensure_seed", "run_startup"]
