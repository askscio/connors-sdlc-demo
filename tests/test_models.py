"""
Tests for billing data models.

Covers:
- Charge, Credit, Tax, Fee, Discount creation
- BillSummary calculations
- Bill composition and summary calculation
- Edge cases: installments, proration
"""

import unittest
from datetime import date
from decimal import Decimal

from billing.models import (
    AdjustmentReason,
    Bill,
    BillLineItem,
    BillSummary,
    Charge,
    ChargeCategory,
    ChargeType,
    Credit,
    Discount,
    DiscountType,
    Fee,
    Tax,
)


class TestCharge(unittest.TestCase):
    """Tests for Charge model."""

    def test_basic_charge_creation(self):
        """Test creating a basic charge."""
        charge = Charge(
            id="chg-001",
            description="Monthly Service",
            amount=Decimal("85.00"),
            category=ChargeCategory.RECURRING,
            charge_type=ChargeType.MONTHLY_SERVICE,
        )

        self.assertEqual(charge.id, "chg-001")
        self.assertEqual(charge.amount, Decimal("85.00"))
        self.assertEqual(charge.category, ChargeCategory.RECURRING)
        self.assertEqual(charge.get_effective_amount(), Decimal("85.00"))

    def test_prorated_charge(self):
        """Test prorated charge returns prorated amount."""
        charge = Charge(
            id="chg-002",
            description="Monthly Service (Prorated)",
            amount=Decimal("85.00"),
            category=ChargeCategory.RECURRING,
            charge_type=ChargeType.MONTHLY_SERVICE,
            prorated_amount=Decimal("42.50"),
            prorated_days=15,
            original_amount=Decimal("85.00"),
        )

        self.assertEqual(charge.amount, Decimal("85.00"))
        self.assertEqual(charge.prorated_amount, Decimal("42.50"))
        self.assertEqual(charge.get_effective_amount(), Decimal("42.50"))

    def test_installment_charge(self):
        """Test installment charge fields."""
        charge = Charge(
            id="chg-003",
            description="Device Payment",
            amount=Decimal("33.33"),
            category=ChargeCategory.EQUIPMENT,
            charge_type=ChargeType.DEVICE_PAYMENT,
            is_installment=True,
            installment_number=5,
            total_installments=24,
            original_amount=Decimal("799.99"),
        )

        self.assertTrue(charge.is_installment)
        self.assertEqual(charge.installment_number, 5)
        self.assertEqual(charge.total_installments, 24)

    def test_display_label_default(self):
        """Test default display label uses description."""
        charge = Charge(
            id="chg-004",
            description="Test Charge",
            amount=Decimal("10.00"),
            category=ChargeCategory.OTHER,
            charge_type=ChargeType.MISCELLANEOUS,
        )

        self.assertEqual(charge.get_display_label(), "Test Charge")

    def test_display_label_custom(self):
        """Test custom display label overrides description."""
        charge = Charge(
            id="chg-005",
            description="Test Charge",
            amount=Decimal("10.00"),
            category=ChargeCategory.OTHER,
            charge_type=ChargeType.MISCELLANEOUS,
            display_label="Custom Label",
        )

        self.assertEqual(charge.get_display_label(), "Custom Label")


class TestCredit(unittest.TestCase):
    """Tests for Credit model."""

    def test_credit_amount_negated(self):
        """Test that positive credit amounts are negated."""
        credit = Credit(
            id="crd-001",
            description="Billing Adjustment",
            amount=Decimal("15.00"),  # Positive input
            category=ChargeCategory.OTHER,
            charge_type=ChargeType.MISCELLANEOUS,
            adjustment_reason=AdjustmentReason.BILLING_ERROR,
        )

        self.assertEqual(credit.amount, Decimal("-15.00"))

    def test_credit_already_negative(self):
        """Test that negative credit amounts stay negative."""
        credit = Credit(
            id="crd-002",
            description="Refund",
            amount=Decimal("-20.00"),
            category=ChargeCategory.OTHER,
            charge_type=ChargeType.MISCELLANEOUS,
            adjustment_reason=AdjustmentReason.REFUND,
        )

        self.assertEqual(credit.amount, Decimal("-20.00"))

    def test_credit_with_related_charge(self):
        """Test credit referencing original charge."""
        credit = Credit(
            id="crd-003",
            description="Service Issue Credit",
            amount=Decimal("25.00"),
            category=ChargeCategory.RECURRING,
            charge_type=ChargeType.MONTHLY_SERVICE,
            adjustment_reason=AdjustmentReason.SERVICE_ISSUE,
            related_charge_id="chg-001",
        )

        self.assertEqual(credit.related_charge_id, "chg-001")
        self.assertEqual(credit.adjustment_reason, AdjustmentReason.SERVICE_ISSUE)


