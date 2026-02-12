"""
Unit Tests for Apple Port-In Dashboard Configuration

Tests the dashboard query generation and metric calculation
for the Apple port-in funnel analytics.
"""

import unittest
from datetime import date

from analytics.dashboards.apple_portin_dashboard import (
    ApplePortInDashboard,
    DashboardFilter,
    FunnelMetrics,
    TimeGranularity,
)


class TestDashboardFilter(unittest.TestCase):
    """Tests for DashboardFilter class."""

    def test_basic_filter_creation(self):
        """Should create filter with required date range."""
        filter = DashboardFilter(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

        self.assertEqual(filter.start_date, date(2024, 1, 1))
        self.assertEqual(filter.end_date, date(2024, 1, 31))

    def test_to_where_clauses_basic(self):
        """Should generate basic WHERE clauses."""
        filter = DashboardFilter(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

        clauses = filter.to_where_clauses()

        self.assertIn("DATE(timestamp) >= '2024-01-01'", clauses)
        self.assertIn("DATE(timestamp) <= '2024-01-31'", clauses)
        self.assertIn("category = 'ApplePortInFunnel'", clauses)

    def test_to_where_clauses_with_channel(self):
        """Should include channel filter when specified."""
        filter = DashboardFilter(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            channel="web",
        )

        clauses = filter.to_where_clauses()

        self.assertIn("channel = 'web'", clauses)

    def test_to_where_clauses_with_apple_sku(self):
        """Should include apple_sku filter when specified."""
        filter = DashboardFilter(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            apple_sku="IPHONE15PRO256",
        )

        clauses = filter.to_where_clauses()

        self.assertIn("apple_sku = 'IPHONE15PRO256'", clauses)

    def test_to_where_clauses_with_offer_id(self):
        """Should include offer_id filter when specified."""
        filter = DashboardFilter(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            offer_id="PROMO_2024Q1",
        )

        clauses = filter.to_where_clauses()

        self.assertIn("offer_id = 'PROMO_2024Q1'", clauses)

    def test_to_where_clauses_all_filters(self):
        """Should include all filters when specified."""
        filter = DashboardFilter(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            channel="mobile_web",
            apple_sku="IPHONE15256",
            offer_id="PROMO_2024",
            device_category="iPhone",
            funnel_step="checkout_start",
            eligibility_result="pass",
        )

        clauses = filter.to_where_clauses()

        self.assertEqual(len(clauses), 9)  # 3 base + 6 optional


class TestFunnelMetrics(unittest.TestCase):
    """Tests for FunnelMetrics class."""

    def test_default_values(self):
        """Should initialize with zero values."""
        metrics = FunnelMetrics()

        self.assertEqual(metrics.landing_page_views, 0)
        self.assertEqual(metrics.checkout_completions, 0)
        self.assertEqual(metrics.overall_conversion_rate, 0.0)

    def test_calculate_rates_basic(self):
        """Should calculate conversion rates from volumes."""
        metrics = FunnelMetrics(
            landing_page_views=1000,
            offer_views=800,
            eligibility_checks=600,
            eligibility_passes=540,
            cart_adds=400,
            checkout_starts=350,
            checkout_completions=300,
        )

        metrics.calculate_rates()

        self.assertEqual(metrics.landing_to_offer_rate, 80.0)
        self.assertEqual(metrics.offer_to_eligibility_rate, 75.0)
        self.assertEqual(metrics.eligibility_pass_rate, 90.0)
        self.assertAlmostEqual(metrics.eligibility_to_cart_rate, 74.07, places=1)
        self.assertEqual(metrics.cart_to_checkout_rate, 87.5)
        self.assertAlmostEqual(metrics.checkout_completion_rate, 85.71, places=1)
        self.assertEqual(metrics.overall_conversion_rate, 30.0)

    def test_calculate_rates_handles_zero_division(self):
        """Should handle zero values gracefully."""
        metrics = FunnelMetrics(
            landing_page_views=0,
            checkout_completions=0,
        )

        # Should not raise
        metrics.calculate_rates()

        self.assertEqual(metrics.overall_conversion_rate, 0.0)

    def test_average_order_value(self):
        """Should calculate average order value."""
        metrics = FunnelMetrics(
            checkout_completions=10,
            total_order_value_cents=999000,  # $9,990
        )

        metrics.calculate_rates()

        self.assertEqual(metrics.average_order_value_cents, 99900.0)  # $999


class TestApplePortInDashboard(unittest.TestCase):
    """Tests for ApplePortInDashboard query generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.dashboard = ApplePortInDashboard(project_id="test-project")
        self.base_filter = DashboardFilter(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

    def test_dashboard_initialization(self):
        """Should initialize with project ID."""
        self.assertEqual(self.dashboard.project_id, "test-project")
        self.assertEqual(self.dashboard.CATEGORY, "ApplePortInFunnel")

    def test_funnel_overview_query_structure(self):
        """Should generate valid funnel overview query."""
        query = self.dashboard.get_funnel_overview_query(self.base_filter)

        # Check query contains expected elements
        self.assertIn("ApplePortInFunnel", query)
        self.assertIn("landing_page_views", query)
        self.assertIn("checkout_completions", query)
        self.assertIn("test-project", query)
        self.assertIn("2024-01-01", query)
        self.assertIn("2024-01-31", query)

    def test_funnel_overview_query_granularity(self):
        """Should support different time granularities."""
        hourly_query = self.dashboard.get_funnel_overview_query(
            self.base_filter,
            granularity=TimeGranularity.HOURLY,
        )
        monthly_query = self.dashboard.get_funnel_overview_query(
            self.base_filter,
            granularity=TimeGranularity.MONTHLY,
        )

        self.assertIn("TIMESTAMP_TRUNC", hourly_query)
        self.assertIn("DATE_TRUNC", monthly_query)

    def test_conversion_rates_query_structure(self):
        """Should generate valid conversion rates query."""
        query = self.dashboard.get_conversion_rates_query(self.base_filter)

        self.assertIn("landing_to_offer_rate", query)
        self.assertIn("eligibility_pass_rate", query)
        self.assertIn("overall_conversion_rate", query)
        self.assertIn("SAFE_DIVIDE", query)

    def test_eligibility_breakdown_query_structure(self):
        """Should generate valid eligibility breakdown query."""
        query = self.dashboard.get_eligibility_breakdown_query(self.base_filter)

        self.assertIn("failure_reason", query)
        self.assertIn("carrier_from", query)
        self.assertIn("EligibilityCheck", query)

    def test_channel_breakdown_query_structure(self):
        """Should generate valid channel breakdown query."""
        query = self.dashboard.get_channel_breakdown_query(self.base_filter)

        self.assertIn("GROUP BY channel", query)
        self.assertIn("conversion_rate", query)
        self.assertIn("unique_sessions", query)

    def test_offer_performance_query_structure(self):
        """Should generate valid offer performance query."""
        query = self.dashboard.get_offer_performance_query(self.base_filter)

        self.assertIn("GROUP BY offer_id", query)
        self.assertIn("eligibility_pass_rate", query)
        self.assertIn("total_discount_cents", query)

    def test_device_breakdown_query_structure(self):
        """Should generate valid device breakdown query."""
        query = self.dashboard.get_device_breakdown_query(self.base_filter)

        self.assertIn("apple_sku", query)
        self.assertIn("device_category", query)
        self.assertIn("avg_order_value_cents", query)

    def test_abandonment_analysis_query_structure(self):
        """Should generate valid abandonment analysis query."""
        query = self.dashboard.get_abandonment_analysis_query(self.base_filter)

        self.assertIn("abandon_step", query)
        self.assertIn("FunnelAbandon", query)
        self.assertIn("time_in_funnel_ms", query)

    def test_queries_with_filters(self):
        """Should include filters in queries."""
        filtered = DashboardFilter(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            channel="web",
            apple_sku="IPHONE15PRO256",
            offer_id="PROMO_2024",
        )

        query = self.dashboard.get_funnel_overview_query(filtered)

        self.assertIn("channel = 'web'", query)
        self.assertIn("apple_sku = 'IPHONE15PRO256'", query)
        self.assertIn("offer_id = 'PROMO_2024'", query)


if __name__ == "__main__":
    unittest.main()
