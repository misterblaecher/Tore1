"""Compatibility wrapper for ORM models.

This module keeps historical `import models` paths stable while the large ORM
surface is hosted in `app.legacy.models_monolith` for incremental extraction.
New domain models can live under `app.models` and are re-exported here during
the progressive split.
"""

from app.compat.reexport import reexport_public
from app.legacy import models_monolith as _models_monolith
from app.models.forum_events import ForumEventPage
from app.models.storage import StoredFile

reexport_public(_models_monolith, globals())
for _model_name in ("StoredFile", "ForumEventPage"):
    if _model_name not in __all__:
        __all__.append(_model_name)
