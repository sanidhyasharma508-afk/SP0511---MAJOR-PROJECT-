"""
Event Bus System for Campus Automation
Implements pub/sub pattern for decoupled event handling
"""

from typing import Callable, List, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Enumeration of all possible events"""

    ATTENDANCE_MARKED = "attendance.marked"
    COMPLAINT_FILED = "complaint.filed"
    SCHEDULE_UPDATED = "schedule.updated"
    COMPLAINT_UPDATED = "complaint.updated"


class Event:
    """Base event class"""

    def __init__(self, event_type: EventType, data: Dict[str, Any], timestamp=None):
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or __import__("datetime").datetime.utcnow()

    def __repr__(self):
        return f"Event({self.event_type}, {self.data}, {self.timestamp})"


class EventBus:
    """Singleton event bus for managing events"""

    _instance = None
    _subscribers: Dict[EventType, List[Callable]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers = {}
        return cls._instance

    def subscribe(self, event_type: EventType, handler: Callable):
        """Subscribe a handler to an event type"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.info(f"Handler {handler.__name__} subscribed to {event_type}")

    def publish(self, event: Event):
        """Publish an event to all subscribed handlers"""
        logger.info(f"Publishing event: {event}")
        if event.event_type in self._subscribers:
            for handler in self._subscribers[event.event_type]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Error handling event {event.event_type}: {e}")
        else:
            logger.warning(f"No subscribers for event type: {event.event_type}")

    def get_subscribers(self, event_type: EventType):
        """Get list of subscribers for an event type"""
        return self._subscribers.get(event_type, [])


# Singleton instance
event_bus = EventBus()
