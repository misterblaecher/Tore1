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


def test_core_environment_settings_and_db_dependencies_do_not_import_monolith():
    for relative in (
        "core/environment.py",
        "core/settings.py",
        "core/startup.py",
        "core/dev_bootstrap.py",
        "deps/db.py",
    ):
        path = APP / relative
        assert _legacy_imports(path) == [], f"{relative} must stay independent from the legacy monolith"


def test_modern_routers_do_not_import_legacy_get_db():
    offenders: dict[str, list[str]] = {}
    for path in sorted((APP / "routers").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.legacy.monolith":
                names = {alias.name for alias in node.names}
                if "get_db" in names:
                    offenders.setdefault(path.name, []).append("get_db")
    assert offenders == {}, (
        "Modern routers must use app.deps.db.get_db; legacy auth helpers may remain "
        f"behind the compatibility boundary. Offenders: {offenders}"
    )


def test_app_composition_does_not_import_monolith_directly():
    for relative in ("main.py", "core/errors.py", "core/logging.py"):
        path = APP / relative
        assert _legacy_imports(path) == [], f"{relative} must use app.legacy.runtime only"


def test_root_entrypoint_has_no_module_alias_or_monkey_patch():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "sys.modules[__name__]" not in source
    assert "_monolith." not in source
