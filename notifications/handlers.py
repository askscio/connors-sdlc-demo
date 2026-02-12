"""
Event handlers for usage notifications.

This module contains handlers that subscribe to usage events and trigger
the appropriate notifications. The handlers integrate with the detection
logic from SE-5034 (50% International Usage Detection).

Event Flow:
1. Usage detection system (SE-5034) emits "international_usage_50_percent" event
2. UsageEventHandler receives the event
3. Handler validates event data and user preferences
4. Handler triggers multi-channel notification delivery

Jira: SE-5035 (Configure and Launch 50% Usage Notifications)
Dependency: SE-5034 (Implement 50% International Usage Detection Logic)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from notifications.models import (
    DeliveryResult,
    NotificationChannel,
    UsageAlertData,
    UsageAlertType,
)

logger = logging.getLogger(__name__)


@dataclass
class UsageEvent:
    """
    Event emitted when a usage threshold is reached.

    This structure matches the event format from SE-5034 detection logic.
    """
    event_type: str  # e.g., "international_usage_50_percent"
    user_id: str
    account_id: str
    timestamp: datetime

    # Usage details
    current_usage_amount: Decimal
    threshold_amount: Decimal
    threshold_percentage: int
    usage_type: str  # "international", "data", "voice", etc.

    # User contact info
    phone_number: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    locale: str = "en_US"

    # Device tokens for push
    device_tokens: List[str] = None

    # Billing context
    billing_cycle_start: Optional[datetime] = None
    billing_cycle_end: Optional[datetime] = None
    currency: str = "USD"

    # Event metadata
    event_id: Optional[str] = None
    source: str = "usage_detection_service"

    def __post_init__(self):
        if self.device_tokens is None:
            self.device_tokens = []


class UsageEventHandler:
    """
    Handles usage threshold events and triggers notifications.

    This handler subscribes to usage events from the detection system (SE-5034)
    and orchestrates the delivery of notifications across all enabled channels.
    """

    # Supported event types and their corresponding alert types
    EVENT_TYPE_MAPPING = {
        "international_usage_50_percent": UsageAlertType.INTERNATIONAL_50_PERCENT,
        "international_usage_75_percent": UsageAlertType.INTERNATIONAL_75_PERCENT,
        "international_usage_90_percent": UsageAlertType.INTERNATIONAL_90_PERCENT,
        "international_usage_100_percent": UsageAlertType.INTERNATIONAL_100_PERCENT,
    }

    def __init__(
        self,
        notification_service: "NotificationService",
        user_preferences_service: Optional[Any] = None,
        deduplication_service: Optional[Any] = None,
    ):
        """
        Initialize the usage event handler.

        Args:
            notification_service: Service for sending notifications
            user_preferences_service: Service for checking user notification preferences
            deduplication_service: Service for preventing duplicate notifications
        """
        self.notification_service = notification_service
        self.user_preferences_service = user_preferences_service
        self.deduplication_service = deduplication_service
        self._event_callbacks: List[Callable] = []

    def handle_event(self, event: UsageEvent) -> List[DeliveryResult]:
        """
        Handle a usage threshold event.

        This is the main entry point called when the detection system
        emits a usage event.

        Args:
            event: The usage event to handle

        Returns:
            List of DeliveryResult objects for each channel attempted
        """
        logger.info(
            f"Handling usage event: {event.event_type} for user {event.user_id}",
            extra={
                "event_id": event.event_id,
                "user_id": event.user_id,
                "threshold_percentage": event.threshold_percentage,
            },
        )

        # Validate event type
        if event.event_type not in self.EVENT_TYPE_MAPPING:
            logger.warning(f"Unknown event type: {event.event_type}")
            return []

        # Check for duplicate notifications
        if self._is_duplicate(event):
            logger.info(f"Skipping duplicate notification for event {event.event_id}")
            return []

        # Get enabled channels for this user
        enabled_channels = self._get_enabled_channels(event.user_id)
        if not enabled_channels:
            logger.info(f"No enabled notification channels for user {event.user_id}")
            return []

        # Convert event to notification data
        alert_data = self._create_alert_data(event)

        # Send notifications across all enabled channels
        results = []
        for channel in enabled_channels:
            try:
                result = self._send_notification(channel, alert_data)
                results.append(result)
            except Exception as e:
                logger.error(
                    f"Failed to send {channel.value} notification to {event.user_id}: {e}",
                    exc_info=True,
                )

        # Mark notification as sent for deduplication
        self._mark_sent(event)

        # Invoke any registered callbacks
        for callback in self._event_callbacks:
            try:
                callback(event, results)
            except Exception as e:
                logger.error(f"Event callback error: {e}", exc_info=True)

        logger.info(
            f"Completed handling event {event.event_id}: "
            f"{sum(1 for r in results if r.is_successful())}/{len(results)} successful"
        )

        return results

    def handle_raw_event(self, raw_event: Dict[str, Any]) -> List[DeliveryResult]:
        """
        Handle a raw event dictionary (e.g., from a message queue).

        Converts the raw event data to a UsageEvent and processes it.

        Args:
            raw_event: Dictionary containing event data

        Returns:
            List of DeliveryResult objects
        """
        try:
            event = self._parse_raw_event(raw_event)
            return self.handle_event(event)
        except Exception as e:
            logger.error(f"Failed to parse raw event: {e}", exc_info=True)
            return []

    def register_callback(self, callback: Callable[[UsageEvent, List[DeliveryResult]], None]):
        """
        Register a callback to be invoked after event handling.

        Useful for metrics, logging, or downstream processing.

        Args:
            callback: Function to call with (event, results) after handling
        """
        self._event_callbacks.append(callback)

    def _create_alert_data(self, event: UsageEvent) -> UsageAlertData:
        """Convert a UsageEvent to UsageAlertData for template rendering."""
        return UsageAlertData(
            user_id=event.user_id,
            account_id=event.account_id,
            phone_number=event.phone_number,
            email=event.email,
            current_usage_amount=event.current_usage_amount,
            threshold_amount=event.threshold_amount,
            threshold_percentage=event.threshold_percentage,
            usage_type=event.usage_type,
            billing_cycle_start=event.billing_cycle_start,
            billing_cycle_end=event.billing_cycle_end,
            currency=event.currency,
            locale=event.locale,
            first_name=event.first_name,
            device_tokens=event.device_tokens,
        )

    def _get_enabled_channels(self, user_id: str) -> List[NotificationChannel]:
        """
        Get the notification channels enabled for a user.

        Args:
            user_id: User identifier

        Returns:
            List of enabled NotificationChannel values
        """
        if self.user_preferences_service:
            try:
                return self.user_preferences_service.get_enabled_channels(user_id)
            except Exception as e:
                logger.warning(f"Failed to get user preferences: {e}")

        # Default: all channels enabled
        return [
            NotificationChannel.SMS,
            NotificationChannel.EMAIL,
            NotificationChannel.PUSH,
        ]

    def _is_duplicate(self, event: UsageEvent) -> bool:
        """
        Check if this notification was already sent.

        Prevents sending duplicate notifications for the same threshold
        within a billing cycle.

        Args:
            event: The usage event to check

        Returns:
            True if notification was already sent, False otherwise
        """
        if self.deduplication_service:
            try:
                return self.deduplication_service.was_sent(
                    user_id=event.user_id,
                    event_type=event.event_type,
                    billing_cycle_start=event.billing_cycle_start,
                )
            except Exception as e:
                logger.warning(f"Deduplication check failed: {e}")

        return False

    def _mark_sent(self, event: UsageEvent):
        """Mark notification as sent for deduplication tracking."""
        if self.deduplication_service:
            try:
                self.deduplication_service.mark_sent(
                    user_id=event.user_id,
                    event_type=event.event_type,
                    billing_cycle_start=event.billing_cycle_start,
                    sent_at=datetime.now(timezone.utc),
                )
            except Exception as e:
                logger.warning(f"Failed to mark notification as sent: {e}")

    def _send_notification(
        self,
        channel: NotificationChannel,
        data: UsageAlertData,
    ) -> DeliveryResult:
        """
        Send notification through the specified channel.

        Args:
            channel: The channel to send through
            data: Alert data for template rendering

        Returns:
            DeliveryResult indicating success or failure
        """
        return self.notification_service.send_usage_alert(
            channel=channel,
            data=data,
            alert_type=UsageAlertType.INTERNATIONAL_50_PERCENT,
        )

    def _parse_raw_event(self, raw: Dict[str, Any]) -> UsageEvent:
        """
        Parse a raw event dictionary into a UsageEvent.

        Args:
            raw: Raw event data dictionary

        Returns:
            Parsed UsageEvent object

        Raises:
            ValueError: If required fields are missing
        """
        required_fields = [
            "event_type",
            "user_id",
            "account_id",
            "phone_number",
            "current_usage_amount",
            "threshold_amount",
            "threshold_percentage",
        ]

        for field in required_fields:
            if field not in raw:
                raise ValueError(f"Missing required field: {field}")

        return UsageEvent(
            event_type=raw["event_type"],
            user_id=raw["user_id"],
            account_id=raw["account_id"],
            timestamp=raw.get("timestamp", datetime.now(timezone.utc)),
            current_usage_amount=Decimal(str(raw["current_usage_amount"])),
            threshold_amount=Decimal(str(raw["threshold_amount"])),
            threshold_percentage=int(raw["threshold_percentage"]),
            usage_type=raw.get("usage_type", "international"),
            phone_number=raw["phone_number"],
            email=raw.get("email"),
            first_name=raw.get("first_name"),
            locale=raw.get("locale", "en_US"),
            device_tokens=raw.get("device_tokens", []),
            billing_cycle_start=raw.get("billing_cycle_start"),
            billing_cycle_end=raw.get("billing_cycle_end"),
            currency=raw.get("currency", "USD"),
            event_id=raw.get("event_id"),
            source=raw.get("source", "usage_detection_service"),
        )


def create_event_subscriber(
    notification_service: "NotificationService",
    message_queue_client: Optional[Any] = None,
) -> UsageEventHandler:
    """
    Factory function to create and configure a UsageEventHandler.

    Sets up the handler with appropriate services and subscribes to
    the message queue if provided.

    Args:
        notification_service: Notification service for delivery
        message_queue_client: Optional message queue client for subscribing

    Returns:
        Configured UsageEventHandler instance
    """
    handler = UsageEventHandler(notification_service=notification_service)

    if message_queue_client:
        # Subscribe to usage events topic
        message_queue_client.subscribe(
            topic="usage.threshold.events",
            callback=handler.handle_raw_event,
        )
        logger.info("Subscribed to usage.threshold.events topic")

    return handler
