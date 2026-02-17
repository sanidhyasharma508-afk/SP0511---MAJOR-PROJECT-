"""
Event Management API Routes
Handles events, registrations, leaderboards, and announcements
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Optional
from datetime import datetime

from backend.database import get_db
from backend.models.events import (
    Event, EventRegistration, EventLeaderboard, EventAnnouncement,
    EventCategory, EventStatus, RegistrationStatus
)
from backend.schemas.events import (
    EventCreate, EventUpdate, EventResponse, EventSummary,
    EventRegistrationCreate, EventRegistrationUpdate, EventRegistrationResponse,
    LeaderboardEntryCreate, LeaderboardEntryUpdate, LeaderboardEntryResponse,
    AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse,
    EventStats, RegistrationStats, MessageResponse
)

router = APIRouter(prefix="/events", tags=["Events Management"])


# ============== Event CRUD Operations ==============

@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(event_data: EventCreate, db: Session = Depends(get_db)):
    """
    Create a new event
    """
    # Check if event with same name already exists
    existing_event = db.query(Event).filter(Event.name == event_data.name).first()
    if existing_event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Event with name '{event_data.name}' already exists"
        )
    
    # Convert lists and dicts to JSON strings
    event_dict = event_data.dict()
    if event_dict.get('gallery_images'):
        import json
        event_dict['gallery_images'] = json.dumps(event_dict['gallery_images'])
    if event_dict.get('prizes'):
        import json
        event_dict['prizes'] = json.dumps(event_dict['prizes'])
    
    # Determine initial status based on registration dates
    now = datetime.utcnow()
    if now < event_data.registration_start_date:
        event_dict['status'] = EventStatus.UPCOMING
    elif event_data.registration_start_date <= now <= event_data.registration_end_date:
        event_dict['status'] = EventStatus.REGISTRATION_OPEN
    elif now > event_data.registration_end_date and now < event_data.event_start_date:
        event_dict['status'] = EventStatus.REGISTRATION_CLOSED
    elif event_data.event_start_date <= now <= event_data.event_end_date:
        event_dict['status'] = EventStatus.ONGOING
    elif now > event_data.event_end_date:
        event_dict['status'] = EventStatus.COMPLETED
    
    # Create event
    new_event = Event(**event_dict)
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    
    return new_event


@router.get("/", response_model=List[EventSummary])
def get_all_events(
    category: Optional[EventCategory] = None,
    status: Optional[EventStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all events with optional filtering
    """
    query = db.query(Event)
    
    if category:
        query = query.filter(Event.category == category)
    if status:
        query = query.filter(Event.status == status)
    
    events = query.order_by(Event.event_start_date.desc()).offset(skip).limit(limit).all()
    return events


@router.get("/upcoming", response_model=List[EventSummary])
def get_upcoming_events(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get upcoming events with open registration
    """
    now = datetime.utcnow()
    events = db.query(Event).filter(
        and_(
            Event.status.in_([EventStatus.UPCOMING, EventStatus.REGISTRATION_OPEN]),
            Event.event_start_date > now
        )
    ).order_by(Event.event_start_date.asc()).limit(limit).all()
    
    return events


@router.get("/{event_id}", response_model=EventResponse)
def get_event_by_id(event_id: int, db: Session = Depends(get_db)):
    """
    Get event details by ID
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} not found"
        )
    
    return event


@router.put("/{event_id}", response_model=EventResponse)
def update_event(event_id: int, event_data: EventUpdate, db: Session = Depends(get_db)):
    """
    Update event details
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} not found"
        )
    
    # Update only provided fields
    update_data = event_data.dict(exclude_unset=True)
    
    # Convert dicts to JSON strings if present
    if 'prizes' in update_data and update_data['prizes']:
        import json
        update_data['prizes'] = json.dumps(update_data['prizes'])
    
    for field, value in update_data.items():
        setattr(event, field, value)
    
    event.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(event)
    
    return event


@router.delete("/{event_id}", response_model=MessageResponse)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    """
    Delete an event (soft delete by marking as cancelled)
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} not found"
        )
    
    # Soft delete by changing status
    event.status = EventStatus.CANCELLED
    event.updated_at = datetime.utcnow()
    db.commit()
    
    return MessageResponse(
        message=f"Event '{event.name}' has been cancelled successfully",
        success=True
    )


