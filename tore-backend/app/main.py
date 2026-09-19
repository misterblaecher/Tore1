"""Application composition entrypoint.

The runtime app is a fresh FastAPI instance. Historical endpoint implementations
are mounted through app.legacy.runtime as an explicit compatibility boundary;
middleware, exception handling and startup belong to the modern app.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.errors import install_exception_handlers
from app.core.settings import _cors_origins
from app.core.startup import _startup
from app.legacy.runtime import mount_legacy_routes
from app.routers.event_manager import router as event_manager
from app.routers.forum_accounting import router as accounting
from app.routers.forum_event_workspace import router as event_workspace
from app.routers.forum_ownership import freeze_guard_middleware, router as ownership
from app.routers.forum_invitations import router as invitations_legacy
from app.routers.forum_invitations_rbac import router as invitations_rbac
from app.routers.forum_channel_acl_current import router as channel_acl
from app.routers.structure_claims import router as claims
from app.routers.structure_claim_review import router as claim_review
from app.routers.structure_lifecycle import router as lifecycle
from app.routers.structure_rbac import router as rbac
from app.routers.structure_visibility import router as visibility
from app.routers.structure_seo import router as seo
from app.routers.forum_planning import router as planning
from app.routers.forum_search import router as search
from app.routers.forum_notifications import router as notifications
from app.routers.forum_directory import router as directory
from app.routers.web_auth import router as web_auth
from app.services.event_cohosting_operational import install_cohost_operational_access
from app.services.rate_limit_service import record_status_code


_REPLACED = {
    ("POST", "/orgas"),
    ("GET", "/orgas/{org_id}"),
    ("PUT", "/orgas/{org_id}"),
    ("PATCH", "/forum/structures/{slug}/visibility"),
}
_MODULES = {"app.legacy.monolith", "app.routers.forum"}
_FORUM_ENDPOINT_REPLACED = {
    "list_structures",
    "list_discussions",
    "create_discussion",
    "update_discussion",
    "list_documents",
}
_INVITE_REPLACED = {
    "list_structure_invitations",
    "create_structure_invitation",
    "resend_structure_invitation",
    "revoke_structure_invitation",
    "accept_structure_invitation",
}


def _has(app: FastAPI, method: str, path: str) -> bool:
    return any(
        getattr(route, "path", "") == path
        and method in (getattr(route, "methods", set()) or set())
        for route in app.router.routes
    )


def _replace(app: FastAPI) -> None:
    kept = []
    for route in app.router.routes:
        endpoint = getattr(route, "endpoint", None)
        module = getattr(endpoint, "__module__", "")
        name = getattr(endpoint, "__name__", "")
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if module in _MODULES and any((method, path) in _REPLACED for method in methods):
            continue
        if module == "app.routers.forum" and name in _FORUM_ENDPOINT_REPLACED:
            continue
        kept.append(route)
    app.router.routes[:] = kept


def _install_metrics_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def metrics_lite_middleware(request, call_next):
        response = await call_next(request)
        try:
            record_status_code(int(response.status_code))
        except Exception:
            pass
        return response


def _install_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_origin_regex=r"^https://.*\.onrender\.com$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _install_modern_overrides(app: FastAPI) -> None:
    install_cohost_operational_access()
    paths = {getattr(route, "path", "") for route in app.routes}

    if not any(path.endswith("/event-workspace") for path in paths):
        app.include_router(event_workspace)
    if not any(path.endswith("/accounting-summary") for path in paths):
        app.include_router(accounting)
    if not any(path.endswith("/event-manager") for path in paths):
        app.include_router(event_manager)
    if not any(
        path.endswith("/publish") and path.startswith("/forum/structures/")
        for path in paths
    ):
        app.include_router(lifecycle)
    if not _has(app, "GET", "/forum/structures/{slug}/workspace"):
        app.include_router(rbac)
    if not _has(app, "PATCH", "/forum/structures/{slug}/visibility"):
        app.include_router(visibility)
    if not _has(app, "GET", "/forum/seo/structures/{slug}"):
        app.include_router(seo)
    if not _has(app, "GET", "/forum/structures/{slug}/planning"):
        app.include_router(planning)
    if not _has(app, "GET", "/forum/structures/{slug}/search"):
        app.include_router(search)
    if not _has(app, "GET", "/forum/structures/{slug}/notifications"):
        app.include_router(notifications)
    if not _has(app, "GET", "/forum/structures"):
        app.include_router(directory)

    if not getattr(app.state, "forum_ownership_installed", False):
        app.include_router(ownership)
        app.middleware("http")(freeze_guard_middleware)
        app.state.forum_ownership_installed = True

    if not getattr(app.state, "forum_claims_installed", False):
        claim_routes = [
            route
            for route in claims.routes
            if getattr(getattr(route, "endpoint", None), "__name__", "")
            != "review_structure_claim"
        ]
        for route in claim_routes:
            app.router.routes.append(route)
        app.include_router(claim_review)
        app.state.forum_claims_installed = True

    if not getattr(app.state, "forum_invitations_installed", False):
        for route in invitations_rbac.routes:
            app.router.routes.append(route)
        for route in invitations_legacy.routes:
            if (
                getattr(getattr(route, "endpoint", None), "__name__", "")
                not in _INVITE_REPLACED
            ):
                app.router.routes.append(route)
        app.state.forum_invitations_installed = True

    if not getattr(app.state, "forum_channel_acl_installed", False):
        app.include_router(channel_acl)
        app.state.forum_channel_acl_installed = True

    if not any(getattr(route, "name", None) == "upload_structure_file" for route in app.routes):
        from app.routers.storage import router as storage
        app.include_router(storage)

    if not any(getattr(route, "name", None) == "get_public_event_page" for route in app.routes):
        from app.routers.forum_events import router as events
        app.include_router(events)

    if not _has(app, "POST", "/auth/web/refresh"):
        app.include_router(web_auth)


def create_app() -> FastAPI:
    app = FastAPI(
        title="TORÈ backend",
        version="0.1.0",
        swagger_ui_parameters={
            "persistAuthorization": True,
            "docExpansion": "none",
            "filter": True,
        },
    )

    install_exception_handlers(app)
    _install_metrics_middleware(app)
    _install_cors(app)

    mount_legacy_routes(app)
    _replace(app)
    _install_modern_overrides(app)

    app.add_event_handler("startup", _startup)
    return app


__all__ = ["create_app"]
