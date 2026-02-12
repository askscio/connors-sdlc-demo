"""
Usage Detection Service (SE-5034 core implementation).

This service:
1. Ingests international usage + rating data from MNO feeds
2. Computes customer international usage according to SE-5033 rules
3. Emits "50% reached" events when thresholds are crossed
4. Ensures performance/data freshness meets latency targets
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Callable
import logging

from international_usage.models import (
    UsageRecord,
    UsageAllowance,
    CustomerUsageState,
    ThresholdEvent,
    EventType,
    MNOFeedBatch,
    UsageType,
    ThresholdType,
    PlanType,
    utc_now,
)
from international_usage.rules import ThresholdRulesEngine, default_rules_engine
from international_usage.events import EventEmitter, InMemoryEventEmitter

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Result of processing a usage record or batch."""
    records_processed: int = 0
    events_emitted: int = 0
    errors: list[str] = field(default_factory=list)
    processing_time_ms: float = 0
    thresholds_crossed: list[tuple[str, int]] = field(default_factory=list)  # (customer_id, threshold)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


@dataclass
class DetectorConfig:
    """Configuration for the usage detector."""

    # Latency targets (per SE-5034 acceptance criteria)
    max_processing_latency_ms: int = 1000  # Max time to process a single record
    max_event_emission_latency_ms: int = 500  # Max time to emit an event
    max_feed_staleness_minutes: int = 15  # Max age of MNO feed data

    # Batch processing settings
    batch_size: int = 100
    parallel_processing: bool = True

    # Feature flags
    emit_events: bool = True
    log_all_records: bool = False
    dry_run: bool = False  # If True, don't update state or emit events


