from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from typing import List, Optional

from backend.database import get_db
from backend.models.club import Club, ClubActivity, ClubMember, ClubAttendance
from backend.models.student import Student
from backend.models.user import User
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
from backend.core.auth import TokenData
from backend.core.rbac import get_current_user, require_staff, require_faculty, require_admin

router = APIRouter(prefix="/clubs", tags=["clubs"])


# ==================== HELPERS ====================

def resolve_student_from_user(current_user: TokenData, db: Session) -> Optional[Student]:
    """Resolve authenticated user to an enrolled Student record"""
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        return None
    if user.linked_student_id:
        student = db.query(Student).filter(Student.id == user.linked_student_id).first()
        if student:
            return student
    student = db.query(Student).filter(
        (Student.roll_no == user.username) | (Student.name.ilike(user.full_name or ""))
    ).first()
    if student and not user.linked_student_id:
        user.linked_student_id = student.id
        db.commit()
    return student


def check_club_permission(club: Club, current_user: TokenData, db: Session) -> bool:
    """Check if user has administrative rights over this club"""
    role = current_user.role.lower()
    if role == "admin":
        return True
    if role in ["staff", "faculty"]:
        if club.created_by and club.created_by == current_user.user_id:
            return True
        if club.advisor == current_user.sub or (club.advisor_email and club.advisor_email == current_user.email):
            return True
        if not club.created_by:
            return True
        return False
    return False


# ==================== CLUB ROUTES ====================

@router.post("/", response_model=ClubResponse, status_code=status.HTTP_201_CREATED)
def create_club(
    club: ClubCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_staff),
):
    """Create a new club (Staff or Admin required)"""
    try:
        db_club = Club(**club.model_dump())
        db_club.created_by = current_user.user_id
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


@router.get("/my-memberships", response_model=List[ClubMemberResponse])
def get_my_memberships(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Get all active club memberships for the authenticated student."""
    student = resolve_student_from_user(current_user, db)
    if not student:
        return []

    memberships = (
        db.query(ClubMember)
        .filter(ClubMember.student_id == student.id, ClubMember.is_active == True)
        .all()
    )
    for m in memberships:
        c = db.query(Club).filter(Club.id == m.club_id).first()
        if c:
            m.club_name = c.name
    return memberships


@router.get("/memberships/student/{student_id}", response_model=List[ClubMemberResponse])
def get_student_memberships(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Get club memberships for a student. Enforces ownership: students can only view their own."""
    if current_user.role.lower() == "student":
        student = resolve_student_from_user(current_user, db)
        if not student or student.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students can only view their own club memberships",
            )

    memberships = (
        db.query(ClubMember)
        .filter(ClubMember.student_id == student_id, ClubMember.is_active == True)
        .all()
    )
    for m in memberships:
        c = db.query(Club).filter(Club.id == m.club_id).first()
        if c:
            m.club_name = c.name
    return memberships


@router.get("/{club_id}", response_model=ClubDetailResponse)
def get_club(club_id: int, db: Session = Depends(get_db)):
    """Get club details with activities and members"""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    return club


@router.put("/{club_id}", response_model=ClubResponse)
def update_club(
    club_id: int,
    club_update: ClubUpdate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Update club information (Staff/Admin or Club Advisor required)"""
    db_club = db.query(Club).filter(Club.id == club_id).first()
    if not db_club:
        raise HTTPException(status_code=404, detail="Club not found")

    if current_user.role.lower() == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot edit clubs",
        )

    if not check_club_permission(db_club, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Unauthorized to modify this club",
        )

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
def delete_club(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Delete a club (Admin or authorized Club Advisor required)"""
    db_club = db.query(Club).filter(Club.id == club_id).first()
    if not db_club:
        raise HTTPException(status_code=404, detail="Club not found")

    if current_user.role.lower() == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot delete clubs",
        )

    if current_user.role.lower() != "admin":
        if not check_club_permission(db_club, current_user, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only administrators or club advisors can delete clubs",
            )

    try:
        db.delete(db_club)
        db.commit()
        return None
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
def create_activity(
    club_id: int,
    activity: ClubActivityCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Create a new club activity/event (Staff or Club Advisor required)"""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    if current_user.role.lower() == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot create club activities without advisor authorization",
        )

    if not check_club_permission(club, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Unauthorized to manage activities for this club",
        )

    try:
        db_activity = ClubActivity(**activity.model_dump())
        db_activity.club_id = club_id
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
    current_user: TokenData = Depends(get_current_user),
):
    """Update activity details (Staff/Admin required)"""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    if current_user.role.lower() == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot update club activities",
        )

    if not check_club_permission(club, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Unauthorized to manage this club's activities",
        )

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
def delete_activity(
    club_id: int,
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Delete an activity (Staff/Admin required)"""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    if current_user.role.lower() == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot delete club activities",
        )

    if not check_club_permission(club, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Unauthorized to manage this club's activities",
        )

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
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error deleting activity: {str(e)}")


