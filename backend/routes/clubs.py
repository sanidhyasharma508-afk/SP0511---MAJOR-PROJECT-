from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.club import Club, ClubActivity, ClubMember, ClubAttendance
from backend.schemas.club import (
    ClubCreate,
    ClubUpdate,
    ClubResponse,
    ClubDetailResponse,
    ClubActivityCreate,
    ClubActivityUpdate,
    ClubActivityResponse,
    ClubActivityDetailResponse,
    ClubMemberCreate,
    ClubMemberUpdate,
    ClubMemberResponse,
    ClubMemberDetailResponse,
    ClubAttendanceCreate,
    ClubAttendanceResponse,
)
from typing import List

router = APIRouter(prefix="/clubs", tags=["clubs"])


# ==================== CLUB ROUTES ====================


@router.post("/", response_model=ClubResponse, status_code=status.HTTP_201_CREATED)
def create_club(club: ClubCreate, db: Session = Depends(get_db)):
    """Create a new club"""
    try:
        db_club = Club(**club.model_dump())
        db.add(db_club)
        db.commit()
        db.refresh(db_club)
        return db_club
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating club: {str(e)}")


@router.get("/", response_model=List[ClubResponse])
def list_clubs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all clubs with pagination"""
    clubs = db.query(Club).offset(skip).limit(limit).all()
    return clubs


@router.get("/{club_id}", response_model=ClubDetailResponse)
def get_club(club_id: int, db: Session = Depends(get_db)):
    """Get club details with activities and members"""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    return club


@router.put("/{club_id}", response_model=ClubResponse)
def update_club(club_id: int, club_update: ClubUpdate, db: Session = Depends(get_db)):
    """Update club information"""
    db_club = db.query(Club).filter(Club.id == club_id).first()
    if not db_club:
        raise HTTPException(status_code=404, detail="Club not found")

    try:
        update_data = club_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_club, key, value)
        db.commit()
        db.refresh(db_club)
        return db_club
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating club: {str(e)}")


@router.delete("/{club_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_club(club_id: int, db: Session = Depends(get_db)):
    """Delete a club"""
    db_club = db.query(Club).filter(Club.id == club_id).first()
    if not db_club:
        raise HTTPException(status_code=404, detail="Club not found")

    try:
        db.delete(db_club)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting club: {str(e)}")


@router.get("/{club_id}/statistics")
def get_club_statistics(club_id: int, db: Session = Depends(get_db)):
    """Get club statistics and activity summary"""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    activities = db.query(ClubActivity).filter(ClubActivity.club_id == club_id).all()
    members = db.query(ClubMember).filter(ClubMember.club_id == club_id).all()

    completed_activities = [a for a in activities if a.status == "Completed"]
    total_participants = sum([a.actual_participants for a in completed_activities])

    return {
        "club_id": club_id,
        "club_name": club.name,
        "total_members": len(members),
        "active_members": len([m for m in members if m.is_active]),
        "total_activities": len(activities),
        "completed_activities": len(completed_activities),
        "upcoming_activities": len([a for a in activities if a.status == "Planned"]),
        "total_participants_engaged": total_participants,
        "average_participation": (
            round(total_participants / len(completed_activities), 2) if completed_activities else 0
        ),
    }


# ==================== CLUB ACTIVITY ROUTES ====================


@router.post(
    "/{club_id}/activities",
    response_model=ClubActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_activity(club_id: int, activity: ClubActivityCreate, db: Session = Depends(get_db)):
    """Create a new club activity/event"""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    try:
        db_activity = ClubActivity(**activity.model_dump())
        db.add(db_activity)
        db.commit()
        db.refresh(db_activity)
        return db_activity
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error creating activity: {str(e)}")


@router.get("/{club_id}/activities", response_model=List[ClubActivityResponse])
def list_club_activities(
    club_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """List all activities for a club"""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    activities = (
        db.query(ClubActivity)
        .filter(ClubActivity.club_id == club_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return activities


@router.get("/activities/{activity_id}", response_model=ClubActivityDetailResponse)
def get_activity(activity_id: int, db: Session = Depends(get_db)):
    """Get activity details"""
    activity = db.query(ClubActivity).filter(ClubActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


@router.put("/{club_id}/activities/{activity_id}", response_model=ClubActivityResponse)
def update_activity(
    club_id: int,
    activity_id: int,
    activity_update: ClubActivityUpdate,
    db: Session = Depends(get_db),
):
    """Update activity details"""
    activity = (
        db.query(ClubActivity)
        .filter(ClubActivity.id == activity_id, ClubActivity.club_id == club_id)
        .first()
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    try:
        update_data = activity_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(activity, key, value)
        db.commit()
        db.refresh(activity)
        return activity
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating activity: {str(e)}")


@router.delete("/{club_id}/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(club_id: int, activity_id: int, db: Session = Depends(get_db)):
    """Delete an activity"""
    activity = (
        db.query(ClubActivity)
        .filter(ClubActivity.id == activity_id, ClubActivity.club_id == club_id)
        .first()
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    try:
        db.delete(activity)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting activity: {str(e)}")


# ==================== CLUB MEMBER ROUTES ====================


@router.post(
    "/{club_id}/members", response_model=ClubMemberResponse, status_code=status.HTTP_201_CREATED
)
def add_member(club_id: int, member: ClubMemberCreate, db: Session = Depends(get_db)):
    """Add a member to a club"""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    # Check if member already exists
    existing = (
        db.query(ClubMember)
        .filter(ClubMember.club_id == club_id, ClubMember.student_id == member.student_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Student is already a member of this club")

    try:
        db_member = ClubMember(**member.model_dump())
        db.add(db_member)
        club.member_count = (
            db.query(ClubMember)
            .filter(ClubMember.club_id == club_id, ClubMember.is_active == True)
            .count()
            + 1
        )
        db.commit()
        db.refresh(db_member)
        return db_member
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error adding member: {str(e)}")


@router.get("/{club_id}/members", response_model=List[ClubMemberResponse])
def list_club_members(club_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all members of a club"""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    members = (
        db.query(ClubMember).filter(ClubMember.club_id == club_id).offset(skip).limit(limit).all()
    )
    return members


