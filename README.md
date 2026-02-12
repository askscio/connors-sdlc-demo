# connors-sdlc-demo

### Test edit to the Readme

Changes go below this line

## International Usage Detection (SE-5034)

This module implements the 50% international usage threshold detection logic as part of the SE-5032 epic for International Usage Threshold Notifications.

### Features

- **Usage Ingestion**: Ingests international usage and rating data from MNO (carrier) feeds
- **Threshold Detection**: Computes customer international usage according to SE-5033 rules
- **Event Emission**: Emits "50% reached" events for downstream notification systems (SE-5035)
- **Monitoring**: Production monitoring/alerting for missing or delayed events

### Module Structure

```
international_usage/
├── __init__.py      # Package exports
├── models.py        # Core data models (UsageRecord, ThresholdEvent, etc.)
├── rules.py         # Threshold rules engine (SE-5033 implementation)
├── detector.py      # Main detection service
├── events.py        # Event emitter for threshold notifications
└── monitoring.py    # Operational monitoring and alerting
```

### Usage Example

```python
from international_usage import (
    UsageDetector, UsageAllowance, UsageRecord,
    PlanType, UsageType, ThresholdType, EventType,
    InMemoryEventEmitter, CallbackSubscriber,
)
from decimal import Decimal
from datetime import datetime, timezone

# Set up detector with event handler
emitter = InMemoryEventEmitter()
emitter.subscribe(EventType.THRESHOLD_50_PERCENT, my_notification_handler)
detector = UsageDetector(event_emitter=emitter)

# Register customer allowance
allowance = UsageAllowance(
    allowance_id="allow_1",
    customer_id="cust_001",
    plan_type=PlanType.INTERNATIONAL_PACKAGE,
    usage_type=UsageType.VOICE_MINUTES,
    threshold_type=ThresholdType.VOLUME,
    volume_limit=Decimal("1000"),
)
detector.register_allowance(allowance)

# Process usage records from MNO feed
record = UsageRecord(
    record_id="rec_001",
    customer_id="cust_001",
    usage_type=UsageType.VOICE_MINUTES,
    amount=Decimal("500"),
    timestamp=datetime.now(timezone.utc),
    country_code="GB",
)
result = detector.process_record(record)
# -> Emits THRESHOLD_50_PERCENT event
```

### Testing

```bash
python -m pytest tests/ -v
```