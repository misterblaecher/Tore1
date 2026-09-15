"""Application composition entrypoint."""

from app.core.startup import run_startup
from app.legacy import monolith
from app.routers.forum_accounting import router as forum_accounting_router
from app.routers.forum_event_workspace import router as forum_event_workspace_router
from app.routers.structure_claims import router as structure_claims_router


def create_app():
    app = monolith.app
    existing_paths = {getattr(route, "path", "") for route in app.routes}
    if not any(path.endswith("/event-workspace") for path in existing_paths):
        app.include_router(forum_event_workspace_router)
    if not any(path.endswith("/accounting-summary") for path in existing_paths):
        app.include_router(forum_accounting_router)
    if not any(path.startswith("/forum/structure-claims") for path in existing_paths):
        app.include_router(structure_claims_router)
    run_startup(app)
    return app


__all__ = ["create_app"]
