"""
Canonical Billing Data Model

This module defines the core data structures for billing across all channels.
The model supports: charges, credits, taxes, fees, discounts, and summaries.

Edge cases explicitly supported:
- Installments: Charges can be split across billing periods
- Adjustments: Credits can represent billing adjustments
- Proration: Charges can have prorated_amount for partial periods
- Promotions: Discounts can represent promotional pricing

Jira: SE-5021
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class ChargeCategory(Enum):
    """Categories for grouping charges in bill presentment."""

    RECURRING = "recurring"
    ONE_TIME = "one_time"
    USAGE = "usage"
    EQUIPMENT = "equipment"
    GOVERNMENT = "government"
    THIRD_PARTY = "third_party"
    OTHER = "other"


class ChargeType(Enum):
    """Specific types of charges within categories."""

    # Recurring
    MONTHLY_SERVICE = "monthly_service"
    SUBSCRIPTION = "subscription"
    PLAN_FEE = "plan_fee"

    # One-time
    ACTIVATION = "activation"
    INSTALLATION = "installation"
    UPGRADE = "upgrade"

    # Usage
    DATA_OVERAGE = "data_overage"
    INTERNATIONAL_CALL = "international_call"
    ROAMING = "roaming"
    PAY_PER_VIEW = "pay_per_view"

    # Equipment
    DEVICE_PAYMENT = "device_payment"
    LEASE = "lease"
    RENTAL = "rental"

    # Government
    FEDERAL_TAX = "federal_tax"
    STATE_TAX = "state_tax"
    LOCAL_TAX = "local_tax"
    REGULATORY_FEE = "regulatory_fee"

    # Third-party
    PREMIUM_SERVICE = "premium_service"
    CONTENT_SUBSCRIPTION = "content_subscription"

    # Other
    MISCELLANEOUS = "miscellaneous"


class AdjustmentReason(Enum):
    """Reasons for billing adjustments (credits/debits)."""

    BILLING_ERROR = "billing_error"
    SERVICE_ISSUE = "service_issue"
    GOODWILL = "goodwill"
    PRORATION = "proration"
    PROMOTION = "promotion"
    REFUND = "refund"
    INSTALLMENT = "installment"


class DiscountType(Enum):
    """Types of discounts that can be applied."""

    PROMOTIONAL = "promotional"
    LOYALTY = "loyalty"
    BUNDLE = "bundle"
    EMPLOYEE = "employee"
    AUTOPAY = "autopay"
    PAPERLESS = "paperless"
    MILITARY = "military"
    SENIOR = "senior"


@dataclass
class BillLineItem:
    """
    Base class for all bill line items.

    All monetary amounts are stored as Decimal for precision.
    """

    id: str
    description: str
    amount: Decimal
    category: ChargeCategory
    charge_type: ChargeType
    service_period_start: Optional[date] = None
    service_period_end: Optional[date] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

    # Presentment fields
    display_label: Optional[str] = None
    display_order: int = 0
    explanation: Optional[str] = None

    def get_display_label(self) -> str:
        """Return the label to display on the bill."""
        return self.display_label or self.description


@dataclass
class Charge(BillLineItem):
    """
    A charge on the bill (positive amount).

    Supports edge cases:
    - Installments: Set is_installment=True, installment_number, total_installments
    - Proration: Set prorated_amount for partial period charges
    """

    is_recurring: bool = False
    is_installment: bool = False
    installment_number: Optional[int] = None
    total_installments: Optional[int] = None
    prorated_amount: Optional[Decimal] = None
    prorated_days: Optional[int] = None
    original_amount: Optional[Decimal] = None

    def get_effective_amount(self) -> Decimal:
        """Return prorated amount if applicable, otherwise full amount."""
        if self.prorated_amount is not None:
            return self.prorated_amount
        return self.amount


@dataclass
class Credit(BillLineItem):
    """
    A credit on the bill (negative amount reducing total).

    Used for:
    - Billing adjustments
    - Service issue credits
    - Promotional credits
    - Refunds
    """

    adjustment_reason: Optional[AdjustmentReason] = None
    related_charge_id: Optional[str] = None
    expiration_date: Optional[date] = None

    def __post_init__(self):
        # Credits should be represented as negative amounts
        if self.amount > 0:
            self.amount = -self.amount


@dataclass
class Tax(BillLineItem):
    """
    A tax line item.

    Taxes are separated from fees for regulatory compliance and reporting.
    """

    tax_rate: Optional[Decimal] = None
    jurisdiction: Optional[str] = None
    tax_authority: Optional[str] = None
    is_estimated: bool = False

    def __post_init__(self):
        # Default category for taxes
        self.category = ChargeCategory.GOVERNMENT


@dataclass
class Fee(BillLineItem):
    """
    A fee line item (regulatory, administrative, or surcharge).

    Fees are non-tax charges required by regulations or company policy.
    """

    is_regulatory: bool = False
    is_passthrough: bool = False
    fee_authority: Optional[str] = None


@dataclass
class Discount(BillLineItem):
    """
    A discount on the bill.

    Supports:
    - Promotional discounts with expiration
    - Bundle discounts
    - Loyalty rewards
    - Auto-pay and paperless billing discounts
    """

    discount_type: DiscountType = DiscountType.PROMOTIONAL
    discount_percentage: Optional[Decimal] = None
    promo_code: Optional[str] = None
    expiration_date: Optional[date] = None
    is_recurring: bool = True
    terms_and_conditions: Optional[str] = None

    def __post_init__(self):
        # Discounts should be represented as negative amounts
        if self.amount > 0:
            self.amount = -self.amount


@dataclass
class BillSummary:
    """
    Summary totals for a bill.

    Provides roll-up of all charges, credits, taxes, fees, and discounts.
    """

    subtotal_charges: Decimal = Decimal("0.00")
    total_credits: Decimal = Decimal("0.00")
    total_taxes: Decimal = Decimal("0.00")
    total_fees: Decimal = Decimal("0.00")
    total_discounts: Decimal = Decimal("0.00")

    # Category subtotals for presentment
    recurring_charges: Decimal = Decimal("0.00")
    one_time_charges: Decimal = Decimal("0.00")
    usage_charges: Decimal = Decimal("0.00")
    equipment_charges: Decimal = Decimal("0.00")
    government_charges: Decimal = Decimal("0.00")
    third_party_charges: Decimal = Decimal("0.00")

    previous_balance: Decimal = Decimal("0.00")
    payments_received: Decimal = Decimal("0.00")

    @property
    def current_charges(self) -> Decimal:
        """Calculate current period charges before credits/discounts."""
        return (
            self.subtotal_charges
            + self.total_taxes
            + self.total_fees
        )

    @property
    def total_adjustments(self) -> Decimal:
        """Calculate total adjustments (credits + discounts)."""
        return self.total_credits + self.total_discounts

    @property
    def amount_due(self) -> Decimal:
        """Calculate total amount due."""
        return (
            self.previous_balance
            - self.payments_received
            + self.current_charges
            + self.total_adjustments  # Negative values reduce amount
        )


@dataclass
class Bill:
    """
    Complete bill representation.

    Contains all line items and summary for a billing period.
    Designed for consistent presentment across all channels.
    """

    id: str
    account_id: str
    billing_period_start: date
    billing_period_end: date
    due_date: date
    statement_date: date

    charges: list[Charge] = field(default_factory=list)
    credits: list[Credit] = field(default_factory=list)
    taxes: list[Tax] = field(default_factory=list)
    fees: list[Fee] = field(default_factory=list)
    discounts: list[Discount] = field(default_factory=list)

    summary: BillSummary = field(default_factory=BillSummary)

    # Metadata
    currency: str = "USD"
    is_final: bool = True
    version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)

    def get_all_line_items(self) -> list[BillLineItem]:
        """Return all line items in a flat list."""
        return self.charges + self.credits + self.taxes + self.fees + self.discounts

    def calculate_summary(self) -> BillSummary:
        """
        Calculate and update the bill summary from line items.

        Returns the updated BillSummary.
        """
        summary = BillSummary()

        # Sum charges
        for charge in self.charges:
            effective_amount = charge.get_effective_amount()
            summary.subtotal_charges += effective_amount

            # Category subtotals
            if charge.category == ChargeCategory.RECURRING:
                summary.recurring_charges += effective_amount
            elif charge.category == ChargeCategory.ONE_TIME:
                summary.one_time_charges += effective_amount
            elif charge.category == ChargeCategory.USAGE:
                summary.usage_charges += effective_amount
            elif charge.category == ChargeCategory.EQUIPMENT:
                summary.equipment_charges += effective_amount
            elif charge.category == ChargeCategory.THIRD_PARTY:
                summary.third_party_charges += effective_amount

        # Sum credits
        for credit in self.credits:
            summary.total_credits += credit.amount

        # Sum taxes
        for tax in self.taxes:
            summary.total_taxes += tax.amount
            summary.government_charges += tax.amount

        # Sum fees
        for fee in self.fees:
            summary.total_fees += fee.amount
            if fee.is_regulatory:
                summary.government_charges += fee.amount

        # Sum discounts
        for discount in self.discounts:
            summary.total_discounts += discount.amount

        # Preserve previous balance and payments
        summary.previous_balance = self.summary.previous_balance
        summary.payments_received = self.summary.payments_received

        self.summary = summary
        return summary
