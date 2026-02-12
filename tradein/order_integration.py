"""
Order Integration Module

Integrates trade-in credits with order management and activation systems.
Credits are applied at order placement/activation time to reduce the
amount due from the customer.

Part of SE-5031: Integrate Trade-In Credits into Order & Billing Flows.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional, Protocol
import logging

from .models import (
    TradeInCredit,
    TradeInTransaction,
    CreditApplication,
    CreditStatus,
    ApplicationTarget,
)

logger = logging.getLogger(__name__)


class OrderSystemClient(Protocol):
    """
    Protocol for order management system integration.

    Implementations should connect to the actual order management system
    (e.g., Salesforce, SAP, custom OMS) to apply credits.
    """

    def get_order(self, order_id: str) -> dict:
        """Retrieve order details."""
        ...

    def apply_credit(self, order_id: str, credit_amount: Decimal, credit_reference: str) -> dict:
        """Apply a credit to an order. Returns updated order details."""
        ...

    def get_order_total(self, order_id: str) -> Decimal:
        """Get the current order total before credit application."""
        ...

    def validate_order_for_credit(self, order_id: str) -> tuple[bool, str]:
        """Validate that an order can receive a credit. Returns (valid, reason)."""
        ...


@dataclass
class OrderCreditResult:
    """Result of applying a trade-in credit to an order."""

    success: bool
    order_id: str
    credit_id: str
    trade_in_transaction_id: str
    amount_applied: Decimal
    order_total_before: Decimal
    order_total_after: Decimal
    application_record: Optional[CreditApplication] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses or logging."""
        return {
            "success": self.success,
            "order_id": self.order_id,
            "credit_id": self.credit_id,
            "trade_in_transaction_id": self.trade_in_transaction_id,
            "amount_applied": str(self.amount_applied),
            "order_total_before": str(self.order_total_before),
            "order_total_after": str(self.order_total_after),
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
        }


