"""
Data models for the notification system.

Defines the core structures for notification templates, payloads,
and delivery results across all supported channels.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional


class NotificationChannel(Enum):
    """Supported notification delivery channels."""
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"


class DeliveryStatus(Enum):
    """Status of notification delivery attempt."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class UsageAlertType(Enum):
    """Types of usage threshold alerts."""
    INTERNATIONAL_50_PERCENT = "international_50_percent"
    INTERNATIONAL_75_PERCENT = "international_75_percent"
    INTERNATIONAL_90_PERCENT = "international_90_percent"
    INTERNATIONAL_100_PERCENT = "international_100_percent"


@dataclass
class UsageAlertData:
    """
    Data payload for international usage alerts.

    Contains all information needed to populate notification templates
    for usage threshold notifications.
    """
    # User identification
    user_id: str
    account_id: str
    phone_number: str
    email: Optional[str] = None

    # Usage details
    current_usage_amount: Decimal = Decimal("0.00")
    threshold_amount: Decimal = Decimal("0.00")
    threshold_percentage: int = 50
    usage_type: str = "international"

    # Billing context
    billing_cycle_start: Optional[datetime] = None
    billing_cycle_end: Optional[datetime] = None
    currency: str = "USD"

    # User preferences
    locale: str = "en_US"
    first_name: Optional[str] = None

    # Deep links
    usage_details_url: str = ""
    buy_pass_url: str = ""
    change_plan_url: str = ""

    # Device info for push notifications
    device_tokens: list = field(default_factory=list)

    def __post_init__(self):
        """Generate default URLs if not provided."""
        base_url = "https://app.example.com"
        if not self.usage_details_url:
            self.usage_details_url = f"{base_url}/usage/international?account={self.account_id}"
        if not self.buy_pass_url:
            self.buy_pass_url = f"{base_url}/plans/international-pass?account={self.account_id}"
        if not self.change_plan_url:
            self.change_plan_url = f"{base_url}/plans/upgrade?account={self.account_id}"


@dataclass
class NotificationTemplate:
    """
    Template definition for a notification.

    Contains the content structure for a specific channel and locale.
    """
    channel: NotificationChannel
    locale: str
    alert_type: UsageAlertType

    # Content fields (populated based on channel)
    subject: Optional[str] = None  # Email only
    title: Optional[str] = None    # Push only
    body: str = ""
    html_body: Optional[str] = None  # Email only

    # Metadata
    template_id: str = ""
    version: str = "1.0"
    legal_approved: bool = False
    legal_approval_date: Optional[datetime] = None

    def __post_init__(self):
        """Generate template_id if not provided."""
        if not self.template_id:
            self.template_id = f"{self.alert_type.value}_{self.channel.value}_{self.locale}"


@dataclass
class NotificationPayload:
    """
    Complete notification ready for delivery.

    Combines template with user-specific data for actual sending.
    """
    template: NotificationTemplate
    recipient_id: str

    # Delivery targets
    phone_number: Optional[str] = None  # SMS
    email_address: Optional[str] = None  # Email
    device_token: Optional[str] = None  # Push

    # Rendered content
    rendered_subject: Optional[str] = None
    rendered_title: Optional[str] = None
    rendered_body: str = ""
    rendered_html_body: Optional[str] = None

    # Tracking
    notification_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Metadata for analytics
    metadata: dict = field(default_factory=dict)


@dataclass
class DeliveryResult:
    """
    Result of a notification delivery attempt.

    Tracks the outcome of sending a notification through a specific channel.
    """
    notification_id: str
    channel: NotificationChannel
    status: DeliveryStatus

    # Timing
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    # Error handling
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Provider details
    provider_message_id: Optional[str] = None
    provider_name: Optional[str] = None

    # Retry tracking
    attempt_number: int = 1
    max_retries: int = 3
    should_retry: bool = False

    def is_successful(self) -> bool:
        """Check if delivery was successful."""
        return self.status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED)
