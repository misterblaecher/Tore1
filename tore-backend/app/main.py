"""Application composition entrypoint."""

from app.core.startup import run_startup
from app.legacy import monolith
from app.routers.forum_event_workspace import router as forum_event_workspace_router


def create_app():
    app = monolith.app
    if not any(getattr(route, "path", "").endswith("/event-workspace") for route in app.routes):
        app.include_router(forum_event_workspace_router)
    run_startup(app)
    return app


__all__ = ["create_app"]
