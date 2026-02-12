"""
Tests for billing integration module.

Tests cover:
- Applying credits to billing accounts
- Posting credits to invoices
- Credit memo generation
- Application record creation for audit trail
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from tradein.models import (
    TradeInTransaction,
    TradeInCredit,
    CreditStatus,
    ApplicationTarget,
    DeviceCondition,
)
from tradein.billing_integration import (
    BillingCreditIntegration,
    BillingCreditResult,
    MockBillingSystemClient,
)


class TestBillingCreditIntegration:
    """Tests for BillingCreditIntegration class."""

    @pytest.fixture
    def billing_client(self):
        """Create a mock billing system client."""
        client = MockBillingSystemClient()
        # Create some test accounts and invoices
        client.create_test_account("ACCT-001", Decimal("100.00"), "active")
        client.create_test_account("ACCT-002", Decimal("0"), "active")
        client.create_test_account("ACCT-003", Decimal("500.00"), "closed")
        client.create_test_invoice("INV-001", "ACCT-001", Decimal("250.00"), "pending")
        client.create_test_invoice("INV-002", "ACCT-002", Decimal("100.00"), "pending")
        return client

    @pytest.fixture
    def integration(self, billing_client):
        """Create a BillingCreditIntegration instance."""
        return BillingCreditIntegration(billing_client)

    @pytest.fixture
    def approved_transaction(self):
        """Create an approved trade-in transaction."""
        return TradeInTransaction(
            transaction_id="TXN-BILL-001",
            quote_id="QUOTE-BILL-001",
            customer_id="CUST-BILL-001",
            partner_id="PARTNER-BILL-001",
            device_imei="987654321098765",
            device_model="Samsung Galaxy S24 Ultra",
            device_condition=DeviceCondition.GOOD,
            quoted_value=Decimal("600.00"),
            approved_value=Decimal("550.00"),
            quote_timestamp=datetime.utcnow(),
            approval_timestamp=datetime.utcnow(),
            expiration_date=date.today() + timedelta(days=30),
        )

    @pytest.fixture
    def test_credit(self, approved_transaction):
        """Create a test credit from the approved transaction."""
        return TradeInCredit.from_transaction(approved_transaction, "ACCT-001")

    def test_apply_credit_to_billing_success(self, integration, test_credit):
        """Test successfully applying a credit to billing."""
        result = integration.apply_credit_to_billing(
            credit=test_credit,
            applied_by="test_user",
            partner_id="PARTNER-BILL-001",
        )

        assert result.success is True
        assert result.account_id == "ACCT-001"
        assert result.credit_id == test_credit.credit_id
        assert result.trade_in_transaction_id == "TXN-BILL-001"
        assert result.amount_applied == Decimal("550.00")
        assert result.credit_memo_id is not None
        assert result.application_record is not None

    def test_apply_credit_to_specific_invoice(self, integration, test_credit, billing_client):
        """Test applying credit to a specific invoice."""
        result = integration.apply_credit_to_billing(
            credit=test_credit,
            applied_by="test_user",
            invoice_id="INV-001",
        )

        assert result.success is True
        assert result.invoice_id == "INV-001"
        assert result.amount_applied == Decimal("550.00")

        # Check invoice was updated
        invoice = billing_client.get_invoice("INV-001")
        assert invoice["credits_applied"] == Decimal("550.00")

    def test_apply_partial_credit_to_billing(self, integration, test_credit):
        """Test applying a partial credit amount to billing."""
        result = integration.apply_credit_to_billing(
            credit=test_credit,
            applied_by="test_user",
            amount=Decimal("200.00"),
        )

        assert result.success is True
        assert result.amount_applied == Decimal("200.00")
        assert test_credit.remaining_amount == Decimal("350.00")

    def test_reject_expired_credit(self, integration):
        """Test that expired credits are rejected."""
        expired_credit = TradeInCredit(
            credit_id="CREDIT-EXP-BILL-001",
            trade_in_transaction_id="TXN-EXP-BILL-001",
            amount=Decimal("300.00"),
            remaining_amount=Decimal("300.00"),
            status=CreditStatus.EXPIRED,
            created_at=datetime.utcnow(),
            customer_id="CUST-EXP-001",
            account_id="ACCT-001",
        )

        result = integration.apply_credit_to_billing(
            credit=expired_credit,
            applied_by="test_user",
        )

        assert result.success is False
        assert "invalid status" in result.error_message.lower()

    def test_reject_cancelled_credit(self, integration):
        """Test that cancelled credits are rejected."""
        cancelled_credit = TradeInCredit(
            credit_id="CREDIT-CAN-BILL-001",
            trade_in_transaction_id="TXN-CAN-BILL-001",
            amount=Decimal("300.00"),
            remaining_amount=Decimal("300.00"),
            status=CreditStatus.CANCELLED,
            created_at=datetime.utcnow(),
            customer_id="CUST-CAN-001",
            account_id="ACCT-001",
        )

        result = integration.apply_credit_to_billing(
            credit=cancelled_credit,
            applied_by="test_user",
        )

        assert result.success is False
        assert "invalid status" in result.error_message.lower()

    def test_reject_zero_remaining_credit(self, integration, test_credit):
        """Test that credits with zero remaining are rejected."""
        # Use up the credit
        test_credit.apply_to_billing("INV-999", test_credit.remaining_amount)

        result = integration.apply_credit_to_billing(
            credit=test_credit,
            applied_by="test_user",
        )

        assert result.success is False
        assert "no remaining" in result.error_message.lower()

    def test_reject_closed_account(self, integration):
        """Test that credits cannot be applied to closed accounts."""
        credit = TradeInCredit(
            credit_id="CREDIT-CLOSED-001",
            trade_in_transaction_id="TXN-CLOSED-001",
            amount=Decimal("300.00"),
            remaining_amount=Decimal("300.00"),
            status=CreditStatus.PENDING,
            created_at=datetime.utcnow(),
            customer_id="CUST-CLOSED-001",
            account_id="ACCT-003",  # Closed account
        )

        result = integration.apply_credit_to_billing(
            credit=credit,
            applied_by="test_user",
        )

        assert result.success is False
        assert "closed" in result.error_message.lower()

    def test_apply_transaction_to_billing_convenience_method(self, integration, approved_transaction):
        """Test the convenience method for applying transaction directly to billing."""
        result = integration.apply_transaction_to_billing(
            transaction=approved_transaction,
            account_id="ACCT-001",
            applied_by="test_user",
        )

        assert result.success is True
        assert result.trade_in_transaction_id == "TXN-BILL-001"
        assert result.amount_applied == Decimal("550.00")

    def test_application_records_created(self, integration, test_credit):
        """Test that application records are created for audit trail."""
        integration.apply_credit_to_billing(
            credit=test_credit,
            applied_by="test_user",
            invoice_id="INV-001",
            partner_id="PARTNER-001",
        )

        records = integration.get_application_records()
        assert len(records) == 1

        record = records[0]
        assert record.credit_id == test_credit.credit_id
        assert record.trade_in_transaction_id == test_credit.trade_in_transaction_id
        assert record.target == ApplicationTarget.BILLING
        assert record.partner_id == "PARTNER-001"

    def test_get_applications_by_account(self, integration, test_credit):
        """Test retrieving applications by account ID."""
        integration.apply_credit_to_billing(
            credit=test_credit,
            applied_by="test_user",
        )

        apps = integration.get_applications_by_account("ACCT-001")
        assert len(apps) == 1
        assert apps[0].account_id == "ACCT-001"

        # Non-existent account should return empty list
        apps = integration.get_applications_by_account("ACCT-999")
        assert len(apps) == 0

    def test_get_applications_by_invoice(self, integration, test_credit):
        """Test retrieving applications by invoice ID."""
        integration.apply_credit_to_billing(
            credit=test_credit,
            applied_by="test_user",
            invoice_id="INV-001",
        )

        apps = integration.get_applications_by_invoice("INV-001")
        assert len(apps) == 1
        assert apps[0].target_id == "INV-001"

    def test_get_applications_by_transaction(self, integration, test_credit):
        """Test retrieving applications by transaction ID."""
        integration.apply_credit_to_billing(
            credit=test_credit,
            applied_by="test_user",
        )

        apps = integration.get_applications_by_transaction(test_credit.trade_in_transaction_id)
        assert len(apps) == 1
        assert apps[0].trade_in_transaction_id == test_credit.trade_in_transaction_id

    def test_result_to_dict(self, integration, test_credit):
        """Test that results can be serialized to dict."""
        result = integration.apply_credit_to_billing(
            credit=test_credit,
            applied_by="test_user",
        )

        result_dict = result.to_dict()
        assert result_dict["success"] is True
        assert result_dict["account_id"] == "ACCT-001"
        assert result_dict["credit_id"] == test_credit.credit_id
        assert result_dict["trade_in_transaction_id"] == test_credit.trade_in_transaction_id
        assert "timestamp" in result_dict


class TestMockBillingSystemClient:
    """Tests for the mock billing system client."""

    def test_create_test_account(self):
        """Test creating a test account."""
        client = MockBillingSystemClient()
        account = client.create_test_account("ACCT-TEST-001", Decimal("100.00"), "active")

        assert account["account_id"] == "ACCT-TEST-001"
        assert account["balance"] == Decimal("100.00")
        assert account["status"] == "active"

    def test_create_test_invoice(self):
        """Test creating a test invoice."""
        client = MockBillingSystemClient()
        invoice = client.create_test_invoice(
            "INV-TEST-001", "ACCT-TEST-001", Decimal("250.00"), "pending"
        )

        assert invoice["invoice_id"] == "INV-TEST-001"
        assert invoice["account_id"] == "ACCT-TEST-001"
        assert invoice["amount"] == Decimal("250.00")
        assert invoice["amount_due"] == Decimal("250.00")

    def test_post_credit_creates_credit_memo(self):
        """Test that posting credit creates a credit memo."""
        client = MockBillingSystemClient()
        client.create_test_account("ACCT-TEST-002", Decimal("0"), "active")

        result = client.post_credit(
            account_id="ACCT-TEST-002",
            amount=Decimal("100.00"),
            description="Trade-in credit",
            reference_id="TRADEIN:TXN-001:CREDIT-001",
        )

        assert "credit_memo_id" in result
        assert result["amount"] == Decimal("100.00")
        assert result["reference_id"] == "TRADEIN:TXN-001:CREDIT-001"

        # Check account was updated
        account = client.get_account("ACCT-TEST-002")
        assert account["credit_balance"] == Decimal("100.00")

    def test_post_credit_to_invoice(self):
        """Test that posting credit to an invoice updates it."""
        client = MockBillingSystemClient()
        client.create_test_account("ACCT-TEST-003", Decimal("0"), "active")
        client.create_test_invoice("INV-TEST-002", "ACCT-TEST-003", Decimal("200.00"), "pending")

        client.post_credit(
            account_id="ACCT-TEST-003",
            amount=Decimal("75.00"),
            description="Trade-in credit",
            reference_id="REF-001",
            invoice_id="INV-TEST-002",
        )

        invoice = client.get_invoice("INV-TEST-002")
        assert invoice["credits_applied"] == Decimal("75.00")
        assert invoice["amount_due"] == Decimal("125.00")

    def test_validate_account_for_credit(self):
        """Test account validation for credit application."""
        client = MockBillingSystemClient()
        client.create_test_account("ACCT-VALID", Decimal("0"), "active")
        client.create_test_account("ACCT-CLOSED", Decimal("0"), "closed")
        client.create_test_account("ACCT-SUSPENDED", Decimal("0"), "suspended")

        valid, reason = client.validate_account_for_credit("ACCT-VALID")
        assert valid is True

        valid, reason = client.validate_account_for_credit("ACCT-CLOSED")
        assert valid is False
        assert "closed" in reason.lower()

        valid, reason = client.validate_account_for_credit("ACCT-SUSPENDED")
        assert valid is False
        assert "suspended" in reason.lower()
