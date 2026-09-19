# Legacy backend boundary and exit plan

Issue: #284

## Goal

The legacy monolith remains a compatibility boundary while runtime responsibilities
move behind stable modules. New code must not add direct dependencies on
`app.legacy.monolith` when an extracted dependency exists.

## Current boundary

Allowed legacy responsibilities during the transition:

- application/route compatibility surface in `app/main.py`;
- legacy auth helpers that have not yet been fully extracted;
- historical router/service wrappers under `app/legacy/`;
- startup seed compatibility until seed/bootstrap extraction is complete.

Extracted responsibilities that must not regress:

- environment resolution and production validation: `app/core/environment.py`,
  `app/core/settings.py`;
- FastAPI DB dependency: `app/deps/db.py`;
- migrations: `app/utils/migrations.py`;
- modern domain routers/services already present under `app/routers` and
  `app/services`.

## Migration order

1. **DB dependency** — complete in this PR. Modern routers use
   `app.deps.db.get_db`.
2. **Configuration** — complete in this PR. Core settings no longer import or
   monkey-patch the monolith.
3. **Auth/token resolution** — move `get_current_user`,
   `_resolve_app_user_from_token`, role resolution and sanctions to stable
   security/services modules; preserve HTTP contracts with parity tests.
4. **Startup/bootstrap** — extract seed/bootstrap behavior from the legacy
   module, then make `app/core/startup.py` completely independent.
5. **Application composition** — once route parity is covered, replace
   `app=monolith.app` with a fresh FastAPI app that mounts the remaining
   legacy router as one explicit compatibility component.
6. **Root compatibility** — remove the `sys.modules[__name__] = _monolith`
   shim after imports of `main` no longer rely on monkey-patching behavior.
7. **Deletion** — remove legacy implementations only after import-boundary,
   route-parity and runtime smoke tests prove no consumer remains.

## Exit criteria

The monolith can be deleted when:

- no non-legacy module imports `app.legacy.monolith`;
- root `main.py` is a normal application entrypoint, not a module alias;
- the app factory constructs a fresh FastAPI instance;
- startup/settings/DB/auth dependencies are autonomous;
- route/RBAC/idempotency parity tests and runtime smoke tests are green;
- a production-like migration + startup smoke is green.

## Guardrails

`tests/test_legacy_import_boundaries.py` prevents re-introducing the legacy DB
dependency into modern routers and protects the already extracted core modules.
The allowlist should only shrink.
