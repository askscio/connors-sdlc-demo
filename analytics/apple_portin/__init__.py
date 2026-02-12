"""
Apple Port-In Funnel Analytics Module

This module provides event tracking and analytics for the Apple port-in purchase
journey on web. It implements the event taxonomy defined in EVENT_TAXONOMY.md.

Jira Reference: SE-5027 (Analytics & Reporting for Apple Port-In Funnel)

Dependencies:
- SE-5026 (Implement Web Flow for Apple Port-In Offers)
- Web tracking framework and analytics platform
"""

from analytics.apple_portin.constants import (
    Category,
    Action,
    FunnelStep,
    EligibilityResult,
    EligibilityFailureReason,
    Channel,
    DeviceCategory,
)
from analytics.apple_portin.events import (
    ApplePortInEvent,
    FunnelViewEvent,
    EligibilityCheckEvent,
    AddToCartEvent,
    CheckoutStartEvent,
    CheckoutCompleteEvent,
    FunnelAbandonEvent,
)
from analytics.apple_portin.tracker import ApplePortInTracker

__all__ = [
    # Constants
    "Category",
    "Action",
    "FunnelStep",
    "EligibilityResult",
    "EligibilityFailureReason",
    "Channel",
    "DeviceCategory",
    # Events
    "ApplePortInEvent",
    "FunnelViewEvent",
    "EligibilityCheckEvent",
    "AddToCartEvent",
    "CheckoutStartEvent",
    "CheckoutCompleteEvent",
    "FunnelAbandonEvent",
    # Tracker
    "ApplePortInTracker",
]