class TestTax(unittest.TestCase):
    """Tests for Tax model."""

    def test_tax_creation(self):
        """Test creating a tax line item."""
        tax = Tax(
            id="tax-001",
            description="State Sales Tax",
            amount=Decimal("5.10"),
            category=ChargeCategory.GOVERNMENT,
            charge_type=ChargeType.STATE_TAX,
            tax_rate=Decimal("0.06"),
            jurisdiction="California",
        )

        self.assertEqual(tax.amount, Decimal("5.10"))
        self.assertEqual(tax.tax_rate, Decimal("0.06"))
        self.assertEqual(tax.jurisdiction, "California")
        self.assertEqual(tax.category, ChargeCategory.GOVERNMENT)


class TestFee(unittest.TestCase):
    """Tests for Fee model."""

    def test_regulatory_fee(self):
        """Test creating a regulatory fee."""
        fee = Fee(
            id="fee-001",
            description="Federal Universal Service Fee",
            amount=Decimal("3.50"),
            category=ChargeCategory.GOVERNMENT,
            charge_type=ChargeType.REGULATORY_FEE,
            is_regulatory=True,
            is_passthrough=True,
        )

        self.assertTrue(fee.is_regulatory)
        self.assertTrue(fee.is_passthrough)


class TestDiscount(unittest.TestCase):
    """Tests for Discount model."""

    def test_discount_amount_negated(self):
        """Test that positive discount amounts are negated."""
        discount = Discount(
            id="disc-001",
            description="Autopay Discount",
            amount=Decimal("5.00"),
            category=ChargeCategory.RECURRING,
            charge_type=ChargeType.MONTHLY_SERVICE,
            discount_type=DiscountType.AUTOPAY,
        )

        self.assertEqual(discount.amount, Decimal("-5.00"))

    def test_promotional_discount(self):
        """Test promotional discount with expiration."""
        discount = Discount(
            id="disc-002",
            description="20% Off First Year",
            amount=Decimal("17.00"),
            category=ChargeCategory.RECURRING,
            charge_type=ChargeType.MONTHLY_SERVICE,
            discount_type=DiscountType.PROMOTIONAL,
            discount_percentage=Decimal("20"),
            promo_code="SAVE20",
            expiration_date=date(2024, 12, 31),
        )

        self.assertEqual(discount.promo_code, "SAVE20")
        self.assertEqual(discount.expiration_date, date(2024, 12, 31))
        self.assertEqual(discount.discount_percentage, Decimal("20"))


class TestBillSummary(unittest.TestCase):
    """Tests for BillSummary calculations."""

    def test_current_charges(self):
        """Test current_charges calculation."""
        summary = BillSummary(
            subtotal_charges=Decimal("100.00"),
            total_taxes=Decimal("8.00"),
            total_fees=Decimal("5.00"),
        )

        self.assertEqual(summary.current_charges, Decimal("113.00"))

    def test_total_adjustments(self):
        """Test total_adjustments calculation."""
        summary = BillSummary(
            total_credits=Decimal("-15.00"),
            total_discounts=Decimal("-10.00"),
        )

        self.assertEqual(summary.total_adjustments, Decimal("-25.00"))

    def test_amount_due(self):
        """Test amount_due calculation."""
        summary = BillSummary(
            previous_balance=Decimal("50.00"),
            payments_received=Decimal("50.00"),
            subtotal_charges=Decimal("100.00"),
            total_taxes=Decimal("8.00"),
            total_fees=Decimal("5.00"),
            total_credits=Decimal("-15.00"),
            total_discounts=Decimal("-10.00"),
        )

        # Previous 50 - Payments 50 + Current 113 + Adjustments -25 = 88
        self.assertEqual(summary.amount_due, Decimal("88.00"))


