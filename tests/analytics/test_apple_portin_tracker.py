"""
Unit Tests for Apple Port-In Funnel Tracker

Tests the tracker class that provides the main interface for
instrumenting the Apple port-in purchase journey.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from typing import List, Dict

from analytics.apple_portin.constants import (
    Channel,
    FunnelStep,
    EligibilityResult,
    EligibilityFailureReason,
    DeviceCategory,
    PaymentMethod,
)
from analytics.apple_portin.tracker import (
    ApplePortInTracker,
    create_tracker,
)


class TestApplePortInTracker(unittest.TestCase):
    """Tests for ApplePortInTracker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.events_captured: List[Dict] = []

        def capture_event(event: Dict) -> None:
            self.events_captured.append(event)

        self.tracker = ApplePortInTracker(
            channel=Channel.WEB,
            event_handlers=[capture_event],
        )

    def tearDown(self):
        """Clean up after tests."""
        self.events_captured.clear()

    def test_initialization(self):
        """Tracker should initialize with default values."""
        tracker = ApplePortInTracker(channel=Channel.WEB)

        self.assertEqual(tracker.channel, Channel.WEB)
        self.assertIsNotNone(tracker.session_id)
        self.assertIsNone(tracker.funnel_start_time)
        self.assertIsNone(tracker.current_step)

    def test_custom_session_id(self):
        """Should accept custom session ID."""
        tracker = ApplePortInTracker(
            channel=Channel.WEB,
            session_id="custom-session-123",
        )

        self.assertEqual(tracker.session_id, "custom-session-123")

    def test_track_landing_page(self):
        """Should track landing page view and set funnel start time."""
        event = self.tracker.track_landing_page(offer_id="PROMO_2024")

        self.assertEqual(len(self.events_captured), 1)
        self.assertEqual(self.events_captured[0]["funnel_step"], "landing_page")
        self.assertEqual(self.events_captured[0]["offer_id"], "PROMO_2024")
        self.assertIsNotNone(self.tracker.funnel_start_time)
        self.assertEqual(self.tracker.current_step, FunnelStep.LANDING_PAGE)

    def test_track_offer_view(self):
        """Should track offer view with offer details."""
        event = self.tracker.track_offer_view(
            offer_id="PROMO_2024",
            apple_sku="IPHONE15PRO256",
        )

        self.assertEqual(len(self.events_captured), 1)
        self.assertEqual(self.events_captured[0]["funnel_step"], "offer_view")
        self.assertEqual(self.events_captured[0]["offer_id"], "PROMO_2024")
        self.assertEqual(self.events_captured[0]["apple_sku"], "IPHONE15PRO256")
        self.assertEqual(self.tracker.current_step, FunnelStep.OFFER_VIEW)

    def test_track_eligibility_check_pass(self):
        """Should track passing eligibility check."""
        event = self.tracker.track_eligibility_check(
            result=EligibilityResult.PASS,
            carrier_from="Verizon",
            check_duration_ms=250,
        )

        self.assertEqual(len(self.events_captured), 1)
        self.assertEqual(self.events_captured[0]["action"], "EligibilityCheck")
        self.assertEqual(self.events_captured[0]["result"], "pass")
        self.assertEqual(self.events_captured[0]["carrier_from"], "Verizon")
        self.assertEqual(self.events_captured[0]["check_duration_ms"], 250)

    def test_track_eligibility_check_fail(self):
        """Should track failing eligibility check with reason."""
        event = self.tracker.track_eligibility_check(
            result=EligibilityResult.FAIL,
            failure_reason=EligibilityFailureReason.INVALID_CARRIER,
            carrier_from="regional_carrier",
        )

        self.assertEqual(self.events_captured[0]["result"], "fail")
        self.assertEqual(self.events_captured[0]["failure_reason"], "INVALID_CARRIER")

    def test_track_add_to_cart(self):
        """Should track add to cart with device details."""
        event = self.tracker.track_add_to_cart(
            apple_sku="IPHONE15PRO256",
            device_name="iPhone 15 Pro 256GB",
            device_category=DeviceCategory.IPHONE,
            offer_value=80000,
            plan_id="UNLIMITED_PLUS",
            cart_total_cents=99900,
        )

        captured = self.events_captured[0]
        self.assertEqual(captured["action"], "AddToCart")
        self.assertEqual(captured["apple_sku"], "IPHONE15PRO256")
        self.assertEqual(captured["device_name"], "iPhone 15 Pro 256GB")
        self.assertEqual(captured["device_category"], "iPhone")
        self.assertEqual(captured["cart_total_cents"], 99900)

    def test_track_checkout_start(self):
        """Should track checkout initiation."""
        event = self.tracker.track_checkout_start(
            plan_id="UNLIMITED_PLUS",
            offer_value=80000,
        )

        self.assertEqual(self.events_captured[0]["action"], "CheckoutStart")
        self.assertEqual(self.events_captured[0]["plan_id"], "UNLIMITED_PLUS")
        self.assertEqual(self.events_captured[0]["offer_value"], 80000)

    def test_track_checkout_complete(self):
        """Should track successful checkout completion."""
        event = self.tracker.track_checkout_complete(
            order_id="ORD-2024-123456",
            order_total_cents=99900,
            payment_method=PaymentMethod.CREDIT_CARD,
            offer_value=80000,
        )

        captured = self.events_captured[0]
        self.assertEqual(captured["action"], "CheckoutComplete")
        self.assertEqual(captured["order_id"], "ORD-2024-123456")
        self.assertEqual(captured["order_total_cents"], 99900)
        self.assertEqual(captured["payment_method"], "credit_card")

    def test_track_funnel_abandon(self):
        """Should track funnel abandonment."""
        # First set current step
        self.tracker.track_landing_page()
        self.tracker.track_offer_view(offer_id="PROMO")

        event = self.tracker.track_funnel_abandon()

        captured = self.events_captured[-1]
        self.assertEqual(captured["action"], "FunnelAbandon")
        self.assertEqual(captured["abandon_step"], "offer_view")

    def test_track_funnel_abandon_explicit_step(self):
        """Should track abandonment at explicit step."""
        event = self.tracker.track_funnel_abandon(
            abandon_step=FunnelStep.ELIGIBILITY_CHECK
        )

        self.assertEqual(self.events_captured[0]["abandon_step"], "eligibility_check")

    def test_session_state_tracking(self):
        """Should track selected items across events."""
        self.tracker.track_landing_page(offer_id="PROMO_2024")
        self.tracker.track_offer_view(
            offer_id="PROMO_2024",
            apple_sku="IPHONE15PRO256"
        )
        self.tracker.track_add_to_cart(
            apple_sku="IPHONE15PRO256",
            device_name="iPhone 15 Pro",
            device_category=DeviceCategory.IPHONE,
            plan_id="UNLIMITED_PLUS",
        )

        state = self.tracker.get_session_state()

        self.assertEqual(state["selected_sku"], "IPHONE15PRO256")
        self.assertEqual(state["selected_offer"], "PROMO_2024")
        self.assertEqual(state["selected_plan"], "UNLIMITED_PLUS")

    def test_reset_session(self):
        """Should reset session state and generate new ID."""
        old_session_id = self.tracker.session_id
        self.tracker.track_landing_page(offer_id="PROMO")
        self.tracker._selected_sku = "SKU123"

        new_session_id = self.tracker.reset_session()

        self.assertNotEqual(old_session_id, new_session_id)
        self.assertEqual(self.tracker.session_id, new_session_id)
        self.assertIsNone(self.tracker.funnel_start_time)
        self.assertIsNone(self.tracker.current_step)
        self.assertIsNone(self.tracker._selected_sku)

    def test_time_in_funnel_calculation(self):
        """Should calculate time spent in funnel."""
        self.tracker.track_landing_page()

        # Wait a small amount (mock this in real tests)
        time_ms = self.tracker._get_time_in_funnel_ms()

        self.assertIsNotNone(time_ms)
        self.assertGreaterEqual(time_ms, 0)

    def test_event_handler_error_handling(self):
        """Should continue dispatching if one handler fails."""
        events_received = []

        def failing_handler(event):
            raise Exception("Handler error")

        def working_handler(event):
            events_received.append(event)

        tracker = ApplePortInTracker(
            channel=Channel.WEB,
            event_handlers=[failing_handler, working_handler],
        )

        # Should not raise
        tracker.track_landing_page()

        # Working handler should still receive event
        self.assertEqual(len(events_received), 1)

    def test_add_remove_event_handler(self):
        """Should support adding and removing handlers."""
        handler = MagicMock()

        self.tracker.add_event_handler(handler)
        self.tracker.track_landing_page()
        self.assertEqual(handler.call_count, 1)

        self.tracker.remove_event_handler(handler)
        self.tracker.track_offer_view(offer_id="TEST")
        self.assertEqual(handler.call_count, 1)  # Still 1, not called again


