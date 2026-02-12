"""
Tests for order integration module.

Tests cover:
- Applying credits to orders at placement/activation time
- Credit validation before application
- Order total reduction
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
from tradein.order_integration import (
    OrderCreditIntegration,
    OrderCreditResult,
    MockOrderSystemClient,
)


class TestOrderCreditIntegration:
    """Tests for OrderCreditIntegration class."""

    @pytest.fixture
    def order_client(self):
        """Create a mock order system client."""
        client = MockOrderSystemClient()
        # Create some test orders
        client.create_test_order("ORD-001", Decimal("1000.00"), "pending")
        client.create_test_order("ORD-002", Decimal("500.00"), "pending")
        client.create_test_order("ORD-003", Decimal("200.00"), "cancelled")
        return client

    @pytest.fixture
    def integration(self, order_client):
        """Create an OrderCreditIntegration instance."""
        return OrderCreditIntegration(order_client)

    @pytest.fixture
    def approved_transaction(self):
        """Create an approved trade-in transaction."""
        return TradeInTransaction(
            transaction_id="TXN-ORD-001",
            quote_id="QUOTE-ORD-001",
            customer_id="CUST-ORD-001",
            partner_id="PARTNER-ORD-001",
            device_imei="123456789012345",
            device_model="iPhone 15",
            device_condition=DeviceCondition.EXCELLENT,
            quoted_value=Decimal("800.00"),
            approved_value=Decimal("750.00"),
            quote_timestamp=datetime.utcnow(),
            approval_timestamp=datetime.utcnow(),
            expiration_date=date.today() + timedelta(days=30),
        )

    @pytest.fixture
    def test_credit(self, approved_transaction):
        """Create a test credit from the approved transaction."""
        return TradeInCredit.from_transaction(approved_transaction, "ACCT-ORD-001")

    def test_apply_credit_to_order_success(self, integration, test_credit):
        """Test successfully applying a credit to an order."""
        result = integration.apply_credit_to_order(
            credit=test_credit,
            order_id="ORD-001",
            applied_by="test_user",
            partner_id="PARTNER-ORD-001",
        )

        assert result.success is True
        assert result.order_id == "ORD-001"
        assert result.credit_id == test_credit.credit_id
        assert result.trade_in_transaction_id == "TXN-ORD-001"
        assert result.amount_applied == Decimal("750.00")
        assert result.order_total_before == Decimal("1000.00")
        assert result.order_total_after == Decimal("250.00")
        assert result.application_record is not None

    def test_apply_partial_credit_to_order(self, integration, test_credit):
        """Test applying a partial credit amount to an order."""
        result = integration.apply_credit_to_order(
            credit=test_credit,
            order_id="ORD-001",
            applied_by="test_user",
            amount=Decimal("300.00"),
        )

        assert result.success is True
        assert result.amount_applied == Decimal("300.00")
        assert result.order_total_after == Decimal("700.00")
        assert test_credit.remaining_amount == Decimal("450.00")

    def test_credit_capped_at_order_total(self, integration, test_credit, order_client):
        """Test that credit application is capped at order total."""
        # Order ORD-002 has only $500 total, credit is $750
        result = integration.apply_credit_to_order(
            credit=test_credit,
            order_id="ORD-002",
            applied_by="test_user",
        )

        assert result.success is True
        assert result.amount_applied == Decimal("500.00")  # Capped at order total
        assert result.order_total_after == Decimal("0")
        assert test_credit.remaining_amount == Decimal("250.00")

    def test_reject_expired_credit(self, integration):
        """Test that expired credits are rejected."""
        expired_credit = TradeInCredit(
            credit_id="CREDIT-EXP-001",
            trade_in_transaction_id="TXN-EXP-001",
            amount=Decimal("500.00"),
            remaining_amount=Decimal("500.00"),
            status=CreditStatus.EXPIRED,
            created_at=datetime.utcnow(),
            customer_id="CUST-EXP-001",
            account_id="ACCT-EXP-001",
        )

        result = integration.apply_credit_to_order(
            credit=expired_credit,
            order_id="ORD-001",
            applied_by="test_user",
        )

        assert result.success is False
        assert "invalid status" in result.error_message.lower()

    def test_reject_cancelled_credit(self, integration):
        """Test that cancelled credits are rejected."""
        cancelled_credit = TradeInCredit(
            credit_id="CREDIT-CAN-001",
            trade_in_transaction_id="TXN-CAN-001",
            amount=Decimal("500.00"),
            remaining_amount=Decimal("500.00"),
            status=CreditStatus.CANCELLED,
            created_at=datetime.utcnow(),
            customer_id="CUST-CAN-001",
            account_id="ACCT-CAN-001",
        )

        result = integration.apply_credit_to_order(
            credit=cancelled_credit,
            order_id="ORD-001",
            applied_by="test_user",
        )

        assert result.success is False
        assert "invalid status" in result.error_message.lower()

    def test_reject_zero_remaining_credit(self, integration, test_credit):
        """Test that credits with zero remaining are rejected."""
        # Use up the credit
        test_credit.apply_to_order("ORD-999", test_credit.remaining_amount)

        result = integration.apply_credit_to_order(
            credit=test_credit,
            order_id="ORD-001",
            applied_by="test_user",
        )

        assert result.success is False
        assert "no remaining" in result.error_message.lower()

    def test_reject_cancelled_order(self, integration, test_credit):
        """Test that credits cannot be applied to cancelled orders."""
        result = integration.apply_credit_to_order(
            credit=test_credit,
            order_id="ORD-003",  # Cancelled order
            applied_by="test_user",
        )

        assert result.success is False
        assert "cancelled" in result.error_message.lower()

    def test_apply_transaction_to_order_convenience_method(self, integration, approved_transaction):
        """Test the convenience method for applying transaction directly to order."""
        result = integration.apply_transaction_to_order(
            transaction=approved_transaction,
            account_id="ACCT-CONV-001",
            order_id="ORD-001",
            applied_by="test_user",
        )

        assert result.success is True
        assert result.trade_in_transaction_id == "TXN-ORD-001"
        assert result.amount_applied == Decimal("750.00")

    def test_application_records_created(self, integration, test_credit):
        """Test that application records are created for audit trail."""
        integration.apply_credit_to_order(
            credit=test_credit,
            order_id="ORD-001",
            applied_by="test_user",
            partner_id="PARTNER-001",
        )

        records = integration.get_application_records()
        assert len(records) == 1

        record = records[0]
        assert record.credit_id == test_credit.credit_id
        assert record.trade_in_transaction_id == test_credit.trade_in_transaction_id
        assert record.target == ApplicationTarget.ORDER
        assert record.target_id == "ORD-001"
        assert record.partner_id == "PARTNER-001"

    def test_get_applications_by_order(self, integration, test_credit):
        """Test retrieving applications by order ID."""
        integration.apply_credit_to_order(
            credit=test_credit,
            order_id="ORD-001",
            applied_by="test_user",
            amount=Decimal("300.00"),
        )

        apps = integration.get_applications_by_order("ORD-001")
        assert len(apps) == 1
        assert apps[0].target_id == "ORD-001"

        # Non-existent order should return empty list
        apps = integration.get_applications_by_order("ORD-999")
        assert len(apps) == 0

    def test_get_applications_by_transaction(self, integration, test_credit):
        """Test retrieving applications by transaction ID."""
        integration.apply_credit_to_order(
            credit=test_credit,
            order_id="ORD-001",
            applied_by="test_user",
        )

        apps = integration.get_applications_by_transaction(test_credit.trade_in_transaction_id)
        assert len(apps) == 1
        assert apps[0].trade_in_transaction_id == test_credit.trade_in_transaction_id

    def test_result_to_dict(self, integration, test_credit):
        """Test that results can be serialized to dict."""
        result = integration.apply_credit_to_order(
            credit=test_credit,
            order_id="ORD-001",
            applied_by="test_user",
        )

        result_dict = result.to_dict()
        assert result_dict["success"] is True
        assert result_dict["order_id"] == "ORD-001"
        assert result_dict["credit_id"] == test_credit.credit_id
        assert result_dict["trade_in_transaction_id"] == test_credit.trade_in_transaction_id
        assert "timestamp" in result_dict


class TestMockOrderSystemClient:
    """Tests for the mock order system client."""

    def test_create_test_order(self):
        """Test creating a test order."""
        client = MockOrderSystemClient()
        order = client.create_test_order("ORD-TEST-001", Decimal("500.00"), "pending")

        assert order["order_id"] == "ORD-TEST-001"
        assert order["total"] == Decimal("500.00")
        assert order["status"] == "pending"

    def test_get_order_creates_default(self):
        """Test that get_order creates a default order if not exists."""
        client = MockOrderSystemClient()
        order = client.get_order("ORD-NEW-001")

        assert order["order_id"] == "ORD-NEW-001"
        assert order["total"] == Decimal("500.00")  # Default

    def test_apply_credit_updates_order(self):
        """Test that applying credit updates the order."""
        client = MockOrderSystemClient()
        client.create_test_order("ORD-TEST-002", Decimal("1000.00"), "pending")

        result = client.apply_credit("ORD-TEST-002", Decimal("300.00"), "REF-001")

        assert result["total"] == Decimal("700.00")
        assert result["credits_applied"] == Decimal("300.00")
        assert result["last_credit_reference"] == "REF-001"

    def test_validate_order_for_credit(self):
        """Test order validation for credit application."""
        client = MockOrderSystemClient()
        client.create_test_order("ORD-VALID", Decimal("500.00"), "pending")
        client.create_test_order("ORD-CANCELLED", Decimal("500.00"), "cancelled")

        valid, reason = client.validate_order_for_credit("ORD-VALID")
        assert valid is True

        valid, reason = client.validate_order_for_credit("ORD-CANCELLED")
        assert valid is False
        assert "cancelled" in reason.lower()
