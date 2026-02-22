"""Compatibility wrapper for the historical portal event control router module."""

from app.compat.reexport import reexport_public
from app.legacy import portal_event_control_router_monolith as _portal_event_control_router_monolith

reexport_public(_portal_event_control_router_monolith, globals())
