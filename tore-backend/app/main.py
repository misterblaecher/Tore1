from __future__ import annotations

import os

from fastapi import Depends

from app.core.startup import run_startup
from app.legacy import monolith
from app.routers.forum_backend import router as forum_backend_router
from app.routers.forum_backend_event_overrides import router as forum_backend_event_override_router
from app.routers.forum_backend_overrides import router as forum_backend_override_router
from app.routers.forum_channel_acl import router as forum_channel_acl_router
from app.routers.forum_channel_acl_admin import router as forum_channel_acl_admin_router
from app.services.forum_identity import get_registered_forum_user


_REPLACED_FORUM_ENDPOINTS = {
    "patch_public_page",
    "post_message",
    "folklore_versions",
    "list_posts",
    "transition_event",
    # ACL-aware replacements. These must be the only registered implementations
    # so OpenAPI and runtime routing describe the same security boundary.
    "list_channels",
    "list_messages",
    "list_documents",
    "get_document_metadata",
    "download_document",
    "search_structure",
}

_ACL_REPLACED_OVERRIDE_ENDPOINTS = {
    "post_message",
    "get_document_metadata",
}


def _server_forum_authority_enabled() -> bool:
    raw = os.getenv("FORUM_BACKEND_ENABLED")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    env = (os.getenv("TORE_ENV") or os.getenv("ENV") or "DEV").strip().upper()
    return env in {"PROD", "PRODUCTION"}


def _install_forum_backend(app) -> None:
    if _server_forum_authority_enabled():
        # The old /forum/* routes were a local/prototype authority.  They remain
        # available in DEV while migration is ongoing, but production authority
        # removes them before installing /forum/v2.
        app.router.routes[:] = [
            route for route in app.router.routes
            if not (
                str(getattr(route, "path", "")).startswith("/forum/")
                and not str(getattr(route, "path", "")).startswith("/forum/v2/")
            )
        ]

    # Compatibility handlers replaced here keep the broader router stable while
    # letting final review hardening stay isolated and typed.
    forum_backend_router.routes[:] = [
        route
        for route in forum_backend_router.routes
        if getattr(getattr(route, "endpoint", None), "__name__", "")
        not in _REPLACED_FORUM_ENDPOINTS
    ]
    forum_backend_override_router.routes[:] = [
        route
        for route in forum_backend_override_router.routes
        if getattr(getattr(route, "endpoint", None), "__name__", "")
        not in _ACL_REPLACED_OVERRIDE_ENDPOINTS
    ]

    if not any(str(getattr(route, "path", "")).startswith("/forum/v2/") for route in app.router.routes):
        forum_guard = [Depends(get_registered_forum_user)]
        # Management metadata is deliberately separate from content access:
        # channels.manage may edit an ACL without becoming a channel reader.
        app.include_router(forum_channel_acl_admin_router, dependencies=forum_guard)
        # Register ACL-aware routes first; descendants (message/thread/reaction/
        # attachment) all inherit the parent channel decision.
        app.include_router(forum_channel_acl_router, dependencies=forum_guard)
        app.include_router(forum_backend_override_router, dependencies=forum_guard)
        app.include_router(forum_backend_event_override_router, dependencies=forum_guard)
        app.include_router(forum_backend_router, dependencies=forum_guard)
    app.openapi_schema = None


def create_app():
    app = monolith.app
    _install_forum_backend(app)
    run_startup(app)
    return app
