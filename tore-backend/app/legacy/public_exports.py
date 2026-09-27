"""Narrow exports for historical endpoint/page implementations.

Only code under app/legacy imports the monolith directly. Non-legacy compatibility
facades may import these names from this module during the strangler migration.
"""

from app.legacy.monolith import (
    partner_portal_bar,
    partner_portal_events,
    partner_portal_list_battles,
    quickstart,
)

__all__ = [
    "partner_portal_bar",
    "partner_portal_events",
    "partner_portal_list_battles",
    "quickstart",
]
