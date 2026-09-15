"""Compatibility wrapper for ORM models.

This module keeps historical `import models` paths stable while the large ORM
surface is hosted in `app.legacy.models_monolith` for incremental extraction.
"""

from app.compat.reexport import reexport_public
from app.legacy import models_monolith as _models_monolith
from app.models_structure_claim import StructureClaim

reexport_public(_models_monolith, globals())

# New Forum models can live outside the legacy monolith while remaining
# available through the historical `from models import ...` import surface.
globals()["StructureClaim"] = StructureClaim
