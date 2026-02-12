"""
Unit Tests for Apple Port-In Funnel Events

Tests the event data classes and their serialization to ensure correct
event payloads for the analytics platform.
"""

import unittest
from datetime import datetime
from unittest.mock import patch

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


class TestConstants(unittest.TestCase):
    """Tests for analytics constants."""

    def test_category_value(self):
        """Category should be 'ApplePortInFunnel'."""
        self.assertEqual(Category.APPLE_PORTIN_FUNNEL.value, "ApplePortInFunnel")

    def test_funnel_step_ordering(self):
        """Funnel steps should have correct sequential order."""
        step_order = FunnelStep.get_step_order()

        self.assertEqual(step_order["landing_page"], 1)
        self.assertEqual(step_order["offer_view"], 2)
        self.assertEqual(step_order["eligibility_check"], 3)
        self.assertEqual(step_order["device_selection"], 4)
        self.assertEqual(step_order["plan_selection"], 5)
        self.assertEqual(step_order["cart_add"], 6)
        self.assertEqual(step_order["checkout_start"], 7)
        self.assertEqual(step_order["checkout_complete"], 8)

    def test_get_step_number(self):
        """get_step_number should return correct order for each step."""
        self.assertEqual(FunnelStep.get_step_number(FunnelStep.LANDING_PAGE), 1)
        self.assertEqual(FunnelStep.get_step_number(FunnelStep.CHECKOUT_COMPLETE), 8)

    def test_eligibility_failure_reasons(self):
        """All expected failure reasons should be defined."""
        expected_reasons = [
            "INVALID_CARRIER",
            "ACCOUNT_TYPE_INELIGIBLE",
            "CREDIT_CHECK_FAILED",
            "EXISTING_CUSTOMER",
            "DEVICE_INELIGIBLE",
            "REGION_INELIGIBLE",
            "TENURE_REQUIREMENT",
            "OFFER_EXPIRED",
            "OFFER_LIMIT_REACHED",
            "SYSTEM_ERROR",
        ]
        actual_reasons = [r.value for r in EligibilityFailureReason]
        self.assertEqual(sorted(expected_reasons), sorted(actual_reasons))


class TestGenerateSessionId(unittest.TestCase):
    """Tests for session ID generation."""

    def test_generates_uuid_string(self):
        """Should generate a valid UUID string."""
        session_id = generate_session_id()
        self.assertIsInstance(session_id, str)
        # UUID format: 8-4-4-4-12 characters
        self.assertEqual(len(session_id), 36)
        self.assertEqual(session_id.count("-"), 4)

    def test_generates_unique_ids(self):
        """Should generate unique IDs on each call."""
        ids = [generate_session_id() for _ in range(100)]
        self.assertEqual(len(ids), len(set(ids)))


class TestFunnelViewEvent(unittest.TestCase):
    """Tests for FunnelViewEvent."""

    def test_basic_event_creation(self):
        """Should create event with required fields."""
        event = FunnelViewEvent(
            session_id="test-session-123",
            channel=Channel.WEB,
            funnel_step=FunnelStep.LANDING_PAGE,
        )

        self.assertEqual(event.session_id, "test-session-123")
        self.assertEqual(event.channel, Channel.WEB)
        self.assertEqual(event.funnel_step, FunnelStep.LANDING_PAGE)
        self.assertEqual(event.category, Category.APPLE_PORTIN_FUNNEL)
        self.assertEqual(event.action, Action.VIEW)

    def test_to_dict_includes_required_fields(self):
        """to_dict should include all required fields."""
        event = FunnelViewEvent(
            session_id="test-session",
            channel=Channel.WEB,
            funnel_step=FunnelStep.OFFER_VIEW,
            offer_id="PROMO_2024",
            apple_sku="IPHONE15PRO256",
        )

        result = event.to_dict()

        self.assertEqual(result["session_id"], "test-session")
        self.assertEqual(result["channel"], "web")
        self.assertEqual(result["category"], "ApplePortInFunnel")
        self.assertEqual(result["action"], "View")
        self.assertEqual(result["funnel_step"], "offer_view")
        self.assertEqual(result["step_number"], 2)
        self.assertEqual(result["offer_id"], "PROMO_2024")
        self.assertEqual(result["apple_sku"], "IPHONE15PRO256")
        self.assertIn("timestamp", result)

    def test_timestamp_format(self):
        """Timestamp should be in ISO 8601 format with Z suffix."""
        event = FunnelViewEvent(
            session_id="test",
            channel=Channel.WEB,
            funnel_step=FunnelStep.LANDING_PAGE,
        )

        result = event.to_dict()
        timestamp = result["timestamp"]

        self.assertTrue(timestamp.endswith("Z"))
        # Should be parseable
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