class TestFullFunnelJourney(unittest.TestCase):
    """Integration tests for complete funnel journeys."""

    def setUp(self):
        """Set up test fixtures."""
        self.events: List[Dict] = []
        self.tracker = ApplePortInTracker(
            channel=Channel.WEB,
            event_handlers=[lambda e: self.events.append(e)],
        )

    def test_successful_purchase_journey(self):
        """Should track complete successful purchase."""
        # User lands on page
        self.tracker.track_landing_page(offer_id="PROMO_Q1_2024")

        # Views offer
        self.tracker.track_offer_view(
            offer_id="PROMO_Q1_2024",
            apple_sku="IPHONE15PRO256",
        )

        # Passes eligibility
        self.tracker.track_eligibility_check(
            result=EligibilityResult.PASS,
            carrier_from="Verizon",
        )

        # Selects device
        self.tracker.track_device_selection(
            apple_sku="IPHONE15PRO256",
        )

        # Selects plan
        self.tracker.track_plan_selection(plan_id="UNLIMITED_PLUS")

        # Adds to cart
        self.tracker.track_add_to_cart(
            apple_sku="IPHONE15PRO256",
            device_name="iPhone 15 Pro 256GB",
            device_category=DeviceCategory.IPHONE,
            offer_value=80000,
            plan_id="UNLIMITED_PLUS",
            cart_total_cents=119900,
        )

        # Starts checkout
        self.tracker.track_checkout_start()

        # Completes purchase
        self.tracker.track_checkout_complete(
            order_id="ORD-2024-001",
            order_total_cents=119900,
            payment_method=PaymentMethod.APPLE_PAY,
        )

        # Verify all events captured
        self.assertEqual(len(self.events), 8)

        # Verify funnel progression
        funnel_steps = [e.get("funnel_step") for e in self.events]
        expected_steps = [
            "landing_page",
            "offer_view",
            "eligibility_check",
            "device_selection",
            "plan_selection",
            "cart_add",
            "checkout_start",
            "checkout_complete",
        ]
        self.assertEqual(funnel_steps, expected_steps)

        # Verify session ID is consistent
        session_ids = set(e["session_id"] for e in self.events)
        self.assertEqual(len(session_ids), 1)

    def test_eligibility_failure_journey(self):
        """Should track journey ending in eligibility failure."""
        self.tracker.track_landing_page(offer_id="PROMO_2024")
        self.tracker.track_offer_view(
            offer_id="PROMO_2024",
            apple_sku="IPHONE15PRO256",
        )
        self.tracker.track_eligibility_check(
            result=EligibilityResult.FAIL,
            failure_reason=EligibilityFailureReason.CREDIT_CHECK_FAILED,
        )
        self.tracker.track_funnel_abandon()

        self.assertEqual(len(self.events), 4)

        # Verify failure is captured
        eligibility_event = self.events[2]
        self.assertEqual(eligibility_event["result"], "fail")
        self.assertEqual(eligibility_event["failure_reason"], "CREDIT_CHECK_FAILED")

        # Verify abandonment is captured
        abandon_event = self.events[3]
        self.assertEqual(abandon_event["action"], "FunnelAbandon")


class TestCreateTracker(unittest.TestCase):
    """Tests for create_tracker convenience function."""

    def test_creates_tracker_with_defaults(self):
        """Should create tracker with default settings."""
        tracker = create_tracker()

        self.assertEqual(tracker.channel, Channel.WEB)
        self.assertIsNotNone(tracker.session_id)

    def test_creates_tracker_with_custom_channel(self):
        """Should create tracker with specified channel."""
        tracker = create_tracker(channel=Channel.MOBILE_WEB)

        self.assertEqual(tracker.channel, Channel.MOBILE_WEB)

    def test_creates_tracker_with_custom_session(self):
        """Should create tracker with specified session ID."""
        tracker = create_tracker(session_id="my-session")

        self.assertEqual(tracker.session_id, "my-session")


if __name__ == "__main__":
    unittest.main()
