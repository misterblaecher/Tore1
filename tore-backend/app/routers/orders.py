"""Compatibility wrapper for the historical orders router module."""

from app.compat.reexport import reexport_public
from app.legacy import orders_router_monolith as _orders_router_monolith

reexport_public(_orders_router_monolith, globals())
