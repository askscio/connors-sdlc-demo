"""
Notification service for multi-channel delivery.

This module provides the core NotificationService class that handles
sending notifications across SMS, email, and push channels.

Jira: SE-5035 (Configure and Launch 50% Usage Notifications)
"""

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol

from notifications.models import (
    DeliveryResult,
    DeliveryStatus,
    NotificationChannel,
    NotificationPayload,
    NotificationTemplate,
    UsageAlertData,
    UsageAlertType,
)
from notifications.templates.usage_50_percent import (
    get_all_templates,
    get_email_template,
    get_push_template,
    get_sms_template,
    render_email,
    render_push,
    render_sms,
)

logger = logging.getLogger(__name__)


class SMSProvider(Protocol):
    """Protocol for SMS delivery providers."""

    def send(self, phone_number: str, message: str) -> Dict:
        """Send an SMS message."""
        ...


class EmailProvider(Protocol):
    """Protocol for email delivery providers."""

    def send(
        self,
        to_address: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> Dict:
        """Send an email."""
        ...


class PushProvider(Protocol):
    """Protocol for push notification delivery providers."""

    def send(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict] = None,
    ) -> Dict:
        """Send a push notification."""
        ...


@dataclass
class NotificationServiceConfig:
    """Configuration for the NotificationService."""

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: int = 5

    # Channel enablement
    sms_enabled: bool = True
    email_enabled: bool = True
    push_enabled: bool = True

    # Rate limiting
    rate_limit_per_minute: int = 100

    # Debug mode (logs but doesn't send)
    dry_run: bool = False


