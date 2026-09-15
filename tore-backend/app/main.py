"""Application composition entrypoint."""

from app.core.startup import run_startup
from app.legacy import monolith
from app.routers.forum_invitations import router as forum_invitations_router


def create_app():
    app = monolith.app
    if not getattr(app.state, "forum_invitations_router_registered", False):
        app.include_router(forum_invitations_router)
        app.state.forum_invitations_router_registered = True
    run_startup(app)
    return app


__all__ = ["create_app"]
