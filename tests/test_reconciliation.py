"""
Tests for reconciliation and reporting module.

Tests cover:
- Reconciliation report generation
- Tracing credits back to trade-in transaction IDs
- Report export formats (JSON, CSV)
- Summary statistics calculation
- Transaction audit trail
"""

import pytest
import json
from datetime import datetime, date, timedelta
from decimal import Decimal

from tradein.models import (
    TradeInTransaction,
    TradeInCredit,
    CreditApplication,
    CreditStatus,
    ApplicationTarget,
    DeviceCondition,
)
from tradein.reconciliation import (
    ReconciliationEngine,
    ReconciliationReport,
    ReconciliationLineItem,
    ReconciliationSummary,
    ReportFormat,
)


class TestReconciliationEngine:
    """Tests for ReconciliationEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a ReconciliationEngine instance."""
        return ReconciliationEngine()

    @pytest.fixture
    def sample_transaction(self):
        """Create a sample trade-in transaction."""
        return TradeInTransaction(
            transaction_id="TXN-REC-001",
            quote_id="QUOTE-REC-001",
            customer_id="CUST-REC-001",
            partner_id="PARTNER-REC-001",
            device_imei="111222333444555",
            device_model="iPhone 15 Pro",
            device_condition=DeviceCondition.EXCELLENT,
            quoted_value=Decimal("800.00"),
            approved_value=Decimal("750.00"),
            quote_timestamp=datetime.utcnow(),
            approval_timestamp=datetime.utcnow(),
            expiration_date=date.today() + timedelta(days=30),
        )

    @pytest.fixture
    def sample_credit(self, sample_transaction):
        """Create a sample credit from the transaction."""
        return TradeInCredit.from_transaction(sample_transaction, "ACCT-REC-001")

    @pytest.fixture
    def sample_application(self, sample_credit):
        """Create a sample application record."""
        return CreditApplication.record_application(
            credit=sample_credit,
            target=ApplicationTarget.ORDER,
            target_id="ORD-REC-001",
            amount=Decimal("750.00"),
            applied_by="test_user",
            partner_id="PARTNER-REC-001",
        )

    def test_add_transaction(self, engine, sample_transaction):
        """Test adding a transaction to the engine."""
        engine.add_transaction(sample_transaction)
        assert len(engine._transactions) == 1

    def test_add_credit(self, engine, sample_credit):
        """Test adding a credit to the engine."""
        engine.add_credit(sample_credit)
        assert len(engine._credits) == 1

    def test_add_application(self, engine, sample_application):
        """Test adding an application to the engine."""
        engine.add_application(sample_application)
        assert len(engine._applications) == 1

    def test_generate_basic_report(self, engine, sample_transaction, sample_credit, sample_application):
        """Test generating a basic reconciliation report."""
        engine.add_transaction(sample_transaction)
        engine.add_credit(sample_credit)
        engine.add_application(sample_application)

        report = engine.generate_report(
            report_name="Test Report",
            generated_by="test_user",
        )

        assert report.report_name == "Test Report"
        assert report.generated_by == "test_user"
        assert len(report.line_items) == 1
        assert report.summary.total_transactions == 1
        assert report.summary.total_credits == 1
        assert report.summary.total_applications == 1

    def test_line_item_traces_to_transaction(self, engine, sample_transaction, sample_credit, sample_application):
        """Test that line items trace back to the source transaction."""
        engine.add_transaction(sample_transaction)
        engine.add_credit(sample_credit)
        engine.add_application(sample_application)

        report = engine.generate_report(
            report_name="Traceability Test",
            generated_by="test_user",
        )

        line_item = report.line_items[0]
        assert line_item.trade_in_transaction_id == "TXN-REC-001"
        assert line_item.quote_id == "QUOTE-REC-001"
        assert line_item.device_imei == "111222333444555"
        assert line_item.device_model == "iPhone 15 Pro"
        assert line_item.quoted_value == Decimal("800.00")
        assert line_item.approved_value == Decimal("750.00")
        assert line_item.credit_id == sample_credit.credit_id
        assert line_item.application_id == sample_application.application_id
        assert line_item.target_id == "ORD-REC-001"
        assert line_item.amount_applied == Decimal("750.00")
        assert line_item.partner_id == "PARTNER-REC-001"

    def test_summary_calculations(self, engine):
        """Test summary statistics are calculated correctly."""
        # Create multiple transactions and credits
        for i in range(3):
            txn = TradeInTransaction(
                transaction_id=f"TXN-SUM-{i:03d}",
                quote_id=f"QUOTE-SUM-{i:03d}",
                customer_id=f"CUST-SUM-{i:03d}",
                partner_id="PARTNER-SUM-001",
                device_imei=f"11122233344{i:04d}",
                device_model="Test Device",
                device_condition=DeviceCondition.GOOD,
                quoted_value=Decimal("500.00"),
                approved_value=Decimal("450.00"),
                quote_timestamp=datetime.utcnow(),
                approval_timestamp=datetime.utcnow(),
            )
            engine.add_transaction(txn)

            credit = TradeInCredit.from_transaction(txn, f"ACCT-SUM-{i:03d}")
            engine.add_credit(credit)

            # Apply half to orders, half to billing
            if i < 2:
                app = CreditApplication.record_application(
                    credit=credit,
                    target=ApplicationTarget.ORDER if i == 0 else ApplicationTarget.BILLING,
                    target_id=f"TARGET-{i:03d}",
                    amount=Decimal("450.00"),
                    applied_by="test_user",
                )
                credit.remaining_amount = Decimal("0")
                engine.add_application(app)

        report = engine.generate_report(
            report_name="Summary Test",
            generated_by="test_user",
        )

        assert report.summary.total_transactions == 3
        assert report.summary.total_credits == 3
        assert report.summary.total_applications == 2
        assert report.summary.total_quoted_value == Decimal("1500.00")  # 3 x 500
        assert report.summary.total_approved_value == Decimal("1350.00")  # 3 x 450
        assert report.summary.total_applied_to_orders == Decimal("450.00")
        assert report.summary.total_applied_to_billing == Decimal("450.00")

    def test_filter_by_partner(self, engine):
        """Test filtering report by partner ID."""
        # Create transactions for different partners
        for partner_id in ["PARTNER-A", "PARTNER-B"]:
            txn = TradeInTransaction(
                transaction_id=f"TXN-{partner_id}",
                quote_id=f"QUOTE-{partner_id}",
                customer_id=f"CUST-{partner_id}",
                partner_id=partner_id,
                device_imei=f"123456789{partner_id[-1]}",
                device_model="Test Device",
                device_condition=DeviceCondition.GOOD,
                quoted_value=Decimal("500.00"),
                approved_value=Decimal("450.00"),
                quote_timestamp=datetime.utcnow(),
                approval_timestamp=datetime.utcnow(),
            )
            engine.add_transaction(txn)

            credit = TradeInCredit.from_transaction(txn, f"ACCT-{partner_id}")
            engine.add_credit(credit)

            app = CreditApplication.record_application(
                credit=credit,
                target=ApplicationTarget.ORDER,
                target_id=f"ORD-{partner_id}",
                amount=Decimal("450.00"),
                applied_by="test_user",
                partner_id=partner_id,
            )
            engine.add_application(app)

        # Filter by partner A
        report = engine.generate_report(
            report_name="Partner Filter Test",
            generated_by="test_user",
            partner_id="PARTNER-A",
        )

        assert len(report.line_items) == 1
        assert report.line_items[0].partner_id == "PARTNER-A"
        assert report.filters_applied["partner_id"] == "PARTNER-A"

    def test_filter_by_customer(self, engine, sample_transaction, sample_credit, sample_application):
        """Test filtering report by customer ID."""
        engine.add_transaction(sample_transaction)
        engine.add_credit(sample_credit)
        engine.add_application(sample_application)

        # Filter by correct customer
        report = engine.generate_report(
            report_name="Customer Filter Test",
            generated_by="test_user",
            customer_id="CUST-REC-001",
        )
        assert len(report.line_items) == 1

        # Filter by different customer
        report = engine.generate_report(
            report_name="Customer Filter Test",
            generated_by="test_user",
            customer_id="CUST-OTHER",
        )
        assert len(report.line_items) == 0

    def test_get_transaction_audit_trail(self, engine, sample_transaction, sample_credit, sample_application):
        """Test getting complete audit trail for a transaction."""
        engine.add_transaction(sample_transaction)
        engine.add_credit(sample_credit)
        engine.add_application(sample_application)

        audit_trail = engine.get_transaction_audit_trail("TXN-REC-001")

        assert audit_trail["transaction_id"] == "TXN-REC-001"
        assert audit_trail["transaction"]["quote_id"] == "QUOTE-REC-001"
        assert audit_trail["transaction"]["device_model"] == "iPhone 15 Pro"
        assert len(audit_trail["credits"]) == 1
        assert len(audit_trail["applications"]) == 1
        assert audit_trail["summary"]["total_credited"] == "750.00"
        assert audit_trail["summary"]["total_applied"] == "750.00"

    def test_get_transaction_audit_trail_not_found(self, engine):
        """Test audit trail for non-existent transaction."""
        result = engine.get_transaction_audit_trail("TXN-NONEXISTENT")
        assert "error" in result

    def test_pending_credits_included_in_report(self, engine, sample_transaction):
        """Test that pending credits (no applications) are included in report."""
        engine.add_transaction(sample_transaction)

        # Create credit but don't apply it
        credit = TradeInCredit.from_transaction(sample_transaction, "ACCT-PENDING")
        engine.add_credit(credit)

        report = engine.generate_report(
            report_name="Pending Credits Test",
            generated_by="test_user",
        )

        assert len(report.line_items) == 1
        assert report.line_items[0].credit_status == CreditStatus.PENDING
        assert report.line_items[0].application_id is None
        assert report.line_items[0].amount_applied == Decimal("0")

    def test_clear_engine(self, engine, sample_transaction, sample_credit, sample_application):
        """Test clearing all data from the engine."""
        engine.add_transaction(sample_transaction)
        engine.add_credit(sample_credit)
        engine.add_application(sample_application)

        engine.clear()

        assert len(engine._transactions) == 0
        assert len(engine._credits) == 0
        assert len(engine._applications) == 0