class NotificationService:
    """
    Service for sending notifications across multiple channels.

    This service handles template rendering, channel-specific delivery,
    and result tracking for usage alert notifications.
    """

    def __init__(
        self,
        config: Optional[NotificationServiceConfig] = None,
        sms_provider: Optional[SMSProvider] = None,
        email_provider: Optional[EmailProvider] = None,
        push_provider: Optional[PushProvider] = None,
    ):
        """
        Initialize the notification service.

        Args:
            config: Service configuration
            sms_provider: Provider for SMS delivery
            email_provider: Provider for email delivery
            push_provider: Provider for push notification delivery
        """
        self.config = config or NotificationServiceConfig()
        self.sms_provider = sms_provider
        self.email_provider = email_provider
        self.push_provider = push_provider

        # Template cache
        self._template_cache: Dict[str, NotificationTemplate] = {}

    def send_usage_alert(
        self,
        channel: NotificationChannel,
        data: UsageAlertData,
        alert_type: UsageAlertType = UsageAlertType.INTERNATIONAL_50_PERCENT,
    ) -> DeliveryResult:
        """
        Send a usage alert notification through the specified channel.

        Args:
            channel: The channel to send through (SMS, EMAIL, PUSH)
            data: Alert data containing user info and usage details
            alert_type: Type of usage alert to send

        Returns:
            DeliveryResult indicating success or failure
        """
        notification_id = str(uuid.uuid4())

        logger.info(
            f"Sending {alert_type.value} notification via {channel.value} to user {data.user_id}",
            extra={
                "notification_id": notification_id,
                "channel": channel.value,
                "user_id": data.user_id,
            },
        )

        # Check if channel is enabled
        if not self._is_channel_enabled(channel):
            return DeliveryResult(
                notification_id=notification_id,
                channel=channel,
                status=DeliveryStatus.FAILED,
                error_code="CHANNEL_DISABLED",
                error_message=f"{channel.value} channel is disabled",
            )

        # Get template for this alert type and locale
        template = self._get_template(channel, data.locale, alert_type)

        # Render template with user data
        payload = self._render_payload(template, data, notification_id)

        # Send through appropriate provider
        if self.config.dry_run:
            logger.info(f"DRY RUN: Would send {channel.value} notification: {payload}")
            return DeliveryResult(
                notification_id=notification_id,
                channel=channel,
                status=DeliveryStatus.SENT,
                sent_at=datetime.now(timezone.utc),
                provider_name="dry_run",
            )

        return self._deliver(channel, payload)

    def send_usage_alert_all_channels(
        self,
        data: UsageAlertData,
        alert_type: UsageAlertType = UsageAlertType.INTERNATIONAL_50_PERCENT,
    ) -> List[DeliveryResult]:
        """
        Send a usage alert through all enabled channels.

        Args:
            data: Alert data containing user info and usage details
            alert_type: Type of usage alert to send

        Returns:
            List of DeliveryResult objects, one per channel attempted
        """
        results = []

        channels_to_try = []
        if self.config.sms_enabled and data.phone_number:
            channels_to_try.append(NotificationChannel.SMS)
        if self.config.email_enabled and data.email:
            channels_to_try.append(NotificationChannel.EMAIL)
        if self.config.push_enabled and data.device_tokens:
            channels_to_try.append(NotificationChannel.PUSH)

        for channel in channels_to_try:
            result = self.send_usage_alert(channel, data, alert_type)
            results.append(result)

        return results

    def _is_channel_enabled(self, channel: NotificationChannel) -> bool:
        """Check if a channel is enabled in configuration."""
        if channel == NotificationChannel.SMS:
            return self.config.sms_enabled
        elif channel == NotificationChannel.EMAIL:
            return self.config.email_enabled
        elif channel == NotificationChannel.PUSH:
            return self.config.push_enabled
        return False

    def _get_template(
        self,
        channel: NotificationChannel,
        locale: str,
        alert_type: UsageAlertType,
    ) -> NotificationTemplate:
        """
        Get the appropriate template for channel, locale, and alert type.

        Uses caching to avoid recreating templates.
        """
        cache_key = f"{alert_type.value}_{channel.value}_{locale}"

        if cache_key not in self._template_cache:
            # Currently only supporting 50% alerts
            if alert_type == UsageAlertType.INTERNATIONAL_50_PERCENT:
                if channel == NotificationChannel.SMS:
                    template = get_sms_template(locale)
                elif channel == NotificationChannel.EMAIL:
                    template = get_email_template(locale)
                elif channel == NotificationChannel.PUSH:
                    template = get_push_template(locale)
                else:
                    raise ValueError(f"Unsupported channel: {channel}")

                self._template_cache[cache_key] = template
            else:
                raise ValueError(f"Unsupported alert type: {alert_type}")

        return self._template_cache[cache_key]

    def _render_payload(
        self,
        template: NotificationTemplate,
        data: UsageAlertData,
        notification_id: str,
    ) -> NotificationPayload:
        """
        Render a template with user-specific data.

        Args:
            template: The template to render
            data: User and usage data for personalization
            notification_id: Unique ID for this notification

        Returns:
            NotificationPayload ready for delivery
        """
        payload = NotificationPayload(
            template=template,
            recipient_id=data.user_id,
            notification_id=notification_id,
            metadata={
                "account_id": data.account_id,
                "threshold_percentage": data.threshold_percentage,
                "usage_type": data.usage_type,
            },
        )

        if template.channel == NotificationChannel.SMS:
            payload.phone_number = data.phone_number
            payload.rendered_body = render_sms(template, data)

        elif template.channel == NotificationChannel.EMAIL:
            payload.email_address = data.email
            rendered = render_email(template, data)
            payload.rendered_subject = rendered["subject"]
            payload.rendered_body = rendered["body"]
            payload.rendered_html_body = rendered["html_body"]

        elif template.channel == NotificationChannel.PUSH:
            if data.device_tokens:
                payload.device_token = data.device_tokens[0]  # Primary device
            rendered = render_push(template, data)
            payload.rendered_title = rendered["title"]
            payload.rendered_body = rendered["body"]
            payload.metadata["deep_link"] = rendered["deep_link"]

        return payload

    def _deliver(
        self,
        channel: NotificationChannel,
        payload: NotificationPayload,
    ) -> DeliveryResult:
        """
        Deliver a notification through the specified channel's provider.

        Args:
            channel: The channel to deliver through
            payload: The rendered notification payload

        Returns:
            DeliveryResult indicating success or failure
        """
        try:
            if channel == NotificationChannel.SMS:
                return self._deliver_sms(payload)
            elif channel == NotificationChannel.EMAIL:
                return self._deliver_email(payload)
            elif channel == NotificationChannel.PUSH:
                return self._deliver_push(payload)
            else:
                return DeliveryResult(
                    notification_id=payload.notification_id,
                    channel=channel,
                    status=DeliveryStatus.FAILED,
                    error_code="UNSUPPORTED_CHANNEL",
                    error_message=f"Channel {channel.value} is not supported",
                )
        except Exception as e:
            logger.error(f"Delivery failed for {channel.value}: {e}", exc_info=True)
            return DeliveryResult(
                notification_id=payload.notification_id,
                channel=channel,
                status=DeliveryStatus.FAILED,
                error_code="DELIVERY_ERROR",
                error_message=str(e),
                should_retry=True,
            )

    def _deliver_sms(self, payload: NotificationPayload) -> DeliveryResult:
        """Deliver an SMS notification."""
        if not self.sms_provider:
            return DeliveryResult(
                notification_id=payload.notification_id,
                channel=NotificationChannel.SMS,
                status=DeliveryStatus.FAILED,
                error_code="NO_PROVIDER",
                error_message="SMS provider not configured",
            )

        if not payload.phone_number:
            return DeliveryResult(
                notification_id=payload.notification_id,
                channel=NotificationChannel.SMS,
                status=DeliveryStatus.FAILED,
                error_code="MISSING_RECIPIENT",
                error_message="No phone number provided",
            )

        result = self.sms_provider.send(
            phone_number=payload.phone_number,
            message=payload.rendered_body,
        )

        return DeliveryResult(
            notification_id=payload.notification_id,
            channel=NotificationChannel.SMS,
            status=DeliveryStatus.SENT,
            sent_at=datetime.now(timezone.utc),
            provider_message_id=result.get("message_id"),
            provider_name=result.get("provider", "sms_provider"),
        )

    def _deliver_email(self, payload: NotificationPayload) -> DeliveryResult:
        """Deliver an email notification."""
        if not self.email_provider:
            return DeliveryResult(
                notification_id=payload.notification_id,
                channel=NotificationChannel.EMAIL,
                status=DeliveryStatus.FAILED,
                error_code="NO_PROVIDER",
                error_message="Email provider not configured",
            )

        if not payload.email_address:
            return DeliveryResult(
                notification_id=payload.notification_id,
                channel=NotificationChannel.EMAIL,
                status=DeliveryStatus.FAILED,
                error_code="MISSING_RECIPIENT",
                error_message="No email address provided",
            )

        result = self.email_provider.send(
            to_address=payload.email_address,
            subject=payload.rendered_subject or "",
            body=payload.rendered_body,
            html_body=payload.rendered_html_body,
        )

        return DeliveryResult(
            notification_id=payload.notification_id,
            channel=NotificationChannel.EMAIL,
            status=DeliveryStatus.SENT,
            sent_at=datetime.now(timezone.utc),
            provider_message_id=result.get("message_id"),
            provider_name=result.get("provider", "email_provider"),
        )

    def _deliver_push(self, payload: NotificationPayload) -> DeliveryResult:
        """Deliver a push notification."""
        if not self.push_provider:
            return DeliveryResult(
                notification_id=payload.notification_id,
                channel=NotificationChannel.PUSH,
                status=DeliveryStatus.FAILED,
                error_code="NO_PROVIDER",
                error_message="Push provider not configured",
            )

        if not payload.device_token:
            return DeliveryResult(
                notification_id=payload.notification_id,
                channel=NotificationChannel.PUSH,
                status=DeliveryStatus.FAILED,
                error_code="MISSING_RECIPIENT",
                error_message="No device token provided",
            )

        result = self.push_provider.send(
            device_token=payload.device_token,
            title=payload.rendered_title or "",
            body=payload.rendered_body,
            data=payload.metadata,
        )

        return DeliveryResult(
            notification_id=payload.notification_id,
            channel=NotificationChannel.PUSH,
            status=DeliveryStatus.SENT,
            sent_at=datetime.now(timezone.utc),
            provider_message_id=result.get("message_id"),
            provider_name=result.get("provider", "push_provider"),
        )


