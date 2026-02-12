"""
Trade-In Credit Data Models

Core data models for trade-in credit integration with full audit trail support.
Designed to maintain traceable mapping from trade-in transaction ID to credit
records for Finance reconciliation (SE-5031 requirement).
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional
import uuid


class CreditStatus(Enum):
    """Status of a trade-in credit through its lifecycle."""

    PENDING = "pending"  # Credit approved but not yet applied
    APPLIED_TO_ORDER = "applied_to_order"  # Credit applied at order/activation
    APPLIED_TO_BILLING = "applied_to_billing"  # Credit posted to billing system
    FULLY_APPLIED = "fully_applied"  # Credit fully consumed across all systems
    EXPIRED = "expired"  # Credit expired before full application
    CANCELLED = "cancelled"  # Credit cancelled (e.g., trade-in rejected)
    PARTIALLY_APPLIED = "partially_applied"  # Credit partially used


class ApplicationTarget(Enum):
    """Target system where credit is applied."""

    ORDER = "order"  # Order management / activation system
    BILLING = "billing"  # Billing / invoicing system
    BOTH = "both"  # Applied to both systems


class DeviceCondition(Enum):
    """Condition of traded-in device (from upstream SE-5030 quoting)."""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    DAMAGED = "damaged"


@dataclass
class TradeInTransaction:
    """
    Represents a trade-in transaction from the upstream quoting workflow (SE-5030).

    This is the source record that generates trade-in credits. Every credit
    must trace back to exactly one TradeInTransaction for reconciliation.

    Attributes:
        transaction_id: Unique identifier for the trade-in transaction
        quote_id: Reference to the original quote from SE-5030 quoting system
        customer_id: Customer performing the trade-in
        partner_id: Indirect retail partner facilitating the trade-in
        device_imei: IMEI of the traded-in device
        device_model: Model of the traded-in device
        device_condition: Assessed condition of the device
        quoted_value: Original quoted trade-in value
        approved_value: Final approved credit value (may differ after inspection)
        quote_timestamp: When the quote was generated
        approval_timestamp: When the trade-in was approved
        expiration_date: When the quote/credit expires
        metadata: Additional context for audit trail
    """

    transaction_id: str
    quote_id: str
    customer_id: str
    partner_id: str
    device_imei: str
    device_model: str
    device_condition: DeviceCondition
    quoted_value: Decimal
    approved_value: Decimal
    quote_timestamp: datetime
    approval_timestamp: Optional[datetime] = None
    expiration_date: Optional[date] = None
    store_location: Optional[str] = None
    sales_rep_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """Ensure monetary values are properly formatted."""
        if isinstance(self.quoted_value, (int, float)):
            self.quoted_value = Decimal(str(self.quoted_value))
        if isinstance(self.approved_value, (int, float)):
            self.approved_value = Decimal(str(self.approved_value))
        # Quantize to 2 decimal places
        self.quoted_value = self.quoted_value.quantize(Decimal("0.01"))
        self.approved_value = self.approved_value.quantize(Decimal("0.01"))

    def is_expired(self) -> bool:
        """Check if the trade-in quote/credit has expired."""
        if self.expiration_date is None:
            return False
        return date.today() > self.expiration_date

    def is_approved(self) -> bool:
        """Check if the trade-in has been approved."""
        return self.approval_timestamp is not None


@dataclass
class TradeInCredit:
    """
    Represents a credit generated from an approved trade-in transaction.

    This is the credit record that gets applied to orders and billing.
    Maintains full audit trail linking back to the source trade-in transaction.

    Attributes:
        credit_id: Unique identifier for this credit record
        trade_in_transaction_id: Links to source TradeInTransaction (for reconciliation)
        amount: Credit amount to be applied
        remaining_amount: Portion of credit not yet applied
        status: Current status in the credit lifecycle
        created_at: When the credit was created
        customer_id: Customer receiving the credit
        account_id: Billing account ID for the customer
        description: Human-readable description for statements
    """

    credit_id: str
    trade_in_transaction_id: str  # Critical: links to source for reconciliation
    amount: Decimal
    remaining_amount: Decimal
    status: CreditStatus
    created_at: datetime
    customer_id: str
    account_id: str
    description: str = ""
    expiration_date: Optional[date] = None
    applied_to_order_id: Optional[str] = None
    applied_to_invoice_id: Optional[str] = None
    last_updated: Optional[datetime] = None
    audit_log: list = field(default_factory=list)

    def __post_init__(self):
        """Ensure monetary values are properly formatted."""
        if isinstance(self.amount, (int, float)):
            self.amount = Decimal(str(self.amount))
        if isinstance(self.remaining_amount, (int, float)):
            self.remaining_amount = Decimal(str(self.remaining_amount))
        self.amount = self.amount.quantize(Decimal("0.01"))
        self.remaining_amount = self.remaining_amount.quantize(Decimal("0.01"))
        if not self.description:
            self.description = f"Trade-in credit (Transaction: {self.trade_in_transaction_id})"

    @classmethod
    def from_transaction(cls, transaction: TradeInTransaction, account_id: str) -> "TradeInCredit":
        """
        Factory method to create a TradeInCredit from an approved TradeInTransaction.

        Args:
            transaction: The approved trade-in transaction
            account_id: The billing account to apply the credit to

        Returns:
            A new TradeInCredit linked to the transaction

        Raises:
            ValueError: If transaction is not approved or is expired
        """
        if not transaction.is_approved():
            raise ValueError(
                f"Cannot create credit from unapproved transaction: {transaction.transaction_id}"
            )
        if transaction.is_expired():
            raise ValueError(
                f"Cannot create credit from expired transaction: {transaction.transaction_id}"
            )

        credit = cls(
            credit_id=str(uuid.uuid4()),
            trade_in_transaction_id=transaction.transaction_id,
            amount=transaction.approved_value,
            remaining_amount=transaction.approved_value,
            status=CreditStatus.PENDING,
            created_at=datetime.utcnow(),
            customer_id=transaction.customer_id,
            account_id=account_id,
            description=f"Trade-in credit for {transaction.device_model} (IMEI: {transaction.device_imei[-4:]})",
            expiration_date=transaction.expiration_date,
        )
        credit._add_audit_entry("CREDIT_CREATED", f"Credit created from transaction {transaction.transaction_id}")
        return credit

    def _add_audit_entry(self, action: str, details: str) -> None:
        """Add an entry to the audit log."""
        self.audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "details": details,
            "credit_id": self.credit_id,
            "trade_in_transaction_id": self.trade_in_transaction_id,
        })
        self.last_updated = datetime.utcnow()

    def apply_to_order(self, order_id: str, amount: Optional[Decimal] = None) -> Decimal:
        """
        Apply credit to an order.

        Args:
            order_id: The order to apply credit to
            amount: Amount to apply (defaults to remaining amount)

        Returns:
            The amount actually applied

        Raises:
            ValueError: If credit cannot be applied
        """
        if self.status in (CreditStatus.EXPIRED, CreditStatus.CANCELLED):
            raise ValueError(f"Cannot apply credit with status: {self.status.value}")

        if self.remaining_amount <= 0:
            raise ValueError("No remaining credit to apply")

        apply_amount = amount if amount is not None else self.remaining_amount
        apply_amount = min(apply_amount, self.remaining_amount)

        self.remaining_amount -= apply_amount
        self.applied_to_order_id = order_id

        if self.remaining_amount <= 0:
            self.status = CreditStatus.APPLIED_TO_ORDER
        else:
            self.status = CreditStatus.PARTIALLY_APPLIED

        self._add_audit_entry(
            "APPLIED_TO_ORDER",
            f"Applied ${apply_amount} to order {order_id}. Remaining: ${self.remaining_amount}"
        )
        return apply_amount

    def apply_to_billing(self, invoice_id: str, amount: Optional[Decimal] = None) -> Decimal:
        """
        Apply credit to a billing invoice.

        Args:
            invoice_id: The invoice to apply credit to
            amount: Amount to apply (defaults to remaining amount)

        Returns:
            The amount actually applied
        """
        if self.status in (CreditStatus.EXPIRED, CreditStatus.CANCELLED):
            raise ValueError(f"Cannot apply credit with status: {self.status.value}")

        if self.remaining_amount <= 0:
            raise ValueError("No remaining credit to apply")

        apply_amount = amount if amount is not None else self.remaining_amount
        apply_amount = min(apply_amount, self.remaining_amount)

        self.remaining_amount -= apply_amount
        self.applied_to_invoice_id = invoice_id

        if self.remaining_amount <= 0:
            if self.applied_to_order_id:
                self.status = CreditStatus.FULLY_APPLIED
            else:
                self.status = CreditStatus.APPLIED_TO_BILLING
        else:
            self.status = CreditStatus.PARTIALLY_APPLIED

        self._add_audit_entry(
            "APPLIED_TO_BILLING",
            f"Applied ${apply_amount} to invoice {invoice_id}. Remaining: ${self.remaining_amount}"
        )
        return apply_amount

    def cancel(self, reason: str) -> None:
        """Cancel the credit with a reason."""
        self.status = CreditStatus.CANCELLED
        self._add_audit_entry("CANCELLED", f"Credit cancelled: {reason}")

    def expire(self) -> None:
        """Mark the credit as expired."""
        self.status = CreditStatus.EXPIRED
        self._add_audit_entry("EXPIRED", "Credit expired")


@dataclass
class CreditApplication:
    """
    Records a specific application of credit to an order or billing system.

    This provides detailed audit trail for each credit application event,
    supporting the reconciliation requirement in SE-5031.

    Attributes:
        application_id: Unique identifier for this application record
        credit_id: The credit being applied
        trade_in_transaction_id: Source transaction (denormalized for reporting)
        target: Whether applied to order, billing, or both
        target_id: Order ID or Invoice ID
        amount_applied: How much credit was applied
        applied_at: When the application occurred
        applied_by: User/system that performed the application
    """

    application_id: str
    credit_id: str
    trade_in_transaction_id: str
    target: ApplicationTarget
    target_id: str
    amount_applied: Decimal
    applied_at: datetime
    applied_by: str
    customer_id: str
    account_id: str
    partner_id: Optional[str] = None
    reversal_id: Optional[str] = None  # If this application was reversed
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """Ensure monetary values are properly formatted."""
        if isinstance(self.amount_applied, (int, float)):
            self.amount_applied = Decimal(str(self.amount_applied))
        self.amount_applied = self.amount_applied.quantize(Decimal("0.01"))

    @classmethod
    def record_application(
        cls,
        credit: TradeInCredit,
        target: ApplicationTarget,
        target_id: str,
        amount: Decimal,
        applied_by: str,
        partner_id: Optional[str] = None,
    ) -> "CreditApplication":
        """
        Factory method to record a credit application.

        Args:
            credit: The credit being applied
            target: Order or billing system
            target_id: The order or invoice ID
            amount: Amount being applied
            applied_by: User or system performing the application
            partner_id: Indirect retail partner if applicable

        Returns:
            A CreditApplication record for audit trail
        """
        return cls(
            application_id=str(uuid.uuid4()),
            credit_id=credit.credit_id,
            trade_in_transaction_id=credit.trade_in_transaction_id,
            target=target,
            target_id=target_id,
            amount_applied=amount,
            applied_at=datetime.utcnow(),
            applied_by=applied_by,
            customer_id=credit.customer_id,
            account_id=credit.account_id,
            partner_id=partner_id,
        )
