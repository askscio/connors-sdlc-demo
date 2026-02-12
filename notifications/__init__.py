"""
Notification system for international usage alerts.

This module provides multi-channel notification delivery (SMS, email, push)
for usage threshold events, starting with the 50% international usage alert.
"""

from notifications.models import (
    NotificationChannel,
    NotificationTemplate,
    NotificationPayload,
    UsageAlertData,
    DeliveryResult,
    DeliveryStatus,
)
from notifications.service import NotificationService
from notifications.handlers import UsageEventHandler
from notifications.templates.usage_50_percent import (
    get_sms_template,
    get_email_template,
    get_push_template,
)

__all__ = [
    "NotificationChannel",
    "NotificationTemplate",
    "NotificationPayload",
    "UsageAlertData",
    "DeliveryResult",
    "DeliveryStatus",
    "NotificationService",
    "UsageEventHandler",
    "get_sms_template",
    "get_email_template",
    "get_push_template",
]
