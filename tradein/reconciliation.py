"""
Reconciliation and Reporting Module

Provides audit trail and reconciliation capabilities for Finance to trace
every credit back to its originating trade-in transaction ID.

Part of SE-5031: Integrate Trade-In Credits into Order & Billing Flows.

Key requirement from acceptance criteria:
- Reconciliation reports can trace each credit back to a trade-in transaction ID
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from enum import Enum
import csv
import io
import json

from .models import (
    TradeInTransaction,
    TradeInCredit,
    CreditApplication,
    CreditStatus,
    ApplicationTarget,
)


class ReportFormat(Enum):
    """Supported report output formats."""

    JSON = "json"
    CSV = "csv"
    DICT = "dict"


@dataclass
class ReconciliationLineItem:
    """
    A single line item in a reconciliation report.

    Traces a credit application back to its source trade-in transaction.
    """

    # Source trade-in information
    trade_in_transaction_id: str
    quote_id: str
    device_imei: str
    device_model: str
    quoted_value: Decimal
    approved_value: Decimal

    # Credit information
    credit_id: str
    credit_amount: Decimal
    credit_remaining: Decimal
    credit_status: CreditStatus

    # Application information
    application_id: Optional[str]
    application_target: Optional[ApplicationTarget]
    target_id: Optional[str]  # Order ID or Invoice ID
    amount_applied: Decimal
    applied_at: Optional[datetime]
    applied_by: Optional[str]

    # Customer/Partner information
    customer_id: str
    account_id: str
    partner_id: Optional[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "trade_in_transaction_id": self.trade_in_transaction_id,
            "quote_id": self.quote_id,
            "device_imei": self.device_imei,
            "device_model": self.device_model,
            "quoted_value": str(self.quoted_value),
            "approved_value": str(self.approved_value),
            "credit_id": self.credit_id,
            "credit_amount": str(self.credit_amount),
            "credit_remaining": str(self.credit_remaining),
            "credit_status": self.credit_status.value,
            "application_id": self.application_id,
            "application_target": self.application_target.value if self.application_target else None,
            "target_id": self.target_id,
            "amount_applied": str(self.amount_applied),
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "applied_by": self.applied_by,
            "customer_id": self.customer_id,
            "account_id": self.account_id,
            "partner_id": self.partner_id,
        }


@dataclass
class ReconciliationSummary:
    """Summary statistics for a reconciliation report."""

    total_transactions: int
    total_credits: int
    total_applications: int
    total_quoted_value: Decimal
    total_approved_value: Decimal
    total_applied_to_orders: Decimal
    total_applied_to_billing: Decimal
    total_pending: Decimal
    total_expired: Decimal
    total_cancelled: Decimal
    report_generated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "total_transactions": self.total_transactions,
            "total_credits": self.total_credits,
            "total_applications": self.total_applications,
            "total_quoted_value": str(self.total_quoted_value),
            "total_approved_value": str(self.total_approved_value),
            "total_applied_to_orders": str(self.total_applied_to_orders),
            "total_applied_to_billing": str(self.total_applied_to_billing),
            "total_pending": str(self.total_pending),
            "total_expired": str(self.total_expired),
            "total_cancelled": str(self.total_cancelled),
            "report_generated_at": self.report_generated_at.isoformat(),
        }


@dataclass
class ReconciliationReport:
    """
    Complete reconciliation report for Finance audit.

    Maps trade-in transactions → credits → applications for full traceability.
    """

    report_id: str
    report_name: str
    generated_at: datetime
    generated_by: str
    date_range_start: Optional[date]
    date_range_end: Optional[date]
    line_items: list[ReconciliationLineItem]
    summary: ReconciliationSummary
    filters_applied: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert entire report to dictionary."""
        return {
            "report_id": self.report_id,
            "report_name": self.report_name,
            "generated_at": self.generated_at.isoformat(),
            "generated_by": self.generated_by,
            "date_range_start": self.date_range_start.isoformat() if self.date_range_start else None,
            "date_range_end": self.date_range_end.isoformat() if self.date_range_end else None,
            "filters_applied": self.filters_applied,
            "summary": self.summary.to_dict(),
            "line_items": [item.to_dict() for item in self.line_items],
        }

    def to_json(self, indent: int = 2) -> str:
        """Export report as JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_csv(self) -> str:
        """Export report line items as CSV string."""
        if not self.line_items:
            return ""

        output = io.StringIO()
        fieldnames = list(self.line_items[0].to_dict().keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for item in self.line_items:
            writer.writerow(item.to_dict())
        return output.getvalue()

    def export(self, format: ReportFormat = ReportFormat.JSON) -> str | dict:
        """
        Export report in specified format.

        Args:
            format: Output format (JSON, CSV, or DICT)

        Returns:
            Report in requested format
        """
        if format == ReportFormat.JSON:
            return self.to_json()
        elif format == ReportFormat.CSV:
            return self.to_csv()
        elif format == ReportFormat.DICT:
            return self.to_dict()
        else:
            raise ValueError(f"Unsupported format: {format}")


class ReconciliationEngine:
    """
    Engine for generating reconciliation reports.

    Aggregates data from transactions, credits, and applications to create
    comprehensive audit reports for Finance reconciliation.

    Example usage:
        engine = ReconciliationEngine()
        engine.add_transaction(transaction)
        engine.add_credit(credit)
        engine.add_applications(applications)

        report = engine.generate_report(
            report_name="Monthly Trade-In Reconciliation",
            generated_by="finance_system",
        )
    """

    def __init__(self):
        self._transactions: dict[str, TradeInTransaction] = {}
        self._credits: dict[str, TradeInCredit] = {}
        self._applications: list[CreditApplication] = []

    def add_transaction(self, transaction: TradeInTransaction) -> None:
        """Add a trade-in transaction to the reconciliation data."""
        self._transactions[transaction.transaction_id] = transaction

    def add_transactions(self, transactions: list[TradeInTransaction]) -> None:
        """Add multiple trade-in transactions."""
        for transaction in transactions:
            self.add_transaction(transaction)

    def add_credit(self, credit: TradeInCredit) -> None:
        """Add a trade-in credit to the reconciliation data."""
        self._credits[credit.credit_id] = credit

    def add_credits(self, credits: list[TradeInCredit]) -> None:
        """Add multiple trade-in credits."""
        for credit in credits:
            self.add_credit(credit)

    def add_application(self, application: CreditApplication) -> None:
        """Add a credit application record."""
        self._applications.append(application)

    def add_applications(self, applications: list[CreditApplication]) -> None:
        """Add multiple credit application records."""
        self._applications.extend(applications)

    def _build_line_items(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        partner_id: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> list[ReconciliationLineItem]:
        """Build reconciliation line items from available data."""
        line_items = []

        # Build index of applications by credit_id
        applications_by_credit: dict[str, list[CreditApplication]] = {}
        for app in self._applications:
            if app.credit_id not in applications_by_credit:
                applications_by_credit[app.credit_id] = []
            applications_by_credit[app.credit_id].append(app)

        # For each credit, create line items
        for credit in self._credits.values():
            # Get source transaction
            transaction = self._transactions.get(credit.trade_in_transaction_id)

            # Apply filters
            if partner_id and transaction and transaction.partner_id != partner_id:
                continue
            if customer_id and credit.customer_id != customer_id:
                continue

            # Get applications for this credit
            credit_applications = applications_by_credit.get(credit.credit_id, [])

            if credit_applications:
                # Create a line item for each application
                for app in credit_applications:
                    # Filter by date if specified
                    if start_date and app.applied_at and app.applied_at.date() < start_date:
                        continue
                    if end_date and app.applied_at and app.applied_at.date() > end_date:
                        continue

                    line_items.append(
                        ReconciliationLineItem(
                            trade_in_transaction_id=credit.trade_in_transaction_id,
                            quote_id=transaction.quote_id if transaction else "UNKNOWN",
                            device_imei=transaction.device_imei if transaction else "UNKNOWN",
                            device_model=transaction.device_model if transaction else "UNKNOWN",
                            quoted_value=transaction.quoted_value if transaction else Decimal("0"),
                            approved_value=transaction.approved_value if transaction else credit.amount,
                            credit_id=credit.credit_id,
                            credit_amount=credit.amount,
                            credit_remaining=credit.remaining_amount,
                            credit_status=credit.status,
                            application_id=app.application_id,
                            application_target=app.target,
                            target_id=app.target_id,
                            amount_applied=app.amount_applied,
                            applied_at=app.applied_at,
                            applied_by=app.applied_by,
                            customer_id=credit.customer_id,
                            account_id=credit.account_id,
                            partner_id=app.partner_id,
                        )
                    )
            else:
                # Credit with no applications yet - still include for visibility
                if credit.status == CreditStatus.PENDING:
                    # Filter by credit creation date if applicable
                    if start_date and credit.created_at.date() < start_date:
                        continue
                    if end_date and credit.created_at.date() > end_date:
                        continue

                    line_items.append(
                        ReconciliationLineItem(
                            trade_in_transaction_id=credit.trade_in_transaction_id,
                            quote_id=transaction.quote_id if transaction else "UNKNOWN",
                            device_imei=transaction.device_imei if transaction else "UNKNOWN",
                            device_model=transaction.device_model if transaction else "UNKNOWN",
                            quoted_value=transaction.quoted_value if transaction else Decimal("0"),
                            approved_value=transaction.approved_value if transaction else credit.amount,
                            credit_id=credit.credit_id,
                            credit_amount=credit.amount,
                            credit_remaining=credit.remaining_amount,
                            credit_status=credit.status,
                            application_id=None,
                            application_target=None,
                            target_id=None,
                            amount_applied=Decimal("0"),
                            applied_at=None,
                            applied_by=None,
                            customer_id=credit.customer_id,
                            account_id=credit.account_id,
                            partner_id=transaction.partner_id if transaction else None,
                        )
                    )

        return line_items

    def _calculate_summary(self, line_items: list[ReconciliationLineItem]) -> ReconciliationSummary:
        """Calculate summary statistics from line items."""
        transaction_ids = set()
        credit_ids = set()
        application_ids = set()
        total_quoted = Decimal("0")
        total_approved = Decimal("0")
        total_order = Decimal("0")
        total_billing = Decimal("0")
        total_pending = Decimal("0")
        total_expired = Decimal("0")
        total_cancelled = Decimal("0")

        # Track seen credits for accurate pending/expired/cancelled counts
        seen_credits: dict[str, ReconciliationLineItem] = {}

        for item in line_items:
            transaction_ids.add(item.trade_in_transaction_id)
            credit_ids.add(item.credit_id)

            # Store credit info (last seen will be used for status)
            seen_credits[item.credit_id] = item

            if item.application_id:
                application_ids.add(item.application_id)
                if item.application_target == ApplicationTarget.ORDER:
                    total_order += item.amount_applied
                elif item.application_target == ApplicationTarget.BILLING:
                    total_billing += item.amount_applied

        # Calculate totals from unique credits
        for item in seen_credits.values():
            total_quoted += item.quoted_value
            total_approved += item.approved_value

            if item.credit_status == CreditStatus.PENDING:
                total_pending += item.credit_remaining
            elif item.credit_status == CreditStatus.EXPIRED:
                total_expired += item.credit_remaining
            elif item.credit_status == CreditStatus.CANCELLED:
                total_cancelled += item.credit_amount

        return ReconciliationSummary(
            total_transactions=len(transaction_ids),
            total_credits=len(credit_ids),
            total_applications=len(application_ids),
            total_quoted_value=total_quoted,
            total_approved_value=total_approved,
            total_applied_to_orders=total_order,
            total_applied_to_billing=total_billing,
            total_pending=total_pending,
            total_expired=total_expired,
            total_cancelled=total_cancelled,
        )

    def generate_report(
        self,
        report_name: str,
        generated_by: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        partner_id: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> ReconciliationReport:
        """
        Generate a reconciliation report.

        Args:
            report_name: Name/title for the report
            generated_by: User or system generating the report
            start_date: Filter to applications on or after this date
            end_date: Filter to applications on or before this date
            partner_id: Filter to specific indirect retail partner
            customer_id: Filter to specific customer

        Returns:
            Complete ReconciliationReport for Finance audit
        """
        import uuid

        # Build line items with filters
        line_items = self._build_line_items(
            start_date=start_date,
            end_date=end_date,
            partner_id=partner_id,
            customer_id=customer_id,
        )

        # Calculate summary
        summary = self._calculate_summary(line_items)

        # Build filters applied dict
        filters = {}
        if start_date:
            filters["start_date"] = start_date.isoformat()
        if end_date:
            filters["end_date"] = end_date.isoformat()
        if partner_id:
            filters["partner_id"] = partner_id
        if customer_id:
            filters["customer_id"] = customer_id

        return ReconciliationReport(
            report_id=str(uuid.uuid4()),
            report_name=report_name,
            generated_at=datetime.utcnow(),
            generated_by=generated_by,
            date_range_start=start_date,
            date_range_end=end_date,
            line_items=line_items,
            summary=summary,
            filters_applied=filters,
        )

    def get_transaction_audit_trail(self, transaction_id: str) -> dict:
        """
        Get complete audit trail for a single trade-in transaction.

        This is the primary method for Finance to trace a specific
        trade-in transaction to all its credits and applications.

        Args:
            transaction_id: The trade-in transaction ID to trace

        Returns:
            Complete audit trail as a dictionary
        """
        transaction = self._transactions.get(transaction_id)
        if not transaction:
            return {"error": f"Transaction {transaction_id} not found"}

        # Find all credits from this transaction
        credits = [
            c for c in self._credits.values()
            if c.trade_in_transaction_id == transaction_id
        ]

        # Find all applications for these credits
        credit_ids = {c.credit_id for c in credits}
        applications = [
            app for app in self._applications
            if app.credit_id in credit_ids
        ]

        return {
            "transaction_id": transaction_id,
            "transaction": {
                "quote_id": transaction.quote_id,
                "customer_id": transaction.customer_id,
                "partner_id": transaction.partner_id,
                "device_imei": transaction.device_imei,
                "device_model": transaction.device_model,
                "device_condition": transaction.device_condition.value,
                "quoted_value": str(transaction.quoted_value),
                "approved_value": str(transaction.approved_value),
                "quote_timestamp": transaction.quote_timestamp.isoformat(),
                "approval_timestamp": transaction.approval_timestamp.isoformat() if transaction.approval_timestamp else None,
                "expiration_date": transaction.expiration_date.isoformat() if transaction.expiration_date else None,
            },
            "credits": [
                {
                    "credit_id": c.credit_id,
                    "amount": str(c.amount),
                    "remaining_amount": str(c.remaining_amount),
                    "status": c.status.value,
                    "created_at": c.created_at.isoformat(),
                    "account_id": c.account_id,
                    "applied_to_order_id": c.applied_to_order_id,
                    "applied_to_invoice_id": c.applied_to_invoice_id,
                    "audit_log": c.audit_log,
                }
                for c in credits
            ],
            "applications": [
                {
                    "application_id": app.application_id,
                    "credit_id": app.credit_id,
                    "target": app.target.value,
                    "target_id": app.target_id,
                    "amount_applied": str(app.amount_applied),
                    "applied_at": app.applied_at.isoformat(),
                    "applied_by": app.applied_by,
                }
                for app in applications
            ],
            "summary": {
                "total_credits": len(credits),
                "total_applications": len(applications),
                "total_credited": str(sum(c.amount for c in credits)),
                "total_applied": str(sum(app.amount_applied for app in applications)),
                "total_remaining": str(sum(c.remaining_amount for c in credits)),
            },
        }

    def clear(self) -> None:
        """Clear all data from the engine."""
        self._transactions.clear()
        self._credits.clear()
        self._applications.clear()
