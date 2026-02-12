"""
Core data models for international usage tracking and threshold detection.

Implements models for:
- Usage records from MNO (carrier) feeds
- Customer allowances and usage state
- Threshold events for downstream notification systems (SE-5035)
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
import uuid


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class UsageType(Enum):
    """Type of international usage being tracked."""
    VOICE_MINUTES = "voice_minutes"
    SMS_COUNT = "sms_count"
    DATA_MB = "data_mb"
    SPEND_AMOUNT = "spend_amount"


class ThresholdType(Enum):
    """How the 50% threshold is calculated (per SE-5033 rules)."""
    VOLUME = "volume"  # Based on usage volume (minutes, MB, etc.)
    SPEND = "spend"    # Based on monetary spend


class CustomerSegment(Enum):
    """Customer segment for rule targeting (per SE-5033)."""
    CONSUMER = "consumer"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"
    PREPAID = "prepaid"
    POSTPAID = "postpaid"


class PlanType(Enum):
    """Plan types in scope for international usage alerts (per SE-5033)."""
    UNLIMITED_INTERNATIONAL = "unlimited_international"
    INTERNATIONAL_PACKAGE = "international_package"
    PAY_AS_YOU_GO = "pay_as_you_go"
    ROAMING_BUNDLE = "roaming_bundle"
    SHARED_PLAN = "shared_plan"
    MULTI_SIM = "multi_sim"


class EventType(Enum):
    """Types of threshold events emitted by the detection system."""
    THRESHOLD_50_PERCENT = "threshold_50_percent"
    THRESHOLD_75_PERCENT = "threshold_75_percent"
    THRESHOLD_90_PERCENT = "threshold_90_percent"
    THRESHOLD_100_PERCENT = "threshold_100_percent"


@dataclass
class UsageRecord:
    """
    A single usage record from MNO (carrier) usage feeds.

    Represents international voice, SMS, data, or spend events
    ingested from carrier rating systems.
    """
    record_id: str
    customer_id: str
    usage_type: UsageType
    amount: Decimal
    timestamp: datetime
    country_code: str  # ISO 3166-1 alpha-2 country code
    roaming_partner: Optional[str] = None  # MNO roaming partner ID
    rated_amount: Optional[Decimal] = None  # Monetary value if applicable
    currency: str = "USD"
    raw_data: Optional[dict] = None  # Original MNO feed data

    @classmethod
    def from_mno_feed(cls, feed_data: dict) -> "UsageRecord":
        """Factory method to create UsageRecord from raw MNO feed data."""
        return cls(
            record_id=feed_data.get("record_id", str(uuid.uuid4())),
            customer_id=feed_data["customer_id"],
            usage_type=UsageType(feed_data["usage_type"]),
            amount=Decimal(str(feed_data["amount"])),
            timestamp=datetime.fromisoformat(feed_data["timestamp"]),
            country_code=feed_data["country_code"],
            roaming_partner=feed_data.get("roaming_partner"),
            rated_amount=Decimal(str(feed_data["rated_amount"])) if feed_data.get("rated_amount") else None,
            currency=feed_data.get("currency", "USD"),
            raw_data=feed_data,
        )


@dataclass
class UsageAllowance:
    """
    Customer's international usage allowance for the billing period.

    Defines the limits against which 50% thresholds are calculated.
    """
    allowance_id: str
    customer_id: str
    plan_type: PlanType
    usage_type: UsageType
    threshold_type: ThresholdType

    # Allowance limits
    volume_limit: Optional[Decimal] = None  # Units depend on usage_type
    spend_limit: Optional[Decimal] = None   # Monetary limit
    currency: str = "USD"

    # Billing period
    period_start: date = field(default_factory=date.today)
    period_end: Optional[date] = None

    # Reset behavior (per SE-5033)
    reset_on_period_end: bool = True
    carry_over_unused: bool = False

    def get_limit(self) -> Decimal:
        """Get the applicable limit based on threshold type."""
        if self.threshold_type == ThresholdType.VOLUME:
            return self.volume_limit or Decimal("0")
        return self.spend_limit or Decimal("0")


@dataclass
class CustomerUsageState:
    """
    Current state of a customer's international usage for the billing period.

    Tracks cumulative usage and threshold crossings.
    """
    customer_id: str
    allowance: UsageAllowance

    # Current usage totals
    current_volume: Decimal = Decimal("0")
    current_spend: Decimal = Decimal("0")

    # Threshold tracking
    last_threshold_crossed: Optional[EventType] = None
    thresholds_notified: list[EventType] = field(default_factory=list)

    # Timestamps
    last_updated: datetime = field(default_factory=utc_now)
    last_usage_record_id: Optional[str] = None

    # Multi-SIM / Shared plan support (per SE-5033 edge cases)
    is_shared_plan: bool = False
    shared_plan_members: list[str] = field(default_factory=list)

    def get_current_value(self) -> Decimal:
        """Get the current value based on threshold type."""
        if self.allowance.threshold_type == ThresholdType.VOLUME:
            return self.current_volume
        return self.current_spend

    def get_usage_percentage(self) -> Decimal:
        """Calculate current usage as a percentage of allowance."""
        limit = self.allowance.get_limit()
        if limit == Decimal("0"):
            return Decimal("0")
        return (self.get_current_value() / limit) * Decimal("100")

    def has_crossed_threshold(self, threshold: EventType) -> bool:
        """Check if a specific threshold has been crossed."""
        return threshold in self.thresholds_notified

    def mark_threshold_notified(self, threshold: EventType) -> None:
        """Mark a threshold as having been notified."""
        if threshold not in self.thresholds_notified:
            self.thresholds_notified.append(threshold)
            self.last_threshold_crossed = threshold


@dataclass
class ThresholdEvent:
    """
    Event emitted when a customer crosses a usage threshold.

    This event is consumed by downstream notification systems (SE-5035)
    to trigger SMS, email, and push notifications.
    """
    event_id: str
    event_type: EventType
    customer_id: str

    # Usage details
    usage_type: UsageType
    threshold_type: ThresholdType
    threshold_percentage: int  # 50, 75, 90, or 100

    # Current state at time of event
    current_value: Decimal
    limit_value: Decimal
    actual_percentage: Decimal

    # Plan/Segment info for notification targeting
    plan_type: PlanType
    customer_segment: Optional[CustomerSegment] = None

    # Timestamps
    timestamp: datetime = field(default_factory=utc_now)
    billing_period_start: Optional[date] = None
    billing_period_end: Optional[date] = None

    # Metadata for downstream processing
    country_code: Optional[str] = None  # Last usage country
    roaming_partner: Optional[str] = None
    currency: str = "USD"

    # Idempotency key for deduplication
    idempotency_key: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def create_50_percent_event(
        cls,
        customer_state: CustomerUsageState,
        triggering_record: Optional[UsageRecord] = None,
    ) -> "ThresholdEvent":
        """Factory method to create a 50% threshold event."""
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=EventType.THRESHOLD_50_PERCENT,
            customer_id=customer_state.customer_id,
            usage_type=customer_state.allowance.usage_type,
            threshold_type=customer_state.allowance.threshold_type,
            threshold_percentage=50,
            current_value=customer_state.get_current_value(),
            limit_value=customer_state.allowance.get_limit(),
            actual_percentage=customer_state.get_usage_percentage(),
            plan_type=customer_state.allowance.plan_type,
            billing_period_start=customer_state.allowance.period_start,
            billing_period_end=customer_state.allowance.period_end,
            country_code=triggering_record.country_code if triggering_record else None,
            roaming_partner=triggering_record.roaming_partner if triggering_record else None,
            currency=customer_state.allowance.currency,
            idempotency_key=f"{customer_state.customer_id}:{EventType.THRESHOLD_50_PERCENT.value}:{customer_state.allowance.period_start}",
        )


@dataclass
class MNOFeedBatch:
    """
    A batch of usage records from MNO feed ingestion.

    Used for batch processing of carrier usage data.
    """
    batch_id: str
    source: str  # MNO/carrier identifier
    records: list[UsageRecord]
    received_at: datetime = field(default_factory=utc_now)
    processed_at: Optional[datetime] = None

    # Latency tracking for monitoring
    feed_timestamp: Optional[datetime] = None  # When MNO generated the data

    @property
    def record_count(self) -> int:
        return len(self.records)

    @property
    def ingestion_latency_seconds(self) -> Optional[float]:
        """Calculate latency from MNO generation to ingestion."""
        if self.feed_timestamp:
            return (self.received_at - self.feed_timestamp).total_seconds()
        return None
