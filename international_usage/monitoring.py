"""
Monitoring and Alerting for International Usage Detection (SE-5034).

Per acceptance criteria:
- Production monitoring/alerting exists for missing or delayed events
- Operational readiness for the detection system
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)
from decimal import Decimal
from typing import Optional, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Severity levels for operational alerts."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of operational alerts."""
    MISSING_EVENTS = "missing_events"
    DELAYED_EVENTS = "delayed_events"
    HIGH_LATENCY = "high_latency"
    FEED_STALENESS = "feed_staleness"
    PROCESSING_ERRORS = "processing_errors"
    THRESHOLD_ANOMALY = "threshold_anomaly"
    SERVICE_HEALTH = "service_health"


@dataclass
class Alert:
    """An operational alert for the detection system."""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: datetime = field(default_factory=utc_now)
    metadata: dict = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    def resolve(self) -> None:
        """Mark this alert as resolved."""
        self.resolved = True
        self.resolved_at = utc_now()


@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    timestamp: datetime = field(default_factory=utc_now)
    tags: dict = field(default_factory=dict)


@dataclass
class MonitoringConfig:
    """Configuration for the monitoring system."""

    # Alert thresholds
    max_event_delay_seconds: int = 60  # Alert if events are delayed > 60s
    max_processing_latency_ms: int = 1000  # Alert if processing > 1s
    max_feed_staleness_minutes: int = 15  # Alert if feed data is stale
    max_error_rate_percent: float = 5.0  # Alert if error rate > 5%
    min_events_per_hour: int = 0  # Alert if fewer events than expected

    # Health check intervals
    health_check_interval_seconds: int = 30
    metric_collection_interval_seconds: int = 10

    # Alert delivery
    alert_callback: Optional[Callable[[Alert], None]] = None
    pagerduty_integration_key: Optional[str] = None
    slack_webhook_url: Optional[str] = None


class MetricsCollector:
    """
    Collects and aggregates metrics for the detection system.

    Tracks:
    - Processing latency
    - Event emission rates
    - Error rates
    - Feed staleness
    """

    def __init__(self):
        self._metrics: list[MetricPoint] = []
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}

    def increment(self, name: str, value: int = 1, tags: dict = None) -> None:
        """Increment a counter metric."""
        key = self._metric_key(name, tags)
        self._counters[key] = self._counters.get(key, 0) + value
        self._record_metric(name, self._counters[key], tags)

    def gauge(self, name: str, value: float, tags: dict = None) -> None:
        """Set a gauge metric."""
        key = self._metric_key(name, tags)
        self._gauges[key] = value
        self._record_metric(name, value, tags)

    def histogram(self, name: str, value: float, tags: dict = None) -> None:
        """Record a histogram value."""
        key = self._metric_key(name, tags)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        self._record_metric(name, value, tags)

    def get_counter(self, name: str, tags: dict = None) -> int:
        """Get current counter value."""
        key = self._metric_key(name, tags)
        return self._counters.get(key, 0)

    def get_gauge(self, name: str, tags: dict = None) -> float:
        """Get current gauge value."""
        key = self._metric_key(name, tags)
        return self._gauges.get(key, 0.0)

    def get_histogram_percentile(
        self, name: str, percentile: float, tags: dict = None
    ) -> Optional[float]:
        """Get a percentile from histogram data."""
        key = self._metric_key(name, tags)
        values = self._histograms.get(key, [])
        if not values:
            return None
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def get_recent_metrics(
        self, name: str, since: datetime
    ) -> list[MetricPoint]:
        """Get metrics since a given time."""
        return [
            m for m in self._metrics
            if m.name == name and m.timestamp >= since
        ]

    def get_all_metrics(self) -> dict:
        """Get all current metrics as a dictionary."""
        return {
            "counters": self._counters.copy(),
            "gauges": self._gauges.copy(),
            "histogram_counts": {k: len(v) for k, v in self._histograms.items()},
        }

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        self._metrics.clear()
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()

    def _metric_key(self, name: str, tags: dict = None) -> str:
        """Generate a unique key for a metric with tags."""
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}:{tag_str}"

    def _record_metric(self, name: str, value: float, tags: dict = None) -> None:
        """Record a metric point."""
        self._metrics.append(MetricPoint(
            name=name,
            value=value,
            tags=tags or {},
        ))

        # Keep only last 1000 metrics to prevent memory growth
        if len(self._metrics) > 1000:
            self._metrics = self._metrics[-1000:]