class TestReconciliationReport:
    """Tests for ReconciliationReport export functionality."""

    @pytest.fixture
    def sample_report(self):
        """Create a sample report for testing exports."""
        line_item = ReconciliationLineItem(
            trade_in_transaction_id="TXN-EXPORT-001",
            quote_id="QUOTE-EXPORT-001",
            device_imei="999888777666555",
            device_model="Test Phone",
            quoted_value=Decimal("500.00"),
            approved_value=Decimal("450.00"),
            credit_id="CREDIT-EXPORT-001",
            credit_amount=Decimal("450.00"),
            credit_remaining=Decimal("0"),
            credit_status=CreditStatus.FULLY_APPLIED,
            application_id="APP-EXPORT-001",
            application_target=ApplicationTarget.ORDER,
            target_id="ORD-EXPORT-001",
            amount_applied=Decimal("450.00"),
            applied_at=datetime.utcnow(),
            applied_by="test_user",
            customer_id="CUST-EXPORT-001",
            account_id="ACCT-EXPORT-001",
            partner_id="PARTNER-EXPORT-001",
        )

        summary = ReconciliationSummary(
            total_transactions=1,
            total_credits=1,
            total_applications=1,
            total_quoted_value=Decimal("500.00"),
            total_approved_value=Decimal("450.00"),
            total_applied_to_orders=Decimal("450.00"),
            total_applied_to_billing=Decimal("0"),
            total_pending=Decimal("0"),
            total_expired=Decimal("0"),
            total_cancelled=Decimal("0"),
        )

        return ReconciliationReport(
            report_id="RPT-EXPORT-001",
            report_name="Export Test Report",
            generated_at=datetime.utcnow(),
            generated_by="test_user",
            date_range_start=date.today() - timedelta(days=30),
            date_range_end=date.today(),
            line_items=[line_item],
            summary=summary,
        )

    def test_export_to_json(self, sample_report):
        """Test exporting report to JSON format."""
        json_output = sample_report.export(ReportFormat.JSON)

        # Should be valid JSON
        data = json.loads(json_output)
        assert data["report_id"] == "RPT-EXPORT-001"
        assert data["report_name"] == "Export Test Report"
        assert len(data["line_items"]) == 1
        assert data["line_items"][0]["trade_in_transaction_id"] == "TXN-EXPORT-001"
        assert data["summary"]["total_transactions"] == 1

    def test_export_to_csv(self, sample_report):
        """Test exporting report to CSV format."""
        csv_output = sample_report.export(ReportFormat.CSV)

        # Should contain header and data row
        lines = csv_output.strip().split("\n")
        assert len(lines) == 2  # Header + 1 data row

        # Header should contain key fields
        header = lines[0]
        assert "trade_in_transaction_id" in header
        assert "credit_id" in header
        assert "amount_applied" in header

        # Data row should contain values
        data_row = lines[1]
        assert "TXN-EXPORT-001" in data_row

    def test_export_to_dict(self, sample_report):
        """Test exporting report to dict format."""
        dict_output = sample_report.export(ReportFormat.DICT)

        assert isinstance(dict_output, dict)
        assert dict_output["report_id"] == "RPT-EXPORT-001"
        assert len(dict_output["line_items"]) == 1

    def test_to_dict(self, sample_report):
        """Test to_dict method."""
        result = sample_report.to_dict()

        assert result["report_id"] == "RPT-EXPORT-001"
        assert result["generated_by"] == "test_user"
        assert "summary" in result
        assert "line_items" in result

    def test_line_item_to_dict(self):
        """Test ReconciliationLineItem to_dict method."""
        line_item = ReconciliationLineItem(
            trade_in_transaction_id="TXN-001",
            quote_id="QUOTE-001",
            device_imei="123456789",
            device_model="Test",
            quoted_value=Decimal("100.00"),
            approved_value=Decimal("90.00"),
            credit_id="CREDIT-001",
            credit_amount=Decimal("90.00"),
            credit_remaining=Decimal("0"),
            credit_status=CreditStatus.FULLY_APPLIED,
            application_id="APP-001",
            application_target=ApplicationTarget.ORDER,
            target_id="ORD-001",
            amount_applied=Decimal("90.00"),
            applied_at=datetime.utcnow(),
            applied_by="user",
            customer_id="CUST-001",
            account_id="ACCT-001",
            partner_id=None,
        )

        result = line_item.to_dict()
        assert result["trade_in_transaction_id"] == "TXN-001"
        assert result["credit_status"] == "fully_applied"
        assert result["application_target"] == "order"
        assert result["partner_id"] is None

    def test_summary_to_dict(self):
        """Test ReconciliationSummary to_dict method."""
        summary = ReconciliationSummary(
            total_transactions=5,
            total_credits=5,
            total_applications=4,
            total_quoted_value=Decimal("2500.00"),
            total_approved_value=Decimal("2250.00"),
            total_applied_to_orders=Decimal("1500.00"),
            total_applied_to_billing=Decimal("500.00"),
            total_pending=Decimal("250.00"),
            total_expired=Decimal("0"),
            total_cancelled=Decimal("0"),
        )

        result = summary.to_dict()
        assert result["total_transactions"] == 5
        assert result["total_quoted_value"] == "2500.00"
        assert result["total_applied_to_orders"] == "1500.00"
        assert "report_generated_at" in result
