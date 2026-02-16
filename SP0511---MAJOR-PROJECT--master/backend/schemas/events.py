"""
Pydantic schemas for Event Management
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from backend.models.events import EventCategory, EventStatus, RegistrationStatus


# ============== Event Schemas ==============

class EventBase(BaseModel):
    """Base event schema"""
    name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    category: EventCategory
    banner_image: Optional[str] = None
    thumbnail_image: Optional[str] = None
    venue: Optional[str] = None
    max_participants: Optional[int] = Field(None, gt=0)
    entry_fee: float = Field(default=0.0, ge=0)
    organizer_name: str = Field(..., min_length=2)
    organizer_email: EmailStr
    organizer_phone: Optional[str] = None
    requires_approval: bool = False
    team_event: bool = False
    min_team_size: Optional[int] = Field(None, gt=0)
    max_team_size: Optional[int] = Field(None, gt=0)
    rules: Optional[str] = None
    eligibility_criteria: Optional[str] = None


class EventCreate(EventBase):
    """Schema for creating a new event"""
    registration_start_date: datetime
    registration_end_date: datetime
    event_start_date: datetime
    event_end_date: datetime
    prizes: Optional[Dict[str, Any]] = None  # {first: "...", second: "...", third: "..."}
    gallery_images: Optional[List[str]] = None

    @validator('registration_end_date')
    def registration_end_after_start(cls, v, values):
        if 'registration_start_date' in values and v <= values['registration_start_date']:
            raise ValueError('Registration end date must be after start date')
        return v

    @validator('event_start_date')
    def event_start_after_registration(cls, v, values):
        if 'registration_end_date' in values and v < values['registration_end_date']:
            raise ValueError('Event start date must be after registration end date')
        return v

    @validator('event_end_date')
    def event_end_after_start(cls, v, values):
        if 'event_start_date' in values and v <= values['event_start_date']:
            raise ValueError('Event end date must be after start date')
        return v

    @validator('max_team_size')
    def max_team_size_validation(cls, v, values):
        if v and 'min_team_size' in values and values['min_team_size'] and v < values['min_team_size']:
            raise ValueError('Max team size must be greater than or equal to min team size')
        return v


class EventUpdate(BaseModel):
    """Schema for updating an event"""
    name: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, min_length=10)
    category: Optional[EventCategory] = None
    banner_image: Optional[str] = None
    thumbnail_image: Optional[str] = None
    venue: Optional[str] = None
    max_participants: Optional[int] = Field(None, gt=0)
    status: Optional[EventStatus] = None
    rules: Optional[str] = None
    eligibility_criteria: Optional[str] = None
    prizes: Optional[Dict[str, Any]] = None


class EventResponse(EventBase):
    """Schema for event response"""
    id: int
    status: EventStatus
    current_participants: int
    registration_start_date: datetime
    registration_end_date: datetime
    event_start_date: datetime
    event_end_date: datetime
    prizes: Optional[Dict[str, Any]] = None
    gallery_images: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EventSummary(BaseModel):
    """Simplified event schema for lists"""
    id: int
    name: str
    description: str
    category: EventCategory
    status: EventStatus
    thumbnail_image: Optional[str] = None
    event_start_date: datetime
    event_end_date: datetime
    registration_end_date: datetime
    current_participants: int
    max_participants: Optional[int] = None
    entry_fee: float

    class Config:
        from_attributes = True


# ============== Event Registration Schemas ==============

class TeamMember(BaseModel):
    """Team member information"""
    name: str
    email: EmailStr
    phone: str
    roll_number: Optional[str] = None


class EventRegistrationBase(BaseModel):
    """Base registration schema"""
    student_name: str = Field(..., min_length=2, max_length=200)
    student_email: EmailStr
    student_phone: str = Field(..., min_length=10, max_length=20)
    branch: Optional[str] = None
    year: Optional[str] = None
    roll_number: Optional[str] = None
    team_name: Optional[str] = None
    team_members: Optional[List[TeamMember]] = None
    previous_experience: Optional[str] = None
    expectations: Optional[str] = None
    special_requirements: Optional[str] = None
    emergency_contact: Optional[str] = None


class EventRegistrationCreate(EventRegistrationBase):
    """Schema for creating a registration"""
    event_id: int
    student_id: str


class EventRegistrationUpdate(BaseModel):
    """Schema for updating registration"""
    status: Optional[RegistrationStatus] = None
    payment_status: Optional[str] = None
    transaction_id: Optional[str] = None
    rejection_reason: Optional[str] = None


class EventRegistrationResponse(EventRegistrationBase):
    """Schema for registration response"""
    id: int
    event_id: int
    student_id: str
    team_leader: bool
    registration_date: datetime
    status: RegistrationStatus
    payment_status: str
    transaction_id: Optional[str] = None
    approved_by: Optional[int] = None
    approval_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Leaderboard Schemas ==============

class LeaderboardEntryBase(BaseModel):
    """Base leaderboard entry schema"""
    participant_name: str
    participant_type: str = "individual"  # individual or team
    score: float = 0.0
    points: int = 0
    matches_played: int = 0
    matches_won: int = 0
    matches_lost: int = 0
    matches_draw: int = 0
    statistics: Optional[Dict[str, Any]] = None


class LeaderboardEntryCreate(LeaderboardEntryBase):
    """Schema for creating leaderboard entry"""
    event_id: int
    participant_id: str


class LeaderboardEntryUpdate(BaseModel):
    """Schema for updating leaderboard entry"""
    score: Optional[float] = None
    points: Optional[int] = None
    matches_played: Optional[int] = None
    matches_won: Optional[int] = None
    matches_lost: Optional[int] = None
    matches_draw: Optional[int] = None
    rank: Optional[int] = None
    position: Optional[str] = None
    prize_won: Optional[str] = None
    certificate_url: Optional[str] = None
    statistics: Optional[Dict[str, Any]] = None


class LeaderboardEntryResponse(LeaderboardEntryBase):
    """Schema for leaderboard entry response"""
    id: int
    event_id: int
    participant_id: str
    rank: Optional[int] = None
    position: Optional[str] = None
    prize_won: Optional[str] = None
    certificate_url: Optional[str] = None
    last_updated: datetime
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Announcement Schemas ==============

class AnnouncementBase(BaseModel):
    """Base announcement schema"""
    title: str = Field(..., min_length=5, max_length=300)
    message: str = Field(..., min_length=10)
    announcement_type: str = "general"  # general, urgent, reminder, update
    target_audience: str = "all"  # all, registered, participants
    is_pinned: bool = False
    image_url: Optional[str] = None
    attachment_url: Optional[str] = None
    link_url: Optional[str] = None
    link_text: Optional[str] = None


class AnnouncementCreate(AnnouncementBase):
    """Schema for creating announcement"""
    event_id: Optional[int] = None
    expiry_date: Optional[datetime] = None


class AnnouncementUpdate(BaseModel):
    """Schema for updating announcement"""
    title: Optional[str] = Field(None, min_length=5, max_length=300)
    message: Optional[str] = Field(None, min_length=10)
    announcement_type: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_active: Optional[bool] = None
    expiry_date: Optional[datetime] = None


class AnnouncementResponse(AnnouncementBase):
    """Schema for announcement response"""
    id: int
    event_id: Optional[int] = None
    is_active: bool
    publish_date: datetime
    expiry_date: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============== Utility Schemas ==============

class EventStats(BaseModel):
    """Event statistics"""
    total_events: int
    upcoming_events: int
    ongoing_events: int
    completed_events: int
    total_registrations: int
    total_participants: int
    events_by_category: Dict[str, int]


class RegistrationStats(BaseModel):
    """Registration statistics for an event"""
    event_id: int
    total_registrations: int
    approved: int
    pending: int
    rejected: int
    waitlisted: int
    spots_remaining: Optional[int] = None


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    success: bool = True
    data: Optional[Dict[str, Any]] = None
