"""
Apple Port-In Funnel Tracker

Provides the main tracking interface for instrumenting the Apple port-in
purchase journey. This class manages session state and provides convenient
methods for firing events at each funnel step.

Usage:
    tracker = ApplePortInTracker(channel=Channel.WEB)
    tracker.track_landing_page()
    tracker.track_offer_view(offer_id="PROMO_2024Q1", apple_sku="IPHONE15PRO256")
    tracker.track_eligibility_check(result=EligibilityResult.PASS)
    ...
"""

from datetime import datetime
from typing import Optional, Callable, List
import logging

from analytics.apple_portin.constants import (
    Channel,
    FunnelStep,
    EligibilityResult,
    EligibilityFailureReason,
    DeviceCategory,
    PaymentMethod,
)
from analytics.apple_portin.events import (
    ApplePortInEvent,
    FunnelViewEvent,
    EligibilityCheckEvent,
    AddToCartEvent,
    CheckoutStartEvent,
    CheckoutCompleteEvent,
    FunnelAbandonEvent,
    generate_session_id,
)


logger = logging.getLogger(__name__)


# Type alias for event handlers
EventHandler = Callable[[dict], None]


class ApplePortInTracker:
    """
    Main tracking interface for Apple port-in funnel analytics.

    Manages session state and provides methods for tracking each event
    in the purchase journey. Events are dispatched to registered handlers
    which can send them to the analytics platform.

    Attributes:
        session_id: Unique identifier for the current user session
        channel: The channel where the user is accessing the funnel
        funnel_start_time: Timestamp when the user entered the funnel
        current_step: The most recent funnel step viewed
    """

    def __init__(
        self,
        channel: Channel,
        session_id: Optional[str] = None,
        event_handlers: Optional[List[EventHandler]] = None,
    ):
        """
        Initialize a new tracker instance.

        Args:
            channel: The channel where the user is accessing the funnel
            session_id: Optional session ID (generated if not provided)
            event_handlers: Optional list of callbacks to handle events
        """
        self.session_id = session_id or generate_session_id()
        self.channel = channel
        self.funnel_start_time: Optional[datetime] = None
        self.current_step: Optional[FunnelStep] = None
        self._event_handlers: List[EventHandler] = event_handlers or []

        # State tracking
        self._selected_sku: Optional[str] = None
        self._selected_offer: Optional[str] = None
        self._selected_plan: Optional[str] = None

    def add_event_handler(self, handler: EventHandler) -> None:
        """Register a new event handler."""
        self._event_handlers.append(handler)

    def remove_event_handler(self, handler: EventHandler) -> None:
        """Remove an event handler."""
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)

    def _dispatch_event(self, event: ApplePortInEvent) -> None:
        """
        Dispatch an event to all registered handlers.

        Converts the event to a dictionary and calls each handler.
        Errors in handlers are logged but don't prevent other handlers.
        """
        event_dict = event.to_dict()

        for handler in self._event_handlers:
            try:
                handler(event_dict)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

        # Also log the event for debugging
        logger.debug(f"Event dispatched: {event_dict}")

    def _get_time_in_funnel_ms(self) -> Optional[int]:
        """Calculate time spent in funnel from start to now."""
        if self.funnel_start_time:
            delta = datetime.utcnow() - self.funnel_start_time
            return int(delta.total_seconds() * 1000)
        return None

    # --- Funnel View Tracking ---

    def track_landing_page(
        self,
        offer_id: Optional[str] = None,
    ) -> FunnelViewEvent:
        """
        Track landing page view.

        This should be called when a user first lands on the Apple port-in
        offer page. It marks the start of the funnel journey.
        """
        self.funnel_start_time = datetime.utcnow()
        self.current_step = FunnelStep.LANDING_PAGE
        self._selected_offer = offer_id

        event = FunnelViewEvent(
            session_id=self.session_id,
            channel=self.channel,
            funnel_step=FunnelStep.LANDING_PAGE,
            offer_id=offer_id,
        )
        self._dispatch_event(event)
        return event

    def track_offer_view(
        self,
        offer_id: str,
        apple_sku: Optional[str] = None,
    ) -> FunnelViewEvent:
        """
        Track offer view.

        Called when a user views a specific port-in offer.
        """
        self.current_step = FunnelStep.OFFER_VIEW
        self._selected_offer = offer_id
        if apple_sku:
            self._selected_sku = apple_sku

        event = FunnelViewEvent(
            session_id=self.session_id,
            channel=self.channel,
            funnel_step=FunnelStep.OFFER_VIEW,
            offer_id=offer_id,
            apple_sku=apple_sku,
        )
        self._dispatch_event(event)
        return event

    def track_device_selection(
        self,
        apple_sku: str,
        offer_id: Optional[str] = None,
    ) -> FunnelViewEvent:
        """
        Track device selection step view.

        Called when a user is selecting an Apple device.
        """
        self.current_step = FunnelStep.DEVICE_SELECTION
        self._selected_sku = apple_sku
        if offer_id:
            self._selected_offer = offer_id

        event = FunnelViewEvent(
            session_id=self.session_id,
            channel=self.channel,
            funnel_step=FunnelStep.DEVICE_SELECTION,
            apple_sku=apple_sku,
            offer_id=offer_id or self._selected_offer,
        )
        self._dispatch_event(event)
        return event

    def track_plan_selection(
        self,
        plan_id: Optional[str] = None,
    ) -> FunnelViewEvent:
        """
        Track plan selection step view.

        Called when a user is selecting a service plan.
        """
        self.current_step = FunnelStep.PLAN_SELECTION
        if plan_id:
            self._selected_plan = plan_id

        event = FunnelViewEvent(
            session_id=self.session_id,
            channel=self.channel,
            funnel_step=FunnelStep.PLAN_SELECTION,
            apple_sku=self._selected_sku,
            offer_id=self._selected_offer,
        )
        self._dispatch_event(event)
        return event

    # --- Eligibility Check Tracking ---

    def track_eligibility_check(
        self,
        result: EligibilityResult,
        failure_reason: Optional[EligibilityFailureReason] = None,
        carrier_from: Optional[str] = None,
        check_duration_ms: Optional[int] = None,
    ) -> EligibilityCheckEvent:
        """
        Track eligibility check outcome.

        Called when the system evaluates user eligibility for port-in offers.
        Both pass and fail outcomes should be tracked.

        Args:
            result: Pass or fail outcome
            failure_reason: Reason code if result is fail
            carrier_from: Source carrier for the port-in
            check_duration_ms: Time taken for the eligibility check
        """
        self.current_step = FunnelStep.ELIGIBILITY_CHECK

        event = EligibilityCheckEvent(
            session_id=self.session_id,
            channel=self.channel,
            result=result,
            failure_reason=failure_reason,
            carrier_from=carrier_from,
            check_duration_ms=check_duration_ms,
            apple_sku=self._selected_sku,
            offer_id=self._selected_offer,
        )
        self._dispatch_event(event)
        return event

    # --- Cart Tracking ---

    def track_add_to_cart(
        self,
        apple_sku: str,
        device_name: str,
        device_category: DeviceCategory,
        offer_value: Optional[int] = None,
        plan_id: Optional[str] = None,
        cart_total_cents: Optional[int] = None,
    ) -> AddToCartEvent:
        """
        Track add to cart action.

        Called when a user adds an Apple device to their cart.

        Args:
            apple_sku: Apple device SKU
            device_name: Human-readable device name
            device_category: Device category (iPhone, iPad, etc.)
            offer_value: Discount value in cents
            plan_id: Selected plan identifier
            cart_total_cents: Cart total in cents
        """
        self.current_step = FunnelStep.CART_ADD
        self._selected_sku = apple_sku
        if plan_id:
            self._selected_plan = plan_id

        event = AddToCartEvent(
            session_id=self.session_id,
            channel=self.channel,
            apple_sku=apple_sku,
            device_name=device_name,
            device_category=device_category,
            offer_id=self._selected_offer,
            offer_value=offer_value,
            plan_id=plan_id,
            cart_total_cents=cart_total_cents,
        )
        self._dispatch_event(event)
        return event

    # --- Checkout Tracking ---

    def track_checkout_start(
        self,
        plan_id: Optional[str] = None,
        offer_value: Optional[int] = None,
    ) -> CheckoutStartEvent:
        """
        Track checkout initiation.

        Called when a user begins the checkout process.
        """
        self.current_step = FunnelStep.CHECKOUT_START
        if plan_id:
            self._selected_plan = plan_id

        event = CheckoutStartEvent(
            session_id=self.session_id,
            channel=self.channel,
            apple_sku=self._selected_sku,
            offer_id=self._selected_offer,
            plan_id=plan_id or self._selected_plan,
            offer_value=offer_value,
        )
        self._dispatch_event(event)
        return event

    def track_checkout_complete(
        self,
        order_id: str,
        order_total_cents: int,
        payment_method: Optional[PaymentMethod] = None,
        offer_value: Optional[int] = None,
    ) -> CheckoutCompleteEvent:
        """
        Track successful order completion.

        Called when a user successfully completes their purchase.
        This is the primary conversion event for the funnel.

        Args:
            order_id: Unique order identifier
            order_total_cents: Order total in cents
            payment_method: Payment method used
            offer_value: Discount value applied in cents
        """
        self.current_step = FunnelStep.CHECKOUT_COMPLETE

        event = CheckoutCompleteEvent(
            session_id=self.session_id,
            channel=self.channel,
            order_id=order_id,
            order_total_cents=order_total_cents,
            apple_sku=self._selected_sku,
            offer_id=self._selected_offer,
            plan_id=self._selected_plan,
            offer_value=offer_value,
            payment_method=payment_method,
        )
        self._dispatch_event(event)
        return event

    # --- Abandonment Tracking ---

    def track_funnel_abandon(
        self,
        abandon_step: Optional[FunnelStep] = None,
    ) -> FunnelAbandonEvent:
        """
        Track funnel abandonment.

        Called when a user leaves the funnel without completing a purchase.
        If abandon_step is not provided, uses the current step.

        Args:
            abandon_step: The step where the user abandoned (defaults to current)
        """
        step = abandon_step or self.current_step or FunnelStep.LANDING_PAGE

        event = FunnelAbandonEvent(
            session_id=self.session_id,
            channel=self.channel,
            abandon_step=step,
            time_in_funnel_ms=self._get_time_in_funnel_ms(),
            apple_sku=self._selected_sku,
            offer_id=self._selected_offer,
        )
        self._dispatch_event(event)
        return event

    # --- Session Management ---

    def reset_session(self) -> str:
        """
        Reset the session state and generate a new session ID.

        Returns the new session ID.
        """
        self.session_id = generate_session_id()
        self.funnel_start_time = None
        self.current_step = None
        self._selected_sku = None
        self._selected_offer = None
        self._selected_plan = None
        return self.session_id

    def get_session_state(self) -> dict:
        """Return the current session state for debugging."""
        return {
            "session_id": self.session_id,
            "channel": self.channel.value,
            "funnel_start_time": self.funnel_start_time.isoformat() if self.funnel_start_time else None,
            "current_step": self.current_step.value if self.current_step else None,
            "selected_sku": self._selected_sku,
            "selected_offer": self._selected_offer,
            "selected_plan": self._selected_plan,
            "time_in_funnel_ms": self._get_time_in_funnel_ms(),
        }


# Convenience function for creating a default tracker
def create_tracker(
    channel: Channel = Channel.WEB,
    session_id: Optional[str] = None,
) -> ApplePortInTracker:
    """
    Create a new Apple port-in tracker with default settings.

    Args:
        channel: The channel where tracking is occurring
        session_id: Optional existing session ID

    Returns:
        Configured ApplePortInTracker instance
    """
    return ApplePortInTracker(channel=channel, session_id=session_id)
