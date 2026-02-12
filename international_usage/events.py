"""
Event Emitter for threshold notifications.

Emits "50% reached" events that downstream notification systems (SE-5035)
subscribe to for SMS/email/push delivery.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)
from typing import Callable, Optional
from collections import defaultdict
import logging
import json

from international_usage.models import ThresholdEvent, EventType

logger = logging.getLogger(__name__)


class EventSubscriber(ABC):
    """
    Abstract base class for event subscribers.

    Downstream systems (notification service, analytics, etc.)
    implement this interface to receive threshold events.
    """

    @abstractmethod
    def on_event(self, event: ThresholdEvent) -> bool:
        """
        Handle a threshold event.

        Returns True if event was processed successfully, False otherwise.
        """
        pass

    @abstractmethod
    def get_subscriber_id(self) -> str:
        """Return unique identifier for this subscriber."""
        pass


class EventEmitter(ABC):
    """
    Abstract base class for event emitters.

    Provides the interface for publishing threshold events to
    downstream subscribers.
    """

    @abstractmethod
    def emit(self, event: ThresholdEvent) -> bool:
        """
        Emit a threshold event to all subscribers.

        Returns True if event was successfully emitted.
        """
        pass

    @abstractmethod
    def subscribe(self, event_type: EventType, subscriber: EventSubscriber) -> None:
        """Subscribe to events of a specific type."""
        pass

    @abstractmethod
    def unsubscribe(self, event_type: EventType, subscriber: EventSubscriber) -> None:
        """Unsubscribe from events of a specific type."""
        pass


@dataclass
class EmittedEvent:
    """Record of an emitted event for tracking and debugging."""
    event: ThresholdEvent
    emitted_at: datetime
    subscribers_notified: list[str]
    success: bool
    error: Optional[str] = None


class InMemoryEventEmitter(EventEmitter):
    """
    In-memory implementation of EventEmitter for development and testing.

    In production, this would be replaced with a message queue implementation
    (e.g., Kafka, RabbitMQ, SQS) for reliable event delivery.
    """

    def __init__(self):
        self._subscribers: dict[EventType, list[EventSubscriber]] = defaultdict(list)
        self._event_log: list[EmittedEvent] = []
        self._emitted_idempotency_keys: set[str] = set()

    def emit(self, event: ThresholdEvent) -> bool:
        """
        Emit a threshold event to all subscribers.

        Implements idempotency to prevent duplicate event delivery.
        """
        # Check idempotency
        if event.idempotency_key in self._emitted_idempotency_keys:
            logger.info(
                f"Skipping duplicate event: {event.event_id} "
                f"(idempotency_key: {event.idempotency_key})"
            )
            return True

        subscribers = self._subscribers.get(event.event_type, [])
        if not subscribers:
            logger.warning(
                f"No subscribers for event type {event.event_type.value}"
            )

        subscribers_notified = []
        success = True
        error = None

        for subscriber in subscribers:
            try:
                subscriber_success = subscriber.on_event(event)
                if subscriber_success:
                    subscribers_notified.append(subscriber.get_subscriber_id())
                else:
                    logger.warning(
                        f"Subscriber {subscriber.get_subscriber_id()} "
                        f"returned False for event {event.event_id}"
                    )
            except Exception as e:
                logger.error(
                    f"Error notifying subscriber {subscriber.get_subscriber_id()}: {e}"
                )
                success = False
                error = str(e)

        # Record emission
        emitted = EmittedEvent(
            event=event,
            emitted_at=utc_now(),
            subscribers_notified=subscribers_notified,
            success=success,
            error=error,
        )
        self._event_log.append(emitted)
        self._emitted_idempotency_keys.add(event.idempotency_key)

        logger.info(
            f"Emitted event {event.event_id} ({event.event_type.value}) "
            f"to {len(subscribers_notified)} subscribers"
        )

        return success

    def subscribe(self, event_type: EventType, subscriber: EventSubscriber) -> None:
        """Subscribe to events of a specific type."""
        if subscriber not in self._subscribers[event_type]:
            self._subscribers[event_type].append(subscriber)
            logger.info(
                f"Subscriber {subscriber.get_subscriber_id()} "
                f"subscribed to {event_type.value}"
            )

    def unsubscribe(self, event_type: EventType, subscriber: EventSubscriber) -> None:
        """Unsubscribe from events of a specific type."""
        if subscriber in self._subscribers[event_type]:
            self._subscribers[event_type].remove(subscriber)
            logger.info(
                f"Subscriber {subscriber.get_subscriber_id()} "
                f"unsubscribed from {event_type.value}"
            )

    def get_event_log(self) -> list[EmittedEvent]:
        """Get the log of all emitted events."""
        return self._event_log.copy()

    def get_events_for_customer(self, customer_id: str) -> list[EmittedEvent]:
        """Get all events emitted for a specific customer."""
        return [
            e for e in self._event_log
            if e.event.customer_id == customer_id
        ]

    def clear_event_log(self) -> None:
        """Clear the event log (for testing)."""
        self._event_log.clear()
        self._emitted_idempotency_keys.clear()


class LoggingSubscriber(EventSubscriber):
    """
    Simple subscriber that logs events.

    Useful for debugging and as a reference implementation.
    """

    def __init__(self, subscriber_id: str = "logging_subscriber"):
        self._subscriber_id = subscriber_id

    def on_event(self, event: ThresholdEvent) -> bool:
        logger.info(
            f"[{self._subscriber_id}] Received {event.event_type.value} event "
            f"for customer {event.customer_id}: "
            f"{event.actual_percentage:.1f}% of {event.usage_type.value} used"
        )
        return True

    def get_subscriber_id(self) -> str:
        return self._subscriber_id


class NotificationServiceSubscriber(EventSubscriber):
    """
    Subscriber that forwards events to the notification service (SE-5035).

    This is a placeholder implementation. In production, this would
    integrate with the actual notification platform.
    """

    def __init__(
        self,
        notification_endpoint: str = "http://notification-service/events",
        subscriber_id: str = "notification_service",
    ):
        self._endpoint = notification_endpoint
        self._subscriber_id = subscriber_id
        self._pending_notifications: list[ThresholdEvent] = []

    def on_event(self, event: ThresholdEvent) -> bool:
        """
        Forward event to notification service.

        In production, this would make an HTTP call or publish to a queue.
        For now, we store the event for later processing.
        """
        self._pending_notifications.append(event)
        logger.info(
            f"Queued notification for customer {event.customer_id}: "
            f"{event.threshold_percentage}% threshold reached"
        )
        return True

    def get_subscriber_id(self) -> str:
        return self._subscriber_id

    def get_pending_notifications(self) -> list[ThresholdEvent]:
        """Get list of pending notifications (for testing)."""
        return self._pending_notifications.copy()

    def clear_pending(self) -> None:
        """Clear pending notifications (for testing)."""
        self._pending_notifications.clear()


class CallbackSubscriber(EventSubscriber):
    """
    Subscriber that invokes a callback function for each event.

    Useful for testing and custom integrations.
    """

    def __init__(
        self,
        callback: Callable[[ThresholdEvent], bool],
        subscriber_id: str = "callback_subscriber",
    ):
        self._callback = callback
        self._subscriber_id = subscriber_id

    def on_event(self, event: ThresholdEvent) -> bool:
        return self._callback(event)

    def get_subscriber_id(self) -> str:
        return self._subscriber_id


def create_event_emitter_with_default_subscribers() -> InMemoryEventEmitter:
    """
    Create an event emitter with default subscribers configured.

    In production, this would configure the actual notification service
    subscriber and any other required subscribers.
    """
    emitter = InMemoryEventEmitter()

    # Add logging subscriber for all event types
    logging_subscriber = LoggingSubscriber()
    for event_type in EventType:
        emitter.subscribe(event_type, logging_subscriber)

    # Add notification service subscriber for threshold events
    notification_subscriber = NotificationServiceSubscriber()
    for event_type in EventType:
        emitter.subscribe(event_type, notification_subscriber)

    return emitter
