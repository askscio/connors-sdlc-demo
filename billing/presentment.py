"""
Presentment Rules for Billing

This module defines how billing data should be presented to customers.
It handles grouping, labeling, roll-ups, and explanations per charge category.

Presentment rules ensure consistent bill display across all channels:
- Web
- Mobile app
- In-store
- Customer care

Jira: SE-5021
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Callable, Optional

from billing.models import (
    Bill,
    BillLineItem,
    Charge,
    ChargeCategory,
    ChargeType,
    Credit,
    Discount,
    Fee,
    Tax,
)


class GroupingStrategy(Enum):
    """How to group line items for display."""

    BY_CATEGORY = "by_category"
    BY_SERVICE = "by_service"
    BY_DATE = "by_date"
    FLAT = "flat"


class RollUpStrategy(Enum):
    """How to roll up line items for summary display."""

    NONE = "none"  # Show all items individually
    BY_TYPE = "by_type"  # Roll up by charge type
    BY_CATEGORY = "by_category"  # Roll up by category
    THRESHOLD = "threshold"  # Roll up items below a threshold


# Default display labels for charge categories
CATEGORY_LABELS = {
    ChargeCategory.RECURRING: "Monthly Charges",
    ChargeCategory.ONE_TIME: "One-Time Charges",
    ChargeCategory.USAGE: "Usage Charges",
    ChargeCategory.EQUIPMENT: "Equipment & Device Charges",
    ChargeCategory.GOVERNMENT: "Taxes, Fees & Government Charges",
    ChargeCategory.THIRD_PARTY: "Third-Party Services",
    ChargeCategory.OTHER: "Other Charges",
}

# Default display labels for charge types
CHARGE_TYPE_LABELS = {
    ChargeType.MONTHLY_SERVICE: "Monthly Service",
    ChargeType.SUBSCRIPTION: "Subscription",
    ChargeType.PLAN_FEE: "Plan Fee",
    ChargeType.ACTIVATION: "Activation Fee",
    ChargeType.INSTALLATION: "Installation Fee",
    ChargeType.UPGRADE: "Upgrade Fee",
    ChargeType.DATA_OVERAGE: "Data Overage",
    ChargeType.INTERNATIONAL_CALL: "International Calls",
    ChargeType.ROAMING: "Roaming Charges",
    ChargeType.PAY_PER_VIEW: "Pay-Per-View",
    ChargeType.DEVICE_PAYMENT: "Device Payment",
    ChargeType.LEASE: "Device Lease",
    ChargeType.RENTAL: "Equipment Rental",
    ChargeType.FEDERAL_TAX: "Federal Tax",
    ChargeType.STATE_TAX: "State Tax",
    ChargeType.LOCAL_TAX: "Local Tax",
    ChargeType.REGULATORY_FEE: "Regulatory Fee",
    ChargeType.PREMIUM_SERVICE: "Premium Service",
    ChargeType.CONTENT_SUBSCRIPTION: "Content Subscription",
    ChargeType.MISCELLANEOUS: "Miscellaneous",
}

# Explanations for charge categories (customer-friendly descriptions)
CATEGORY_EXPLANATIONS = {
    ChargeCategory.RECURRING: (
        "These are your regular monthly charges for services and plans."
    ),
    ChargeCategory.ONE_TIME: (
        "These charges occur once and will not repeat on future bills."
    ),
    ChargeCategory.USAGE: (
        "These charges are based on your actual usage during the billing period."
    ),
    ChargeCategory.EQUIPMENT: (
        "Charges for devices, equipment rentals, or payment plans."
    ),
    ChargeCategory.GOVERNMENT: (
        "Required taxes and regulatory fees mandated by federal, state, and local "
        "governments. These are not charges from us."
    ),
    ChargeCategory.THIRD_PARTY: (
        "Charges from third-party services you've subscribed to through your account."
    ),
    ChargeCategory.OTHER: (
        "Additional charges that don't fall into other categories."
    ),
}


@dataclass
class PresentmentRule:
    """
    A rule for presenting a specific type of charge.

    Defines how a charge should be labeled, grouped, and explained.
    """

    charge_type: Optional[ChargeType] = None
    category: Optional[ChargeCategory] = None

    # Display settings
    display_label: Optional[str] = None
    explanation: Optional[str] = None
    display_order: int = 100

    # Grouping
    group_key: Optional[str] = None

    # Roll-up
    roll_up: bool = False
    roll_up_label: Optional[str] = None

    # Visibility
    hide_if_zero: bool = True
    show_details: bool = True

    # Formatting
    show_service_period: bool = False
    show_breakdown: bool = False

    def matches(self, item: BillLineItem) -> bool:
        """Check if this rule matches a line item."""
        if self.charge_type and item.charge_type != self.charge_type:
            return False
        if self.category and item.category != self.category:
            return False
        return True

    def apply(self, item: BillLineItem) -> BillLineItem:
        """Apply this rule to a line item."""
        if self.display_label:
            item.display_label = self.display_label
        if self.explanation:
            item.explanation = self.explanation
        if self.display_order:
            item.display_order = self.display_order
        return item


@dataclass
class PresentmentConfig:
    """
    Configuration for bill presentment.

    Defines how the entire bill should be formatted and displayed.
    """

    grouping_strategy: GroupingStrategy = GroupingStrategy.BY_CATEGORY
    roll_up_strategy: RollUpStrategy = RollUpStrategy.NONE
    roll_up_threshold: Decimal = Decimal("1.00")

    # Display settings
    show_category_subtotals: bool = True
    show_category_explanations: bool = True
    show_previous_balance: bool = True
    show_payment_history: bool = True

    # Custom labels
    category_labels: dict[ChargeCategory, str] = field(
        default_factory=lambda: CATEGORY_LABELS.copy()
    )
    category_explanations: dict[ChargeCategory, str] = field(
        default_factory=lambda: CATEGORY_EXPLANATIONS.copy()
    )
    charge_type_labels: dict[ChargeType, str] = field(
        default_factory=lambda: CHARGE_TYPE_LABELS.copy()
    )

    # Custom rules (applied in order)
    rules: list[PresentmentRule] = field(default_factory=list)

    # Category display order
    category_order: list[ChargeCategory] = field(
        default_factory=lambda: [
            ChargeCategory.RECURRING,
            ChargeCategory.ONE_TIME,
            ChargeCategory.USAGE,
            ChargeCategory.EQUIPMENT,
            ChargeCategory.THIRD_PARTY,
            ChargeCategory.GOVERNMENT,
            ChargeCategory.OTHER,
        ]
    )


@dataclass
class GroupedLineItems:
    """A group of line items for display."""

    category: ChargeCategory
    label: str
    explanation: Optional[str]
    items: list[BillLineItem]
    subtotal: Decimal
    display_order: int

    def __post_init__(self):
        # Sort items by display_order
        self.items.sort(key=lambda x: x.display_order)


@dataclass
class FormattedBill:
    """A bill formatted for display according to presentment rules."""

    bill: Bill
    groups: list[GroupedLineItems]
    config: PresentmentConfig

    # Summary display values
    subtotal_display: str = ""
    taxes_fees_display: str = ""
    credits_display: str = ""
    discounts_display: str = ""
    total_display: str = ""
    previous_balance_display: str = ""
    amount_due_display: str = ""


def get_category_label(category: ChargeCategory, config: PresentmentConfig) -> str:
    """Get the display label for a category."""
    return config.category_labels.get(category, CATEGORY_LABELS.get(category, "Other"))


def get_category_explanation(
    category: ChargeCategory, config: PresentmentConfig
) -> Optional[str]:
    """Get the explanation for a category."""
    if not config.show_category_explanations:
        return None
    return config.category_explanations.get(
        category, CATEGORY_EXPLANATIONS.get(category)
    )


def get_charge_type_label(charge_type: ChargeType, config: PresentmentConfig) -> str:
    """Get the display label for a charge type."""
    return config.charge_type_labels.get(
        charge_type, CHARGE_TYPE_LABELS.get(charge_type, "Charge")
    )


def apply_rules_to_item(
    item: BillLineItem, config: PresentmentConfig
) -> BillLineItem:
    """Apply presentment rules to a line item."""
    # Apply default label if not set
    if not item.display_label:
        item.display_label = get_charge_type_label(item.charge_type, config)

    # Apply custom rules
    for rule in config.rules:
        if rule.matches(item):
            rule.apply(item)

    return item


def group_line_items(
    items: list[BillLineItem], config: PresentmentConfig
) -> list[GroupedLineItems]:
    """
    Group line items according to the configured strategy.

    Returns a list of GroupedLineItems sorted by display order.
    """
    if config.grouping_strategy == GroupingStrategy.FLAT:
        # Return all items in a single group
        return [
            GroupedLineItems(
                category=ChargeCategory.OTHER,
                label="All Charges",
                explanation=None,
                items=items,
                subtotal=sum(item.amount for item in items),
                display_order=0,
            )
        ]

    # Group by category
    groups: dict[ChargeCategory, list[BillLineItem]] = {}
    for item in items:
        if item.category not in groups:
            groups[item.category] = []
        groups[item.category].append(item)

    # Create GroupedLineItems
    result = []
    for i, category in enumerate(config.category_order):
        if category in groups:
            category_items = groups[category]
            subtotal = sum(item.amount for item in category_items)

            # Skip empty groups
            if not category_items:
                continue

            result.append(
                GroupedLineItems(
                    category=category,
                    label=get_category_label(category, config),
                    explanation=get_category_explanation(category, config),
                    items=category_items,
                    subtotal=subtotal,
                    display_order=i,
                )
            )

    # Add any categories not in the order list
    for category, category_items in groups.items():
        if category not in config.category_order and category_items:
            subtotal = sum(item.amount for item in category_items)
            result.append(
                GroupedLineItems(
                    category=category,
                    label=get_category_label(category, config),
                    explanation=get_category_explanation(category, config),
                    items=category_items,
                    subtotal=subtotal,
                    display_order=len(config.category_order),
                )
            )

    return result


def apply_roll_up(
    groups: list[GroupedLineItems], config: PresentmentConfig
) -> list[GroupedLineItems]:
    """
    Apply roll-up strategy to grouped line items.

    Roll-ups combine multiple small line items into a summary line.
    """
    if config.roll_up_strategy == RollUpStrategy.NONE:
        return groups

    for group in groups:
        if config.roll_up_strategy == RollUpStrategy.THRESHOLD:
            # Roll up items below the threshold
            small_items = [
                item
                for item in group.items
                if abs(item.amount) < config.roll_up_threshold
            ]
            if len(small_items) > 1:
                # Create a rolled-up item
                rolled_total = sum(item.amount for item in small_items)
                rolled_item = BillLineItem(
                    id="rolled_up",
                    description=f"Other {group.label}",
                    amount=rolled_total,
                    category=group.category,
                    charge_type=ChargeType.MISCELLANEOUS,
                    display_label=f"Other {group.label} ({len(small_items)} items)",
                    display_order=999,
                )
                # Remove small items and add rolled-up item
                group.items = [
                    item
                    for item in group.items
                    if abs(item.amount) >= config.roll_up_threshold
                ]
                group.items.append(rolled_item)

    return groups


def apply_presentment_rules(
    bill: Bill, config: Optional[PresentmentConfig] = None
) -> Bill:
    """
    Apply presentment rules to all line items in a bill.

    Modifies the bill in place and returns it.
    """
    if config is None:
        config = PresentmentConfig()

    # Apply rules to all line items
    for charge in bill.charges:
        apply_rules_to_item(charge, config)
    for credit in bill.credits:
        apply_rules_to_item(credit, config)
    for tax in bill.taxes:
        apply_rules_to_item(tax, config)
    for fee in bill.fees:
        apply_rules_to_item(fee, config)
    for discount in bill.discounts:
        apply_rules_to_item(discount, config)

    return bill


def format_currency(amount: Decimal, currency: str = "USD") -> str:
    """Format a decimal amount as currency."""
    if currency == "USD":
        if amount < 0:
            return f"-${abs(amount):,.2f}"
        return f"${amount:,.2f}"
    return f"{amount:,.2f} {currency}"


def format_bill_for_display(
    bill: Bill, config: Optional[PresentmentConfig] = None
) -> FormattedBill:
    """
    Format a bill for display according to presentment rules.

    Returns a FormattedBill with grouped and formatted data ready for rendering.
    """
    if config is None:
        config = PresentmentConfig()

    # Ensure summary is calculated
    bill.calculate_summary()

    # Apply presentment rules
    apply_presentment_rules(bill, config)

    # Get all line items
    all_items = bill.get_all_line_items()

    # Group items
    groups = group_line_items(all_items, config)

    # Apply roll-up
    groups = apply_roll_up(groups, config)

    # Format summary values
    summary = bill.summary
    formatted = FormattedBill(
        bill=bill,
        groups=groups,
        config=config,
        subtotal_display=format_currency(summary.subtotal_charges, bill.currency),
        taxes_fees_display=format_currency(
            summary.total_taxes + summary.total_fees, bill.currency
        ),
        credits_display=format_currency(summary.total_credits, bill.currency),
        discounts_display=format_currency(summary.total_discounts, bill.currency),
        total_display=format_currency(summary.current_charges, bill.currency),
        previous_balance_display=format_currency(
            summary.previous_balance, bill.currency
        ),
        amount_due_display=format_currency(summary.amount_due, bill.currency),
    )

    return formatted