@router.get("/stats/overview", response_model=EventStats)
def get_event_statistics(db: Session = Depends(get_db)):
    """
    Get overall event statistics
    """
    total_events = db.query(Event).count()
    upcoming = db.query(Event).filter(Event.status == EventStatus.UPCOMING).count()
    ongoing = db.query(Event).filter(Event.status == EventStatus.ONGOING).count()
    completed = db.query(Event).filter(Event.status == EventStatus.COMPLETED).count()
    
    total_registrations = db.query(EventRegistration).count()
    total_participants = db.query(EventRegistration).filter(
        EventRegistration.status == RegistrationStatus.APPROVED
    ).count()
    
    # Count events by category
    category_counts = db.query(
        Event.category,
        func.count(Event.id)
    ).group_by(Event.category).all()
    
    events_by_category = {str(cat): count for cat, count in category_counts}
    
    return EventStats(
        total_events=total_events,
        upcoming_events=upcoming,
        ongoing_events=ongoing,
        completed_events=completed,
        total_registrations=total_registrations,
        total_participants=total_participants,
        events_by_category=events_by_category
    )


# ============== Event Registration Operations ==============

@router.post("/registrations", response_model=EventRegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_for_event(registration_data: EventRegistrationCreate, db: Session = Depends(get_db)):
    """
    Register a student for an event
    """
    # Check if event exists
    event = db.query(Event).filter(Event.id == registration_data.event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {registration_data.event_id} not found"
        )
    
    # Check if registration is open
    if not event.is_registration_open():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration is not currently open for this event"
        )
    
    # Check if event is full
    if event.is_full():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event has reached maximum capacity"
        )
    
    # Check if student already registered
    existing_registration = db.query(EventRegistration).filter(
        and_(
            EventRegistration.event_id == registration_data.event_id,
            EventRegistration.student_id == registration_data.student_id
        )
    ).first()
    
    if existing_registration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already registered for this event"
        )
    
    # Validate team information for team events
    if event.team_event:
        if not registration_data.team_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team name is required for team events"
            )
        if registration_data.team_members:
            team_size = len(registration_data.team_members) + 1  # +1 for team leader
            if event.min_team_size and team_size < event.min_team_size:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Team size must be at least {event.min_team_size} members"
                )
            if event.max_team_size and team_size > event.max_team_size:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Team size cannot exceed {event.max_team_size} members"
                )
    
    # Convert team_members list to JSON string
    reg_dict = registration_data.dict()
    if reg_dict.get('team_members'):
        import json
        reg_dict['team_members'] = json.dumps([member.dict() for member in registration_data.team_members])
    
    # Set initial status
    reg_dict['status'] = RegistrationStatus.PENDING if event.requires_approval else RegistrationStatus.APPROVED
    
    # Create registration
    new_registration = EventRegistration(**reg_dict)
    db.add(new_registration)
    
    # Update participant count
    event.current_participants += 1
    
    db.commit()
    db.refresh(new_registration)
    
    return new_registration


@router.get("/registrations/{registration_id}", response_model=EventRegistrationResponse)
def get_registration(registration_id: int, db: Session = Depends(get_db)):
    """
    Get registration details
    """
    registration = db.query(EventRegistration).filter(EventRegistration.id == registration_id).first()
    if not registration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Registration with ID {registration_id} not found"
        )
    
    return registration


@router.get("/{event_id}/registrations", response_model=List[EventRegistrationResponse])
def get_event_registrations(
    event_id: int,
    status: Optional[RegistrationStatus] = None,
    db: Session = Depends(get_db)
):
    """
    Get all registrations for an event
    """
    query = db.query(EventRegistration).filter(EventRegistration.event_id == event_id)
    
    if status:
        query = query.filter(EventRegistration.status == status)
    
    registrations = query.order_by(EventRegistration.registration_date.desc()).all()
    return registrations


