"""
Utility to integrate event bus with agent handlers
Registers all agents with the event bus
"""

import logging
from functools import wraps
from backend.core.event_bus import event_bus, EventType, Event
from backend.core.agents import AttendanceRiskAgent, ComplaintTriageAgent, SchedulerConflictAgent
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def register_agents(db: Session = None):
    """
    Register all agents with the event bus
    Must be called once during app startup
    """

    def attendance_handler(event: Event):
        """Wrapper to pass db to agent"""
        from backend.database import SessionLocal

        session = db or SessionLocal()
        try:
            AttendanceRiskAgent.handle_attendance_marked(event, session)
        finally:
            if not db:
                session.close()

    def complaint_handler(event: Event):
        """Wrapper to pass db to agent"""
        from backend.database import SessionLocal

        session = db or SessionLocal()
        try:
            ComplaintTriageAgent.handle_complaint_filed(event, session)
        finally:
            if not db:
                session.close()

    def schedule_handler(event: Event):
        """Wrapper to pass db to agent"""
        from backend.database import SessionLocal

        session = db or SessionLocal()
        try:
            SchedulerConflictAgent.handle_schedule_updated(event, session)
        finally:
            if not db:
                session.close()

    # Subscribe agents to their respective events
    event_bus.subscribe(EventType.ATTENDANCE_MARKED, attendance_handler)
    event_bus.subscribe(EventType.COMPLAINT_FILED, complaint_handler)
    event_bus.subscribe(EventType.SCHEDULE_UPDATED, schedule_handler)

    logger.info("✓ All agents registered with event bus")


def publish_event(event_type: EventType, data: dict):
    """
    Publish an event to the event bus
    Convenience function for routes
    """
    event = Event(event_type, data)
    event_bus.publish(event)
