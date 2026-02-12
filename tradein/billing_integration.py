"""
Billing Integration Module

Integrates trade-in credits with billing systems so credits appear
on invoices and customer statements.

Part of SE-5031: Integrate Trade-In Credits into Order & Billing Flows.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
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


class BillingSystemClient(Protocol):
    """
    Protocol for billing system integration.

    Implementations should connect to the actual billing system
    (e.g., Zuora, Stripe Billing, SAP, custom billing platform).
    """

    def get_account(self, account_id: str) -> dict:
        """Retrieve billing account details."""
        ...

    def get_invoice(self, invoice_id: str) -> dict:
        """Retrieve invoice details."""
        ...

    def get_current_invoice(self, account_id: str) -> dict:
        """Get the current/pending invoice for an account."""
        ...

    def post_credit(
        self,
        account_id: str,
        amount: Decimal,
        description: str,
        reference_id: str,
        invoice_id: Optional[str] = None,
    ) -> dict:
        """Post a credit to the billing system. Returns credit memo details."""
        ...

    def validate_account_for_credit(self, account_id: str) -> tuple[bool, str]:
        """Validate that an account can receive a credit."""
        ...


@dataclass
class BillingCreditResult:
    """Result of applying a trade-in credit to billing."""

    success: bool
    account_id: str
    invoice_id: Optional[str]
    credit_id: str
    trade_in_transaction_id: str
    amount_applied: Decimal
    credit_memo_id: Optional[str] = None
    application_record: Optional[CreditApplication] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses or logging."""
        return {
            "success": self.success,
            "account_id": self.account_id,
            "invoice_id": self.invoice_id,
            "credit_id": self.credit_id,
            "trade_in_transaction_id": self.trade_in_transaction_id,
            "amount_applied": str(self.amount_applied),
            "credit_memo_id": self.credit_memo_id,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
        }


