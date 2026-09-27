import importlib

from fastapi import HTTPException
from fastapi.testclient import TestClient

import main
from app.legacy.runtime import legacy_app_identity
from app.legacy import monolith as legacy_monolith
from app.main import create_app


def test_root_main_is_a_real_module_not_legacy_alias():
    assert main.__name__ == "main"
    assert main is not importlib.import_module("app.legacy.monolith")


def test_app_factory_returns_fresh_instances():
    first = create_app()
    second = create_app()
    assert first is not second
    assert first is not legacy_app_identity()
    assert second is not legacy_app_identity()


def test_fresh_app_keeps_key_legacy_and_modern_routes():
    app = create_app()
    paths = [getattr(route, "path", "") for route in app.routes]
    assert paths.count("/openapi.json") == 1
    assert "/healthz" in paths
    assert "/partner/portal/bar" in paths
    assert "/auth/web/refresh" in paths


def test_fresh_app_owns_handlers_and_startup():
    app = create_app()
    assert HTTPException in app.exception_handlers
    assert Exception in app.exception_handlers
    startup_modules = {
        getattr(handler, "__module__", "")
        for handler in app.router.on_startup
    }
    assert "app.core.startup" in startup_modules


def test_root_app_smoke_contracts():
    client = TestClient(main.app)
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/partner/portal/bar").status_code == 401


def test_root_legacy_attribute_fallback_is_narrow_compatibility():
    # Existing tests/integrations that still import a historical constant from
    # main keep working without replacing the main module itself.
    assert isinstance(main.JWT_ALG, str)


def test_mounted_legacy_routes_are_cloned_for_each_app():
    fresh = create_app()
    fresh_route = next(
        route for route in fresh.routes
        if getattr(route, "path", "") == "/partner/portal/bar"
    )
    legacy_route = next(
        route for route in legacy_monolith.app.routes
        if getattr(route, "path", "") == "/partner/portal/bar"
    )
    assert fresh_route is not legacy_route
    assert getattr(fresh_route, "dependency_overrides_provider", None) is fresh


def test_filtered_modern_routes_bind_dependency_overrides_to_fresh_app():
    fresh = create_app()
    expected = {
        ("GET", "/forum/structure-claims/mine"),
        ("GET", "/forum/structures/{slug}/invitations"),
        ("GET", "/forum/invitations/{token}"),
    }
    found = set()
    for route in fresh.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        for method, expected_path in expected:
            if path == expected_path and method in methods:
                assert getattr(route, "dependency_overrides_provider", None) is fresh
                found.add((method, expected_path))
    assert found == expected


def test_legacy_context_decoder_is_an_explicit_dependency():
    assert legacy_monolith.decode_user_token is not None
