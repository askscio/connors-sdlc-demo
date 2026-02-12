"""
Event Data Classes for Apple Port-In Funnel Analytics

Defines structured event classes for each event type in the Apple port-in
funnel. These classes ensure type safety and consistent event schemas.

See EVENT_TAXONOMY.md for full documentation.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import uuid

from analytics.apple_portin.constants import (
    Category,
    Action,
    FunnelStep,
    EligibilityResult,
    EligibilityFailureReason,
    Channel,
    DeviceCategory,
    PaymentMethod,
    EventProperty,
)


@dataclass
class ApplePortInEvent:
    """
    Base class for all Apple port-in funnel events.

    All events share common properties for session tracking, channel attribution,
    and timestamp recording.
    """
    session_id: str
    channel: Channel
    timestamp: datetime = field(default_factory=datetime.utcnow)
    category: Category = field(default=Category.APPLE_PORTIN_FUNNEL, init=False)

    # Optional common properties
    apple_sku: Optional[str] = None
    offer_id: Optional[str] = None

    def to_dict(self) -> dict:
        """
        Convert event to dictionary for analytics transmission.

        Returns a dictionary with all non-None properties, suitable for
        sending to the analytics platform.
        """
        result = {
            EventProperty.SESSION_ID: self.session_id,
            EventProperty.CHANNEL: self.channel.value if isinstance(self.channel, Channel) else self.channel,
            EventProperty.TIMESTAMP: self.timestamp.isoformat() + "Z",
            "category": self.category.value,
        }

        if self.apple_sku:
            result[EventProperty.APPLE_SKU] = self.apple_sku
        if self.offer_id:
            result[EventProperty.OFFER_ID] = self.offer_id

        return result


@dataclass
class FunnelViewEvent(ApplePortInEvent):
    """
    Event for tracking funnel step views.

    Fired when a user views any step in the Apple port-in funnel.
    Used to calculate step-by-step conversion rates.
    """
    funnel_step: FunnelStep = field(default=FunnelStep.LANDING_PAGE)
    action: Action = field(default=Action.VIEW, init=False)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["action"] = self.action.value
        result[EventProperty.FUNNEL_STEP] = self.funnel_step.value
        result[EventProperty.STEP_NUMBER] = FunnelStep.get_step_number(self.funnel_step)
        return result


@dataclass
class EligibilityCheckEvent(ApplePortInEvent):
    """
    Event for tracking eligibility check outcomes.

    Fired when the system evaluates a user's eligibility for port-in offers.
    Tracks pass/fail results and failure reasons for fallout analysis.
    """
    result: EligibilityResult = field(default=EligibilityResult.PASS)
    failure_reason: Optional[EligibilityFailureReason] = None
    carrier_from: Optional[str] = None
    check_duration_ms: Optional[int] = None
    action: Action = field(default=Action.ELIGIBILITY_CHECK, init=False)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["action"] = self.action.value
        result[EventProperty.RESULT] = self.result.value
        result[EventProperty.FUNNEL_STEP] = FunnelStep.ELIGIBILITY_CHECK.value

        if self.failure_reason:
            result[EventProperty.FAILURE_REASON] = self.failure_reason.value
        if self.carrier_from:
            result[EventProperty.CARRIER_FROM] = self.carrier_from
        if self.check_duration_ms is not None:
            result[EventProperty.CHECK_DURATION_MS] = self.check_duration_ms

        return result


@dataclass
class AddToCartEvent(ApplePortInEvent):
    """
    Event for tracking add-to-cart actions.

    Fired when a user adds an Apple device to their cart.
    Includes device details, offer information, and cart totals.
    """
    device_name: str = ""
    device_category: DeviceCategory = field(default=DeviceCategory.IPHONE)
    offer_value: Optional[int] = None  # Value in cents
    plan_id: Optional[str] = None
    cart_total_cents: Optional[int] = None
    action: Action = field(default=Action.ADD_TO_CART, init=False)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["action"] = self.action.value
        result[EventProperty.FUNNEL_STEP] = FunnelStep.CART_ADD.value
        result[EventProperty.DEVICE_NAME] = self.device_name
        result[EventProperty.DEVICE_CATEGORY] = self.device_category.value

        if self.offer_value is not None:
            result[EventProperty.OFFER_VALUE] = self.offer_value
        if self.plan_id:
            result[EventProperty.PLAN_ID] = self.plan_id
        if self.cart_total_cents is not None:
            result[EventProperty.CART_TOTAL_CENTS] = self.cart_total_cents

        return result


@dataclass
class CheckoutStartEvent(ApplePortInEvent):
    """
    Event for tracking checkout initiation.

    Fired when a user begins the checkout process.
    """
    plan_id: Optional[str] = None
    offer_value: Optional[int] = None
    action: Action = field(default=Action.CHECKOUT_START, init=False)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["action"] = self.action.value
        result[EventProperty.FUNNEL_STEP] = FunnelStep.CHECKOUT_START.value

        if self.plan_id:
            result[EventProperty.PLAN_ID] = self.plan_id
        if self.offer_value is not None:
            result[EventProperty.OFFER_VALUE] = self.offer_value

        return result


@dataclass
class CheckoutCompleteEvent(ApplePortInEvent):
    """
    Event for tracking successful order completion.

    Fired when a user successfully completes their purchase.
    This is the primary conversion event for the funnel.
    """
    order_id: str = ""
    order_total_cents: int = 0
    plan_id: Optional[str] = None
    offer_value: Optional[int] = None
    payment_method: Optional[PaymentMethod] = None
    action: Action = field(default=Action.CHECKOUT_COMPLETE, init=False)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["action"] = self.action.value
        result[EventProperty.FUNNEL_STEP] = FunnelStep.CHECKOUT_COMPLETE.value
        result[EventProperty.ORDER_ID] = self.order_id
        result[EventProperty.ORDER_TOTAL_CENTS] = self.order_total_cents

        if self.plan_id:
            result[EventProperty.PLAN_ID] = self.plan_id
        if self.offer_value is not None:
            result[EventProperty.OFFER_VALUE] = self.offer_value
        if self.payment_method:
            result[EventProperty.PAYMENT_METHOD] = self.payment_method.value

        return result


@dataclass
class FunnelAbandonEvent(ApplePortInEvent):
    """
    Event for tracking funnel abandonment.

    Fired when a user leaves the funnel without completing a purchase.
    Used to identify drop-off points and abandonment patterns.
    """
    abandon_step: FunnelStep = field(default=FunnelStep.LANDING_PAGE)
    time_in_funnel_ms: Optional[int] = None
    action: Action = field(default=Action.FUNNEL_ABANDON, init=False)

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["action"] = self.action.value
        result[EventProperty.ABANDON_STEP] = self.abandon_step.value
        result[EventProperty.STEP_NUMBER] = FunnelStep.get_step_number(self.abandon_step)

        if self.time_in_funnel_ms is not None:
            result[EventProperty.TIME_IN_FUNNEL_MS] = self.time_in_funnel_ms

        return result


def generate_session_id() -> str:
    """
    Generate a unique session ID for tracking a user's journey.

    Returns a UUID string that should be persisted across all events
    in a single user session.
    """
    return str(uuid.uuid4())
