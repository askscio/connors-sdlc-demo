"""
Canonical Billing Data Model & Presentment Rules

This module defines the canonical billing data model for omnichannel billing experiences.
It provides consistent data structures for charges, credits, taxes, fees, discounts,
and summaries across all channels (web, app, in-store, care).

Jira: SE-5021
"""

from billing.models import (
    Charge,
    Credit,
    Tax,
    Fee,
    Discount,
    BillLineItem,
    BillSummary,
    Bill,
    ChargeCategory,
    ChargeType,
)

from billing.presentment import (
    PresentmentRule,
    PresentmentConfig,
    group_line_items,
    apply_presentment_rules,
    format_bill_for_display,
)

__all__ = [
    # Models
    "Charge",
    "Credit",
    "Tax",
    "Fee",
    "Discount",
    "BillLineItem",
    "BillSummary",
    "Bill",
    "ChargeCategory",
    "ChargeType",
    # Presentment
    "PresentmentRule",
    "PresentmentConfig",
    "group_line_items",
    "apply_presentment_rules",
    "format_bill_for_display",
]