class TestBill(unittest.TestCase):
    """Tests for Bill model."""

    def setUp(self):
        """Set up test bill with sample data."""
        self.bill = Bill(
            id="bill-001",
            account_id="acct-001",
            billing_period_start=date(2024, 1, 1),
            billing_period_end=date(2024, 1, 31),
            due_date=date(2024, 2, 15),
            statement_date=date(2024, 2, 1),
        )

        # Add charges
        self.bill.charges = [
            Charge(
                id="chg-001",
                description="Monthly Service",
                amount=Decimal("85.00"),
                category=ChargeCategory.RECURRING,
                charge_type=ChargeType.MONTHLY_SERVICE,
            ),
            Charge(
                id="chg-002",
                description="Device Payment",
                amount=Decimal("33.33"),
                category=ChargeCategory.EQUIPMENT,
                charge_type=ChargeType.DEVICE_PAYMENT,
            ),
        ]

        # Add taxes
        self.bill.taxes = [
            Tax(
                id="tax-001",
                description="State Tax",
                amount=Decimal("5.10"),
                category=ChargeCategory.GOVERNMENT,
                charge_type=ChargeType.STATE_TAX,
            ),
        ]

        # Add discounts
        self.bill.discounts = [
            Discount(
                id="disc-001",
                description="Autopay Discount",
                amount=Decimal("5.00"),
                category=ChargeCategory.RECURRING,
                charge_type=ChargeType.MONTHLY_SERVICE,
                discount_type=DiscountType.AUTOPAY,
            ),
        ]

    def test_get_all_line_items(self):
        """Test getting all line items."""
        items = self.bill.get_all_line_items()

        self.assertEqual(len(items), 4)

    def test_calculate_summary(self):
        """Test summary calculation."""
        summary = self.bill.calculate_summary()

        self.assertEqual(summary.subtotal_charges, Decimal("118.33"))
        self.assertEqual(summary.total_taxes, Decimal("5.10"))
        self.assertEqual(summary.total_discounts, Decimal("-5.00"))
        self.assertEqual(summary.recurring_charges, Decimal("85.00"))
        self.assertEqual(summary.equipment_charges, Decimal("33.33"))

    def test_summary_with_previous_balance(self):
        """Test summary with previous balance and payment."""
        self.bill.summary.previous_balance = Decimal("100.00")
        self.bill.summary.payments_received = Decimal("100.00")

        summary = self.bill.calculate_summary()

        # Charges 118.33 + Taxes 5.10 + Discounts -5.00 = 118.43
        self.assertEqual(summary.amount_due, Decimal("118.43"))


class TestBillWithProration(unittest.TestCase):
    """Tests for bills with prorated charges."""

    def test_prorated_charge_in_summary(self):
        """Test that prorated amounts are used in summary."""
        bill = Bill(
            id="bill-002",
            account_id="acct-001",
            billing_period_start=date(2024, 1, 1),
            billing_period_end=date(2024, 1, 31),
            due_date=date(2024, 2, 15),
            statement_date=date(2024, 2, 1),
        )

        # Prorated charge for half the month
        bill.charges = [
            Charge(
                id="chg-001",
                description="Monthly Service (Prorated)",
                amount=Decimal("85.00"),
                category=ChargeCategory.RECURRING,
                charge_type=ChargeType.MONTHLY_SERVICE,
                prorated_amount=Decimal("42.50"),
                prorated_days=15,
            ),
        ]

        summary = bill.calculate_summary()

        # Should use prorated amount
        self.assertEqual(summary.subtotal_charges, Decimal("42.50"))
        self.assertEqual(summary.recurring_charges, Decimal("42.50"))


if __name__ == "__main__":
    unittest.main()
