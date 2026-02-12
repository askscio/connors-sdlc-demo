"""
Apple Port-In Funnel Dashboard Configuration

Provides dashboard configuration, metric definitions, and BigQuery templates
for visualizing the Apple port-in funnel analytics.

This module is designed to work with the company's analytics platform
(BigQuery + dashboard tools like Looker/Metabase).

Jira Reference: SE-5027 (Analytics & Reporting for Apple Port-In Funnel)
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class TimeGranularity(str, Enum):
    """Time granularity for dashboard aggregations."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class MetricType(str, Enum):
    """Types of metrics available in the dashboard."""
    COUNT = "count"
    RATE = "rate"
    CONVERSION = "conversion"
    AVERAGE = "average"
    PERCENTILE = "percentile"


@dataclass
class DashboardFilter:
    """
    Filter configuration for dashboard queries.

    Supports the required breakdown dimensions:
    - channel
    - offer
    - device (apple_sku)
    - offer_id
    """
    # Date range (required)
    start_date: date
    end_date: date

    # Required breakdown filters
    channel: Optional[str] = None
    apple_sku: Optional[str] = None
    offer_id: Optional[str] = None
    device_category: Optional[str] = None

    # Additional filters
    funnel_step: Optional[str] = None
    eligibility_result: Optional[str] = None

    def to_where_clauses(self) -> List[str]:
        """Generate SQL WHERE clauses from filters."""
        clauses = [
            f"DATE(timestamp) >= '{self.start_date.isoformat()}'",
            f"DATE(timestamp) <= '{self.end_date.isoformat()}'",
            "category = 'ApplePortInFunnel'",
        ]

        if self.channel:
            clauses.append(f"channel = '{self.channel}'")
        if self.apple_sku:
            clauses.append(f"apple_sku = '{self.apple_sku}'")
        if self.offer_id:
            clauses.append(f"offer_id = '{self.offer_id}'")
        if self.device_category:
            clauses.append(f"device_category = '{self.device_category}'")
        if self.funnel_step:
            clauses.append(f"funnel_step = '{self.funnel_step}'")
        if self.eligibility_result:
            clauses.append(f"result = '{self.eligibility_result}'")

        return clauses


@dataclass
class FunnelMetrics:
    """
    Container for funnel metrics and KPIs.

    Represents the calculated metrics for a given time period and filter set.
    """
    # Volume metrics
    landing_page_views: int = 0
    offer_views: int = 0
    eligibility_checks: int = 0
    eligibility_passes: int = 0
    eligibility_failures: int = 0
    device_selections: int = 0
    plan_selections: int = 0
    cart_adds: int = 0
    checkout_starts: int = 0
    checkout_completions: int = 0
    funnel_abandons: int = 0

    # Conversion rates (as percentages)
    landing_to_offer_rate: float = 0.0
    offer_to_eligibility_rate: float = 0.0
    eligibility_pass_rate: float = 0.0
    eligibility_to_cart_rate: float = 0.0
    cart_to_checkout_rate: float = 0.0
    checkout_completion_rate: float = 0.0
    overall_conversion_rate: float = 0.0

    # Revenue metrics
    total_order_value_cents: int = 0
    total_offer_value_cents: int = 0
    average_order_value_cents: float = 0.0

    def calculate_rates(self) -> None:
        """Calculate conversion rates from volume metrics."""
        if self.landing_page_views > 0:
            self.landing_to_offer_rate = (
                self.offer_views / self.landing_page_views * 100
            )
            self.overall_conversion_rate = (
                self.checkout_completions / self.landing_page_views * 100
            )

        if self.offer_views > 0:
            self.offer_to_eligibility_rate = (
                self.eligibility_checks / self.offer_views * 100
            )

        if self.eligibility_checks > 0:
            self.eligibility_pass_rate = (
                self.eligibility_passes / self.eligibility_checks * 100
            )

        if self.eligibility_passes > 0:
            self.eligibility_to_cart_rate = (
                self.cart_adds / self.eligibility_passes * 100
            )

        if self.cart_adds > 0:
            self.cart_to_checkout_rate = (
                self.checkout_starts / self.cart_adds * 100
            )

        if self.checkout_starts > 0:
            self.checkout_completion_rate = (
                self.checkout_completions / self.checkout_starts * 100
            )

        if self.checkout_completions > 0:
            self.average_order_value_cents = (
                self.total_order_value_cents / self.checkout_completions
            )


