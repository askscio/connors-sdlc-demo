"""
Tests for Monitoring and Alerting (SE-5034).

Per acceptance criteria:
- Monitoring/alerts for missing or delayed events in production
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


from international_usage.monitoring import (
    Alert,
    AlertSeverity,
    AlertType,
    MetricsCollector,
    AlertManager,
    HealthCheck,
    MonitoringConfig,
    HealthStatus,
)


class TestMetricsCollector:
    """Tests for the MetricsCollector."""

    def test_increment_counter(self):
        """Test incrementing counters."""
        collector = MetricsCollector()

        collector.increment("records_processed")
        collector.increment("records_processed")
        collector.increment("records_processed", value=3)

        assert collector.get_counter("records_processed") == 5

    def test_gauge_metric(self):
        """Test gauge metrics."""
        collector = MetricsCollector()

        collector.gauge("active_customers", 100)
        assert collector.get_gauge("active_customers") == 100

        collector.gauge("active_customers", 150)
        assert collector.get_gauge("active_customers") == 150

    def test_histogram_percentile(self):
        """Test histogram percentile calculation."""
        collector = MetricsCollector()

        # Add 100 latency values from 1 to 100
        for i in range(1, 101):
            collector.histogram("latency_ms", float(i))

        p50 = collector.get_histogram_percentile("latency_ms", 50)
        assert p50 is not None
        assert 45 <= p50 <= 55  # Should be around 50

        p99 = collector.get_histogram_percentile("latency_ms", 99)
        assert p99 is not None
        assert p99 >= 95

    def test_metrics_with_tags(self):
        """Test metrics with tags."""
        collector = MetricsCollector()

        collector.increment("events", tags={"type": "50_percent"})
        collector.increment("events", tags={"type": "75_percent"})
        collector.increment("events", tags={"type": "50_percent"})

        assert collector.get_counter("events", tags={"type": "50_percent"}) == 2
        assert collector.get_counter("events", tags={"type": "75_percent"}) == 1

    def test_get_all_metrics(self):
        """Test getting all metrics."""
        collector = MetricsCollector()

        collector.increment("counter1")
        collector.gauge("gauge1", 10.5)
        collector.histogram("hist1", 5.0)

        metrics = collector.get_all_metrics()

        assert "counters" in metrics
        assert "gauges" in metrics
        assert "histogram_counts" in metrics

    def test_reset_metrics(self):
        """Test resetting metrics."""
        collector = MetricsCollector()

        collector.increment("counter1", value=10)
        collector.reset()

        assert collector.get_counter("counter1") == 0


class TestAlertManager:
    """Tests for the AlertManager."""

    def test_check_event_delay(self):
        """Test alert for delayed events (per SE-5034)."""
        config = MonitoringConfig(max_event_delay_seconds=60)
        manager = AlertManager(config)

        expected = utc_now() - timedelta(seconds=120)
        actual = utc_now()

        alert = manager.check_event_delay(expected, actual, "cust_001")

        assert alert is not None
        assert alert.alert_type == AlertType.DELAYED_EVENTS
        assert alert.severity == AlertSeverity.WARNING
        assert "cust_001" in alert.message

    def test_no_alert_for_acceptable_delay(self):
        """Test no alert for acceptable delay."""
        config = MonitoringConfig(max_event_delay_seconds=60)
        manager = AlertManager(config)

        expected = utc_now() - timedelta(seconds=30)
        actual = utc_now()

        alert = manager.check_event_delay(expected, actual, "cust_001")
        assert alert is None

    def test_check_missing_events(self):
        """Test alert for missing events (per SE-5034)."""
        manager = AlertManager()

        alert = manager.check_missing_events(
            expected_count=100,
            actual_count=80,
            time_window=timedelta(hours=1),
        )

        assert alert is not None
        assert alert.alert_type == AlertType.MISSING_EVENTS
        assert alert.severity == AlertSeverity.ERROR
        assert "20" in alert.message  # Missing count

    def test_no_alert_when_events_not_missing(self):
        """Test no alert when events are not missing."""
        manager = AlertManager()

        alert = manager.check_missing_events(
            expected_count=100,
            actual_count=100,
            time_window=timedelta(hours=1),
        )
        assert alert is None

    def test_check_processing_latency(self):
        """Test alert for high processing latency."""
        config = MonitoringConfig(max_processing_latency_ms=1000)
        manager = AlertManager(config)

        alert = manager.check_processing_latency(latency_ms=1500)

        assert alert is not None
        assert alert.alert_type == AlertType.HIGH_LATENCY
        assert alert.severity == AlertSeverity.WARNING

    def test_check_processing_latency_critical(self):
        """Test critical alert for very high latency."""
        config = MonitoringConfig(max_processing_latency_ms=1000)
        manager = AlertManager(config)

        # More than 2x threshold = ERROR severity
        alert = manager.check_processing_latency(latency_ms=2500)

        assert alert is not None
        assert alert.severity == AlertSeverity.ERROR

    def test_check_feed_staleness(self):
        """Test alert for stale MNO feed data."""
        config = MonitoringConfig(max_feed_staleness_minutes=15)
        manager = AlertManager(config)

        stale_timestamp = utc_now() - timedelta(minutes=30)
        alert = manager.check_feed_staleness(stale_timestamp, "mno_feed_1")

        assert alert is not None
        assert alert.alert_type == AlertType.FEED_STALENESS
        assert "mno_feed_1" in alert.message

    def test_check_error_rate(self):
        """Test alert for high error rate."""
        config = MonitoringConfig(max_error_rate_percent=5.0)
        manager = AlertManager(config)

        alert = manager.check_error_rate(error_count=10, total_count=100)

        assert alert is not None
        assert alert.alert_type == AlertType.PROCESSING_ERRORS
        assert "10" in alert.message

    def test_get_active_alerts(self):
        """Test getting active alerts."""
        manager = AlertManager()

        # Create some alerts
        manager.check_event_delay(
            utc_now() - timedelta(seconds=120),
            utc_now(),
            "cust_001",
        )
        manager.check_missing_events(100, 50, timedelta(hours=1))

        active = manager.get_active_alerts()
        assert len(active) == 2

    def test_resolve_alert(self):
        """Test resolving alerts."""
        manager = AlertManager()

        alert = manager.check_missing_events(100, 50, timedelta(hours=1))
        assert alert is not None

        # Resolve it
        success = manager.resolve_alert(alert.alert_id)
        assert success

        # Should no longer be active
        active = manager.get_active_alerts()
        assert len(active) == 0

    def test_alert_history(self):
        """Test getting alert history."""
        manager = AlertManager()

        # Create alerts
        manager.check_event_delay(
            utc_now() - timedelta(seconds=120),
            utc_now(),
            "cust_001",
        )
        manager.check_processing_latency(2000)

        history = manager.get_alert_history()
        assert len(history) == 2

        # Filter by type
        delay_alerts = manager.get_alert_history(alert_type=AlertType.DELAYED_EVENTS)
        assert len(delay_alerts) == 1


class TestHealthCheck:
    """Tests for the HealthCheck system."""

    def test_healthy_system(self):
        """Test health check for a healthy system."""
        metrics = MetricsCollector()
        alerts = AlertManager()

        # Add some healthy metrics
        metrics.increment("records_processed", value=100)
        metrics.increment("events_emitted", value=10)

        health = HealthCheck(metrics, alerts)
        status = health.check_health()

        assert status.healthy
        assert status.status == "healthy"
        assert all(status.checks.values())

    def test_unhealthy_with_critical_alerts(self):
        """Test health check with critical alerts."""
        metrics = MetricsCollector()
        alerts = AlertManager()

        # Create a critical alert manually
        alerts._create_alert(
            AlertType.SERVICE_HEALTH,
            AlertSeverity.CRITICAL,
            "Service is down",
        )

        health = HealthCheck(metrics, alerts)
        status = health.check_health()

        assert not status.healthy
        assert status.status == "unhealthy"
        assert not status.checks["no_critical_alerts"]

    def test_unhealthy_with_high_error_rate(self):
        """Test health check with high error rate."""
        metrics = MetricsCollector()
        alerts = AlertManager()

        # Add metrics showing high error rate
        metrics.increment("records_processed", value=100)
        metrics.increment("processing_errors", value=10)  # 10% error rate

        health = HealthCheck(metrics, alerts)
        status = health.check_health()

        assert not status.healthy
        assert not status.checks["error_rate_acceptable"]

    def test_is_healthy_shortcut(self):
        """Test is_healthy() shortcut method."""
        metrics = MetricsCollector()
        alerts = AlertManager()

        metrics.increment("records_processed", value=100)

        health = HealthCheck(metrics, alerts)
        assert health.is_healthy()


class TestAlertCallback:
    """Tests for alert callback delivery."""

    def test_alert_callback_invoked(self):
        """Test that alert callback is invoked."""
        received_alerts = []

        def callback(alert: Alert):
            received_alerts.append(alert)

        config = MonitoringConfig(
            max_event_delay_seconds=60,
            alert_callback=callback,
        )
        manager = AlertManager(config)

        manager.check_event_delay(
            utc_now() - timedelta(seconds=120),
            utc_now(),
            "cust_001",
        )

        assert len(received_alerts) == 1
        assert received_alerts[0].alert_type == AlertType.DELAYED_EVENTS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
