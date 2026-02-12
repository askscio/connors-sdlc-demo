"""
International Usage Detection Module (SE-5034)

This module implements the 50% international usage threshold detection logic
as part of the SE-5032 epic for International Usage Threshold Notifications.

Key Components:
- models: Core data models for usage tracking and events
- rules: Threshold rules engine (implements SE-5033 specs)
- detector: Usage detection service that monitors thresholds
- events: Event emitter for threshold notifications
- monitoring: Operational monitoring and alerting
"""

from international_usage.models import (
    UsageType,
    ThresholdType,
    CustomerSegment,
    PlanType,
    UsageRecord,
    UsageAllowance,
    CustomerUsageState,
    ThresholdEvent,
    EventType,
)
from international_usage.rules import (
    ThresholdRule,
    ThresholdRulesEngine,
    default_rules_engine,
)
from international_usage.detector import (
    UsageDetector,
    DetectionResult,
)
from international_usage.events import (
    EventEmitter,
    EventSubscriber,
    InMemoryEventEmitter,
)
from international_usage.monitoring import (
    MetricsCollector,
    AlertManager,
    HealthCheck,
)

__all__ = [
    # Models
    "UsageType",
    "ThresholdType",
    "CustomerSegment",
    "PlanType",
    "UsageRecord",
    "UsageAllowance",
    "CustomerUsageState",
    "ThresholdEvent",
    "EventType",
    # Rules
    "ThresholdRule",
    "ThresholdRulesEngine",
    "default_rules_engine",
    # Detection
    "UsageDetector",
    "DetectionResult",
    # Events
    "EventEmitter",
    "EventSubscriber",
    "InMemoryEventEmitter",
    # Monitoring
    "MetricsCollector",
    "AlertManager",
    "HealthCheck",
]
