"""Helpers for compatibility wrappers that re-export module symbols."""

from __future__ import annotations

from types import ModuleType
from typing import Iterable


def reexport_public(
    module: ModuleType,
    globals_dict: dict,
    allowlist: Iterable[str] | None = None,
    denylist: Iterable[str] | None = None,
) -> list[str]:
    """Assign selected symbols into ``globals_dict`` and return ``__all__``.

    - Public symbols (without leading underscore) are exported by default.
    - ``allowlist`` forces additional names to be exported (including private).
    - ``denylist`` removes names from export.
    """

    allow = set(allowlist or [])
    deny = set(denylist or [])

    exported: list[str] = []
    seen: set[str] = set()

    for name in dir(module):
        if name in deny:
            continue
        if not name.startswith("_") or name in allow:
            globals_dict[name] = getattr(module, name)
            if name not in seen:
                exported.append(name)
                seen.add(name)

    for name in allow:
        if name in deny or name in seen:
            continue
        if hasattr(module, name):
            globals_dict[name] = getattr(module, name)
            exported.append(name)
            seen.add(name)

    globals_dict["__all__"] = exported
    return exported