class OrderCreditIntegration:
    """
    Handles integration of trade-in credits with order management systems.

    This class is responsible for:
    - Validating credits can be applied to orders
    - Applying credits at order placement/activation time
    - Recording credit applications for audit trail
    - Handling partial credit applications

    Example usage:
        integration = OrderCreditIntegration(order_client)
        result = integration.apply_credit_to_order(
            credit=trade_in_credit,
            order_id="ORD-12345",
            applied_by="system",
        )
    """

    def __init__(self, order_client: Optional[OrderSystemClient] = None):
        """
        Initialize the order credit integration.

        Args:
            order_client: Client for the order management system.
                         If None, uses a mock client for testing.
        """
        self._order_client = order_client or MockOrderSystemClient()
        self._application_records: list[CreditApplication] = []

    def apply_credit_to_order(
        self,
        credit: TradeInCredit,
        order_id: str,
        applied_by: str,
        amount: Optional[Decimal] = None,
        partner_id: Optional[str] = None,
    ) -> OrderCreditResult:
        """
        Apply a trade-in credit to an order at placement/activation time.

        Args:
            credit: The trade-in credit to apply
            order_id: Target order ID
            applied_by: User or system performing the application
            amount: Specific amount to apply (defaults to full remaining credit)
            partner_id: Indirect retail partner ID if applicable

        Returns:
            OrderCreditResult with details of the application
        """
        logger.info(
            f"Applying credit {credit.credit_id} to order {order_id}. "
            f"Transaction: {credit.trade_in_transaction_id}"
        )

        # Validate credit status
        if credit.status in (CreditStatus.EXPIRED, CreditStatus.CANCELLED):
            return OrderCreditResult(
                success=False,
                order_id=order_id,
                credit_id=credit.credit_id,
                trade_in_transaction_id=credit.trade_in_transaction_id,
                amount_applied=Decimal("0"),
                order_total_before=Decimal("0"),
                order_total_after=Decimal("0"),
                error_message=f"Credit has invalid status: {credit.status.value}",
            )

        # Validate remaining credit amount
        if credit.remaining_amount <= 0:
            return OrderCreditResult(
                success=False,
                order_id=order_id,
                credit_id=credit.credit_id,
                trade_in_transaction_id=credit.trade_in_transaction_id,
                amount_applied=Decimal("0"),
                order_total_before=Decimal("0"),
                order_total_after=Decimal("0"),
                error_message="Credit has no remaining balance",
            )

        # Validate order can receive credit
        valid, reason = self._order_client.validate_order_for_credit(order_id)
        if not valid:
            return OrderCreditResult(
                success=False,
                order_id=order_id,
                credit_id=credit.credit_id,
                trade_in_transaction_id=credit.trade_in_transaction_id,
                amount_applied=Decimal("0"),
                order_total_before=Decimal("0"),
                order_total_after=Decimal("0"),
                error_message=f"Order validation failed: {reason}",
            )

        # Get order total before application
        order_total_before = self._order_client.get_order_total(order_id)

        # Determine amount to apply (don't exceed order total)
        apply_amount = amount if amount is not None else credit.remaining_amount
        apply_amount = min(apply_amount, credit.remaining_amount, order_total_before)

        if apply_amount <= 0:
            return OrderCreditResult(
                success=False,
                order_id=order_id,
                credit_id=credit.credit_id,
                trade_in_transaction_id=credit.trade_in_transaction_id,
                amount_applied=Decimal("0"),
                order_total_before=order_total_before,
                order_total_after=order_total_before,
                error_message="No credit amount to apply",
            )

        # Apply credit to the order system
        try:
            self._order_client.apply_credit(
                order_id=order_id,
                credit_amount=apply_amount,
                credit_reference=f"TRADEIN:{credit.trade_in_transaction_id}:{credit.credit_id}",
            )
        except Exception as e:
            logger.error(f"Failed to apply credit to order system: {e}")
            return OrderCreditResult(
                success=False,
                order_id=order_id,
                credit_id=credit.credit_id,
                trade_in_transaction_id=credit.trade_in_transaction_id,
                amount_applied=Decimal("0"),
                order_total_before=order_total_before,
                order_total_after=order_total_before,
                error_message=f"Order system error: {str(e)}",
            )

        # Update credit record
        actual_applied = credit.apply_to_order(order_id, apply_amount)
        order_total_after = order_total_before - actual_applied

        # Create application record for audit trail
        application = CreditApplication.record_application(
            credit=credit,
            target=ApplicationTarget.ORDER,
            target_id=order_id,
            amount=actual_applied,
            applied_by=applied_by,
            partner_id=partner_id,
        )
        self._application_records.append(application)

        logger.info(
            f"Successfully applied ${actual_applied} to order {order_id}. "
            f"Order total: ${order_total_before} -> ${order_total_after}"
        )

        return OrderCreditResult(
            success=True,
            order_id=order_id,
            credit_id=credit.credit_id,
            trade_in_transaction_id=credit.trade_in_transaction_id,
            amount_applied=actual_applied,
            order_total_before=order_total_before,
            order_total_after=order_total_after,
            application_record=application,
        )

    def apply_transaction_to_order(
        self,
        transaction: TradeInTransaction,
        account_id: str,
        order_id: str,
        applied_by: str,
    ) -> OrderCreditResult:
        """
        Convenience method to create credit from transaction and apply to order.

        Args:
            transaction: Approved trade-in transaction from SE-5030 workflow
            account_id: Customer's billing account ID
            order_id: Target order ID
            applied_by: User or system performing the application

        Returns:
            OrderCreditResult with details of the application
        """
        # Create credit from transaction
        credit = TradeInCredit.from_transaction(transaction, account_id)

        # Apply to order
        return self.apply_credit_to_order(
            credit=credit,
            order_id=order_id,
            applied_by=applied_by,
            partner_id=transaction.partner_id,
        )

    def get_application_records(self) -> list[CreditApplication]:
        """Get all application records for reconciliation."""
        return self._application_records.copy()

    def get_applications_by_order(self, order_id: str) -> list[CreditApplication]:
        """Get all credit applications for a specific order."""
        return [
            app for app in self._application_records
            if app.target == ApplicationTarget.ORDER and app.target_id == order_id
        ]

    def get_applications_by_transaction(self, transaction_id: str) -> list[CreditApplication]:
        """Get all credit applications for a specific trade-in transaction."""
        return [
            app for app in self._application_records
            if app.trade_in_transaction_id == transaction_id
        ]


class MockOrderSystemClient:
    """
    Mock order system client for testing and development.

    In production, this would be replaced with actual integrations to
    order management systems (Salesforce, SAP, custom OMS, etc.).
    """

    def __init__(self):
        self._orders: dict[str, dict] = {}

    def create_test_order(self, order_id: str, total: Decimal, status: str = "pending") -> dict:
        """Create a test order for testing purposes."""
        order = {
            "order_id": order_id,
            "total": total,
            "credits_applied": Decimal("0"),
            "status": status,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._orders[order_id] = order
        return order

    def get_order(self, order_id: str) -> dict:
        """Retrieve order details."""
        if order_id not in self._orders:
            # Create a default test order
            self.create_test_order(order_id, Decimal("500.00"))
        return self._orders[order_id]

    def apply_credit(self, order_id: str, credit_amount: Decimal, credit_reference: str) -> dict:
        """Apply a credit to an order."""
        order = self.get_order(order_id)
        order["credits_applied"] += credit_amount
        order["total"] -= credit_amount
        order["last_credit_reference"] = credit_reference
        order["last_updated"] = datetime.utcnow().isoformat()
        return order

    def get_order_total(self, order_id: str) -> Decimal:
        """Get the current order total."""
        order = self.get_order(order_id)
        return order["total"]

    def validate_order_for_credit(self, order_id: str) -> tuple[bool, str]:
        """Validate that an order can receive a credit."""
        order = self.get_order(order_id)
        if order["status"] == "cancelled":
            return False, "Order is cancelled"
        if order["status"] == "completed":
            return False, "Order is already completed"
        if order["total"] <= 0:
            return False, "Order total is zero or negative"
        return True, "OK"
