from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"


def _legacy_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app.legacy.monolith":
            names = ", ".join(alias.name for alias in node.names)
            found.append(f"from app.legacy.monolith import {names}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "app.legacy.monolith":
                    found.append(f"import {alias.name}")
    return found


def test_extracted_core_dependencies_do_not_import_monolith():
    for relative in (
        "core/environment.py",
        "core/settings.py",
        "core/startup.py",
        "core/dev_bootstrap.py",
        "core/errors.py",
        "core/logging.py",
        "core/security/user_auth.py",
        "core/security/jwt.py",
        "deps/db.py",
        "services/event_role_service.py",
    ):
        path = APP / relative
        assert _legacy_imports(path) == [], (
            f"{relative} must stay independent from the legacy monolith"
        )


def test_modern_routers_do_not_import_extracted_legacy_dependencies():
    extracted = {
        "get_db",
        "get_current_user",
        "_extract_bearer_token",
        "_resolve_app_user_from_token",
        "_resolve_partner_identity_from_token",
        "_enforce_user_sanctions",
        "_role_rank",
        "resolve_event_role",
    }
    offenders: dict[str, list[str]] = {}
    for path in sorted((APP / "routers").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.legacy.monolith":
                names = sorted(extracted & {alias.name for alias in node.names})
                if names:
                    offenders.setdefault(path.name, []).extend(names)
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "app.legacy"
                and any(alias.name == "monolith" for alias in node.names)
            ):
                offenders.setdefault(path.name, []).append("monolith-module")
    assert offenders == {}, (
        "Modern routers must use extracted DB/auth/role boundaries. "
        f"Offenders: {offenders}"
    )


def test_nonlegacy_application_code_has_no_direct_monolith_imports():
    offenders: dict[str, list[str]] = {}
    for path in sorted(APP.rglob("*.py")):
        relative = path.relative_to(APP).as_posix()
        if relative.startswith("legacy/"):
            continue
        imports = _legacy_imports(path)
        if imports:
            offenders[relative] = imports
    assert offenders == {}, (
        "Non-legacy application code must not import app.legacy.monolith directly; "
        f"use an extracted service or explicit app.legacy facade. Offenders: {offenders}"
    )


def test_app_composition_does_not_import_monolith_directly():
    for relative in ("main.py", "core/errors.py", "core/logging.py"):
        path = APP / relative
        assert _legacy_imports(path) == [], (
            f"{relative} must use app.legacy.runtime only"
        )


def test_root_entrypoint_has_no_module_alias_or_monkey_patch():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "sys.modules[__name__]" not in source
    assert "_monolith." not in source
