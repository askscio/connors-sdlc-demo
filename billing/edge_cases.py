"""
Edge Cases for Billing Data Model

This module documents and provides utilities for handling billing edge cases:
- Installments: Payment plans split across billing periods
- Adjustments: Corrections to previous billing errors
- Proration: Partial period charges for mid-cycle changes
- Promotions: Discounts and promotional pricing

Jira: SE-5021
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from billing.models import (
    AdjustmentReason,
    Charge,
    ChargeCategory,
    ChargeType,
    Credit,
    Discount,
    DiscountType,
)


# =============================================================================
# INSTALLMENTS
# =============================================================================
# Installments are used when a large charge (e.g., device purchase) is split
# into multiple payments across billing periods.
#
# Key fields:
#   - is_installment: True
#   - installment_number: Current payment number (1-indexed)
#   - total_installments: Total number of payments
#   - original_amount: Full amount before splitting
#
# Example: A $600 phone paid over 24 months = $25/month
# =============================================================================


@dataclass
class InstallmentPlan:
    """Configuration for an installment payment plan."""

    total_amount: Decimal
    num_installments: int
    down_payment: Decimal = Decimal("0.00")
    interest_rate: Decimal = Decimal("0.00")  # Annual interest rate

    @property
    def financed_amount(self) -> Decimal:
        """Amount being financed (total minus down payment)."""
        return self.total_amount - self.down_payment

    @property
    def monthly_payment(self) -> Decimal:
        """Calculate monthly payment amount."""
        if self.interest_rate == 0:
            # Simple division for 0% interest
            return (self.financed_amount / self.num_installments).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        # Compound interest calculation
        monthly_rate = self.interest_rate / 12
        payment = (
            self.financed_amount
            * (monthly_rate * (1 + monthly_rate) ** self.num_installments)
            / ((1 + monthly_rate) ** self.num_installments - 1)
        )
        return payment.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def create_installment_charge(
    plan: InstallmentPlan,
    installment_number: int,
    charge_id: str,
    description: str,
    service_period_start: Optional[date] = None,
    service_period_end: Optional[date] = None,
) -> Charge:
    """
    Create a charge for a single installment payment.

    Args:
        plan: The installment plan configuration
        installment_number: Which payment this is (1-indexed)
        charge_id: Unique identifier for this charge
        description: Description for the charge
        service_period_start: Start of billing period
        service_period_end: End of billing period

    Returns:
        A Charge configured as an installment payment
    """
    return Charge(
        id=charge_id,
        description=description,
        amount=plan.monthly_payment,
        category=ChargeCategory.EQUIPMENT,
        charge_type=ChargeType.DEVICE_PAYMENT,
        is_recurring=True,
        is_installment=True,
        installment_number=installment_number,
        total_installments=plan.num_installments,
        original_amount=plan.total_amount,
        service_period_start=service_period_start,
        service_period_end=service_period_end,
        display_label=f"Device Payment ({installment_number} of {plan.num_installments})",
        explanation=(
            f"Monthly payment for your device. "
            f"Remaining balance: ${plan.financed_amount - (plan.monthly_payment * installment_number):.2f}"
        ),
    )


# =============================================================================
# ADJUSTMENTS
# =============================================================================
# Adjustments are credits applied to correct billing errors or compensate
# for service issues. They reference the original charge being adjusted.
#
# Key fields:
#   - adjustment_reason: Why the adjustment is being made
#   - related_charge_id: ID of the charge being adjusted (if applicable)
#
# Common reasons:
#   - BILLING_ERROR: Incorrect charge on previous bill
#   - SERVICE_ISSUE: Outage or quality problem
#   - GOODWILL: Customer retention
# =============================================================================


def create_adjustment_credit(
    credit_id: str,
    amount: Decimal,
    reason: AdjustmentReason,
    description: str,
    related_charge_id: Optional[str] = None,
    category: ChargeCategory = ChargeCategory.OTHER,
    charge_type: ChargeType = ChargeType.MISCELLANEOUS,
) -> Credit:
    """
    Create a credit for a billing adjustment.

    Args:
        credit_id: Unique identifier for this credit
        amount: Amount to credit (positive value, will be negated)
        reason: Why the adjustment is being made
        description: Customer-facing description
        related_charge_id: ID of the original charge being adjusted
        category: Category for grouping
        charge_type: Type for labeling

    Returns:
        A Credit configured as an adjustment
    """
    # Build explanation based on reason
    explanations = {
        AdjustmentReason.BILLING_ERROR: (
            "This credit corrects an error on a previous bill."
        ),
        AdjustmentReason.SERVICE_ISSUE: (
            "This credit compensates for a service disruption you experienced."
        ),
        AdjustmentReason.GOODWILL: (
            "This credit has been applied to your account as a courtesy."
        ),
        AdjustmentReason.REFUND: (
            "This is a refund for a previous charge."
        ),
    }

    return Credit(
        id=credit_id,
        description=description,
        amount=amount,  # Will be negated in __post_init__
        category=category,
        charge_type=charge_type,
        adjustment_reason=reason,
        related_charge_id=related_charge_id,
        display_label=f"Adjustment - {description}",
        explanation=explanations.get(reason, "Credit applied to your account."),
    )


# =============================================================================
# PRORATION
# =============================================================================
# Proration occurs when a charge covers only part of a billing period,
# such as when a customer upgrades mid-cycle or starts/stops service.
#
# Key fields:
#   - prorated_amount: The adjusted amount for partial period
#   - prorated_days: Number of days in the partial period
#   - original_amount: What the full-period charge would be
#   - service_period_start/end: The actual dates covered
#
# Calculation: prorated_amount = original_amount * (prorated_days / days_in_period)
# =============================================================================


def calculate_prorated_amount(
    original_amount: Decimal,
    start_date: date,
    end_date: date,
    billing_period_start: date,
    billing_period_end: date,
) -> tuple[Decimal, int]:
    """
    Calculate the prorated amount for a partial billing period.

    Args:
        original_amount: Full period charge amount
        start_date: When service started (or change took effect)
        end_date: When service ended (or billing period ends)
        billing_period_start: Start of full billing period
        billing_period_end: End of full billing period

    Returns:
        Tuple of (prorated_amount, prorated_days)
    """
    # Calculate days in full billing period
    total_days = (billing_period_end - billing_period_start).days + 1

    # Calculate days in prorated period
    prorated_days = (end_date - start_date).days + 1

    # Calculate prorated amount
    prorated_amount = (original_amount * Decimal(prorated_days) / Decimal(total_days))
    prorated_amount = prorated_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return prorated_amount, prorated_days


def create_prorated_charge(
    charge_id: str,
    description: str,
    original_amount: Decimal,
    category: ChargeCategory,
    charge_type: ChargeType,
    start_date: date,
    end_date: date,
    billing_period_start: date,
    billing_period_end: date,
) -> Charge:
    """
    Create a prorated charge for a partial billing period.

    Args:
        charge_id: Unique identifier for this charge
        description: Description for the charge
        original_amount: What the full period charge would be
        category: Charge category
        charge_type: Type of charge
        start_date: When the service/charge started
        end_date: When the service/charge ended
        billing_period_start: Start of full billing period
        billing_period_end: End of full billing period

    Returns:
        A Charge with proration applied
    """
    prorated_amount, prorated_days = calculate_prorated_amount(
        original_amount,
        start_date,
        end_date,
        billing_period_start,
        billing_period_end,
    )

    total_days = (billing_period_end - billing_period_start).days + 1

    return Charge(
        id=charge_id,
        description=description,
        amount=original_amount,
        category=category,
        charge_type=charge_type,
        service_period_start=start_date,
        service_period_end=end_date,
        prorated_amount=prorated_amount,
        prorated_days=prorated_days,
        original_amount=original_amount,
        display_label=f"{description} (Prorated)",
        explanation=(
            f"This charge covers {prorated_days} of {total_days} days in the "
            f"billing period ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d')})."
        ),
    )


# =============================================================================
# PROMOTIONS
# =============================================================================
# Promotions are temporary discounts that may have expiration dates,
# promo codes, or specific terms and conditions.
#
# Key fields:
#   - discount_type: Category of promotion (PROMOTIONAL, LOYALTY, etc.)
#   - promo_code: The code used to apply the discount (if any)
#   - expiration_date: When the promotion ends
#   - discount_percentage: For percentage-based discounts
#   - terms_and_conditions: Legal text for the promotion
#
# Promotions can be:
#   - One-time discounts
#   - Recurring discounts (applied each billing period)
#   - Time-limited (with expiration)
# =============================================================================


@dataclass
class Promotion:
    """Configuration for a promotional offer."""

    promo_code: str
    description: str
    discount_amount: Optional[Decimal] = None
    discount_percentage: Optional[Decimal] = None
    discount_type: DiscountType = DiscountType.PROMOTIONAL
    start_date: Optional[date] = None
    expiration_date: Optional[date] = None
    is_recurring: bool = True
    max_applications: Optional[int] = None
    terms_and_conditions: Optional[str] = None

    def is_valid(self, as_of_date: Optional[date] = None) -> bool:
        """Check if the promotion is valid as of a given date."""
        check_date = as_of_date or date.today()

        if self.start_date and check_date < self.start_date:
            return False
        if self.expiration_date and check_date > self.expiration_date:
            return False

        return True

    def calculate_discount(self, base_amount: Decimal) -> Decimal:
        """Calculate the discount amount for a given base charge."""
        if self.discount_amount:
            return self.discount_amount
        if self.discount_percentage:
            discount = base_amount * (self.discount_percentage / 100)
            return discount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return Decimal("0.00")


def create_promotional_discount(
    discount_id: str,
    promotion: Promotion,
    base_amount: Decimal,
    category: ChargeCategory = ChargeCategory.RECURRING,
    charge_type: ChargeType = ChargeType.MONTHLY_SERVICE,
) -> Discount:
    """
    Create a discount from a promotional offer.

    Args:
        discount_id: Unique identifier for this discount
        promotion: The promotion configuration
        base_amount: The base charge amount to apply the discount to
        category: Category for grouping
        charge_type: Type for labeling

    Returns:
        A Discount for the promotion
    """
    discount_amount = promotion.calculate_discount(base_amount)

    # Build expiration notice if applicable
    explanation_parts = [promotion.description]
    if promotion.expiration_date:
        explanation_parts.append(
            f"This offer expires on {promotion.expiration_date.strftime('%B %d, %Y')}."
        )

    return Discount(
        id=discount_id,
        description=promotion.description,
        amount=discount_amount,  # Will be negated in __post_init__
        category=category,
        charge_type=charge_type,
        discount_type=promotion.discount_type,
        discount_percentage=promotion.discount_percentage,
        promo_code=promotion.promo_code,
        expiration_date=promotion.expiration_date,
        is_recurring=promotion.is_recurring,
        terms_and_conditions=promotion.terms_and_conditions,
        display_label=f"Discount - {promotion.description}",
        explanation=" ".join(explanation_parts),
    )


# =============================================================================
# EXAMPLE USAGE
# =============================================================================


def example_usage():
    """Demonstrate edge case handling with examples."""
    from datetime import date
    from decimal import Decimal

    # Example 1: Installment Plan
    phone_plan = InstallmentPlan(
        total_amount=Decimal("799.99"),
        num_installments=24,
        down_payment=Decimal("0.00"),
        interest_rate=Decimal("0.00"),  # 0% financing
    )
    installment = create_installment_charge(
        plan=phone_plan,
        installment_number=3,
        charge_id="inst-003",
        description="iPhone 15 Pro",
        service_period_start=date(2024, 1, 1),
        service_period_end=date(2024, 1, 31),
    )
    print(f"Installment: {installment.display_label} - ${installment.amount}")

    # Example 2: Billing Adjustment
    adjustment = create_adjustment_credit(
        credit_id="adj-001",
        amount=Decimal("15.00"),
        reason=AdjustmentReason.BILLING_ERROR,
        description="Duplicate charge correction",
        related_charge_id="chg-001",
    )
    print(f"Adjustment: {adjustment.display_label} - ${adjustment.amount}")

    # Example 3: Prorated Charge
    prorated = create_prorated_charge(
        charge_id="pro-001",
        description="Unlimited Plan",
        original_amount=Decimal("85.00"),
        category=ChargeCategory.RECURRING,
        charge_type=ChargeType.MONTHLY_SERVICE,
        start_date=date(2024, 1, 15),  # Started mid-month
        end_date=date(2024, 1, 31),
        billing_period_start=date(2024, 1, 1),
        billing_period_end=date(2024, 1, 31),
    )
    print(f"Prorated: {prorated.display_label} - ${prorated.get_effective_amount()}")

    # Example 4: Promotional Discount
    promo = Promotion(
        promo_code="SAVE20",
        description="20% off for 12 months",
        discount_percentage=Decimal("20"),
        discount_type=DiscountType.PROMOTIONAL,
        expiration_date=date(2024, 12, 31),
        is_recurring=True,
        terms_and_conditions="Discount applies to base plan only. Cannot be combined with other offers.",
    )
    discount = create_promotional_discount(
        discount_id="disc-001",
        promotion=promo,
        base_amount=Decimal("85.00"),
    )
    print(f"Promotion: {discount.display_label} - ${discount.amount}")


if __name__ == "__main__":
    example_usage()