class UsageDetector:
    """
    Main detection service for international usage thresholds.

    This is the core implementation of SE-5034. It:
    - Ingests usage records from MNO feeds
    - Maintains customer usage state
    - Evaluates threshold rules
    - Emits events when thresholds are crossed
    """

    def __init__(
        self,
        rules_engine: Optional[ThresholdRulesEngine] = None,
        event_emitter: Optional[EventEmitter] = None,
        config: Optional[DetectorConfig] = None,
    ):
        self._rules_engine = rules_engine or default_rules_engine()
        self._event_emitter = event_emitter or InMemoryEventEmitter()
        self._config = config or DetectorConfig()

        # In-memory state (in production, this would be backed by a database)
        self._customer_states: dict[str, CustomerUsageState] = {}
        self._customer_allowances: dict[str, UsageAllowance] = {}

        # Metrics
        self._records_processed = 0
        self._events_emitted = 0
        self._last_processing_time: Optional[datetime] = None

    def register_allowance(self, allowance: UsageAllowance) -> None:
        """
        Register a customer's usage allowance.

        This sets up the limits against which thresholds are calculated.
        Must be called before processing usage records for a customer.
        """
        self._customer_allowances[allowance.customer_id] = allowance

        # Initialize customer state if not exists
        if allowance.customer_id not in self._customer_states:
            self._customer_states[allowance.customer_id] = CustomerUsageState(
                customer_id=allowance.customer_id,
                allowance=allowance,
            )
        else:
            # Update allowance in existing state
            self._customer_states[allowance.customer_id].allowance = allowance

        logger.info(
            f"Registered allowance for customer {allowance.customer_id}: "
            f"{allowance.plan_type.value}, limit={allowance.get_limit()}"
        )

    def get_customer_state(self, customer_id: str) -> Optional[CustomerUsageState]:
        """Get the current usage state for a customer."""
        return self._customer_states.get(customer_id)

    def process_record(self, record: UsageRecord) -> DetectionResult:
        """
        Process a single usage record and check for threshold crossings.

        This is the core detection loop:
        1. Update customer's cumulative usage
        2. Evaluate threshold rules
        3. Emit events for any crossed thresholds
        """
        start_time = utc_now()
        result = DetectionResult()

        try:
            # Get or create customer state
            state = self._get_or_create_state(record.customer_id)
            if state is None:
                result.errors.append(
                    f"No allowance registered for customer {record.customer_id}"
                )
                return result

            # Update usage totals
            self._update_usage(state, record)
            result.records_processed = 1

            # Evaluate thresholds
            crossed_thresholds = self._rules_engine.evaluate_thresholds(state)

            # Emit events for crossed thresholds
            for threshold_pct, event_type in crossed_thresholds:
                if self._config.emit_events and not self._config.dry_run:
                    event = self._create_event(state, event_type, record)
                    success = self._event_emitter.emit(event)
                    if success:
                        state.mark_threshold_notified(event_type)
                        result.events_emitted += 1
                        result.thresholds_crossed.append(
                            (record.customer_id, threshold_pct)
                        )
                        self._events_emitted += 1
                        logger.info(
                            f"Customer {record.customer_id} crossed {threshold_pct}% threshold"
                        )

            self._records_processed += 1
            self._last_processing_time = utc_now()

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"Error processing record {record.record_id}: {e}")

        result.processing_time_ms = (
            utc_now() - start_time
        ).total_seconds() * 1000

        # Check latency target
        if result.processing_time_ms > self._config.max_processing_latency_ms:
            logger.warning(
                f"Processing latency {result.processing_time_ms}ms exceeded target "
                f"{self._config.max_processing_latency_ms}ms"
            )

        return result

    def process_batch(self, batch: MNOFeedBatch) -> DetectionResult:
        """
        Process a batch of usage records from an MNO feed.

        Checks feed staleness and processes records in sequence.
        """
        start_time = utc_now()
        result = DetectionResult()

        # Check feed staleness
        if batch.feed_timestamp:
            staleness_minutes = (
                batch.received_at - batch.feed_timestamp
            ).total_seconds() / 60
            if staleness_minutes > self._config.max_feed_staleness_minutes:
                logger.warning(
                    f"Feed batch {batch.batch_id} is {staleness_minutes:.1f} minutes old, "
                    f"exceeds target {self._config.max_feed_staleness_minutes} minutes"
                )

        # Process each record
        for record in batch.records:
            record_result = self.process_record(record)
            result.records_processed += record_result.records_processed
            result.events_emitted += record_result.events_emitted
            result.errors.extend(record_result.errors)
            result.thresholds_crossed.extend(record_result.thresholds_crossed)

        result.processing_time_ms = (
            utc_now() - start_time
        ).total_seconds() * 1000

        batch.processed_at = utc_now()

        logger.info(
            f"Processed batch {batch.batch_id}: {result.records_processed} records, "
            f"{result.events_emitted} events, {result.processing_time_ms:.1f}ms"
        )

        return result

    def reset_customer_state(self, customer_id: str) -> bool:
        """
        Reset a customer's usage state (e.g., at billing cycle boundary).

        Per SE-5033: Reset behavior depends on rule configuration.
        """
        state = self._customer_states.get(customer_id)
        if state is None:
            return False

        state.current_volume = Decimal("0")
        state.current_spend = Decimal("0")
        state.thresholds_notified.clear()
        state.last_threshold_crossed = None
        state.last_updated = utc_now()

        logger.info(f"Reset usage state for customer {customer_id}")
        return True

    def get_metrics(self) -> dict:
        """Get detector metrics for monitoring."""
        return {
            "records_processed": self._records_processed,
            "events_emitted": self._events_emitted,
            "active_customers": len(self._customer_states),
            "last_processing_time": (
                self._last_processing_time.isoformat()
                if self._last_processing_time else None
            ),
        }

    def _get_or_create_state(
        self, customer_id: str
    ) -> Optional[CustomerUsageState]:
        """Get or create customer state, returning None if no allowance exists."""
        if customer_id in self._customer_states:
            return self._customer_states[customer_id]

        allowance = self._customer_allowances.get(customer_id)
        if allowance is None:
            return None

        state = CustomerUsageState(
            customer_id=customer_id,
            allowance=allowance,
        )
        self._customer_states[customer_id] = state
        return state

    def _update_usage(
        self, state: CustomerUsageState, record: UsageRecord
    ) -> None:
        """Update customer's cumulative usage from a record."""
        # Update volume based on usage type
        if record.usage_type == state.allowance.usage_type:
            state.current_volume += record.amount

        # Update spend if rated amount is available
        if record.rated_amount:
            state.current_spend += record.rated_amount

        state.last_updated = utc_now()
        state.last_usage_record_id = record.record_id

        if self._config.log_all_records:
            logger.debug(
                f"Updated usage for {state.customer_id}: "
                f"volume={state.current_volume}, spend={state.current_spend}, "
                f"percentage={state.get_usage_percentage():.1f}%"
            )

    def _create_event(
        self,
        state: CustomerUsageState,
        event_type: EventType,
        triggering_record: Optional[UsageRecord] = None,
    ) -> ThresholdEvent:
        """Create a threshold event from the current state."""
        threshold_pct = {
            EventType.THRESHOLD_50_PERCENT: 50,
            EventType.THRESHOLD_75_PERCENT: 75,
            EventType.THRESHOLD_90_PERCENT: 90,
            EventType.THRESHOLD_100_PERCENT: 100,
        }.get(event_type, 50)

        return ThresholdEvent(
            event_id=f"evt_{state.customer_id}_{event_type.value}_{utc_now().timestamp()}",
            event_type=event_type,
            customer_id=state.customer_id,
            usage_type=state.allowance.usage_type,
            threshold_type=state.allowance.threshold_type,
            threshold_percentage=threshold_pct,
            current_value=state.get_current_value(),
            limit_value=state.allowance.get_limit(),
            actual_percentage=state.get_usage_percentage(),
            plan_type=state.allowance.plan_type,
            billing_period_start=state.allowance.period_start,
            billing_period_end=state.allowance.period_end,
            country_code=triggering_record.country_code if triggering_record else None,
            roaming_partner=triggering_record.roaming_partner if triggering_record else None,
            currency=state.allowance.currency,
            idempotency_key=(
                f"{state.customer_id}:{event_type.value}:"
                f"{state.allowance.period_start}"
            ),
        )


