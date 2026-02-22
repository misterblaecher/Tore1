"""Compatibility wrapper for the historical polymarket service module."""

from app.compat.reexport import reexport_public
from app.legacy import polymarket_service_monolith as _polymarket_service_monolith

reexport_public(_polymarket_service_monolith, globals())
