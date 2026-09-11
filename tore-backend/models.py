"""Compatibility wrapper for ORM models.

Historical imports remain stable while the Forum production foundation adds
new additive models outside the legacy monolith. Importing this module registers
both model sets on the same SQLAlchemy Base/metadata.
"""

from app.compat.reexport import reexport_public
from app.legacy import models_monolith as _models_monolith
from app import forum_models as _forum_models

reexport_public(_models_monolith, globals())
reexport_public(_forum_models, globals())
