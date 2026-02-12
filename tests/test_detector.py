"""
Tests for the Usage Detection Service (SE-5034).

Per acceptance criteria:
- Test accounts reliably generate 50% events at the correct usage thresholds
"""

import pytest
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


from international_usage.models import (
    UsageType,
    ThresholdType,
    CustomerSegment,
    PlanType,
    UsageRecord,
    UsageAllowance,
    CustomerUsageState,
    ThresholdEvent,
    EventType,
    MNOFeedBatch,
)
from international_usage.rules import (
    ThresholdRule,
    ThresholdRulesEngine,
    default_rules_engine,
)
from international_usage.detector import (
    UsageDetector,
    DetectionResult,
    DetectorConfig,
    MNOFeedIngester,
)
from international_usage.events import (
    InMemoryEventEmitter,
    CallbackSubscriber,
)


class TestUsageDetector:
    """Tests for the core UsageDetector class."""

    def test_register_allowance(self):
        """Test that allowances can be registered for customers."""
        detector = UsageDetector()
        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )

        detector.register_allowance(allowance)
        state = detector.get_customer_state("cust_001")

        assert state is not None
        assert state.customer_id == "cust_001"
        assert state.allowance.volume_limit == Decimal("1000")

    def test_process_record_below_threshold(self):
        """Test processing a record that doesn't cross threshold."""
        detector = UsageDetector()

        # Register allowance with 1000 minute limit
        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        detector.register_allowance(allowance)

        # Process 100 minutes (10% - below 50% threshold)
        record = UsageRecord(
            record_id="rec_001",
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            amount=Decimal("100"),
            timestamp=utc_now(),
            country_code="GB",
        )

        result = detector.process_record(record)

        assert result.success
        assert result.records_processed == 1
        assert result.events_emitted == 0
        assert len(result.thresholds_crossed) == 0

    def test_process_record_crosses_50_percent_threshold(self):
        """
        Test that 50% threshold event is generated correctly.

        This is the core acceptance criteria for SE-5034:
        Test accounts reliably generate 50% events at correct thresholds.
        """
        emitted_events = []
        emitter = InMemoryEventEmitter()

        # Add callback subscriber to capture events
        def capture_event(event: ThresholdEvent) -> bool:
            emitted_events.append(event)
            return True

        subscriber = CallbackSubscriber(capture_event, "test_subscriber")
        emitter.subscribe(EventType.THRESHOLD_50_PERCENT, subscriber)

        detector = UsageDetector(event_emitter=emitter)

        # Register allowance with 1000 minute limit
        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        detector.register_allowance(allowance)

        # Process 500 minutes (exactly 50%)
        record = UsageRecord(
            record_id="rec_001",
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            amount=Decimal("500"),
            timestamp=utc_now(),
            country_code="GB",
        )

        result = detector.process_record(record)

        assert result.success
        assert result.records_processed == 1
        assert result.events_emitted == 1
        assert (result.thresholds_crossed[0] == ("cust_001", 50))

        # Verify the emitted event
        assert len(emitted_events) == 1
        event = emitted_events[0]
        assert event.event_type == EventType.THRESHOLD_50_PERCENT
        assert event.customer_id == "cust_001"
        assert event.threshold_percentage == 50
        assert event.actual_percentage == Decimal("50")
        assert event.current_value == Decimal("500")
        assert event.limit_value == Decimal("1000")

    def test_process_record_crosses_multiple_thresholds(self):
        """Test that multiple thresholds can be crossed in sequence."""
        emitter = InMemoryEventEmitter()
        detector = UsageDetector(event_emitter=emitter)

        # Register allowance with 1000 minute limit
        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        detector.register_allowance(allowance)

        # Process 500 minutes - crosses 50%
        record1 = UsageRecord(
            record_id="rec_001",
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            amount=Decimal("500"),
            timestamp=utc_now(),
            country_code="GB",
        )
        result1 = detector.process_record(record1)
        assert result1.events_emitted == 1

        # Process another 300 minutes - crosses 75%
        record2 = UsageRecord(
            record_id="rec_002",
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            amount=Decimal("300"),
            timestamp=utc_now(),
            country_code="FR",
        )
        result2 = detector.process_record(record2)
        assert result2.events_emitted == 1

        # Verify state
        state = detector.get_customer_state("cust_001")
        assert state.current_volume == Decimal("800")
        assert len(state.thresholds_notified) == 2
        assert EventType.THRESHOLD_50_PERCENT in state.thresholds_notified
        assert EventType.THRESHOLD_75_PERCENT in state.thresholds_notified

    def test_no_duplicate_threshold_events(self):
        """Test that threshold events are not duplicated."""
        emitter = InMemoryEventEmitter()
        detector = UsageDetector(event_emitter=emitter)

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        detector.register_allowance(allowance)

        # First record crosses 50%
        record1 = UsageRecord(
            record_id="rec_001",
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            amount=Decimal("500"),
            timestamp=utc_now(),
            country_code="GB",
        )
        result1 = detector.process_record(record1)
        assert result1.events_emitted == 1

        # Second record keeps us above 50% but shouldn't trigger again
        record2 = UsageRecord(
            record_id="rec_002",
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            amount=Decimal("50"),
            timestamp=utc_now(),
            country_code="GB",
        )
        result2 = detector.process_record(record2)
        assert result2.events_emitted == 0  # No duplicate event

    def test_spend_based_threshold(self):
        """Test threshold detection based on spend amount."""
        emitter = InMemoryEventEmitter()
        detector = UsageDetector(event_emitter=emitter)

        # Register allowance with $100 spend limit
        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.PAY_AS_YOU_GO,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.SPEND,
            spend_limit=Decimal("100"),
        )
        detector.register_allowance(allowance)

        # Process record with $50 rated amount (50% of spend)
        record = UsageRecord(
            record_id="rec_001",
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            amount=Decimal("30"),  # Volume doesn't matter for spend-based
            timestamp=utc_now(),
            country_code="GB",
            rated_amount=Decimal("50"),
        )

        result = detector.process_record(record)

        assert result.success
        assert result.events_emitted == 1
        assert result.thresholds_crossed[0] == ("cust_001", 50)

    def test_reset_customer_state(self):
        """Test that customer state can be reset (billing cycle boundary)."""
        detector = UsageDetector()

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        detector.register_allowance(allowance)

        # Add usage
        record = UsageRecord(
            record_id="rec_001",
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            amount=Decimal("600"),
            timestamp=utc_now(),
            country_code="GB",
        )
        detector.process_record(record)

        # Verify usage accumulated
        state = detector.get_customer_state("cust_001")
        assert state.current_volume == Decimal("600")

        # Reset state
        success = detector.reset_customer_state("cust_001")
        assert success

        # Verify state is reset
        state = detector.get_customer_state("cust_001")
        assert state.current_volume == Decimal("0")
        assert state.current_spend == Decimal("0")
        assert len(state.thresholds_notified) == 0

    def test_no_allowance_returns_error(self):
        """Test that processing without allowance returns error."""
        detector = UsageDetector()

        record = UsageRecord(
            record_id="rec_001",
            customer_id="unknown_customer",
            usage_type=UsageType.VOICE_MINUTES,
            amount=Decimal("100"),
            timestamp=utc_now(),
            country_code="GB",
        )

        result = detector.process_record(record)

        assert not result.success
        assert len(result.errors) > 0
        assert "No allowance registered" in result.errors[0]


