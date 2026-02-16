from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
from sqlalchemy.sql import func
import enum
from backend.models.student import Base


class IssueType(str, enum.Enum):
    CLASS_TIMING_CLASH = "Class Timing Clash"
    MESS_TIMING_ISSUE = "Mess Timing Issue"
    SUGGEST_BETTER_TIME = "Suggesting Better Time Slots"
    ATTENDANCE_DIFFICULTY = "Difficulty Attending Sessions"
    OTHER = "Other Issue"


class ScheduleFeedback(Base):
    __tablename__ = "schedule_feedback"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    roll_number = Column(String(50), nullable=False)
    issue_type = Column(String(100), nullable=False)
    preferred_timing = Column(String(200), nullable=True)
    additional_comments = Column(Text, nullable=True)
    status = Column(String(50), default="pending")  # pending, resolved, in_progress
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<ScheduleFeedback {self.id}: {self.issue_type} by {self.roll_number}>"


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    author = Column(String(100), nullable=False)  # Faculty name
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    target_audience = Column(String(100), default="all")  # all, specific_year, specific_branch
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Announcement {self.id}: {self.title}>"
