from __future__ import annotations

from app.utils import migrations


def test_run_migrations_calls_upgrade_when_enabled(monkeypatch):
    monkeypatch.setenv("RUN_MIGRATIONS", "1")
    monkeypatch.setenv("MIGRATIONS_FATAL", "1")
    monkeypatch.setattr(migrations, "_MIGRATIONS_EXECUTED", False)

    calls: list[str] = []

    def _fake_upgrade() -> None:
        calls.append("upgrade")

    monkeypatch.setattr(migrations, "_run_alembic_upgrade_head", _fake_upgrade)

    migrations.run_migrations_on_startup()

    assert calls == ["upgrade"]


def test_run_migrations_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("RUN_MIGRATIONS", "0")
    monkeypatch.setattr(migrations, "_MIGRATIONS_EXECUTED", False)

    calls: list[str] = []
    monkeypatch.setattr(migrations, "_run_alembic_upgrade_head", lambda: calls.append("upgrade"))

    migrations.run_migrations_on_startup()

    assert calls == []
