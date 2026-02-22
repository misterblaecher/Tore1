"""Application composition entrypoint."""

from app.core.startup import run_startup
from app.legacy import monolith


def create_app():
    app = monolith.app
    run_startup(app)
    return app


__all__ = ["create_app"]