@router.patch("/registrations/{registration_id}", response_model=EventRegistrationResponse)
def update_registration(
    registration_id: int,
    update_data: EventRegistrationUpdate,
    db: Session = Depends(get_db)
):
    """
    Update registration status (approve/reject/payment)
    """
    registration = db.query(EventRegistration).filter(EventRegistration.id == registration_id).first()
    if not registration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Registration with ID {registration_id} not found"
        )
    
    # Update fields
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(registration, field, value)
    
    # Set approval date if status is being approved
    if update_data.status == RegistrationStatus.APPROVED and registration.approval_date is None:
        registration.approval_date = datetime.utcnow()
    
    registration.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(registration)
    
    return registration


@router.get("/{event_id}/stats", response_model=RegistrationStats)
def get_registration_stats(event_id: int, db: Session = Depends(get_db)):
    """
    Get registration statistics for an event
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} not found"
        )
    
    total = db.query(EventRegistration).filter(EventRegistration.event_id == event_id).count()
    approved = db.query(EventRegistration).filter(
        and_(EventRegistration.event_id == event_id, EventRegistration.status == RegistrationStatus.APPROVED)
    ).count()
    pending = db.query(EventRegistration).filter(
        and_(EventRegistration.event_id == event_id, EventRegistration.status == RegistrationStatus.PENDING)
    ).count()
    rejected = db.query(EventRegistration).filter(
        and_(EventRegistration.event_id == event_id, EventRegistration.status == RegistrationStatus.REJECTED)
    ).count()
    waitlisted = db.query(EventRegistration).filter(
        and_(EventRegistration.event_id == event_id, EventRegistration.status == RegistrationStatus.WAITLISTED)
    ).count()
    
    return RegistrationStats(
        event_id=event_id,
        total_registrations=total,
        approved=approved,
        pending=pending,
        rejected=rejected,
        waitlisted=waitlisted,
        spots_remaining=event.get_spots_remaining()
    )


# ============== Leaderboard Operations ==============

@router.post("/leaderboard", response_model=LeaderboardEntryResponse, status_code=status.HTTP_201_CREATED)
def create_leaderboard_entry(entry_data: LeaderboardEntryCreate, db: Session = Depends(get_db)):
    """
    Add an entry to event leaderboard
    """
    # Check if event exists
    event = db.query(Event).filter(Event.id == entry_data.event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {entry_data.event_id} not found"
        )
    
    # Check if participant already exists in leaderboard
    existing_entry = db.query(EventLeaderboard).filter(
        and_(
            EventLeaderboard.event_id == entry_data.event_id,
            EventLeaderboard.participant_id == entry_data.participant_id
        )
    ).first()
    
    if existing_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Participant already exists in leaderboard. Use update endpoint to modify."
        )
    
    # Convert statistics dict to JSON string
    entry_dict = entry_data.dict()
    if entry_dict.get('statistics'):
        import json
        entry_dict['statistics'] = json.dumps(entry_dict['statistics'])
    
    # Create leaderboard entry
    new_entry = EventLeaderboard(**entry_dict)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    
    # Update ranks for all entries in this event
    update_leaderboard_ranks(entry_data.event_id, db)
    
    return new_entry


@router.get("/{event_id}/leaderboard", response_model=List[LeaderboardEntryResponse])
def get_event_leaderboard(
    event_id: int,
    limit: Optional[int] = Query(None, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get leaderboard for an event
    """
    query = db.query(EventLeaderboard).filter(EventLeaderboard.event_id == event_id)
    query = query.order_by(EventLeaderboard.rank.asc(), EventLeaderboard.score.desc())
    
    if limit:
        query = query.limit(limit)
    
    leaderboard = query.all()
    return leaderboard


