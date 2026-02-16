"""
Event Management Models
Handles event creation, registration, leaderboards, and announcements
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from backend.database import Base


class EventCategory(str, enum.Enum):
    """Event categories"""
    SPORTS = "sports"
    TECHNICAL = "technical"
    CULTURAL = "cultural"
    GAMING = "gaming"
    WORKSHOP = "workshop"
    COMPETITION = "competition"


class EventStatus(str, enum.Enum):
    """Event status"""
    UPCOMING = "upcoming"
    REGISTRATION_OPEN = "registration_open"
    REGISTRATION_CLOSED = "registration_closed"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RegistrationStatus(str, enum.Enum):
    """Registration status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WAITLISTED = "waitlisted"


class Event(Base):
    """
    Event model for storing event information
    """
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False)
    category = Column(SQLEnum(EventCategory), nullable=False, index=True)
    
    # Event images and media
    banner_image = Column(String(500), nullable=True)  # URL or path to banner image
    thumbnail_image = Column(String(500), nullable=True)
    gallery_images = Column(Text, nullable=True)  # JSON array of image URLs
    
    # Event timing
    registration_start_date = Column(DateTime, nullable=False)
    registration_end_date = Column(DateTime, nullable=False)
    event_start_date = Column(DateTime, nullable=False)
    event_end_date = Column(DateTime, nullable=False)
    
    # Event details
    venue = Column(String(300), nullable=True)
    max_participants = Column(Integer, nullable=True)
    current_participants = Column(Integer, default=0)
    entry_fee = Column(Float, default=0.0)
    
    # Organizer information
    organizer_name = Column(String(200), nullable=False)
    organizer_email = Column(String(200), nullable=False)
    organizer_phone = Column(String(20), nullable=True)
    
    # Event configuration
    status = Column(SQLEnum(EventStatus), default=EventStatus.UPCOMING)
    requires_approval = Column(Boolean, default=False)
    team_event = Column(Boolean, default=False)
    min_team_size = Column(Integer, nullable=True)
    max_team_size = Column(Integer, nullable=True)
    
    # Rules and requirements
    rules = Column(Text, nullable=True)
    eligibility_criteria = Column(Text, nullable=True)
    prizes = Column(Text, nullable=True)  # JSON object with prize details
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, nullable=True)  # User ID of creator
    
    # Relationships
    registrations = relationship("EventRegistration", back_populates="event", cascade="all, delete-orphan")
    leaderboard = relationship("EventLeaderboard", back_populates="event", cascade="all, delete-orphan")
    announcements = relationship("EventAnnouncement", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Event(id={self.id}, name='{self.name}', category='{self.category}', status='{self.status}')>"

    def is_registration_open(self):
        """Check if registration is currently open"""
        now = datetime.utcnow()
        return (
            self.status == EventStatus.REGISTRATION_OPEN and
            self.registration_start_date <= now <= self.registration_end_date
        )

    def is_full(self):
        """Check if event has reached max participants"""
        if self.max_participants is None:
            return False
        return self.current_participants >= self.max_participants

    def get_spots_remaining(self):
        """Get number of spots remaining"""
        if self.max_participants is None:
            return None
        return self.max_participants - self.current_participants


class EventRegistration(Base):
    """
    Event registration model for tracking participant registrations
    """
    __tablename__ = "event_registrations"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    
    # Participant information
    student_id = Column(String(50), nullable=False, index=True)
    student_name = Column(String(200), nullable=False)
    student_email = Column(String(200), nullable=False)
    student_phone = Column(String(20), nullable=False)
    branch = Column(String(100), nullable=True)
    year = Column(String(20), nullable=True)
    roll_number = Column(String(50), nullable=True)
    
    # Team information (if team event)
    team_name = Column(String(200), nullable=True)
    team_members = Column(Text, nullable=True)  # JSON array of team member details
    team_leader = Column(Boolean, default=True)
    
    # Registration details
    registration_date = Column(DateTime, default=datetime.utcnow)
    status = Column(SQLEnum(RegistrationStatus), default=RegistrationStatus.PENDING)
    payment_status = Column(String(50), default="pending")  # pending, completed, failed
    transaction_id = Column(String(100), nullable=True)
    
    # Additional information
    previous_experience = Column(Text, nullable=True)
    expectations = Column(Text, nullable=True)
    special_requirements = Column(Text, nullable=True)
    emergency_contact = Column(String(20), nullable=True)
    
    # Approval workflow
    approved_by = Column(Integer, nullable=True)  # Admin user ID
    approval_date = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    event = relationship("Event", back_populates="registrations")

    def __repr__(self):
        return f"<EventRegistration(id={self.id}, event_id={self.event_id}, student='{self.student_name}', status='{self.status}')>"


class EventLeaderboard(Base):
    """
    Event leaderboard model for tracking rankings and scores
    """
    __tablename__ = "event_leaderboard"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    
    # Participant information
    participant_id = Column(String(50), nullable=False)  # Student ID or Team ID
    participant_name = Column(String(200), nullable=False)
    participant_type = Column(String(20), default="individual")  # individual or team
    
    # Scoring
    score = Column(Float, default=0.0)
    rank = Column(Integer, nullable=True)
    points = Column(Integer, default=0)
    
    # Performance metrics
    matches_played = Column(Integer, default=0)
    matches_won = Column(Integer, default=0)
    matches_lost = Column(Integer, default=0)
    matches_draw = Column(Integer, default=0)
    
    # Additional stats (JSON format for flexibility)
    statistics = Column(Text, nullable=True)  # JSON object with custom stats
    
    # Awards and achievements
    position = Column(String(50), nullable=True)  # Winner, Runner-up, etc.
    prize_won = Column(String(200), nullable=True)
    certificate_url = Column(String(500), nullable=True)
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    event = relationship("Event", back_populates="leaderboard")

    def __repr__(self):
        return f"<EventLeaderboard(id={self.id}, event_id={self.event_id}, participant='{self.participant_name}', rank={self.rank}, score={self.score})>"

    def calculate_win_rate(self):
        """Calculate win rate percentage"""
        if self.matches_played == 0:
            return 0.0
        return (self.matches_won / self.matches_played) * 100


class EventAnnouncement(Base):
    """
    Event announcements model for updates and notifications
    """
    __tablename__ = "event_announcements"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=True)
    
    # Announcement content
    title = Column(String(300), nullable=False)
    message = Column(Text, nullable=False)
    announcement_type = Column(String(50), default="general")  # general, urgent, reminder, update
    
    # Visibility and targeting
    target_audience = Column(String(100), default="all")  # all, registered, participants
    is_pinned = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Timing
    publish_date = Column(DateTime, default=datetime.utcnow)
    expiry_date = Column(DateTime, nullable=True)
    
    # Rich content
    image_url = Column(String(500), nullable=True)
    attachment_url = Column(String(500), nullable=True)
    link_url = Column(String(500), nullable=True)
    link_text = Column(String(100), nullable=True)
    
    # Metadata
    created_by = Column(Integer, nullable=True)  # Admin user ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    event = relationship("Event", back_populates="announcements")

    def __repr__(self):
        return f"<EventAnnouncement(id={self.id}, title='{self.title}', type='{self.announcement_type}')>"

    def is_expired(self):
        """Check if announcement has expired"""
        if self.expiry_date is None:
            return False
        return datetime.utcnow() > self.expiry_date

    def is_visible(self):
        """Check if announcement should be visible"""
        return self.is_active and not self.is_expired()
