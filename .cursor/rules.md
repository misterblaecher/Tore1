# TORÈ — Cursor rules

Repo: monorepo (backend FastAPI, Flutter app, Portal React)

## Architecture
- Backend: tore-backend/ (FastAPI + SQLAlchemy + Alembic + pytest)
- App: tore/app/ (Flutter + Riverpod + Dio + offline cache)
- Portal: tore-portal/ (React + TS + Vite)

## Non-negotiables
- Ne jamais casser les tests existants.
- Toute nouvelle feature backend => tests pytest.
- Toute nouvelle action write => idempotency key + audit log.
- Offline-first: prévoir READ_ONLY quand réseau down.
- Modules ON/OFF: UI ne montre que les modules ON.
- Event state: respecter PAUSE / DEGRADED / FROZEN partout.

## Conventions API
- Prefer /me snapshot for identity+roles+capabilities
- Prefer capability checks (can.*) over role-string checks in clients
- Keep endpoints stable; document changes.

## Output style
- Small, focused commits
- Explicit naming, minimal magic
- Comment business rules