class ApplePortInDashboard:
    """
    Dashboard configuration and query generator for Apple port-in funnel.

    Provides methods to generate BigQuery queries for dashboard visualizations
    and calculate funnel metrics.
    """

    # BigQuery table pattern for client analytics
    TABLE_PATTERN = "scrubbed_client_analytics.scrubbed_client_analytics_*"

    # Event category for all Apple port-in events
    CATEGORY = "ApplePortInFunnel"

    def __init__(self, project_id: str = "scio-apps"):
        """
        Initialize dashboard with project configuration.

        Args:
            project_id: GCP project ID containing analytics data
        """
        self.project_id = project_id

    def get_funnel_overview_query(
        self,
        filters: DashboardFilter,
        granularity: TimeGranularity = TimeGranularity.DAILY,
    ) -> str:
        """
        Generate query for funnel overview metrics.

        Returns step-by-step funnel volumes for the given time period.
        """
        where_clauses = filters.to_where_clauses()
        where_sql = " AND ".join(where_clauses)

        date_trunc = {
            TimeGranularity.HOURLY: "TIMESTAMP_TRUNC(timestamp, HOUR)",
            TimeGranularity.DAILY: "DATE(timestamp)",
            TimeGranularity.WEEKLY: "DATE_TRUNC(DATE(timestamp), WEEK)",
            TimeGranularity.MONTHLY: "DATE_TRUNC(DATE(timestamp), MONTH)",
        }[granularity]

        return f"""
-- Apple Port-In Funnel Overview
-- Generated for SE-5027 Analytics Dashboard

WITH events AS (
  SELECT
    e.trackingparams.category AS category,
    e.trackingparams.eventname AS action,
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ',
      (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'timestamp')
    ) AS timestamp,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'funnel_step') AS funnel_step,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'channel') AS channel,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'apple_sku') AS apple_sku,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'offer_id') AS offer_id,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'result') AS result,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'session_id') AS session_id,
    (SELECT ep.value.doublevalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'order_total_cents') AS order_total_cents
  FROM `{self.project_id}.{self.TABLE_PATTERN}`,
    UNNEST(jsonPayload.events) AS e
  WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE('{filters.start_date.isoformat()}'))
    AND _TABLE_SUFFIX <= FORMAT_DATE('%Y%m%d', DATE('{filters.end_date.isoformat()}'))
    AND e.trackingparams.category = '{self.CATEGORY}'
)

SELECT
  {date_trunc} AS time_period,

  -- Funnel step volumes
  COUNTIF(funnel_step = 'landing_page') AS landing_page_views,
  COUNTIF(funnel_step = 'offer_view') AS offer_views,
  COUNTIF(funnel_step = 'eligibility_check') AS eligibility_checks,
  COUNTIF(funnel_step = 'eligibility_check' AND result = 'pass') AS eligibility_passes,
  COUNTIF(funnel_step = 'eligibility_check' AND result = 'fail') AS eligibility_failures,
  COUNTIF(funnel_step = 'device_selection') AS device_selections,
  COUNTIF(funnel_step = 'plan_selection') AS plan_selections,
  COUNTIF(funnel_step = 'cart_add') AS cart_adds,
  COUNTIF(funnel_step = 'checkout_start') AS checkout_starts,
  COUNTIF(funnel_step = 'checkout_complete') AS checkout_completions,
  COUNTIF(action = 'FunnelAbandon') AS funnel_abandons,

  -- Unique sessions
  COUNT(DISTINCT session_id) AS unique_sessions,
  COUNT(DISTINCT CASE WHEN funnel_step = 'checkout_complete' THEN session_id END) AS converting_sessions,

  -- Revenue metrics
  SUM(CASE WHEN funnel_step = 'checkout_complete' THEN order_total_cents ELSE 0 END) AS total_order_value_cents

FROM events
WHERE {where_sql}
GROUP BY time_period
ORDER BY time_period
"""

    def get_conversion_rates_query(self, filters: DashboardFilter) -> str:
        """
        Generate query for step-by-step conversion rates.

        Returns conversion rates between each funnel step.
        """
        where_clauses = filters.to_where_clauses()
        where_sql = " AND ".join(where_clauses)

        return f"""
-- Apple Port-In Funnel Conversion Rates
-- Generated for SE-5027 Analytics Dashboard

WITH events AS (
  SELECT
    e.trackingparams.category AS category,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'funnel_step') AS funnel_step,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'channel') AS channel,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'apple_sku') AS apple_sku,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'offer_id') AS offer_id,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'result') AS result,
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ',
      (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'timestamp')
    ) AS timestamp
  FROM `{self.project_id}.{self.TABLE_PATTERN}`,
    UNNEST(jsonPayload.events) AS e
  WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE('{filters.start_date.isoformat()}'))
    AND _TABLE_SUFFIX <= FORMAT_DATE('%Y%m%d', DATE('{filters.end_date.isoformat()}'))
    AND e.trackingparams.category = '{self.CATEGORY}'
),

step_counts AS (
  SELECT
    COUNTIF(funnel_step = 'landing_page') AS landing_page,
    COUNTIF(funnel_step = 'offer_view') AS offer_view,
    COUNTIF(funnel_step = 'eligibility_check') AS eligibility_check,
    COUNTIF(funnel_step = 'eligibility_check' AND result = 'pass') AS eligibility_pass,
    COUNTIF(funnel_step = 'cart_add') AS cart_add,
    COUNTIF(funnel_step = 'checkout_start') AS checkout_start,
    COUNTIF(funnel_step = 'checkout_complete') AS checkout_complete
  FROM events
  WHERE {where_sql}
)

SELECT
  -- Step volumes
  landing_page,
  offer_view,
  eligibility_check,
  eligibility_pass,
  cart_add,
  checkout_start,
  checkout_complete,

  -- Step-to-step conversion rates
  SAFE_DIVIDE(offer_view, landing_page) * 100 AS landing_to_offer_rate,
  SAFE_DIVIDE(eligibility_check, offer_view) * 100 AS offer_to_eligibility_rate,
  SAFE_DIVIDE(eligibility_pass, eligibility_check) * 100 AS eligibility_pass_rate,
  SAFE_DIVIDE(cart_add, eligibility_pass) * 100 AS eligibility_to_cart_rate,
  SAFE_DIVIDE(checkout_start, cart_add) * 100 AS cart_to_checkout_rate,
  SAFE_DIVIDE(checkout_complete, checkout_start) * 100 AS checkout_completion_rate,

  -- Overall funnel conversion
  SAFE_DIVIDE(checkout_complete, landing_page) * 100 AS overall_conversion_rate

FROM step_counts
"""

    def get_eligibility_breakdown_query(self, filters: DashboardFilter) -> str:
        """
        Generate query for eligibility check outcomes by failure reason.

        Returns breakdown of eligibility failures for fallout analysis.
        """
        where_clauses = filters.to_where_clauses()
        where_sql = " AND ".join(where_clauses)

        return f"""
-- Apple Port-In Eligibility Check Breakdown
-- Generated for SE-5027 Analytics Dashboard

WITH events AS (
  SELECT
    e.trackingparams.category AS category,
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ',
      (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'timestamp')
    ) AS timestamp,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'funnel_step') AS funnel_step,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'channel') AS channel,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'apple_sku') AS apple_sku,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'offer_id') AS offer_id,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'result') AS result,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'failure_reason') AS failure_reason,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'carrier_from') AS carrier_from
  FROM `{self.project_id}.{self.TABLE_PATTERN}`,
    UNNEST(jsonPayload.events) AS e
  WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE('{filters.start_date.isoformat()}'))
    AND _TABLE_SUFFIX <= FORMAT_DATE('%Y%m%d', DATE('{filters.end_date.isoformat()}'))
    AND e.trackingparams.category = '{self.CATEGORY}'
    AND e.trackingparams.eventname = 'EligibilityCheck'
)

SELECT
  result,
  failure_reason,
  carrier_from,
  channel,
  apple_sku,
  offer_id,
  COUNT(*) AS check_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS percentage
FROM events
WHERE {where_sql}
GROUP BY result, failure_reason, carrier_from, channel, apple_sku, offer_id
ORDER BY check_count DESC
"""

    def get_channel_breakdown_query(self, filters: DashboardFilter) -> str:
        """
        Generate query for funnel metrics broken down by channel.

        Supports the required channel breakdown filter.
        """
        base_filters = DashboardFilter(
            start_date=filters.start_date,
            end_date=filters.end_date,
            apple_sku=filters.apple_sku,
            offer_id=filters.offer_id,
        )
        where_clauses = base_filters.to_where_clauses()
        where_sql = " AND ".join(where_clauses)

        return f"""
-- Apple Port-In Funnel by Channel
-- Generated for SE-5027 Analytics Dashboard

WITH events AS (
  SELECT
    e.trackingparams.category AS category,
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ',
      (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'timestamp')
    ) AS timestamp,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'funnel_step') AS funnel_step,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'channel') AS channel,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'apple_sku') AS apple_sku,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'offer_id') AS offer_id,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'result') AS result,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'session_id') AS session_id,
    (SELECT ep.value.doublevalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'order_total_cents') AS order_total_cents
  FROM `{self.project_id}.{self.TABLE_PATTERN}`,
    UNNEST(jsonPayload.events) AS e
  WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE('{filters.start_date.isoformat()}'))
    AND _TABLE_SUFFIX <= FORMAT_DATE('%Y%m%d', DATE('{filters.end_date.isoformat()}'))
    AND e.trackingparams.category = '{self.CATEGORY}'
)

SELECT
  channel,
  COUNTIF(funnel_step = 'landing_page') AS landing_page_views,
  COUNTIF(funnel_step = 'checkout_complete') AS completions,
  SAFE_DIVIDE(
    COUNTIF(funnel_step = 'checkout_complete'),
    COUNTIF(funnel_step = 'landing_page')
  ) * 100 AS conversion_rate,
  COUNT(DISTINCT session_id) AS unique_sessions,
  SUM(CASE WHEN funnel_step = 'checkout_complete' THEN order_total_cents ELSE 0 END) AS total_revenue_cents
FROM events
WHERE {where_sql}
GROUP BY channel
ORDER BY completions DESC
"""

    def get_offer_performance_query(self, filters: DashboardFilter) -> str:
        """
        Generate query for funnel metrics broken down by offer ID.

        Supports the required offer breakdown filter.
        """
        base_filters = DashboardFilter(
            start_date=filters.start_date,
            end_date=filters.end_date,
            channel=filters.channel,
            apple_sku=filters.apple_sku,
        )
        where_clauses = base_filters.to_where_clauses()
        where_sql = " AND ".join(where_clauses)

        return f"""
-- Apple Port-In Offer Performance
-- Generated for SE-5027 Analytics Dashboard

WITH events AS (
  SELECT
    e.trackingparams.category AS category,
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ',
      (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'timestamp')
    ) AS timestamp,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'funnel_step') AS funnel_step,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'channel') AS channel,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'apple_sku') AS apple_sku,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'offer_id') AS offer_id,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'result') AS result,
    (SELECT ep.value.doublevalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'offer_value') AS offer_value,
    (SELECT ep.value.doublevalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'order_total_cents') AS order_total_cents
  FROM `{self.project_id}.{self.TABLE_PATTERN}`,
    UNNEST(jsonPayload.events) AS e
  WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE('{filters.start_date.isoformat()}'))
    AND _TABLE_SUFFIX <= FORMAT_DATE('%Y%m%d', DATE('{filters.end_date.isoformat()}'))
    AND e.trackingparams.category = '{self.CATEGORY}'
)

SELECT
  offer_id,
  COUNTIF(funnel_step = 'offer_view') AS offer_views,
  COUNTIF(funnel_step = 'checkout_complete') AS completions,
  SAFE_DIVIDE(
    COUNTIF(funnel_step = 'checkout_complete'),
    COUNTIF(funnel_step = 'offer_view')
  ) * 100 AS conversion_rate,
  COUNTIF(funnel_step = 'eligibility_check' AND result = 'pass') AS eligibility_passes,
  COUNTIF(funnel_step = 'eligibility_check' AND result = 'fail') AS eligibility_failures,
  SAFE_DIVIDE(
    COUNTIF(funnel_step = 'eligibility_check' AND result = 'pass'),
    COUNTIF(funnel_step = 'eligibility_check')
  ) * 100 AS eligibility_pass_rate,
  SUM(CASE WHEN funnel_step = 'checkout_complete' THEN order_total_cents ELSE 0 END) AS total_revenue_cents,
  SUM(CASE WHEN funnel_step = 'checkout_complete' THEN offer_value ELSE 0 END) AS total_discount_cents
FROM events
WHERE {where_sql}
  AND offer_id IS NOT NULL
GROUP BY offer_id
ORDER BY completions DESC
"""

    def get_device_breakdown_query(self, filters: DashboardFilter) -> str:
        """
        Generate query for funnel metrics broken down by Apple SKU.

        Supports the required device/SKU breakdown filter.
        """
        base_filters = DashboardFilter(
            start_date=filters.start_date,
            end_date=filters.end_date,
            channel=filters.channel,
            offer_id=filters.offer_id,
        )
        where_clauses = base_filters.to_where_clauses()
        where_sql = " AND ".join(where_clauses)

        return f"""
-- Apple Port-In Device Performance
-- Generated for SE-5027 Analytics Dashboard

WITH events AS (
  SELECT
    e.trackingparams.category AS category,
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ',
      (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'timestamp')
    ) AS timestamp,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'funnel_step') AS funnel_step,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'channel') AS channel,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'apple_sku') AS apple_sku,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'device_name') AS device_name,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'device_category') AS device_category,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'offer_id') AS offer_id,
    (SELECT ep.value.doublevalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'order_total_cents') AS order_total_cents
  FROM `{self.project_id}.{self.TABLE_PATTERN}`,
    UNNEST(jsonPayload.events) AS e
  WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE('{filters.start_date.isoformat()}'))
    AND _TABLE_SUFFIX <= FORMAT_DATE('%Y%m%d', DATE('{filters.end_date.isoformat()}'))
    AND e.trackingparams.category = '{self.CATEGORY}'
)

SELECT
  apple_sku,
  device_name,
  device_category,
  COUNTIF(funnel_step = 'device_selection') AS device_selections,
  COUNTIF(funnel_step = 'cart_add') AS cart_adds,
  COUNTIF(funnel_step = 'checkout_complete') AS completions,
  SAFE_DIVIDE(
    COUNTIF(funnel_step = 'cart_add'),
    COUNTIF(funnel_step = 'device_selection')
  ) * 100 AS selection_to_cart_rate,
  SAFE_DIVIDE(
    COUNTIF(funnel_step = 'checkout_complete'),
    COUNTIF(funnel_step = 'cart_add')
  ) * 100 AS cart_to_completion_rate,
  SUM(CASE WHEN funnel_step = 'checkout_complete' THEN order_total_cents ELSE 0 END) AS total_revenue_cents,
  AVG(CASE WHEN funnel_step = 'checkout_complete' THEN order_total_cents END) AS avg_order_value_cents
FROM events
WHERE {where_sql}
  AND apple_sku IS NOT NULL
GROUP BY apple_sku, device_name, device_category
ORDER BY completions DESC
"""

    def get_abandonment_analysis_query(self, filters: DashboardFilter) -> str:
        """
        Generate query for funnel abandonment analysis.

        Shows where users are dropping out of the funnel.
        """
        where_clauses = filters.to_where_clauses()
        where_sql = " AND ".join(where_clauses)

        return f"""
-- Apple Port-In Funnel Abandonment Analysis
-- Generated for SE-5027 Analytics Dashboard

WITH events AS (
  SELECT
    e.trackingparams.category AS category,
    e.trackingparams.eventname AS action,
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ',
      (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'timestamp')
    ) AS timestamp,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'abandon_step') AS abandon_step,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'channel') AS channel,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'apple_sku') AS apple_sku,
    (SELECT ep.value.stringvalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'offer_id') AS offer_id,
    (SELECT ep.value.doublevalue FROM UNNEST(e.eventparams) ep WHERE ep.key = 'time_in_funnel_ms') AS time_in_funnel_ms
  FROM `{self.project_id}.{self.TABLE_PATTERN}`,
    UNNEST(jsonPayload.events) AS e
  WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE('{filters.start_date.isoformat()}'))
    AND _TABLE_SUFFIX <= FORMAT_DATE('%Y%m%d', DATE('{filters.end_date.isoformat()}'))
    AND e.trackingparams.category = '{self.CATEGORY}'
    AND e.trackingparams.eventname = 'FunnelAbandon'
)

SELECT
  abandon_step,
  channel,
  COUNT(*) AS abandonment_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS abandonment_percentage,
  AVG(time_in_funnel_ms) AS avg_time_in_funnel_ms,
  PERCENTILE_CONT(time_in_funnel_ms, 0.5) OVER(PARTITION BY abandon_step) AS median_time_in_funnel_ms
FROM events
WHERE {where_sql}
GROUP BY abandon_step, channel
ORDER BY abandonment_count DESC
"""