class MNOFeedIngester:
    """
    Ingests usage data from MNO (carrier) feeds.

    This class handles the data pipeline from MNO systems to the detector.
    In production, this would connect to actual MNO data sources.
    """

    def __init__(
        self,
        detector: UsageDetector,
        feed_source: str = "default_mno",
    ):
        self._detector = detector
        self._feed_source = feed_source
        self._batches_processed = 0
        self._last_batch_time: Optional[datetime] = None

    def ingest_batch(self, raw_records: list[dict]) -> DetectionResult:
        """
        Ingest a batch of raw records from the MNO feed.

        Parses raw data into UsageRecords and processes them.
        """
        records = []
        errors = []

        for raw in raw_records:
            try:
                record = UsageRecord.from_mno_feed(raw)
                records.append(record)
            except Exception as e:
                errors.append(f"Failed to parse record: {e}")

        if not records:
            return DetectionResult(errors=errors)

        batch = MNOFeedBatch(
            batch_id=f"batch_{self._batches_processed + 1}_{utc_now().timestamp()}",
            source=self._feed_source,
            records=records,
            feed_timestamp=utc_now(),
        )

        result = self._detector.process_batch(batch)
        result.errors.extend(errors)

        self._batches_processed += 1
        self._last_batch_time = utc_now()

        return result

    def get_ingestion_metrics(self) -> dict:
        """Get ingestion metrics for monitoring."""
        return {
            "feed_source": self._feed_source,
            "batches_processed": self._batches_processed,
            "last_batch_time": (
                self._last_batch_time.isoformat()
                if self._last_batch_time else None
            ),
        }