class TestMNOFeedIngester:
    """Tests for MNO feed ingestion."""

    def test_ingest_batch_from_raw_data(self):
        """Test ingesting raw MNO feed data."""
        detector = UsageDetector()

        # Register allowance
        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        detector.register_allowance(allowance)

        ingester = MNOFeedIngester(detector, feed_source="test_mno")

        raw_records = [
            {
                "customer_id": "cust_001",
                "usage_type": "voice_minutes",
                "amount": "250",
                "timestamp": utc_now().isoformat(),
                "country_code": "GB",
            },
            {
                "customer_id": "cust_001",
                "usage_type": "voice_minutes",
                "amount": "300",
                "timestamp": utc_now().isoformat(),
                "country_code": "FR",
            },
        ]

        result = ingester.ingest_batch(raw_records)

        assert result.success
        assert result.records_processed == 2
        assert result.events_emitted == 1  # 550/1000 = 55%, crosses 50%

    def test_ingest_batch_handles_parse_errors(self):
        """Test that parse errors are handled gracefully."""
        detector = UsageDetector()
        ingester = MNOFeedIngester(detector)

        raw_records = [
            {
                "customer_id": "cust_001",
                # Missing required fields
            },
        ]

        result = ingester.ingest_batch(raw_records)

        # Should have errors but not crash
        assert len(result.errors) > 0


class TestBatchProcessing:
    """Tests for batch processing of usage records."""

    def test_process_batch(self):
        """Test processing a batch of records."""
        emitter = InMemoryEventEmitter()
        detector = UsageDetector(event_emitter=emitter)

        # Register allowance
        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        detector.register_allowance(allowance)

        # Create batch
        records = [
            UsageRecord(
                record_id=f"rec_{i}",
                customer_id="cust_001",
                usage_type=UsageType.VOICE_MINUTES,
                amount=Decimal("100"),
                timestamp=utc_now(),
                country_code="GB",
            )
            for i in range(6)  # 600 minutes total = 60%
        ]

        batch = MNOFeedBatch(
            batch_id="batch_001",
            source="test_mno",
            records=records,
        )

        result = detector.process_batch(batch)

        assert result.success
        assert result.records_processed == 6
        assert result.events_emitted == 1  # Should emit at 50%