# ==================== CLUB ATTENDANCE (NEW) ====================

@router.post("/{club_id}/attendance", response_model=list[ClubAttendanceResponse], status_code=status.HTTP_201_CREATED)
def record_club_attendance(club_id: int, payload: ClubAttendanceCreate, db: Session = Depends(get_db)):
    """Record attendance for a club on a specific date. Accepts a roster array."""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    records = []
    try:
        for item in payload.roster:
            status_val = "Present" if item.present else "Absent"
            att = ClubAttendance(
                club_id=club_id,
                student_name=item.student_name,
                roll_number=item.roll_number or "",
                section=item.section or "",
                status=status_val,
                attendance_date=payload.attendance_date,
            )
            db.add(att)
            records.append(att)

        db.commit()
        # refresh objects
        for r in records:
            db.refresh(r)

        return records
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error saving attendance: {str(e)}")


@router.get("/{club_id}/attendance", response_model=list[ClubAttendanceResponse])
def get_club_attendance(club_id: int, date: str | None = None, db: Session = Depends(get_db)):
    """Get attendance for a club; filter by ISO date string if provided."""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    query = db.query(ClubAttendance).filter(ClubAttendance.club_id == club_id)
    if date:
        # accept YYYY-MM-DD or full ISO; compare date portion
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(date)
            start = datetime(dt.year, dt.month, dt.day)
            end = datetime(dt.year, dt.month, dt.day, 23, 59, 59)
            query = query.filter(ClubAttendance.attendance_date >= start, ClubAttendance.attendance_date <= end)
        except Exception:
            pass

    results = query.order_by(ClubAttendance.attendance_date.desc()).all()
    return results


@router.get("/{club_id}/attendance/dates")
def get_club_attendance_dates(club_id: int, db: Session = Depends(get_db)):
    """Return list of dates for which attendance records exist for a club"""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    rows = (
        db.query(ClubAttendance.attendance_date)
        .filter(ClubAttendance.club_id == club_id)
        .group_by(ClubAttendance.attendance_date)
        .order_by(ClubAttendance.attendance_date.desc())
        .all()
    )
    # Flatten to ISO date strings
    return [r[0].isoformat() for r in rows]

