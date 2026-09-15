"""Application composition entrypoint."""

from app.core.startup import run_startup
from app.legacy import monolith


def create_app():
    app = monolith.app
    # Extracted routers are guarded because the legacy singleton app may be
    # composed repeatedly by compatibility callers and tests.
    if not any(getattr(route, "name", None) == "upload_structure_file" for route in app.routes):
        from app.routers.storage import router as storage_router

        app.include_router(storage_router)
    if not any(getattr(route, "name", None) == "list_managed_events" for route in app.routes):
        from app.routers.event_manager import router as event_manager_router

        app.include_router(event_manager_router)
    run_startup(app)
    return app


__all__ = ["create_app"]
