"""Compatibility wrapper for ORM models.

This module keeps historical `import models` paths stable while the large ORM
surface is hosted in `app.legacy.models_monolith` for incremental extraction.
"""

from app.compat.reexport import reexport_public
from app.legacy import models_monolith as _models_monolith

reexport_public(_models_monolith, globals())
