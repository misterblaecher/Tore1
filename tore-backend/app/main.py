"""Application composition entrypoint."""

from app.core.startup import run_startup
from app.legacy import monolith
from app.routers.forum_ownership import freeze_guard_middleware, router as forum_ownership_router


def create_app():
    app = monolith.app
    if not getattr(app.state, "forum_ownership_installed", False):
        app.include_router(forum_ownership_router)
        app.middleware("http")(freeze_guard_middleware)
        app.state.forum_ownership_installed = True
    run_startup(app)
    return app


__all__ = ["create_app"]
