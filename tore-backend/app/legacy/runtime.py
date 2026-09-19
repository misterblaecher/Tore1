"""Explicit compatibility boundary for routes still implemented by the legacy runtime.

Only this module imports the legacy monolith for application composition.
Modern application code consumes the narrow helpers below instead of reaching
into app.legacy.monolith directly.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterator

from fastapi import FastAPI

from app.legacy import monolith as _monolith


_FRAMEWORK_PATHS = {
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}


def iter_legacy_routes() -> Iterator[Any]:
    for route in _monolith.app.router.routes:
        if getattr(route, "path", None) in _FRAMEWORK_PATHS:
            continue
        yield route


def mount_legacy_routes(app: FastAPI) -> None:
    """Mount historical route objects onto a fresh FastAPI application."""
    existing = {
        (
            getattr(route, "path", ""),
            tuple(sorted(getattr(route, "methods", set()) or set())),
            getattr(route, "name", None),
        )
        for route in app.router.routes
    }
    for route in iter_legacy_routes():
        signature = (
            getattr(route, "path", ""),
            tuple(sorted(getattr(route, "methods", set()) or set())),
            getattr(route, "name", None),
        )
        if signature in existing:
            continue
        app.router.routes.append(route)
        existing.add(signature)


def legacy_route_inventory() -> dict[str, int]:
    modules = Counter(
        getattr(getattr(route, "endpoint", None), "__module__", "<unknown>")
        for route in iter_legacy_routes()
    )
    return dict(sorted(modules.items()))


def legacy_export(name: str):
    """Compatibility lookup for historical imports from root main.py."""
    return getattr(_monolith, name)


def legacy_app_identity() -> FastAPI:
    """Testing/introspection only: return the historical app instance."""
    return _monolith.app


__all__ = [
    "iter_legacy_routes",
    "mount_legacy_routes",
    "legacy_route_inventory",
    "legacy_export",
    "legacy_app_identity",
]
