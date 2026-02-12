"""
Tests for billing presentment rules.

Covers:
- Grouping strategies
- Labeling and display
- Roll-up strategies
- Bill formatting
"""

import unittest
from datetime import date
from decimal import Decimal

from billing.models import (
    Bill,
    Charge,
    ChargeCategory,
    ChargeType,
    Credit,
    Discount,
    DiscountType,
    Fee,
    Tax,
)
from billing.presentment import (
    CATEGORY_EXPLANATIONS,
    CATEGORY_LABELS,
    FormattedBill,
    GroupedLineItems,
    GroupingStrategy,
    PresentmentConfig,
    PresentmentRule,
    RollUpStrategy,
    apply_presentment_rules,
    format_bill_for_display,
    format_currency,
    get_category_explanation,
    get_category_label,
    group_line_items,
)


class TestCategoryLabels(unittest.TestCase):
    """Tests for category labeling."""

    def test_default_category_labels(self):
        """Test default category labels exist."""
        config = PresentmentConfig()

        self.assertEqual(
            get_category_label(ChargeCategory.RECURRING, config),
            "Monthly Charges",
        )
        self.assertEqual(
            get_category_label(ChargeCategory.GOVERNMENT, config),
            "Taxes, Fees & Government Charges",
        )

    def test_custom_category_labels(self):
        """Test custom category labels override defaults."""
        config = PresentmentConfig(
            category_labels={
                ChargeCategory.RECURRING: "Your Plan Charges",
            }
        )

        self.assertEqual(
            get_category_label(ChargeCategory.RECURRING, config),
            "Your Plan Charges",
        )

    def test_category_explanations(self):
        """Test category explanations."""
        config = PresentmentConfig()

        explanation = get_category_explanation(ChargeCategory.GOVERNMENT, config)
        self.assertIn("taxes", explanation.lower())
        self.assertIn("regulatory", explanation.lower())

    def test_explanations_disabled(self):
        """Test that explanations can be disabled."""
        config = PresentmentConfig(show_category_explanations=False)

        explanation = get_category_explanation(ChargeCategory.RECURRING, config)
        self.assertIsNone(explanation)


class TestGrouping(unittest.TestCase):
    """Tests for line item grouping."""

    def setUp(self):
        """Set up test line items."""
        self.items = [
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
            Tax(
                id="tax-001",
                description="State Tax",
                amount=Decimal("5.10"),
                category=ChargeCategory.GOVERNMENT,
                charge_type=ChargeType.STATE_TAX,
            ),
        ]

    def test_group_by_category(self):
        """Test grouping by category."""
        config = PresentmentConfig(grouping_strategy=GroupingStrategy.BY_CATEGORY)

        groups = group_line_items(self.items, config)

        # Should have 3 groups: RECURRING, EQUIPMENT, GOVERNMENT
        self.assertEqual(len(groups), 3)

        # Find recurring group
        recurring_group = next(
            g for g in groups if g.category == ChargeCategory.RECURRING
        )
        self.assertEqual(len(recurring_group.items), 1)
        self.assertEqual(recurring_group.subtotal, Decimal("85.00"))

    def test_group_flat(self):
        """Test flat grouping (no categories)."""
        config = PresentmentConfig(grouping_strategy=GroupingStrategy.FLAT)

        groups = group_line_items(self.items, config)

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0].items), 3)

    def test_category_order(self):
        """Test that groups are ordered by category_order."""
        config = PresentmentConfig(
            category_order=[
                ChargeCategory.RECURRING,
                ChargeCategory.EQUIPMENT,
                ChargeCategory.GOVERNMENT,
            ]
        )

        groups = group_line_items(self.items, config)

        self.assertEqual(groups[0].category, ChargeCategory.RECURRING)
        self.assertEqual(groups[1].category, ChargeCategory.EQUIPMENT)
        self.assertEqual(groups[2].category, ChargeCategory.GOVERNMENT)


class TestPresentmentRules(unittest.TestCase):
    """Tests for presentment rules application."""

    def test_rule_matching_by_category(self):
        """Test rule matching by category."""
        rule = PresentmentRule(
            category=ChargeCategory.RECURRING,
            display_label="Custom Recurring Label",
        )

        charge_recurring = Charge(
            id="chg-001",
            description="Service",
            amount=Decimal("50.00"),
            category=ChargeCategory.RECURRING,
            charge_type=ChargeType.MONTHLY_SERVICE,
        )
        charge_one_time = Charge(
            id="chg-002",
            description="Fee",
            amount=Decimal("25.00"),
            category=ChargeCategory.ONE_TIME,
            charge_type=ChargeType.ACTIVATION,
        )

        self.assertTrue(rule.matches(charge_recurring))
        self.assertFalse(rule.matches(charge_one_time))

    def test_rule_matching_by_type(self):
        """Test rule matching by charge type."""
        rule = PresentmentRule(
            charge_type=ChargeType.DEVICE_PAYMENT,
            display_label="Your Device Payment",
            explanation="Monthly payment for your device.",
        )

        device_charge = Charge(
            id="chg-001",
            description="Device",
            amount=Decimal("33.33"),
            category=ChargeCategory.EQUIPMENT,
            charge_type=ChargeType.DEVICE_PAYMENT,
        )

        self.assertTrue(rule.matches(device_charge))

    def test_rule_application(self):
        """Test applying rule to line item."""
        rule = PresentmentRule(
            charge_type=ChargeType.MONTHLY_SERVICE,
            display_label="Your Plan",
            explanation="Your monthly plan charge.",
            display_order=1,
        )

        charge = Charge(
            id="chg-001",
            description="Monthly Service",
            amount=Decimal("85.00"),
            category=ChargeCategory.RECURRING,
            charge_type=ChargeType.MONTHLY_SERVICE,
        )

        rule.apply(charge)

        self.assertEqual(charge.display_label, "Your Plan")
        self.assertEqual(charge.explanation, "Your monthly plan charge.")
        self.assertEqual(charge.display_order, 1)


