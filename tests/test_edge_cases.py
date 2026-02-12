"""
Tests for billing edge cases.

Covers:
- Installment plans
- Billing adjustments
- Proration calculations
- Promotional discounts
"""

import unittest
from datetime import date
from decimal import Decimal

from billing.edge_cases import (
    InstallmentPlan,
    Promotion,
    calculate_prorated_amount,
    create_adjustment_credit,
    create_installment_charge,
    create_promotional_discount,
    create_prorated_charge,
)
from billing.models import (
    AdjustmentReason,
    ChargeCategory,
    ChargeType,
    DiscountType,
)


class TestInstallmentPlan(unittest.TestCase):
    """Tests for installment payment plans."""

    def test_simple_installment_plan(self):
        """Test basic installment plan without interest."""
        plan = InstallmentPlan(
            total_amount=Decimal("600.00"),
            num_installments=24,
            down_payment=Decimal("0.00"),
            interest_rate=Decimal("0.00"),
        )

        self.assertEqual(plan.financed_amount, Decimal("600.00"))
        self.assertEqual(plan.monthly_payment, Decimal("25.00"))

    def test_installment_with_down_payment(self):
        """Test installment plan with down payment."""
        plan = InstallmentPlan(
            total_amount=Decimal("1000.00"),
            num_installments=20,
            down_payment=Decimal("200.00"),
            interest_rate=Decimal("0.00"),
        )

        self.assertEqual(plan.financed_amount, Decimal("800.00"))
        self.assertEqual(plan.monthly_payment, Decimal("40.00"))

    def test_create_installment_charge(self):
        """Test creating an installment charge."""
        plan = InstallmentPlan(
            total_amount=Decimal("799.99"),
            num_installments=24,
        )

        charge = create_installment_charge(
            plan=plan,
            installment_number=5,
            charge_id="inst-005",
            description="iPhone 15",
            service_period_start=date(2024, 5, 1),
            service_period_end=date(2024, 5, 31),
        )

        self.assertTrue(charge.is_installment)
        self.assertEqual(charge.installment_number, 5)
        self.assertEqual(charge.total_installments, 24)
        self.assertEqual(charge.category, ChargeCategory.EQUIPMENT)
        self.assertIn("5 of 24", charge.display_label)


class TestAdjustments(unittest.TestCase):
    """Tests for billing adjustments."""

    def test_billing_error_adjustment(self):
        """Test creating a billing error credit."""
        credit = create_adjustment_credit(
            credit_id="adj-001",
            amount=Decimal("25.00"),
            reason=AdjustmentReason.BILLING_ERROR,
            description="Duplicate charge correction",
            related_charge_id="chg-001",
        )

        self.assertEqual(credit.amount, Decimal("-25.00"))
        self.assertEqual(credit.adjustment_reason, AdjustmentReason.BILLING_ERROR)
        self.assertEqual(credit.related_charge_id, "chg-001")
        self.assertIn("error", credit.explanation.lower())

    def test_service_issue_adjustment(self):
        """Test creating a service issue credit."""
        credit = create_adjustment_credit(
            credit_id="adj-002",
            amount=Decimal("10.00"),
            reason=AdjustmentReason.SERVICE_ISSUE,
            description="Outage compensation",
        )

        self.assertEqual(credit.adjustment_reason, AdjustmentReason.SERVICE_ISSUE)
        self.assertIn("disruption", credit.explanation.lower())

    def test_goodwill_adjustment(self):
        """Test creating a goodwill credit."""
        credit = create_adjustment_credit(
            credit_id="adj-003",
            amount=Decimal("50.00"),
            reason=AdjustmentReason.GOODWILL,
            description="Courtesy credit",
        )

        self.assertEqual(credit.adjustment_reason, AdjustmentReason.GOODWILL)
        self.assertIn("courtesy", credit.explanation.lower())


