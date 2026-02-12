"""
Tests for the 50% International Usage Notification System.

Covers:
- Template rendering for all channels (SMS, email, push)
- Localization for supported markets
- Event handling and notification triggering
- Multi-channel delivery
- Edge cases and error handling

Jira: SE-5035 (Configure and Launch 50% Usage Notifications)
"""

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from notifications.models import (
    DeliveryStatus,
    NotificationChannel,
    NotificationTemplate,
    UsageAlertData,
    UsageAlertType,
)
from notifications.localization import (
    get_localized_strings,
    get_supported_locales,
    is_locale_supported,
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
from notifications.service import (
    MockEmailProvider,
    MockPushProvider,
    MockSMSProvider,
    NotificationService,
    NotificationServiceConfig,
    create_test_notification_service,
)
from notifications.handlers import UsageEvent, UsageEventHandler


class TestUsageAlertData(unittest.TestCase):
    """Tests for UsageAlertData model."""

    def test_basic_creation(self):
        """Test creating UsageAlertData with minimal fields."""
        data = UsageAlertData(
            user_id="user123",
            account_id="acc456",
            phone_number="+15551234567",
        )

        self.assertEqual(data.user_id, "user123")
        self.assertEqual(data.account_id, "acc456")
        self.assertEqual(data.threshold_percentage, 50)
        self.assertEqual(data.locale, "en_US")

    def test_default_urls_generated(self):
        """Test that default URLs are generated when not provided."""
        data = UsageAlertData(
            user_id="user123",
            account_id="acc456",
            phone_number="+15551234567",
        )

        self.assertIn("acc456", data.usage_details_url)
        self.assertIn("acc456", data.buy_pass_url)
        self.assertIn("acc456", data.change_plan_url)

    def test_custom_urls_preserved(self):
        """Test that custom URLs are preserved when provided."""
        custom_url = "https://custom.example.com/usage"
        data = UsageAlertData(
            user_id="user123",
            account_id="acc456",
            phone_number="+15551234567",
            usage_details_url=custom_url,
        )

        self.assertEqual(data.usage_details_url, custom_url)


class TestLocalization(unittest.TestCase):
    """Tests for localization functionality."""

    def test_supported_locales(self):
        """Test that expected locales are supported."""
        locales = get_supported_locales()

        self.assertIn("en_US", locales)
        self.assertIn("es_MX", locales)
        self.assertIn("fr_CA", locales)
        self.assertIn("de_DE", locales)
        self.assertIn("pt_BR", locales)

    def test_en_us_strings(self):
        """Test English (US) localized strings."""
        strings = get_localized_strings("en_US")

        self.assertIn("sms_50_percent_body", strings)
        self.assertIn("email_50_percent_subject", strings)
        self.assertIn("email_50_percent_body", strings)
        self.assertIn("push_50_percent_title", strings)

    def test_spanish_strings(self):
        """Test Spanish (Mexico) localized strings."""
        strings = get_localized_strings("es_MX")

        self.assertIn("límite internacional", strings["sms_50_percent_body"])
        self.assertIn("Alerta de Uso Internacional", strings["push_50_percent_title"])

    def test_fallback_to_default(self):
        """Test fallback to en_US for unsupported locales."""
        strings = get_localized_strings("xx_XX")

        # Should get English strings
        self.assertEqual(strings, get_localized_strings("en_US"))

    def test_language_fallback(self):
        """Test fallback to language match when exact locale not found."""
        # es_AR not supported, should fall back to es_US or es_MX
        strings = get_localized_strings("es_AR")

        self.assertIn("límite internacional", strings["sms_50_percent_body"])


class TestSMSTemplate(unittest.TestCase):
    """Tests for SMS notification template."""

    def test_sms_template_creation(self):
        """Test SMS template has correct attributes."""
        template = get_sms_template("en_US")

        self.assertEqual(template.channel, NotificationChannel.SMS)
        self.assertEqual(template.locale, "en_US")
        self.assertEqual(template.alert_type, UsageAlertType.INTERNATIONAL_50_PERCENT)
        self.assertTrue(template.legal_approved)

    def test_sms_template_has_placeholders(self):
        """Test SMS template body has required placeholders."""
        template = get_sms_template("en_US")

        self.assertIn("{first_name}", template.body)
        self.assertIn("{percentage}", template.body)
        self.assertIn("{usage_url}", template.body)

    def test_sms_rendering(self):
        """Test SMS template renders correctly with data."""
        template = get_sms_template("en_US")
        data = UsageAlertData(
            user_id="user123",
            account_id="acc456",
            phone_number="+15551234567",
            first_name="John",
            current_usage_amount=Decimal("25.00"),
            threshold_amount=Decimal("50.00"),
            threshold_percentage=50,
        )

        rendered = render_sms(template, data)

        self.assertIn("John", rendered)
        self.assertIn("50%", rendered)
        self.assertIn("USD 25.00", rendered)


class TestEmailTemplate(unittest.TestCase):
    """Tests for email notification template."""

    def test_email_template_creation(self):
        """Test email template has correct attributes."""
        template = get_email_template("en_US")

        self.assertEqual(template.channel, NotificationChannel.EMAIL)
        self.assertIsNotNone(template.subject)
        self.assertIsNotNone(template.body)
        self.assertIsNotNone(template.html_body)

    def test_email_template_has_action_links(self):
        """Test email template includes links to actions."""
        template = get_email_template("en_US")

        self.assertIn("{buy_pass_url}", template.body)
        self.assertIn("{change_plan_url}", template.body)
        self.assertIn("{usage_url}", template.body)

    def test_email_html_has_buttons(self):
        """Test email HTML has action buttons."""
        template = get_email_template("en_US")

        self.assertIn("{buy_pass_url}", template.html_body)
        self.assertIn("International Pass", template.html_body)

    def test_email_rendering(self):
        """Test email template renders correctly with data."""
        template = get_email_template("en_US")
        data = UsageAlertData(
            user_id="user123",
            account_id="acc456",
            phone_number="+15551234567",
            email="john@example.com",
            first_name="John",
            current_usage_amount=Decimal("25.00"),
            threshold_amount=Decimal("50.00"),
            threshold_percentage=50,
            billing_cycle_end=datetime(2026, 2, 28),
        )

        rendered = render_email(template, data)

        self.assertIn("John", rendered["body"])
        self.assertIn("50%", rendered["subject"])
        self.assertIn("February 28, 2026", rendered["body"])


class TestPushTemplate(unittest.TestCase):
    """Tests for push notification template."""

    def test_push_template_creation(self):
        """Test push template has correct attributes."""
        template = get_push_template("en_US")

        self.assertEqual(template.channel, NotificationChannel.PUSH)
        self.assertIsNotNone(template.title)
        self.assertIsNotNone(template.body)

    def test_push_rendering(self):
        """Test push template renders correctly with data."""
        template = get_push_template("en_US")
        data = UsageAlertData(
            user_id="user123",
            account_id="acc456",
            phone_number="+15551234567",
            first_name="John",
            current_usage_amount=Decimal("25.00"),
            threshold_percentage=50,
        )

        rendered = render_push(template, data)

        self.assertIn("John", rendered["body"])
        self.assertIn("50%", rendered["body"])
        self.assertIn("deep_link", rendered)


class TestAllTemplates(unittest.TestCase):
    """Tests for getting all templates at once."""

    def test_get_all_templates(self):
        """Test get_all_templates returns all channels."""
        templates = get_all_templates("en_US")

        self.assertEqual(len(templates), 3)
        self.assertIn(NotificationChannel.SMS, templates)
        self.assertIn(NotificationChannel.EMAIL, templates)
        self.assertIn(NotificationChannel.PUSH, templates)

    def test_all_templates_localized(self):
        """Test all templates are localized for each supported locale."""
        for locale in get_supported_locales():
            templates = get_all_templates(locale)

            for channel, template in templates.items():
                self.assertEqual(
                    template.locale,
                    locale,
                    f"Template for {channel.value} has wrong locale: {template.locale}",
                )


class TestNotificationService(unittest.TestCase):
    """Tests for NotificationService."""

    def setUp(self):
        """Set up test fixtures."""
        self.sms_provider = MockSMSProvider()
        self.email_provider = MockEmailProvider()
        self.push_provider = MockPushProvider()

        self.service = NotificationService(
            config=NotificationServiceConfig(),
            sms_provider=self.sms_provider,
            email_provider=self.email_provider,
            push_provider=self.push_provider,
        )

        self.test_data = UsageAlertData(
            user_id="user123",
            account_id="acc456",
            phone_number="+15551234567",
            email="test@example.com",
            first_name="Test",
            current_usage_amount=Decimal("25.00"),
            threshold_amount=Decimal("50.00"),
            threshold_percentage=50,
            device_tokens=["device_token_123"],
        )

    def test_send_sms_success(self):
        """Test successful SMS delivery."""
        result = self.service.send_usage_alert(
            channel=NotificationChannel.SMS,
            data=self.test_data,
        )

        self.assertEqual(result.status, DeliveryStatus.SENT)
        self.assertEqual(len(self.sms_provider.sent_messages), 1)
        self.assertIn("Test", self.sms_provider.sent_messages[0]["message"])

    def test_send_email_success(self):
        """Test successful email delivery."""
        result = self.service.send_usage_alert(
            channel=NotificationChannel.EMAIL,
            data=self.test_data,
        )

        self.assertEqual(result.status, DeliveryStatus.SENT)
        self.assertEqual(len(self.email_provider.sent_emails), 1)
        self.assertEqual(
            self.email_provider.sent_emails[0]["to_address"],
            "test@example.com",
        )

    def test_send_push_success(self):
        """Test successful push notification delivery."""
        result = self.service.send_usage_alert(
            channel=NotificationChannel.PUSH,
            data=self.test_data,
        )

        self.assertEqual(result.status, DeliveryStatus.SENT)
        self.assertEqual(len(self.push_provider.sent_notifications), 1)

    def test_send_all_channels(self):
        """Test sending to all channels at once."""
        results = self.service.send_usage_alert_all_channels(data=self.test_data)

        self.assertEqual(len(results), 3)
        for result in results:
            self.assertEqual(result.status, DeliveryStatus.SENT)

    def test_disabled_channel(self):
        """Test that disabled channels are not used."""
        service = NotificationService(
            config=NotificationServiceConfig(sms_enabled=False),
            sms_provider=self.sms_provider,
        )

        result = service.send_usage_alert(
            channel=NotificationChannel.SMS,
            data=self.test_data,
        )

        self.assertEqual(result.status, DeliveryStatus.FAILED)
        self.assertEqual(result.error_code, "CHANNEL_DISABLED")

    def test_dry_run_mode(self):
        """Test dry run mode doesn't actually send."""
        service = NotificationService(
            config=NotificationServiceConfig(dry_run=True),
            sms_provider=self.sms_provider,
        )

        result = service.send_usage_alert(
            channel=NotificationChannel.SMS,
            data=self.test_data,
        )

        self.assertEqual(result.status, DeliveryStatus.SENT)
        self.assertEqual(len(self.sms_provider.sent_messages), 0)

    def test_missing_provider(self):
        """Test error handling when provider is not configured."""
        service = NotificationService(
            config=NotificationServiceConfig(),
            # No providers configured
        )

        result = service.send_usage_alert(
            channel=NotificationChannel.SMS,
            data=self.test_data,
        )

        self.assertEqual(result.status, DeliveryStatus.FAILED)
        self.assertEqual(result.error_code, "NO_PROVIDER")


class TestUsageEventHandler(unittest.TestCase):
    """Tests for UsageEventHandler."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = create_test_notification_service()
        self.handler = UsageEventHandler(notification_service=self.service)

        self.test_event = UsageEvent(
            event_type="international_usage_50_percent",
            user_id="user123",
            account_id="acc456",
            timestamp=datetime.now(timezone.utc),
            current_usage_amount=Decimal("25.00"),
            threshold_amount=Decimal("50.00"),
            threshold_percentage=50,
            usage_type="international",
            phone_number="+15551234567",
            email="test@example.com",
            first_name="Test",
            device_tokens=["device_token_123"],
        )

    def test_handle_event_sends_notifications(self):
        """Test that handling an event sends notifications."""
        results = self.handler.handle_event(self.test_event)

        # Should send to all 3 channels
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertTrue(result.is_successful())

    def test_unknown_event_type_ignored(self):
        """Test that unknown event types are ignored."""
        self.test_event.event_type = "unknown_event"
        results = self.handler.handle_event(self.test_event)

        self.assertEqual(len(results), 0)

    def test_handle_raw_event(self):
        """Test handling raw event dictionary."""
        raw_event = {
            "event_type": "international_usage_50_percent",
            "user_id": "user123",
            "account_id": "acc456",
            "phone_number": "+15551234567",
            "email": "test@example.com",
            "current_usage_amount": "25.00",
            "threshold_amount": "50.00",
            "threshold_percentage": 50,
        }

        results = self.handler.handle_raw_event(raw_event)

        self.assertEqual(len(results), 3)

    def test_callback_invoked(self):
        """Test that registered callbacks are invoked."""
        callback_invoked = []

        def test_callback(event, results):
            callback_invoked.append((event, results))

        self.handler.register_callback(test_callback)
        self.handler.handle_event(self.test_event)

        self.assertEqual(len(callback_invoked), 1)
        self.assertEqual(callback_invoked[0][0], self.test_event)


class TestLocalizedNotificationDelivery(unittest.TestCase):
    """Integration tests for localized notification delivery."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = create_test_notification_service()

    def test_spanish_sms_delivery(self):
        """Test SMS delivery with Spanish localization."""
        data = UsageAlertData(
            user_id="user123",
            account_id="acc456",
            phone_number="+15551234567",
            first_name="Juan",
            locale="es_MX",
            current_usage_amount=Decimal("25.00"),
            threshold_amount=Decimal("50.00"),
        )

        result = self.service.send_usage_alert(
            channel=NotificationChannel.SMS,
            data=data,
        )

        self.assertTrue(result.is_successful())

        # Check the message was in Spanish
        sms_provider = self.service.sms_provider
        self.assertIn("límite internacional", sms_provider.sent_messages[0]["message"])

    def test_french_email_delivery(self):
        """Test email delivery with French localization."""
        data = UsageAlertData(
            user_id="user123",
            account_id="acc456",
            phone_number="+15551234567",
            email="jean@example.com",
            first_name="Jean",
            locale="fr_CA",
            current_usage_amount=Decimal("25.00"),
            threshold_amount=Decimal("50.00"),
        )

        result = self.service.send_usage_alert(
            channel=NotificationChannel.EMAIL,
            data=data,
        )

        self.assertTrue(result.is_successful())

        # Check the email was in French
        email_provider = self.service.email_provider
        self.assertIn(
            "limite d'utilisation internationale",
            email_provider.sent_emails[0]["subject"],
        )

    def test_german_push_delivery(self):
        """Test push delivery with German localization."""
        data = UsageAlertData(
            user_id="user123",
            account_id="acc456",
            phone_number="+15551234567",
            first_name="Hans",
            locale="de_DE",
            current_usage_amount=Decimal("25.00"),
            device_tokens=["device_token_123"],
        )

        result = self.service.send_usage_alert(
            channel=NotificationChannel.PUSH,
            data=data,
        )

        self.assertTrue(result.is_successful())

        # Check the notification was in German
        push_provider = self.service.push_provider
        self.assertIn(
            "Internationale Nutzungswarnung",
            push_provider.sent_notifications[0]["title"],
        )


class TestNotificationContent(unittest.TestCase):
    """Tests for notification content requirements."""

    def test_usage_details_link_included(self):
        """Test that usage details link is included in all channels."""
        data = UsageAlertData(
            user_id="user123",
            account_id="acc456",
            phone_number="+15551234567",
            usage_details_url="https://example.com/usage",
        )

        # Check SMS
        sms_template = get_sms_template("en_US")
        sms_rendered = render_sms(sms_template, data)
        self.assertIn("https://example.com/usage", sms_rendered)

        # Check Email
        email_template = get_email_template("en_US")
        email_rendered = render_email(email_template, data)
        self.assertIn("https://example.com/usage", email_rendered["body"])
        self.assertIn("https://example.com/usage", email_rendered["html_body"])

        # Check Push (deep link)
        push_template = get_push_template("en_US")
        push_rendered = render_push(push_template, data)
        self.assertEqual(push_rendered["deep_link"], "https://example.com/usage")

    def test_recommended_actions_included(self):
        """Test that recommended actions are included in email."""
        data = UsageAlertData(
            user_id="user123",
            account_id="acc456",
            phone_number="+15551234567",
            email="test@example.com",
            buy_pass_url="https://example.com/pass",
            change_plan_url="https://example.com/plan",
        )

        email_template = get_email_template("en_US")
        email_rendered = render_email(email_template, data)

        # Check buy pass link
        self.assertIn("https://example.com/pass", email_rendered["body"])
        self.assertIn("https://example.com/pass", email_rendered["html_body"])

        # Check change plan link
        self.assertIn("https://example.com/plan", email_rendered["body"])
        self.assertIn("https://example.com/plan", email_rendered["html_body"])

    def test_legal_approval_status(self):
        """Test that templates are marked as legally approved."""
        for locale in get_supported_locales():
            templates = get_all_templates(locale)

            for channel, template in templates.items():
                self.assertTrue(
                    template.legal_approved,
                    f"Template {channel.value}/{locale} is not legally approved",
                )
                self.assertIsNotNone(
                    template.legal_approval_date,
                    f"Template {channel.value}/{locale} has no approval date",
                )


if __name__ == "__main__":
    unittest.main()
