"""
Analytics Module

Provides event tracking and reporting capabilities for various funnels
and user journeys.

Modules:
- apple_portin: Apple port-in funnel analytics (SE-5027)
- dashboards: Dashboard configurations and query templates
"""

from analytics.apple_portin import (
    # Constants
    Category,
    Action,
    FunnelStep,
    EligibilityResult,
    EligibilityFailureReason,
    Channel,
    DeviceCategory,
    # Events
    ApplePortInEvent,
    FunnelViewEvent,
    EligibilityCheckEvent,
    AddToCartEvent,
    CheckoutStartEvent,
    CheckoutCompleteEvent,
    FunnelAbandonEvent,
    # Tracker
    ApplePortInTracker,
)

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