class BillingCreditIntegration:
    """
    Handles integration of trade-in credits with billing systems.

    This class is responsible for:
    - Posting credits to billing accounts
    - Applying credits to specific invoices
    - Recording credit applications for audit trail
    - Supporting credit memo generation

    Example usage:
        integration = BillingCreditIntegration(billing_client)
        result = integration.apply_credit_to_billing(
            credit=trade_in_credit,
            applied_by="system",
        )
    """

    def __init__(self, billing_client: Optional[BillingSystemClient] = None):
        """
        Initialize the billing credit integration.

        Args:
            billing_client: Client for the billing system.
                           If None, uses a mock client for testing.
        """
        self._billing_client = billing_client or MockBillingSystemClient()
        self._application_records: list[CreditApplication] = []

    def apply_credit_to_billing(
        self,
        credit: TradeInCredit,
        applied_by: str,
        invoice_id: Optional[str] = None,
        amount: Optional[Decimal] = None,
        partner_id: Optional[str] = None,
    ) -> BillingCreditResult:
        """
        Apply a trade-in credit to the billing system.

        The credit can be applied to:
        - A specific invoice (if invoice_id provided)
        - The account balance (if no invoice_id, creates credit memo)

        Args:
            credit: The trade-in credit to apply
            applied_by: User or system performing the application
            invoice_id: Specific invoice to credit (optional)
            amount: Specific amount to apply (defaults to full remaining credit)
            partner_id: Indirect retail partner ID if applicable

        Returns:
            BillingCreditResult with details of the application
        """
        logger.info(
            f"Applying credit {credit.credit_id} to billing account {credit.account_id}. "
            f"Transaction: {credit.trade_in_transaction_id}"
        )

        # Validate credit status
        if credit.status in (CreditStatus.EXPIRED, CreditStatus.CANCELLED):
            return BillingCreditResult(
                success=False,
                account_id=credit.account_id,
                invoice_id=invoice_id,
                credit_id=credit.credit_id,
                trade_in_transaction_id=credit.trade_in_transaction_id,
                amount_applied=Decimal("0"),
                error_message=f"Credit has invalid status: {credit.status.value}",
            )

        # Validate remaining credit amount
        if credit.remaining_amount <= 0:
            return BillingCreditResult(
                success=False,
                account_id=credit.account_id,
                invoice_id=invoice_id,
                credit_id=credit.credit_id,
                trade_in_transaction_id=credit.trade_in_transaction_id,
                amount_applied=Decimal("0"),
                error_message="Credit has no remaining balance",
            )

        # Validate account can receive credit
        valid, reason = self._billing_client.validate_account_for_credit(credit.account_id)
        if not valid:
            return BillingCreditResult(
                success=False,
                account_id=credit.account_id,
                invoice_id=invoice_id,
                credit_id=credit.credit_id,
                trade_in_transaction_id=credit.trade_in_transaction_id,
                amount_applied=Decimal("0"),
                error_message=f"Account validation failed: {reason}",
            )

        # Determine amount to apply
        apply_amount = amount if amount is not None else credit.remaining_amount
        apply_amount = min(apply_amount, credit.remaining_amount)

        if apply_amount <= 0:
            return BillingCreditResult(
                success=False,
                account_id=credit.account_id,
                invoice_id=invoice_id,
                credit_id=credit.credit_id,
                trade_in_transaction_id=credit.trade_in_transaction_id,
                amount_applied=Decimal("0"),
                error_message="No credit amount to apply",
            )

        # Build credit reference for audit trail
        credit_reference = f"TRADEIN:{credit.trade_in_transaction_id}:{credit.credit_id}"

        # Post credit to billing system
        try:
            credit_memo = self._billing_client.post_credit(
                account_id=credit.account_id,
                amount=apply_amount,
                description=credit.description,
                reference_id=credit_reference,
                invoice_id=invoice_id,
            )
        except Exception as e:
            logger.error(f"Failed to post credit to billing system: {e}")
            return BillingCreditResult(
                success=False,
                account_id=credit.account_id,
                invoice_id=invoice_id,
                credit_id=credit.credit_id,
                trade_in_transaction_id=credit.trade_in_transaction_id,
                amount_applied=Decimal("0"),
                error_message=f"Billing system error: {str(e)}",
            )

        # Update credit record
        target_id = invoice_id or credit_memo.get("credit_memo_id", credit.account_id)
        actual_applied = credit.apply_to_billing(target_id, apply_amount)

        # Create application record for audit trail
        application = CreditApplication.record_application(
            credit=credit,
            target=ApplicationTarget.BILLING,
            target_id=target_id,
            amount=actual_applied,
            applied_by=applied_by,
            partner_id=partner_id,
        )
        self._application_records.append(application)

        logger.info(
            f"Successfully posted ${actual_applied} credit to account {credit.account_id}. "
            f"Credit memo: {credit_memo.get('credit_memo_id')}"
        )

        return BillingCreditResult(
            success=True,
            account_id=credit.account_id,
            invoice_id=invoice_id,
            credit_id=credit.credit_id,
            trade_in_transaction_id=credit.trade_in_transaction_id,
            amount_applied=actual_applied,
            credit_memo_id=credit_memo.get("credit_memo_id"),
            application_record=application,
        )

    def apply_transaction_to_billing(
        self,
        transaction: TradeInTransaction,
        account_id: str,
        applied_by: str,
        invoice_id: Optional[str] = None,
    ) -> BillingCreditResult:
        """
        Convenience method to create credit from transaction and apply to billing.

        Args:
            transaction: Approved trade-in transaction from SE-5030 workflow
            account_id: Customer's billing account ID
            applied_by: User or system performing the application
            invoice_id: Specific invoice to credit (optional)

        Returns:
            BillingCreditResult with details of the application
        """
        # Create credit from transaction
        credit = TradeInCredit.from_transaction(transaction, account_id)

        # Apply to billing
        return self.apply_credit_to_billing(
            credit=credit,
            applied_by=applied_by,
            invoice_id=invoice_id,
            partner_id=transaction.partner_id,
        )

    def get_application_records(self) -> list[CreditApplication]:
        """Get all application records for reconciliation."""
        return self._application_records.copy()

    def get_applications_by_account(self, account_id: str) -> list[CreditApplication]:
        """Get all credit applications for a specific billing account."""
        return [
            app for app in self._application_records
            if app.account_id == account_id
        ]

    def get_applications_by_invoice(self, invoice_id: str) -> list[CreditApplication]:
        """Get all credit applications for a specific invoice."""
        return [
            app for app in self._application_records
            if app.target == ApplicationTarget.BILLING and app.target_id == invoice_id
        ]

    def get_applications_by_transaction(self, transaction_id: str) -> list[CreditApplication]:
        """Get all billing credit applications for a specific trade-in transaction."""
        return [
            app for app in self._application_records
            if app.trade_in_transaction_id == transaction_id
        ]