@router.patch("/leaderboard/{entry_id}", response_model=LeaderboardEntryResponse)
def update_leaderboard_entry(
    entry_id: int,
    update_data: LeaderboardEntryUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a leaderboard entry
    """
    entry = db.query(EventLeaderboard).filter(EventLeaderboard.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leaderboard entry with ID {entry_id} not found"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    if 'statistics' in update_dict and update_dict['statistics']:
        import json
        update_dict['statistics'] = json.dumps(update_dict['statistics'])
    
    for field, value in update_dict.items():
        setattr(entry, field, value)
    
    entry.last_updated = datetime.utcnow()
    db.commit()
    db.refresh(entry)
    
    # Update ranks if score changed
    if 'score' in update_dict or 'points' in update_dict:
        update_leaderboard_ranks(entry.event_id, db)
    
    return entry


@router.delete("/leaderboard/{entry_id}", response_model=MessageResponse)
def delete_leaderboard_entry(entry_id: int, db: Session = Depends(get_db)):
    """
    Delete a leaderboard entry
    """
    entry = db.query(EventLeaderboard).filter(EventLeaderboard.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leaderboard entry with ID {entry_id} not found"
        )
    
    event_id = entry.event_id
    db.delete(entry)
    db.commit()
    
    # Update ranks after deletion
    update_leaderboard_ranks(event_id, db)
    
    return MessageResponse(
        message="Leaderboard entry deleted successfully",
        success=True
    )


def update_leaderboard_ranks(event_id: int, db: Session):
    """
    Helper function to update ranks for all entries in an event
    """
    entries = db.query(EventLeaderboard).filter(
        EventLeaderboard.event_id == event_id
    ).order_by(EventLeaderboard.score.desc(), EventLeaderboard.points.desc()).all()
    
    for index, entry in enumerate(entries, start=1):
        entry.rank = index
    
    db.commit()


# ============== Announcement Operations ==============

@router.post("/announcements", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
def create_announcement(announcement_data: AnnouncementCreate, db: Session = Depends(get_db)):
    """
    Create a new announcement
    """
    # Verify event exists if event_id is provided
    if announcement_data.event_id:
        event = db.query(Event).filter(Event.id == announcement_data.event_id).first()
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with ID {announcement_data.event_id} not found"
            )
    
    announcement = EventAnnouncement(**announcement_data.dict())
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    
    return announcement


@router.get("/announcements", response_model=List[AnnouncementResponse])
def get_all_announcements(
    event_id: Optional[int] = None,
    active_only: bool = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get announcements with optional filtering
    """
    query = db.query(EventAnnouncement)
    
    if event_id:
        query = query.filter(EventAnnouncement.event_id == event_id)
    
    if active_only:
        now = datetime.utcnow()
        query = query.filter(
            and_(
                EventAnnouncement.is_active == True,
                or_(
                    EventAnnouncement.expiry_date == None,
                    EventAnnouncement.expiry_date > now
                )
            )
        )
    
    announcements = query.order_by(
        EventAnnouncement.is_pinned.desc(),
        EventAnnouncement.publish_date.desc()
    ).offset(skip).limit(limit).all()
    
    return announcements


@router.get("/announcements/{announcement_id}", response_model=AnnouncementResponse)
def get_announcement(announcement_id: int, db: Session = Depends(get_db)):
    """
    Get announcement by ID
    """
    announcement = db.query(EventAnnouncement).filter(EventAnnouncement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Announcement with ID {announcement_id} not found"
        )
    
    return announcement


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementResponse)
def update_announcement(
    announcement_id: int,
    update_data: AnnouncementUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an announcement
    """
    announcement = db.query(EventAnnouncement).filter(EventAnnouncement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Announcement with ID {announcement_id} not found"
        )
    
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(announcement, field, value)
    
    announcement.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(announcement)
    
    return announcement


@router.delete("/announcements/{announcement_id}", response_model=MessageResponse)
def delete_announcement(announcement_id: int, db: Session = Depends(get_db)):
    """
    Delete an announcement
    """
    announcement = db.query(EventAnnouncement).filter(EventAnnouncement.id == announcement_id).first()
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Announcement with ID {announcement_id} not found"
        )
    
    db.delete(announcement)
    db.commit()
    
    return MessageResponse(
        message="Announcement deleted successfully",
        success=True
    )