class TestProration(unittest.TestCase):
    """Tests for proration calculations."""

    def test_half_month_proration(self):
        """Test proration for half a billing period."""
        prorated_amount, prorated_days = calculate_prorated_amount(
            original_amount=Decimal("100.00"),
            start_date=date(2024, 1, 16),
            end_date=date(2024, 1, 31),
            billing_period_start=date(2024, 1, 1),
            billing_period_end=date(2024, 1, 31),
        )

        # 16 days out of 31
        self.assertEqual(prorated_days, 16)
        self.assertEqual(prorated_amount, Decimal("51.61"))

    def test_full_month_proration(self):
        """Test proration for full billing period (no change)."""
        prorated_amount, prorated_days = calculate_prorated_amount(
            original_amount=Decimal("85.00"),
            start_date=date(2024, 2, 1),
            end_date=date(2024, 2, 29),
            billing_period_start=date(2024, 2, 1),
            billing_period_end=date(2024, 2, 29),
        )

        self.assertEqual(prorated_days, 29)
        self.assertEqual(prorated_amount, Decimal("85.00"))

    def test_single_day_proration(self):
        """Test proration for a single day."""
        prorated_amount, prorated_days = calculate_prorated_amount(
            original_amount=Decimal("30.00"),
            start_date=date(2024, 4, 30),
            end_date=date(2024, 4, 30),
            billing_period_start=date(2024, 4, 1),
            billing_period_end=date(2024, 4, 30),
        )

        self.assertEqual(prorated_days, 1)
        self.assertEqual(prorated_amount, Decimal("1.00"))

    def test_create_prorated_charge(self):
        """Test creating a prorated charge."""
        charge = create_prorated_charge(
            charge_id="pro-001",
            description="Premium Plan",
            original_amount=Decimal("120.00"),
            category=ChargeCategory.RECURRING,
            charge_type=ChargeType.MONTHLY_SERVICE,
            start_date=date(2024, 3, 15),
            end_date=date(2024, 3, 31),
            billing_period_start=date(2024, 3, 1),
            billing_period_end=date(2024, 3, 31),
        )

        # 17 days out of 31
        self.assertEqual(charge.prorated_days, 17)
        self.assertEqual(charge.get_effective_amount(), Decimal("65.81"))
        self.assertIn("Prorated", charge.display_label)
        self.assertIn("17", charge.explanation)


class TestPromotions(unittest.TestCase):
    """Tests for promotional discounts."""

    def test_percentage_promotion(self):
        """Test percentage-based promotion."""
        promo = Promotion(
            promo_code="SAVE20",
            description="20% Off",
            discount_percentage=Decimal("20"),
            discount_type=DiscountType.PROMOTIONAL,
        )

        discount = promo.calculate_discount(Decimal("100.00"))
        self.assertEqual(discount, Decimal("20.00"))

    def test_fixed_amount_promotion(self):
        """Test fixed amount promotion."""
        promo = Promotion(
            promo_code="FLAT10",
            description="$10 Off",
            discount_amount=Decimal("10.00"),
        )

        discount = promo.calculate_discount(Decimal("100.00"))
        self.assertEqual(discount, Decimal("10.00"))

    def test_promotion_validity(self):
        """Test promotion validity date checking."""
        promo = Promotion(
            promo_code="LIMITED",
            description="Limited Time",
            discount_amount=Decimal("25.00"),
            start_date=date(2024, 1, 1),
            expiration_date=date(2024, 12, 31),
        )

        self.assertTrue(promo.is_valid(date(2024, 6, 15)))
        self.assertFalse(promo.is_valid(date(2023, 12, 15)))
        self.assertFalse(promo.is_valid(date(2025, 1, 1)))

    def test_create_promotional_discount(self):
        """Test creating a promotional discount."""
        promo = Promotion(
            promo_code="WELCOME",
            description="Welcome Discount",
            discount_percentage=Decimal("15"),
            expiration_date=date(2024, 12, 31),
            terms_and_conditions="New customers only.",
        )

        discount = create_promotional_discount(
            discount_id="disc-001",
            promotion=promo,
            base_amount=Decimal("80.00"),
        )

        self.assertEqual(discount.amount, Decimal("-12.00"))
        self.assertEqual(discount.promo_code, "WELCOME")
        self.assertEqual(discount.expiration_date, date(2024, 12, 31))
        self.assertIn("expires", discount.explanation.lower())

    def test_recurring_vs_one_time_promotion(self):
        """Test recurring vs one-time promotions."""
        recurring_promo = Promotion(
            promo_code="MONTHLY",
            description="Monthly Savings",
            discount_amount=Decimal("10.00"),
            is_recurring=True,
        )

        one_time_promo = Promotion(
            promo_code="ONCE",
            description="One-Time Bonus",
            discount_amount=Decimal("50.00"),
            is_recurring=False,
        )

        recurring_discount = create_promotional_discount(
            discount_id="disc-r",
            promotion=recurring_promo,
            base_amount=Decimal("100.00"),
        )

        one_time_discount = create_promotional_discount(
            discount_id="disc-o",
            promotion=one_time_promo,
            base_amount=Decimal("100.00"),
        )

        self.assertTrue(recurring_discount.is_recurring)
        self.assertFalse(one_time_discount.is_recurring)


class TestEdgeCaseIntegration(unittest.TestCase):
    """Integration tests combining multiple edge cases."""

    def test_prorated_installment(self):
        """Test combining proration with installment."""
        # Device started mid-month with installment plan
        plan = InstallmentPlan(
            total_amount=Decimal("500.00"),
            num_installments=20,
        )

        # First installment is prorated
        full_payment = plan.monthly_payment

        prorated_amount, prorated_days = calculate_prorated_amount(
            original_amount=full_payment,
            start_date=date(2024, 1, 20),
            end_date=date(2024, 1, 31),
            billing_period_start=date(2024, 1, 1),
            billing_period_end=date(2024, 1, 31),
        )

        self.assertEqual(prorated_days, 12)
        # 25 * 12/31 = 9.68
        self.assertEqual(prorated_amount, Decimal("9.68"))


if __name__ == "__main__":
    unittest.main()