class MockBillingSystemClient:
    """
    Mock billing system client for testing and development.

    In production, this would be replaced with actual integrations to
    billing systems (Zuora, Stripe Billing, SAP, custom platforms, etc.).
    """

    def __init__(self):
        self._accounts: dict[str, dict] = {}
        self._invoices: dict[str, dict] = {}
        self._credit_memos: dict[str, dict] = {}
        self._credit_memo_counter = 0

    def create_test_account(
        self,
        account_id: str,
        balance: Decimal = Decimal("0"),
        status: str = "active",
    ) -> dict:
        """Create a test account for testing purposes."""
        account = {
            "account_id": account_id,
            "balance": balance,
            "credit_balance": Decimal("0"),
            "status": status,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._accounts[account_id] = account
        return account

    def create_test_invoice(
        self,
        invoice_id: str,
        account_id: str,
        amount: Decimal,
        status: str = "pending",
    ) -> dict:
        """Create a test invoice for testing purposes."""
        invoice = {
            "invoice_id": invoice_id,
            "account_id": account_id,
            "amount": amount,
            "credits_applied": Decimal("0"),
            "amount_due": amount,
            "status": status,
            "due_date": date.today().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
        }
        self._invoices[invoice_id] = invoice
        return invoice

    def get_account(self, account_id: str) -> dict:
        """Retrieve billing account details."""
        if account_id not in self._accounts:
            self.create_test_account(account_id)
        return self._accounts[account_id]

    def get_invoice(self, invoice_id: str) -> dict:
        """Retrieve invoice details."""
        return self._invoices.get(invoice_id, {})

    def get_current_invoice(self, account_id: str) -> dict:
        """Get the current/pending invoice for an account."""
        for invoice in self._invoices.values():
            if invoice["account_id"] == account_id and invoice["status"] == "pending":
                return invoice
        # Create a default invoice
        invoice_id = f"INV-{account_id}-{datetime.utcnow().strftime('%Y%m')}"
        return self.create_test_invoice(invoice_id, account_id, Decimal("100.00"))

    def post_credit(
        self,
        account_id: str,
        amount: Decimal,
        description: str,
        reference_id: str,
        invoice_id: Optional[str] = None,
    ) -> dict:
        """Post a credit to the billing system."""
        self._credit_memo_counter += 1
        credit_memo_id = f"CM-{self._credit_memo_counter:06d}"

        account = self.get_account(account_id)
        account["credit_balance"] += amount
        account["last_updated"] = datetime.utcnow().isoformat()

        credit_memo = {
            "credit_memo_id": credit_memo_id,
            "account_id": account_id,
            "amount": amount,
            "description": description,
            "reference_id": reference_id,
            "invoice_id": invoice_id,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._credit_memos[credit_memo_id] = credit_memo

        # If applying to specific invoice, update it
        if invoice_id and invoice_id in self._invoices:
            invoice = self._invoices[invoice_id]
            invoice["credits_applied"] += amount
            invoice["amount_due"] -= amount
            invoice["last_updated"] = datetime.utcnow().isoformat()

        return credit_memo

    def validate_account_for_credit(self, account_id: str) -> tuple[bool, str]:
        """Validate that an account can receive a credit."""
        account = self.get_account(account_id)
        if account["status"] == "closed":
            return False, "Account is closed"
        if account["status"] == "suspended":
            return False, "Account is suspended"
        return True, "OK"
