"""Compatibility wrapper for ORM models."""
from app.compat.reexport import reexport_public
from app.legacy import models_monolith as _models_monolith
from app.models.forum_events import ForumEventPage
from app.models.storage import StoredFile
from app.models_structure_claim import StructureClaim

reexport_public(_models_monolith, globals())
for _model_name in ("StoredFile","ForumEventPage","StructureClaim"):
    globals()[_model_name]=globals().get(_model_name) or locals()[_model_name]
    if _model_name not in __all__: __all__.append(_model_name)