# ==================== STUDENT JOIN & LEAVE ROUTES ====================

@router.post("/{club_id}/join", response_model=ClubMemberResponse, status_code=status.HTTP_201_CREATED)
def join_club(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Authenticated student joins a club."""
    student = resolve_student_from_user(current_user, db)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not linked to any student record. Only enrolled students can join clubs.",
        )

    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")

    if not club.is_active or not club.accepting_members:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Club is currently not accepting new members")

    existing = db.query(ClubMember).filter(
        ClubMember.club_id == club_id,
        ClubMember.student_id == student.id,
        ClubMember.is_active == True,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student is already a member of this club")

    try:
        new_member = ClubMember(
            club_id=club_id,
            student_id=student.id,
            position="Member",
            is_active=True,
            join_date=datetime.utcnow(),
        )
        db.add(new_member)
        club.member_count = (
            db.query(ClubMember)
            .filter(ClubMember.club_id == club_id, ClubMember.is_active == True)
            .count()
            + 1
        )
        db.commit()
        db.refresh(new_member)
        new_member.club_name = club.name
        return new_member
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student is already a member of this club")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error joining club: {str(e)}")


@router.post("/{club_id}/leave", status_code=status.HTTP_200_OK)
def leave_club(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Authenticated student leaves a club."""
    student = resolve_student_from_user(current_user, db)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not linked to any student record.",
        )

    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Club not found")

    member = db.query(ClubMember).filter(
        ClubMember.club_id == club_id,
        ClubMember.student_id == student.id,
        ClubMember.is_active == True,
    ).first()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not an active member of this club")

    try:
        db.delete(member)
        club.member_count = max(0, (
            db.query(ClubMember)
            .filter(ClubMember.club_id == club_id, ClubMember.is_active == True)
            .count()
            - 1
        ))
        db.commit()
        return {"success": True, "message": f"Left {club.name} successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error leaving club: {str(e)}")


# ==================== CLUB MEMBER ROUTES ====================

@router.post(
    "/{club_id}/members", response_model=ClubMemberResponse, status_code=status.HTTP_201_CREATED
)
def add_member(
    club_id: int,
    member: ClubMemberCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Add a member to a club."""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    if current_user.role.lower() == "student":
        student = resolve_student_from_user(current_user, db)
        if not student or student.id != member.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot add membership on behalf of another student",
            )
    else:
        target_student = db.query(Student).filter(Student.id == member.student_id).first()
        if not target_student:
            raise HTTPException(status_code=404, detail="Student not found")

    existing = (
        db.query(ClubMember)
        .filter(ClubMember.club_id == club_id, ClubMember.student_id == member.student_id, ClubMember.is_active == True)
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
        db_member.club_name = club.name
        return db_member
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Student is already a member of this club")
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
    for m in members:
        m.club_name = club.name
    return members


@router.put("/{club_id}/members/{member_id}", response_model=ClubMemberResponse)
def update_member(
    club_id: int,
    member_id: int,
    member_update: ClubMemberUpdate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Update member information (Staff or Club Advisor required)"""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    if current_user.role.lower() == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Students cannot update member positions or status",
        )

    if not check_club_permission(club, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Unauthorized to manage this club's members",
        )

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
        member.club_name = club.name
        return member
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error updating member: {str(e)}")


@router.delete("/{club_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    club_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Remove a member from a club"""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    member = (
        db.query(ClubMember)
        .filter(ClubMember.id == member_id, ClubMember.club_id == club_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if current_user.role.lower() == "student":
        student = resolve_student_from_user(current_user, db)
        if not student or student.id != member.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students cannot remove other members",
            )
    else:
        if not check_club_permission(club, current_user, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Unauthorized to manage this club's memberships",
            )

    try:
        db.delete(member)
        club.member_count = max(0, (
            db.query(ClubMember)
            .filter(ClubMember.club_id == club_id, ClubMember.is_active == True)
            .count()
            - 1
        ))
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error removing member: {str(e)}")


# ==================== CLUB ATTENDANCE ====================

@router.post("/{club_id}/attendance", response_model=List[ClubAttendanceResponse], status_code=status.HTTP_201_CREATED)
def record_club_attendance(
    club_id: int,
    payload: ClubAttendanceCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """Record attendance for a club on a specific date (Faculty/Staff/Admin required)."""
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
        for r in records:
            db.refresh(r)

        return records
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error saving attendance: {str(e)}")


@router.get("/{club_id}/attendance", response_model=List[ClubAttendanceResponse])
def get_club_attendance(
    club_id: int,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Get attendance for a club; filter by ISO date string if provided (Authenticated users)."""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")

    query = db.query(ClubAttendance).filter(ClubAttendance.club_id == club_id)
    if date:
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
    return [r[0].isoformat() for r in rows]


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

        category = club.category
        summary["clubs_by_category"][category] = summary["clubs_by_category"].get(category, 0) + 1

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
    from datetime import timedelta

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
                "club_name": club.name if club else "Campus Club",
                "club_id": activity.club_id,
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
