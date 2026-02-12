"""
50% International Usage Alert Templates.

This module contains notification templates for the 50% international usage
threshold alert across all supported channels (SMS, email, push).

Templates are designed to:
- Include links to usage details
- Provide recommended next actions (buy a pass, change plan)
- Support localization for required markets
- Meet legal/regulatory requirements

Jira: SE-5035 (Configure and Launch 50% Usage Notifications)
Dependency: SE-5034 (Implement 50% International Usage Detection Logic)
"""

from datetime import datetime
from typing import Dict

from notifications.models import (
    NotificationChannel,
    NotificationTemplate,
    UsageAlertData,
    UsageAlertType,
)
from notifications.localization import get_localized_strings


def get_sms_template(locale: str = "en_US") -> NotificationTemplate:
    """
    Get SMS template for 50% international usage alert.

    SMS messages are limited to 160 characters for single segment.
    Includes shortened URL for usage details.

    Args:
        locale: User's locale for localization (e.g., "en_US", "es_MX")

    Returns:
        NotificationTemplate configured for SMS delivery
    """
    strings = get_localized_strings(locale)

    body = strings["sms_50_percent_body"]

    return NotificationTemplate(
        channel=NotificationChannel.SMS,
        locale=locale,
        alert_type=UsageAlertType.INTERNATIONAL_50_PERCENT,
        body=body,
        template_id=f"intl_usage_50_sms_{locale}",
        version="1.0",
        legal_approved=True,
        legal_approval_date=datetime(2026, 2, 1),
    )


def get_email_template(locale: str = "en_US") -> NotificationTemplate:
    """
    Get email template for 50% international usage alert.

    Email includes:
    - Subject line with account context
    - HTML body with usage details and action buttons
    - Plain text fallback

    Args:
        locale: User's locale for localization

    Returns:
        NotificationTemplate configured for email delivery
    """
    strings = get_localized_strings(locale)

    subject = strings["email_50_percent_subject"]
    body = strings["email_50_percent_body"]
    html_body = strings["email_50_percent_html"]

    return NotificationTemplate(
        channel=NotificationChannel.EMAIL,
        locale=locale,
        alert_type=UsageAlertType.INTERNATIONAL_50_PERCENT,
        subject=subject,
        body=body,
        html_body=html_body,
        template_id=f"intl_usage_50_email_{locale}",
        version="1.0",
        legal_approved=True,
        legal_approval_date=datetime(2026, 2, 1),
    )


def get_push_template(locale: str = "en_US") -> NotificationTemplate:
    """
    Get push notification template for 50% international usage alert.

    Push notifications include:
    - Short title for notification center
    - Body with key information
    - Deep link to usage details

    Args:
        locale: User's locale for localization

    Returns:
        NotificationTemplate configured for push delivery
    """
    strings = get_localized_strings(locale)

    title = strings["push_50_percent_title"]
    body = strings["push_50_percent_body"]

    return NotificationTemplate(
        channel=NotificationChannel.PUSH,
        locale=locale,
        alert_type=UsageAlertType.INTERNATIONAL_50_PERCENT,
        title=title,
        body=body,
        template_id=f"intl_usage_50_push_{locale}",
        version="1.0",
        legal_approved=True,
        legal_approval_date=datetime(2026, 2, 1),
    )


def render_sms(template: NotificationTemplate, data: UsageAlertData) -> str:
    """
    Render SMS template with user-specific data.

    Args:
        template: SMS template to render
        data: User and usage data for personalization

    Returns:
        Rendered SMS body text
    """
    return template.body.format(
        first_name=data.first_name or "Customer",
        percentage=data.threshold_percentage,
        current_usage=f"{data.currency} {data.current_usage_amount:.2f}",
        threshold=f"{data.currency} {data.threshold_amount:.2f}",
        usage_url=data.usage_details_url,
    )


def render_email(template: NotificationTemplate, data: UsageAlertData) -> Dict[str, str]:
    """
    Render email template with user-specific data.

    Args:
        template: Email template to render
        data: User and usage data for personalization

    Returns:
        Dictionary with 'subject', 'body', and 'html_body' keys
    """
    format_data = {
        "first_name": data.first_name or "Valued Customer",
        "percentage": data.threshold_percentage,
        "current_usage": f"{data.currency} {data.current_usage_amount:.2f}",
        "threshold": f"{data.currency} {data.threshold_amount:.2f}",
        "usage_url": data.usage_details_url,
        "buy_pass_url": data.buy_pass_url,
        "change_plan_url": data.change_plan_url,
        "billing_cycle_end": (
            data.billing_cycle_end.strftime("%B %d, %Y")
            if data.billing_cycle_end
            else "end of billing cycle"
        ),
    }

    return {
        "subject": template.subject.format(**format_data) if template.subject else "",
        "body": template.body.format(**format_data),
        "html_body": template.html_body.format(**format_data) if template.html_body else "",
    }


def render_push(template: NotificationTemplate, data: UsageAlertData) -> Dict[str, str]:
    """
    Render push notification template with user-specific data.

    Args:
        template: Push template to render
        data: User and usage data for personalization

    Returns:
        Dictionary with 'title', 'body', and 'deep_link' keys
    """
    format_data = {
        "first_name": data.first_name or "Customer",
        "percentage": data.threshold_percentage,
        "current_usage": f"{data.currency} {data.current_usage_amount:.2f}",
    }

    return {
        "title": template.title.format(**format_data) if template.title else "",
        "body": template.body.format(**format_data),
        "deep_link": data.usage_details_url,
    }


def get_all_templates(locale: str = "en_US") -> Dict[NotificationChannel, NotificationTemplate]:
    """
    Get all channel templates for the 50% usage alert.

    Args:
        locale: User's locale for localization

    Returns:
        Dictionary mapping channels to their templates
    """
    return {
        NotificationChannel.SMS: get_sms_template(locale),
        NotificationChannel.EMAIL: get_email_template(locale),
        NotificationChannel.PUSH: get_push_template(locale),
    }