@router.put("/{club_id}/members/{member_id}", response_model=ClubMemberResponse)
def update_member(
    club_id: int, member_id: int, member_update: ClubMemberUpdate, db: Session = Depends(get_db)
):
    """Update member information"""
    member = (
        db.query(ClubMember)
        .filter(ClubMember.id == member_id, ClubMember.club_id == club_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    try:
        update_data = member_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(member, key, value)
        db.commit()
        db.refresh(member)
        return member
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating member: {str(e)}")


@router.delete("/{club_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(club_id: int, member_id: int, db: Session = Depends(get_db)):
    """Remove a member from a club"""
    member = (
        db.query(ClubMember)
        .filter(ClubMember.id == member_id, ClubMember.club_id == club_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    try:
        db.delete(member)
        # Update member count
        club = db.query(Club).filter(Club.id == club_id).first()
        club.member_count = (
            db.query(ClubMember)
            .filter(ClubMember.club_id == club_id, ClubMember.is_active == True)
            .count()
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error removing member: {str(e)}")


# ==================== DASHBOARD / ANALYTICS ====================


@router.get("/dashboard/all-clubs-summary")
def get_all_clubs_summary(db: Session = Depends(get_db)):
    """Get summary statistics for all clubs"""
    clubs = db.query(Club).filter(Club.is_active == True).all()

    summary = {
        "total_clubs": len(clubs),
        "total_members": 0,
        "total_activities": 0,
        "activities_by_type": {},
        "clubs_by_category": {},
        "club_details": [],
    }

    for club in clubs:
        members = (
            db.query(ClubMember)
            .filter(ClubMember.club_id == club.id, ClubMember.is_active == True)
            .count()
        )
        activities = db.query(ClubActivity).filter(ClubActivity.club_id == club.id).all()

        summary["total_members"] += members
        summary["total_activities"] += len(activities)

        # Count by category
        category = club.category
        summary["clubs_by_category"][category] = summary["clubs_by_category"].get(category, 0) + 1

        # Count by activity type
        for activity in activities:
            activity_type = activity.activity_type
            summary["activities_by_type"][activity_type] = (
                summary["activities_by_type"].get(activity_type, 0) + 1
            )

        summary["club_details"].append(
            {
                "id": club.id,
                "name": club.name,
                "category": club.category,
                "member_count": members,
                "activity_count": len(activities),
                "president": club.president,
            }
        )

    return summary


@router.get("/dashboard/upcoming-events")
def get_upcoming_events(days: int = 30, db: Session = Depends(get_db)):
    """Get upcoming club events in the next N days"""
    from datetime import datetime, timedelta

    upcoming_date = datetime.utcnow() + timedelta(days=days)
    activities = (
        db.query(ClubActivity)
        .filter(
            ClubActivity.status.in_(["Planned", "Ongoing"]),
            ClubActivity.start_date >= datetime.utcnow(),
            ClubActivity.start_date <= upcoming_date,
        )
        .order_by(ClubActivity.start_date)
        .all()
    )

    events = []
    for activity in activities:
        club = db.query(Club).filter(Club.id == activity.club_id).first()
        events.append(
            {
                "activity_id": activity.id,
                "club_name": club.name,
                "club_id": club.id,
                "title": activity.title,
                "activity_type": activity.activity_type,
                "start_date": activity.start_date,
                "end_date": activity.end_date,
                "location": activity.location,
                "expected_participants": activity.expected_participants,
                "status": activity.status,
            }
        )

    return {"period_days": days, "total_upcoming_events": len(events), "events": events}


@router.get("/dashboard/club-activities-by-category")
def get_activities_by_category(db: Session = Depends(get_db)):
    """Get activity breakdown by club category"""
    clubs = db.query(Club).all()

    category_breakdown = {}
    for club in clubs:
        category = club.category
        if category not in category_breakdown:
            category_breakdown[category] = {
                "club_count": 0,
                "member_count": 0,
                "activity_count": 0,
                "clubs": [],
            }

        members = (
            db.query(ClubMember)
            .filter(ClubMember.club_id == club.id, ClubMember.is_active == True)
            .count()
        )
        activities = db.query(ClubActivity).filter(ClubActivity.club_id == club.id).count()

        category_breakdown[category]["club_count"] += 1
        category_breakdown[category]["member_count"] += members
        category_breakdown[category]["activity_count"] += activities
        category_breakdown[category]["clubs"].append(
            {"id": club.id, "name": club.name, "members": members, "activities": activities}
        )

    return {"total_categories": len(category_breakdown), "breakdown": category_breakdown}
