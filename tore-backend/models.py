"""Compatibility wrapper for ORM models.

This module keeps historical `import models` paths stable while the large ORM
surface is hosted in `app.legacy.models_monolith` for incremental extraction.
"""

from app.legacy import models_monolith as _models_monolith

# Re-export public symbols through module-level assignments to keep import
# compatibility and preserve monkeypatchability (tests can patch `models.X`).
for _name in dir(_models_monolith):
    if _name.startswith("_"):
        continue
    globals()[_name] = getattr(_models_monolith, _name)

__all__ = [name for name in globals() if not name.startswith("_")]