class TestRollUp(unittest.TestCase):
    """Tests for roll-up strategies."""

    def test_no_rollup(self):
        """Test that no roll-up keeps all items."""
        items = [
            Charge(
                id=f"chg-{i}",
                description=f"Charge {i}",
                amount=Decimal("0.50"),
                category=ChargeCategory.OTHER,
                charge_type=ChargeType.MISCELLANEOUS,
            )
            for i in range(5)
        ]

        config = PresentmentConfig(roll_up_strategy=RollUpStrategy.NONE)
        groups = group_line_items(items, config)

        self.assertEqual(len(groups[0].items), 5)

    def test_threshold_rollup(self):
        """Test threshold-based roll-up."""
        items = [
            Charge(
                id="chg-big",
                description="Big Charge",
                amount=Decimal("10.00"),
                category=ChargeCategory.OTHER,
                charge_type=ChargeType.MISCELLANEOUS,
            ),
            Charge(
                id="chg-small-1",
                description="Small 1",
                amount=Decimal("0.25"),
                category=ChargeCategory.OTHER,
                charge_type=ChargeType.MISCELLANEOUS,
            ),
            Charge(
                id="chg-small-2",
                description="Small 2",
                amount=Decimal("0.30"),
                category=ChargeCategory.OTHER,
                charge_type=ChargeType.MISCELLANEOUS,
            ),
        ]

        config = PresentmentConfig(
            roll_up_strategy=RollUpStrategy.THRESHOLD,
            roll_up_threshold=Decimal("1.00"),
        )
        groups = group_line_items(items, config)

        # Import and apply roll-up
        from billing.presentment import apply_roll_up

        groups = apply_roll_up(groups, config)

        # Should have 2 items: big charge and rolled-up small charges
        self.assertEqual(len(groups[0].items), 2)


class TestCurrencyFormatting(unittest.TestCase):
    """Tests for currency formatting."""

    def test_format_positive_usd(self):
        """Test formatting positive USD amounts."""
        self.assertEqual(format_currency(Decimal("100.00")), "$100.00")
        self.assertEqual(format_currency(Decimal("1234.56")), "$1,234.56")

    def test_format_negative_usd(self):
        """Test formatting negative USD amounts."""
        self.assertEqual(format_currency(Decimal("-15.00")), "-$15.00")

    def test_format_other_currency(self):
        """Test formatting non-USD currency."""
        self.assertEqual(format_currency(Decimal("100.00"), "EUR"), "100.00 EUR")


class TestBillFormatting(unittest.TestCase):
    """Tests for full bill formatting."""

    def setUp(self):
        """Set up test bill."""
        self.bill = Bill(
            id="bill-001",
            account_id="acct-001",
            billing_period_start=date(2024, 1, 1),
            billing_period_end=date(2024, 1, 31),
            due_date=date(2024, 2, 15),
            statement_date=date(2024, 2, 1),
        )

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
                description="Data Overage",
                amount=Decimal("15.00"),
                category=ChargeCategory.USAGE,
                charge_type=ChargeType.DATA_OVERAGE,
            ),
        ]

        self.bill.taxes = [
            Tax(
                id="tax-001",
                description="State Tax",
                amount=Decimal("6.00"),
                category=ChargeCategory.GOVERNMENT,
                charge_type=ChargeType.STATE_TAX,
            ),
        ]

        self.bill.discounts = [
            Discount(
                id="disc-001",
                description="Autopay",
                amount=Decimal("5.00"),
                category=ChargeCategory.RECURRING,
                charge_type=ChargeType.MONTHLY_SERVICE,
                discount_type=DiscountType.AUTOPAY,
            ),
        ]

    def test_format_bill_creates_groups(self):
        """Test that formatting creates correct groups."""
        formatted = format_bill_for_display(self.bill)

        self.assertIsInstance(formatted, FormattedBill)
        self.assertGreater(len(formatted.groups), 0)

    def test_format_bill_calculates_summary(self):
        """Test that formatting calculates summary values."""
        formatted = format_bill_for_display(self.bill)

        self.assertEqual(formatted.subtotal_display, "$100.00")
        self.assertEqual(formatted.discounts_display, "-$5.00")

    def test_format_bill_with_custom_config(self):
        """Test formatting with custom configuration."""
        config = PresentmentConfig(
            category_labels={
                ChargeCategory.RECURRING: "Your Monthly Plan",
            },
            show_category_explanations=False,
        )

        formatted = format_bill_for_display(self.bill, config)

        # Find recurring group
        recurring = next(
            (g for g in formatted.groups if g.category == ChargeCategory.RECURRING),
            None,
        )
        if recurring:
            self.assertEqual(recurring.label, "Your Monthly Plan")
            self.assertIsNone(recurring.explanation)


if __name__ == "__main__":
    unittest.main()