class TestEligibilityCheckEvent(unittest.TestCase):
    """Tests for EligibilityCheckEvent."""

    def test_pass_event(self):
        """Should create pass event correctly."""
        event = EligibilityCheckEvent(
            session_id="test-session",
            channel=Channel.WEB,
            result=EligibilityResult.PASS,
            carrier_from="Verizon",
            check_duration_ms=245,
        )

        result = event.to_dict()

        self.assertEqual(result["action"], "EligibilityCheck")
        self.assertEqual(result["result"], "pass")
        self.assertEqual(result["carrier_from"], "Verizon")
        self.assertEqual(result["check_duration_ms"], 245)
        self.assertNotIn("failure_reason", result)

    def test_fail_event_with_reason(self):
        """Should include failure reason for failed checks."""
        event = EligibilityCheckEvent(
            session_id="test-session",
            channel=Channel.WEB,
            result=EligibilityResult.FAIL,
            failure_reason=EligibilityFailureReason.INVALID_CARRIER,
            carrier_from="regional_carrier",
        )

        result = event.to_dict()

        self.assertEqual(result["result"], "fail")
        self.assertEqual(result["failure_reason"], "INVALID_CARRIER")
        self.assertEqual(result["carrier_from"], "regional_carrier")


class TestAddToCartEvent(unittest.TestCase):
    """Tests for AddToCartEvent."""

    def test_full_cart_event(self):
        """Should include all cart details."""
        event = AddToCartEvent(
            session_id="test-session",
            channel=Channel.WEB,
            apple_sku="IPHONE15PRO256",
            device_name="iPhone 15 Pro 256GB",
            device_category=DeviceCategory.IPHONE,
            offer_id="PROMO_2024",
            offer_value=80000,
            plan_id="UNLIMITED_PLUS",
            cart_total_cents=99900,
        )

        result = event.to_dict()

        self.assertEqual(result["action"], "AddToCart")
        self.assertEqual(result["apple_sku"], "IPHONE15PRO256")
        self.assertEqual(result["device_name"], "iPhone 15 Pro 256GB")
        self.assertEqual(result["device_category"], "iPhone")
        self.assertEqual(result["offer_id"], "PROMO_2024")
        self.assertEqual(result["offer_value"], 80000)
        self.assertEqual(result["plan_id"], "UNLIMITED_PLUS")
        self.assertEqual(result["cart_total_cents"], 99900)
        self.assertEqual(result["funnel_step"], "cart_add")


class TestCheckoutCompleteEvent(unittest.TestCase):
    """Tests for CheckoutCompleteEvent."""

    def test_complete_checkout_event(self):
        """Should include all checkout completion details."""
        event = CheckoutCompleteEvent(
            session_id="test-session",
            channel=Channel.WEB,
            apple_sku="IPHONE15PRO256",
            offer_id="PROMO_2024",
            order_id="ORD-2024-123456",
            order_total_cents=99900,
            payment_method=PaymentMethod.CREDIT_CARD,
            offer_value=80000,
            plan_id="UNLIMITED_PLUS",
        )

        result = event.to_dict()

        self.assertEqual(result["action"], "CheckoutComplete")
        self.assertEqual(result["order_id"], "ORD-2024-123456")
        self.assertEqual(result["order_total_cents"], 99900)
        self.assertEqual(result["payment_method"], "credit_card")
        self.assertEqual(result["offer_value"], 80000)
        self.assertEqual(result["funnel_step"], "checkout_complete")


class TestFunnelAbandonEvent(unittest.TestCase):
    """Tests for FunnelAbandonEvent."""

    def test_abandonment_event(self):
        """Should include abandonment details."""
        event = FunnelAbandonEvent(
            session_id="test-session",
            channel=Channel.WEB,
            abandon_step=FunnelStep.ELIGIBILITY_CHECK,
            time_in_funnel_ms=45000,
            apple_sku="IPHONE15PRO256",
            offer_id="PROMO_2024",
        )

        result = event.to_dict()

        self.assertEqual(result["action"], "FunnelAbandon")
        self.assertEqual(result["abandon_step"], "eligibility_check")
        self.assertEqual(result["step_number"], 3)
        self.assertEqual(result["time_in_funnel_ms"], 45000)


class TestEventOptionalFields(unittest.TestCase):
    """Tests for optional field handling."""

    def test_optional_fields_excluded_when_none(self):
        """Optional fields should not appear in dict when None."""
        event = FunnelViewEvent(
            session_id="test",
            channel=Channel.WEB,
            funnel_step=FunnelStep.LANDING_PAGE,
            # apple_sku and offer_id not provided
        )

        result = event.to_dict()

        self.assertNotIn("apple_sku", result)
        self.assertNotIn("offer_id", result)

    def test_optional_fields_included_when_set(self):
        """Optional fields should appear when provided."""
        event = FunnelViewEvent(
            session_id="test",
            channel=Channel.WEB,
            funnel_step=FunnelStep.LANDING_PAGE,
            apple_sku="SKU123",
            offer_id="OFFER456",
        )

        result = event.to_dict()

        self.assertEqual(result["apple_sku"], "SKU123")
        self.assertEqual(result["offer_id"], "OFFER456")


if __name__ == "__main__":
    unittest.main()