class TestThresholdAccuracy:
    """
    Tests to verify threshold accuracy per SE-5034 acceptance criteria:
    "Test accounts reliably generate 50% events at the correct usage thresholds"
    """

    def test_exact_50_percent_threshold(self):
        """Test exact 50% threshold crossing."""
        emitter = InMemoryEventEmitter()
        detector = UsageDetector(event_emitter=emitter)

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="test_account_1",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        detector.register_allowance(allowance)

        # Add exactly 499 minutes - should NOT trigger
        record1 = UsageRecord(
            record_id="rec_001",
            customer_id="test_account_1",
            usage_type=UsageType.VOICE_MINUTES,
            amount=Decimal("499"),
            timestamp=utc_now(),
            country_code="GB",
        )
        result1 = detector.process_record(record1)
        assert result1.events_emitted == 0  # 49.9% - no event

        # Add 1 more minute to hit exactly 50%
        record2 = UsageRecord(
            record_id="rec_002",
            customer_id="test_account_1",
            usage_type=UsageType.VOICE_MINUTES,
            amount=Decimal("1"),
            timestamp=utc_now(),
            country_code="GB",
        )
        result2 = detector.process_record(record2)
        assert result2.events_emitted == 1  # 50% - event triggered

    def test_threshold_with_fractional_usage(self):
        """Test threshold with fractional usage values."""
        emitter = InMemoryEventEmitter()
        detector = UsageDetector(event_emitter=emitter)

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="test_account_2",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.DATA_MB,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1024.5"),  # Fractional limit
        )
        detector.register_allowance(allowance)

        # Add 512.25 MB (exactly 50%)
        record = UsageRecord(
            record_id="rec_001",
            customer_id="test_account_2",
            usage_type=UsageType.DATA_MB,
            amount=Decimal("512.25"),
            timestamp=utc_now(),
            country_code="DE",
        )
        result = detector.process_record(record)

        assert result.events_emitted == 1
        state = detector.get_customer_state("test_account_2")
        assert state.get_usage_percentage() == Decimal("50")

    def test_multiple_test_accounts(self):
        """Test that multiple test accounts generate events correctly."""
        emitter = InMemoryEventEmitter()
        detector = UsageDetector(event_emitter=emitter)

        # Register multiple test accounts with different plans
        test_accounts = [
            ("test_001", PlanType.INTERNATIONAL_PACKAGE, Decimal("500")),
            ("test_002", PlanType.ROAMING_BUNDLE, Decimal("1000")),
            ("test_003", PlanType.PAY_AS_YOU_GO, Decimal("2000")),
        ]

        for customer_id, plan_type, limit in test_accounts:
            allowance = UsageAllowance(
                allowance_id=f"allow_{customer_id}",
                customer_id=customer_id,
                plan_type=plan_type,
                usage_type=UsageType.VOICE_MINUTES,
                threshold_type=ThresholdType.VOLUME,
                volume_limit=limit,
            )
            detector.register_allowance(allowance)

        # Process 50% usage for each account
        for customer_id, _, limit in test_accounts:
            record = UsageRecord(
                record_id=f"rec_{customer_id}",
                customer_id=customer_id,
                usage_type=UsageType.VOICE_MINUTES,
                amount=limit / 2,  # Exactly 50%
                timestamp=utc_now(),
                country_code="GB",
            )
            result = detector.process_record(record)
            assert result.events_emitted == 1, f"Account {customer_id} should emit event"

        # Verify all accounts have threshold marked
        for customer_id, _, _ in test_accounts:
            state = detector.get_customer_state(customer_id)
            assert EventType.THRESHOLD_50_PERCENT in state.thresholds_notified


class TestDryRunMode:
    """Tests for dry-run mode (testing without emitting events)."""

    def test_dry_run_does_not_emit_events(self):
        """Test that dry-run mode doesn't emit events."""
        config = DetectorConfig(dry_run=True)
        emitter = InMemoryEventEmitter()
        detector = UsageDetector(event_emitter=emitter, config=config)

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        detector.register_allowance(allowance)

        record = UsageRecord(
            record_id="rec_001",
            customer_id="cust_001",
            usage_type=UsageType.VOICE_MINUTES,
            amount=Decimal("500"),
            timestamp=utc_now(),
            country_code="GB",
        )

        result = detector.process_record(record)

        # Should process but not emit
        assert result.records_processed == 1
        assert result.events_emitted == 0
        assert len(emitter.get_event_log()) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