class MockSMSProvider:
    """Mock SMS provider for testing."""

    def __init__(self):
        self.sent_messages: List[Dict] = []

    def send(self, phone_number: str, message: str) -> Dict:
        record = {
            "phone_number": phone_number,
            "message": message,
            "message_id": str(uuid.uuid4()),
            "provider": "mock_sms",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        self.sent_messages.append(record)
        return record


class MockEmailProvider:
    """Mock email provider for testing."""

    def __init__(self):
        self.sent_emails: List[Dict] = []

    def send(
        self,
        to_address: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> Dict:
        record = {
            "to_address": to_address,
            "subject": subject,
            "body": body,
            "html_body": html_body,
            "message_id": str(uuid.uuid4()),
            "provider": "mock_email",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        self.sent_emails.append(record)
        return record


class MockPushProvider:
    """Mock push provider for testing."""

    def __init__(self):
        self.sent_notifications: List[Dict] = []

    def send(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict] = None,
    ) -> Dict:
        record = {
            "device_token": device_token,
            "title": title,
            "body": body,
            "data": data,
            "message_id": str(uuid.uuid4()),
            "provider": "mock_push",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        self.sent_notifications.append(record)
        return record


def create_test_notification_service() -> NotificationService:
    """
    Create a NotificationService configured for testing.

    Returns a service with mock providers for all channels.
    """
    return NotificationService(
        config=NotificationServiceConfig(dry_run=False),
        sms_provider=MockSMSProvider(),
        email_provider=MockEmailProvider(),
        push_provider=MockPushProvider(),
    )
