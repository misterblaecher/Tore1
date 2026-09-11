from __future__ import annotations

import os

from app.core.startup import run_startup
from app.legacy import monolith
from app.routers.forum_backend import router as forum_backend_router


def _server_forum_authority_enabled() -> bool:
    raw = os.getenv("FORUM_BACKEND_ENABLED")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    env = (os.getenv("TORE_ENV") or os.getenv("ENV") or "DEV").strip().upper()
    return env in {"PROD", "PRODUCTION"}


def _install_forum_backend(app) -> None:
    if _server_forum_authority_enabled():
        # The old /forum/* routes were a local/prototype authority.  They remain
        # available in DEV while migration is ongoing, but production authority
        # removes them before installing /forum/v2.
        app.router.routes[:] = [
            route for route in app.router.routes
            if not (
                str(getattr(route, "path", "")).startswith("/forum/")
                and not str(getattr(route, "path", "")).startswith("/forum/v2/")
            )
        ]
    if not any(str(getattr(route, "path", "")).startswith("/forum/v2/") for route in app.router.routes):
        app.include_router(forum_backend_router)
    app.openapi_schema = None


def create_app():
    app = monolith.app
    _install_forum_backend(app)
    run_startup(app)
    return app
