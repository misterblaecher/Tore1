"""Application composition entrypoint."""

from app.core.startup import run_startup
from app.legacy import monolith


def create_app():
    app = monolith.app
    # Storage is extracted from the legacy monolith. Guard the singleton app so
    # compatibility callers that invoke create_app repeatedly do not duplicate routes.
    if not any(getattr(route, "name", None) == "upload_structure_file" for route in app.routes):
        from app.routers.storage import router as storage_router

        app.include_router(storage_router)
    run_startup(app)
    return app


__all__ = ["create_app"]
