"""
Tests for trade-in credit data models.

Tests cover:
- TradeInTransaction creation and validation
- TradeInCredit creation from transactions
- Credit application to orders and billing
- Audit trail recording
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from tradein.models import (
    TradeInTransaction,
    TradeInCredit,
    CreditApplication,
    CreditStatus,
    ApplicationTarget,
    DeviceCondition,
)


class TestTradeInTransaction:
    """Tests for TradeInTransaction model."""

    def test_create_transaction(self):
        """Test creating a basic trade-in transaction."""
        transaction = TradeInTransaction(
            transaction_id="TXN-001",
            quote_id="QUOTE-001",
            customer_id="CUST-001",
            partner_id="PARTNER-001",
            device_imei="123456789012345",
            device_model="iPhone 14 Pro",
            device_condition=DeviceCondition.GOOD,
            quoted_value=Decimal("500.00"),
            approved_value=Decimal("450.00"),
            quote_timestamp=datetime.utcnow(),
        )

        assert transaction.transaction_id == "TXN-001"
        assert transaction.quoted_value == Decimal("500.00")
        assert transaction.approved_value == Decimal("450.00")
        assert transaction.device_condition == DeviceCondition.GOOD

    def test_monetary_values_quantized(self):
        """Test that monetary values are quantized to 2 decimal places."""
        transaction = TradeInTransaction(
            transaction_id="TXN-002",
            quote_id="QUOTE-002",
            customer_id="CUST-002",
            partner_id="PARTNER-002",
            device_imei="123456789012346",
            device_model="Samsung Galaxy S23",
            device_condition=DeviceCondition.EXCELLENT,
            quoted_value=500.999,  # Should be quantized
            approved_value=450.001,  # Should be quantized
            quote_timestamp=datetime.utcnow(),
        )

        assert transaction.quoted_value == Decimal("501.00")
        assert transaction.approved_value == Decimal("450.00")

    def test_is_approved(self):
        """Test approval status checking."""
        transaction = TradeInTransaction(
            transaction_id="TXN-003",
            quote_id="QUOTE-003",
            customer_id="CUST-003",
            partner_id="PARTNER-003",
            device_imei="123456789012347",
            device_model="Pixel 8",
            device_condition=DeviceCondition.FAIR,
            quoted_value=Decimal("300.00"),
            approved_value=Decimal("250.00"),
            quote_timestamp=datetime.utcnow(),
        )

        # Not approved yet
        assert not transaction.is_approved()

        # Approve
        transaction.approval_timestamp = datetime.utcnow()
        assert transaction.is_approved()

    def test_is_expired(self):
        """Test expiration status checking."""
        transaction = TradeInTransaction(
            transaction_id="TXN-004",
            quote_id="QUOTE-004",
            customer_id="CUST-004",
            partner_id="PARTNER-004",
            device_imei="123456789012348",
            device_model="iPhone 13",
            device_condition=DeviceCondition.GOOD,
            quoted_value=Decimal("400.00"),
            approved_value=Decimal("380.00"),
            quote_timestamp=datetime.utcnow(),
            expiration_date=date.today() - timedelta(days=1),  # Yesterday
        )

        assert transaction.is_expired()

        # Not expired
        transaction.expiration_date = date.today() + timedelta(days=30)
        assert not transaction.is_expired()

        # No expiration
        transaction.expiration_date = None
        assert not transaction.is_expired()


class TestTradeInCredit:
    """Tests for TradeInCredit model."""

    @pytest.fixture
    def approved_transaction(self):
        """Create an approved transaction for testing."""
        return TradeInTransaction(
            transaction_id="TXN-100",
            quote_id="QUOTE-100",
            customer_id="CUST-100",
            partner_id="PARTNER-100",
            device_imei="999888777666555",
            device_model="iPhone 15 Pro Max",
            device_condition=DeviceCondition.EXCELLENT,
            quoted_value=Decimal("800.00"),
            approved_value=Decimal("750.00"),
            quote_timestamp=datetime.utcnow(),
            approval_timestamp=datetime.utcnow(),
            expiration_date=date.today() + timedelta(days=30),
        )

    def test_create_credit_from_transaction(self, approved_transaction):
        """Test creating a credit from an approved transaction."""
        credit = TradeInCredit.from_transaction(approved_transaction, "ACCT-100")

        assert credit.trade_in_transaction_id == "TXN-100"
        assert credit.amount == Decimal("750.00")
        assert credit.remaining_amount == Decimal("750.00")
        assert credit.status == CreditStatus.PENDING
        assert credit.customer_id == "CUST-100"
        assert credit.account_id == "ACCT-100"
        assert len(credit.audit_log) == 1
        assert credit.audit_log[0]["action"] == "CREDIT_CREATED"

    def test_cannot_create_credit_from_unapproved_transaction(self):
        """Test that credits cannot be created from unapproved transactions."""
        unapproved = TradeInTransaction(
            transaction_id="TXN-101",
            quote_id="QUOTE-101",
            customer_id="CUST-101",
            partner_id="PARTNER-101",
            device_imei="111222333444555",
            device_model="Galaxy S24",
            device_condition=DeviceCondition.GOOD,
            quoted_value=Decimal("600.00"),
            approved_value=Decimal("550.00"),
            quote_timestamp=datetime.utcnow(),
            # No approval_timestamp
        )

        with pytest.raises(ValueError, match="unapproved transaction"):
            TradeInCredit.from_transaction(unapproved, "ACCT-101")

    def test_cannot_create_credit_from_expired_transaction(self):
        """Test that credits cannot be created from expired transactions."""
        expired = TradeInTransaction(
            transaction_id="TXN-102",
            quote_id="QUOTE-102",
            customer_id="CUST-102",
            partner_id="PARTNER-102",
            device_imei="222333444555666",
            device_model="Pixel 7",
            device_condition=DeviceCondition.FAIR,
            quoted_value=Decimal("300.00"),
            approved_value=Decimal("250.00"),
            quote_timestamp=datetime.utcnow(),
            approval_timestamp=datetime.utcnow(),
            expiration_date=date.today() - timedelta(days=1),  # Expired
        )

        with pytest.raises(ValueError, match="expired transaction"):
            TradeInCredit.from_transaction(expired, "ACCT-102")

    def test_apply_to_order(self, approved_transaction):
        """Test applying credit to an order."""
        credit = TradeInCredit.from_transaction(approved_transaction, "ACCT-100")
        initial_amount = credit.remaining_amount

        applied = credit.apply_to_order("ORD-001", Decimal("300.00"))

        assert applied == Decimal("300.00")
        assert credit.remaining_amount == initial_amount - Decimal("300.00")
        assert credit.applied_to_order_id == "ORD-001"
        assert credit.status == CreditStatus.PARTIALLY_APPLIED
        assert len(credit.audit_log) == 2  # Created + applied

    def test_apply_full_credit_to_order(self, approved_transaction):
        """Test applying full credit amount to an order."""
        credit = TradeInCredit.from_transaction(approved_transaction, "ACCT-100")

        applied = credit.apply_to_order("ORD-002")  # No amount = full credit

        assert applied == Decimal("750.00")
        assert credit.remaining_amount == Decimal("0")
        assert credit.status == CreditStatus.APPLIED_TO_ORDER

    def test_apply_to_billing(self, approved_transaction):
        """Test applying credit to billing."""
        credit = TradeInCredit.from_transaction(approved_transaction, "ACCT-100")

        applied = credit.apply_to_billing("INV-001", Decimal("200.00"))

        assert applied == Decimal("200.00")
        assert credit.remaining_amount == Decimal("550.00")
        assert credit.applied_to_invoice_id == "INV-001"
        assert credit.status == CreditStatus.PARTIALLY_APPLIED

    def test_apply_to_both_order_and_billing(self, approved_transaction):
        """Test applying credit to both order and billing."""
        credit = TradeInCredit.from_transaction(approved_transaction, "ACCT-100")

        # Apply to order first
        credit.apply_to_order("ORD-003", Decimal("400.00"))
        assert credit.status == CreditStatus.PARTIALLY_APPLIED

        # Apply remaining to billing
        credit.apply_to_billing("INV-002")
        assert credit.remaining_amount == Decimal("0")
        assert credit.status == CreditStatus.FULLY_APPLIED

    def test_cannot_apply_expired_credit(self, approved_transaction):
        """Test that expired credits cannot be applied."""
        credit = TradeInCredit.from_transaction(approved_transaction, "ACCT-100")
        credit.expire()

        with pytest.raises(ValueError, match="invalid status"):
            credit.apply_to_order("ORD-004")

    def test_cannot_apply_cancelled_credit(self, approved_transaction):
        """Test that cancelled credits cannot be applied."""
        credit = TradeInCredit.from_transaction(approved_transaction, "ACCT-100")
        credit.cancel("Trade-in device rejected")

        with pytest.raises(ValueError, match="invalid status"):
            credit.apply_to_billing("INV-003")

    def test_cannot_exceed_remaining_amount(self, approved_transaction):
        """Test that applications are capped at remaining amount."""
        credit = TradeInCredit.from_transaction(approved_transaction, "ACCT-100")

        # Try to apply more than available
        applied = credit.apply_to_order("ORD-005", Decimal("1000.00"))

        assert applied == Decimal("750.00")  # Capped at remaining
        assert credit.remaining_amount == Decimal("0")

    def test_audit_log_records_all_actions(self, approved_transaction):
        """Test that audit log captures all credit actions."""
        credit = TradeInCredit.from_transaction(approved_transaction, "ACCT-100")

        credit.apply_to_order("ORD-006", Decimal("200.00"))
        credit.apply_to_billing("INV-004", Decimal("300.00"))

        assert len(credit.audit_log) == 3
        assert credit.audit_log[0]["action"] == "CREDIT_CREATED"
        assert credit.audit_log[1]["action"] == "APPLIED_TO_ORDER"
        assert credit.audit_log[2]["action"] == "APPLIED_TO_BILLING"

        # Each entry should have the transaction ID for traceability
        for entry in credit.audit_log:
            assert entry["trade_in_transaction_id"] == "TXN-100"


class TestCreditApplication:
    """Tests for CreditApplication model."""

    @pytest.fixture
    def test_credit(self):
        """Create a test credit for application recording."""
        return TradeInCredit(
            credit_id="CREDIT-200",
            trade_in_transaction_id="TXN-200",
            amount=Decimal("500.00"),
            remaining_amount=Decimal("500.00"),
            status=CreditStatus.PENDING,
            created_at=datetime.utcnow(),
            customer_id="CUST-200",
            account_id="ACCT-200",
        )

    def test_record_order_application(self, test_credit):
        """Test recording a credit application to an order."""
        application = CreditApplication.record_application(
            credit=test_credit,
            target=ApplicationTarget.ORDER,
            target_id="ORD-200",
            amount=Decimal("300.00"),
            applied_by="system",
            partner_id="PARTNER-200",
        )

        assert application.credit_id == "CREDIT-200"
        assert application.trade_in_transaction_id == "TXN-200"
        assert application.target == ApplicationTarget.ORDER
        assert application.target_id == "ORD-200"
        assert application.amount_applied == Decimal("300.00")
        assert application.applied_by == "system"
        assert application.partner_id == "PARTNER-200"
        assert application.customer_id == "CUST-200"
        assert application.account_id == "ACCT-200"

    def test_record_billing_application(self, test_credit):
        """Test recording a credit application to billing."""
        application = CreditApplication.record_application(
            credit=test_credit,
            target=ApplicationTarget.BILLING,
            target_id="INV-200",
            amount=Decimal("200.00"),
            applied_by="billing_system",
        )

        assert application.target == ApplicationTarget.BILLING
        assert application.target_id == "INV-200"
        assert application.amount_applied == Decimal("200.00")

    def test_application_has_unique_id(self, test_credit):
        """Test that each application has a unique ID."""
        app1 = CreditApplication.record_application(
            credit=test_credit,
            target=ApplicationTarget.ORDER,
            target_id="ORD-201",
            amount=Decimal("100.00"),
            applied_by="system",
        )
        app2 = CreditApplication.record_application(
            credit=test_credit,
            target=ApplicationTarget.ORDER,
            target_id="ORD-202",
            amount=Decimal("100.00"),
            applied_by="system",
        )

        assert app1.application_id != app2.application_id