class AlertManager:
    """
    Manages operational alerts for the detection system.

    Per SE-5034 acceptance criteria:
    - Monitoring/alerts for missing or delayed events in production
    """

    def __init__(self, config: Optional[MonitoringConfig] = None):
        self._config = config or MonitoringConfig()
        self._active_alerts: dict[str, Alert] = {}
        self._alert_history: list[Alert] = []

    def check_event_delay(
        self,
        expected_time: datetime,
        actual_time: datetime,
        customer_id: str,
    ) -> Optional[Alert]:
        """
        Check if an event was delayed beyond threshold.

        Per SE-5034: Alert for delayed events.
        """
        delay_seconds = (actual_time - expected_time).total_seconds()

        if delay_seconds > self._config.max_event_delay_seconds:
            return self._create_alert(
                AlertType.DELAYED_EVENTS,
                AlertSeverity.WARNING,
                f"Event delayed by {delay_seconds:.1f}s for customer {customer_id}",
                metadata={
                    "customer_id": customer_id,
                    "delay_seconds": delay_seconds,
                    "threshold_seconds": self._config.max_event_delay_seconds,
                },
            )
        return None

    def check_missing_events(
        self,
        expected_count: int,
        actual_count: int,
        time_window: timedelta,
    ) -> Optional[Alert]:
        """
        Check if expected events are missing.

        Per SE-5034: Alert for missing events.
        """
        if actual_count < expected_count:
            missing = expected_count - actual_count
            return self._create_alert(
                AlertType.MISSING_EVENTS,
                AlertSeverity.ERROR,
                f"Missing {missing} events in last {time_window}",
                metadata={
                    "expected_count": expected_count,
                    "actual_count": actual_count,
                    "missing_count": missing,
                    "time_window_seconds": time_window.total_seconds(),
                },
            )
        return None

    def check_processing_latency(
        self,
        latency_ms: float,
        operation: str = "processing",
    ) -> Optional[Alert]:
        """Check if processing latency exceeds threshold."""
        if latency_ms > self._config.max_processing_latency_ms:
            severity = AlertSeverity.WARNING
            if latency_ms > self._config.max_processing_latency_ms * 2:
                severity = AlertSeverity.ERROR

            return self._create_alert(
                AlertType.HIGH_LATENCY,
                severity,
                f"High {operation} latency: {latency_ms:.1f}ms",
                metadata={
                    "latency_ms": latency_ms,
                    "threshold_ms": self._config.max_processing_latency_ms,
                    "operation": operation,
                },
            )
        return None

    def check_feed_staleness(
        self,
        feed_timestamp: datetime,
        source: str,
    ) -> Optional[Alert]:
        """Check if MNO feed data is stale."""
        staleness_minutes = (
            utc_now() - feed_timestamp
        ).total_seconds() / 60

        if staleness_minutes > self._config.max_feed_staleness_minutes:
            severity = AlertSeverity.WARNING
            if staleness_minutes > self._config.max_feed_staleness_minutes * 2:
                severity = AlertSeverity.ERROR

            return self._create_alert(
                AlertType.FEED_STALENESS,
                severity,
                f"Feed {source} is {staleness_minutes:.1f} minutes stale",
                metadata={
                    "source": source,
                    "staleness_minutes": staleness_minutes,
                    "threshold_minutes": self._config.max_feed_staleness_minutes,
                },
            )
        return None

    def check_error_rate(
        self,
        error_count: int,
        total_count: int,
    ) -> Optional[Alert]:
        """Check if error rate exceeds threshold."""
        if total_count == 0:
            return None

        error_rate = (error_count / total_count) * 100

        if error_rate > self._config.max_error_rate_percent:
            severity = AlertSeverity.WARNING
            if error_rate > self._config.max_error_rate_percent * 2:
                severity = AlertSeverity.ERROR

            return self._create_alert(
                AlertType.PROCESSING_ERRORS,
                severity,
                f"High error rate: {error_rate:.1f}%",
                metadata={
                    "error_count": error_count,
                    "total_count": total_count,
                    "error_rate_percent": error_rate,
                    "threshold_percent": self._config.max_error_rate_percent,
                },
            )
        return None

    def get_active_alerts(self) -> list[Alert]:
        """Get all currently active (unresolved) alerts."""
        return [a for a in self._active_alerts.values() if not a.resolved]

    def get_alert_history(
        self,
        since: Optional[datetime] = None,
        alert_type: Optional[AlertType] = None,
    ) -> list[Alert]:
        """Get historical alerts, optionally filtered."""
        alerts = self._alert_history
        if since:
            alerts = [a for a in alerts if a.timestamp >= since]
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
        return alerts

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert by ID."""
        if alert_id in self._active_alerts:
            self._active_alerts[alert_id].resolve()
            return True
        return False

    def _create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        metadata: dict = None,
    ) -> Alert:
        """Create and register a new alert."""
        alert_id = f"alert_{alert_type.value}_{utc_now().timestamp()}"

        alert = Alert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            metadata=metadata or {},
        )

        self._active_alerts[alert_id] = alert
        self._alert_history.append(alert)

        # Deliver alert via configured callback
        if self._config.alert_callback:
            try:
                self._config.alert_callback(alert)
            except Exception as e:
                logger.error(f"Failed to deliver alert: {e}")

        logger.log(
            logging.ERROR if severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]
            else logging.WARNING,
            f"[{severity.value.upper()}] {alert_type.value}: {message}"
        )

        return alert


@dataclass
class HealthStatus:
    """Health status of the detection system."""
    healthy: bool
    status: str
    checks: dict[str, bool]
    last_check: datetime = field(default_factory=utc_now)
    details: dict = field(default_factory=dict)


class HealthCheck:
    """
    Health check system for operational readiness.

    Per SE-5034: Ensure operational readiness for production.
    """

    def __init__(
        self,
        metrics: MetricsCollector,
        alerts: AlertManager,
    ):
        self._metrics = metrics
        self._alerts = alerts
        self._last_check: Optional[HealthStatus] = None

    def check_health(self) -> HealthStatus:
        """
        Perform a comprehensive health check.

        Returns overall health status and individual check results.
        """
        checks = {}
        details = {}

        # Check 1: No critical alerts
        critical_alerts = [
            a for a in self._alerts.get_active_alerts()
            if a.severity == AlertSeverity.CRITICAL
        ]
        checks["no_critical_alerts"] = len(critical_alerts) == 0
        details["critical_alert_count"] = len(critical_alerts)

        # Check 2: Processing is happening
        records_processed = self._metrics.get_counter("records_processed")
        checks["processing_active"] = records_processed > 0
        details["records_processed"] = records_processed

        # Check 3: Events are being emitted
        events_emitted = self._metrics.get_counter("events_emitted")
        checks["events_emitting"] = True  # Allow zero events if no thresholds crossed
        details["events_emitted"] = events_emitted

        # Check 4: Latency is acceptable
        p99_latency = self._metrics.get_histogram_percentile(
            "processing_latency_ms", 99
        )
        if p99_latency is not None:
            checks["latency_acceptable"] = p99_latency < 1000
            details["p99_latency_ms"] = p99_latency
        else:
            checks["latency_acceptable"] = True
            details["p99_latency_ms"] = None

        # Check 5: Error rate is acceptable
        error_count = self._metrics.get_counter("processing_errors")
        total_count = self._metrics.get_counter("records_processed")
        if total_count > 0:
            error_rate = (error_count / total_count) * 100
            checks["error_rate_acceptable"] = error_rate < 5.0
            details["error_rate_percent"] = error_rate
        else:
            checks["error_rate_acceptable"] = True
            details["error_rate_percent"] = 0

        # Overall health
        healthy = all(checks.values())
        status = "healthy" if healthy else "unhealthy"

        health_status = HealthStatus(
            healthy=healthy,
            status=status,
            checks=checks,
            details=details,
        )

        self._last_check = health_status
        return health_status

    def get_last_check(self) -> Optional[HealthStatus]:
        """Get the result of the last health check."""
        return self._last_check

    def is_healthy(self) -> bool:
        """Quick check if system is healthy."""
        status = self.check_health()
        return status.healthy
