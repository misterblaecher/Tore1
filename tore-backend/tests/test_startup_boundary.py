from types import SimpleNamespace

from app.core import startup


def test_startup_pipeline_bootstraps_in_order(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(startup, "run_migrations_on_startup", lambda: calls.append("migrations"))
    monkeypatch.setattr(startup, "validate_env_or_warn", lambda: calls.append("env"))
    monkeypatch.setattr(startup, "_startup_sanity_checks", lambda: calls.append("sanity"))
    monkeypatch.setattr(startup, "_should_bootstrap_on_startup", lambda: True)
    monkeypatch.setattr(startup, "ensure_seed", lambda: calls.append("seed"))

    startup._startup()

    assert calls == ["migrations", "env", "sanity", "seed"]


def test_startup_pipeline_skips_seed_when_bootstrap_disabled(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(startup, "run_migrations_on_startup", lambda: calls.append("migrations"))
    monkeypatch.setattr(startup, "validate_env_or_warn", lambda: calls.append("env"))
    monkeypatch.setattr(startup, "_startup_sanity_checks", lambda: calls.append("sanity"))
    monkeypatch.setattr(startup, "_should_bootstrap_on_startup", lambda: False)
    monkeypatch.setattr(startup, "ensure_seed", lambda: calls.append("seed"))

    startup._startup()

    assert calls == ["migrations", "env", "sanity"]


def test_sqlite_always_bootstraps(monkeypatch):
    monkeypatch.setattr(startup, "engine", SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    monkeypatch.setenv("TORE_AUTO_DB_BOOTSTRAP", "0")
    assert startup._should_bootstrap_on_startup() is True


def test_postgres_bootstrap_is_explicit(monkeypatch):
    monkeypatch.setattr(startup, "engine", SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
    monkeypatch.delenv("TORE_AUTO_DB_BOOTSTRAP", raising=False)
    assert startup._should_bootstrap_on_startup() is False
    monkeypatch.setenv("TORE_AUTO_DB_BOOTSTRAP", "1")
    assert startup._should_bootstrap_on_startup() is True
