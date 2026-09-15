"""Application composition entrypoint."""

from app.core.startup import run_startup
from app.legacy import monolith
from app.routers.forum_accounting import router as forum_accounting_router
from app.routers.forum_event_workspace import router as forum_event_workspace_router
from app.routers.structure_lifecycle import router as structure_lifecycle_router
from app.routers.structure_rbac import router as structure_rbac_router
from app.routers.structure_visibility import router as structure_visibility_router


_LEGACY_STRUCTURE_ROUTES_REPLACED = {
    ("POST", "/orgas"),
    ("GET", "/orgas/{org_id}"),
    ("PUT", "/orgas/{org_id}"),
    ("PATCH", "/forum/structures/{slug}/visibility"),
}
_LEGACY_STRUCTURE_MODULES = {"app.legacy.monolith", "app.routers.forum"}


def _replace_legacy_structure_routes(app) -> None:
    """Keep URLs stable while replacing only handlers that violate privacy invariants."""

    filtered = []
    for route in app.router.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        endpoint_module = getattr(getattr(route, "endpoint", None), "__module__", "")
        if endpoint_module in _LEGACY_STRUCTURE_MODULES and any(
            (method, path) in _LEGACY_STRUCTURE_ROUTES_REPLACED for method in methods
        ):
            continue
        filtered.append(route)
    app.router.routes[:] = filtered


def _has_route(app, method: str, path: str) -> bool:
    return any(
        getattr(route, "path", "") == path and method in (getattr(route, "methods", set()) or set())
        for route in app.router.routes
    )


def create_app():
    app = monolith.app
    _replace_legacy_structure_routes(app)
    existing_paths = {getattr(route, "path", "") for route in app.routes}
    if not any(path.endswith("/event-workspace") for path in existing_paths):
        app.include_router(forum_event_workspace_router)
    if not any(path.endswith("/accounting-summary") for path in existing_paths):
        app.include_router(forum_accounting_router)
    if not any(path.endswith("/publish") and path.startswith("/forum/structures/") for path in existing_paths):
        app.include_router(structure_lifecycle_router)
    if not _has_route(app, "GET", "/forum/structures/{slug}/workspace"):
        app.include_router(structure_rbac_router)
    if not _has_route(app, "PATCH", "/forum/structures/{slug}/visibility"):
        app.include_router(structure_visibility_router)
    run_startup(app)
    return app


__all__ = ["create_app"]
