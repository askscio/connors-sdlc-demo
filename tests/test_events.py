"""
Tests for the Event Emitter system.

Tests that events are correctly emitted for downstream notification
systems (SE-5035) to consume.
"""

import pytest
from datetime import datetime, date
from decimal import Decimal

from international_usage.models import (
    UsageType,
    ThresholdType,
    PlanType,
    UsageAllowance,
    CustomerUsageState,
    ThresholdEvent,
    EventType,
)
from international_usage.events import (
    EventEmitter,
    EventSubscriber,
    InMemoryEventEmitter,
    LoggingSubscriber,
    NotificationServiceSubscriber,
    CallbackSubscriber,
    create_event_emitter_with_default_subscribers,
)


class TestThresholdEvent:
    """Tests for ThresholdEvent creation."""

    def test_create_50_percent_event(self):
        """Test creating a 50% threshold event."""
        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
        )
        state = CustomerUsageState(
            customer_id="cust_001",
            allowance=allowance,
            current_volume=Decimal("500"),
        )

        event = ThresholdEvent.create_50_percent_event(state)

        assert event.event_type == EventType.THRESHOLD_50_PERCENT
        assert event.customer_id == "cust_001"
        assert event.threshold_percentage == 50
        assert event.current_value == Decimal("500")
        assert event.limit_value == Decimal("1000")
        assert event.actual_percentage == Decimal("50")
        assert event.plan_type == PlanType.INTERNATIONAL_PACKAGE

    def test_event_idempotency_key(self):
        """Test that events have stable idempotency keys."""
        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
            period_start=date(2024, 1, 1),
        )
        state = CustomerUsageState(
            customer_id="cust_001",
            allowance=allowance,
            current_volume=Decimal("500"),
        )

        event1 = ThresholdEvent.create_50_percent_event(state)
        event2 = ThresholdEvent.create_50_percent_event(state)

        # Same customer, event type, and period should have same idempotency key
        assert event1.idempotency_key == event2.idempotency_key


