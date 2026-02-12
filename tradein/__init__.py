"""
Trade-In Credit Integration Module

This module implements SE-5031: Integrate Trade-In Credits into Order & Billing Flows.

It provides the integration layer between:
- Upstream trade-in quoting workflow (SE-5030) that generates approved credits
- Order/activation systems where credits impact order placement
- Billing systems where credits appear on invoices/statements

Key requirement: Full auditability with traceable mapping from
trade-in transaction ID → credit record(s) for Finance reconciliation.
"""

from .models import (
    TradeInTransaction,
    TradeInCredit,
    CreditApplication,
    CreditStatus,
    ApplicationTarget,
)
from .order_integration import OrderCreditIntegration
from .billing_integration import BillingCreditIntegration
from .reconciliation import ReconciliationReport, ReconciliationEngine

__all__ = [
    # Models
    "TradeInTransaction",
    "TradeInCredit",
    "CreditApplication",
    "CreditStatus",
    "ApplicationTarget",
    # Integration
    "OrderCreditIntegration",
    "BillingCreditIntegration",
    # Reconciliation
    "ReconciliationReport",
    "ReconciliationEngine",
]