class TestInMemoryEventEmitter:
    """Tests for the InMemoryEventEmitter."""

    def test_emit_to_subscribers(self):
        """Test that events are emitted to subscribers."""
        emitter = InMemoryEventEmitter()
        received = []

        def callback(event):
            received.append(event)
            return True

        subscriber = CallbackSubscriber(callback, "test_sub")
        emitter.subscribe(EventType.THRESHOLD_50_PERCENT, subscriber)

        event = ThresholdEvent(
            event_id="evt_001",
            event_type=EventType.THRESHOLD_50_PERCENT,
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            threshold_percentage=50,
            current_value=Decimal("500"),
            limit_value=Decimal("1000"),
            actual_percentage=Decimal("50"),
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
        )

        success = emitter.emit(event)

        assert success
        assert len(received) == 1
        assert received[0].event_id == "evt_001"

    def test_emit_to_multiple_subscribers(self):
        """Test emitting to multiple subscribers."""
        emitter = InMemoryEventEmitter()
        received1 = []
        received2 = []

        sub1 = CallbackSubscriber(lambda e: received1.append(e) or True, "sub1")
        sub2 = CallbackSubscriber(lambda e: received2.append(e) or True, "sub2")

        emitter.subscribe(EventType.THRESHOLD_50_PERCENT, sub1)
        emitter.subscribe(EventType.THRESHOLD_50_PERCENT, sub2)

        event = ThresholdEvent(
            event_id="evt_001",
            event_type=EventType.THRESHOLD_50_PERCENT,
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            threshold_percentage=50,
            current_value=Decimal("500"),
            limit_value=Decimal("1000"),
            actual_percentage=Decimal("50"),
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
        )

        emitter.emit(event)

        assert len(received1) == 1
        assert len(received2) == 1

    def test_idempotent_emission(self):
        """Test that duplicate events are not re-emitted."""
        emitter = InMemoryEventEmitter()
        received = []

        subscriber = CallbackSubscriber(lambda e: received.append(e) or True, "test")
        emitter.subscribe(EventType.THRESHOLD_50_PERCENT, subscriber)

        event = ThresholdEvent(
            event_id="evt_001",
            event_type=EventType.THRESHOLD_50_PERCENT,
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            threshold_percentage=50,
            current_value=Decimal("500"),
            limit_value=Decimal("1000"),
            actual_percentage=Decimal("50"),
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            idempotency_key="unique_key_123",
        )

        # Emit twice
        emitter.emit(event)
        emitter.emit(event)

        # Should only receive once
        assert len(received) == 1

    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        emitter = InMemoryEventEmitter()
        received = []

        subscriber = CallbackSubscriber(lambda e: received.append(e) or True, "test")
        emitter.subscribe(EventType.THRESHOLD_50_PERCENT, subscriber)
        emitter.unsubscribe(EventType.THRESHOLD_50_PERCENT, subscriber)

        event = ThresholdEvent(
            event_id="evt_001",
            event_type=EventType.THRESHOLD_50_PERCENT,
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            threshold_percentage=50,
            current_value=Decimal("500"),
            limit_value=Decimal("1000"),
            actual_percentage=Decimal("50"),
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
        )

        emitter.emit(event)

        assert len(received) == 0

    def test_get_event_log(self):
        """Test getting the event log."""
        emitter = InMemoryEventEmitter()

        for i in range(3):
            event = ThresholdEvent(
                event_id=f"evt_{i}",
                event_type=EventType.THRESHOLD_50_PERCENT,
                customer_id="cust_001",
                usage_type=UsageType.VOICE_MINUTES,
                threshold_type=ThresholdType.VOLUME,
                threshold_percentage=50,
                current_value=Decimal("500"),
                limit_value=Decimal("1000"),
                actual_percentage=Decimal("50"),
                plan_type=PlanType.INTERNATIONAL_PACKAGE,
                idempotency_key=f"key_{i}",  # Different keys to allow all
            )
            emitter.emit(event)

        log = emitter.get_event_log()
        assert len(log) == 3

    def test_get_events_for_customer(self):
        """Test filtering events by customer."""
        emitter = InMemoryEventEmitter()

        customers = ["cust_001", "cust_002", "cust_001"]
        for i, customer_id in enumerate(customers):
            event = ThresholdEvent(
                event_id=f"evt_{i}",
                event_type=EventType.THRESHOLD_50_PERCENT,
                customer_id=customer_id,
                usage_type=UsageType.VOICE_MINUTES,
                threshold_type=ThresholdType.VOLUME,
                threshold_percentage=50,
                current_value=Decimal("500"),
                limit_value=Decimal("1000"),
                actual_percentage=Decimal("50"),
                plan_type=PlanType.INTERNATIONAL_PACKAGE,
                idempotency_key=f"key_{i}",
            )
            emitter.emit(event)

        cust1_events = emitter.get_events_for_customer("cust_001")
        assert len(cust1_events) == 2

        cust2_events = emitter.get_events_for_customer("cust_002")
        assert len(cust2_events) == 1


class TestNotificationServiceSubscriber:
    """Tests for the NotificationServiceSubscriber (SE-5035 integration)."""

    def test_queues_notifications(self):
        """Test that notifications are queued for delivery."""
        subscriber = NotificationServiceSubscriber()

        event = ThresholdEvent(
            event_id="evt_001",
            event_type=EventType.THRESHOLD_50_PERCENT,
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            threshold_percentage=50,
            current_value=Decimal("500"),
            limit_value=Decimal("1000"),
            actual_percentage=Decimal("50"),
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
        )

        success = subscriber.on_event(event)

        assert success
        pending = subscriber.get_pending_notifications()
        assert len(pending) == 1
        assert pending[0].customer_id == "cust_001"


class TestDefaultEmitter:
    """Tests for the default emitter factory."""

    def test_create_with_default_subscribers(self):
        """Test creating emitter with default subscribers."""
        emitter = create_event_emitter_with_default_subscribers()

        # Should have subscribers for all event types
        event = ThresholdEvent(
            event_id="evt_001",
            event_type=EventType.THRESHOLD_50_PERCENT,
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            threshold_percentage=50,
            current_value=Decimal("500"),
            limit_value=Decimal("1000"),
            actual_percentage=Decimal("50"),
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
        )

        success = emitter.emit(event)
        assert success

        # Should have logged the event
        log = emitter.get_event_log()
        assert len(log) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
