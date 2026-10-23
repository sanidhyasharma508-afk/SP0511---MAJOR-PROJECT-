from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from backend.database import get_db
from backend.schemas.schedule import ScheduleCreate, ScheduleOut, ScheduleUpdate
from backend.models.schedule import Schedule
from backend.models.student import Student
from backend.core.event_bus import EventType, event_bus, Event
from datetime import datetime
from backend.core.auth import TokenData
from backend.core.rbac import get_current_user, require_staff, require_admin

router = APIRouter(prefix="/schedules", tags=["Schedules"])


@router.post("/", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
def create_schedule(
    schedule: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_staff),
):
    """Create a new schedule/event (Staff or Admin required)"""

    if schedule.end_date <= schedule.start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    valid_types = ["Class", "Exam", "Event", "Holiday"]
    if schedule.event_type not in valid_types:
        raise HTTPException(
            status_code=400, detail=f"Invalid event type. Must be one of {valid_types}"
        )

    # Check for duplicate schedule entries
    existing_dup = (
        db.query(Schedule)
        .filter(
            Schedule.title == schedule.title,
            Schedule.event_type == schedule.event_type,
            Schedule.start_date == schedule.start_date,
            Schedule.end_date == schedule.end_date,
            Schedule.location == schedule.location,
            Schedule.is_active == 1,
        )
        .first()
    )
    if existing_dup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An identical active schedule entry already exists for this time and location.",
        )

    new_schedule = Schedule(
        title=schedule.title,
        description=schedule.description,
        event_type=schedule.event_type,
        start_date=schedule.start_date,
        end_date=schedule.end_date,
        location=schedule.location,
        audience=schedule.audience,
    )
    db.add(new_schedule)
    db.commit()
    db.refresh(new_schedule)

    # Publish event to trigger schedule conflict agent
    event = Event(
        EventType.SCHEDULE_UPDATED,
        {
            "schedule_id": new_schedule.id,
            "title": schedule.title,
            "event_type": schedule.event_type,
            "location": schedule.location,
            "start_date": str(schedule.start_date),
            "end_date": str(schedule.end_date),
        },
    )
    event_bus.publish(event)

    return new_schedule


@router.get("/", response_model=list[ScheduleOut])
def get_all_schedules(db: Session = Depends(get_db)):
    """Get all schedules"""
    return db.query(Schedule).all()


@router.get("/active", response_model=list[ScheduleOut])
def get_active_schedules(db: Session = Depends(get_db)):
    """Get all active schedules"""
    return db.query(Schedule).filter(Schedule.is_active == 1).all()


@router.get("/my-schedule", response_model=list[ScheduleOut])
def get_my_schedule(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Get relevant institutional schedules for the authenticated user.
    Students receive general and department-specific schedules.
    Personal study tasks remain distinct under the /study-tasks API.
    """
    query = db.query(Schedule).filter(Schedule.is_active == 1)
    role = (current_user.role or "").lower()

    if role == "student":
        student = None
        if current_user.linked_student_id is not None:
            student = db.query(Student).filter(Student.id == current_user.linked_student_id).first()
        if not student and current_user.sub:
            student = db.query(Student).filter(Student.roll_no == current_user.sub).first()
        if not student and current_user.user_id:
            student = db.query(Student).filter(Student.id == current_user.user_id).first()

        if student and student.department:
            dept_pattern = f"%{student.department}%"
            sem_pattern = f"%Semester {student.semester}%"
            query = query.filter(
                or_(
                    Schedule.audience == None,
                    Schedule.audience == "",
                    Schedule.audience.ilike("All%"),
                    Schedule.audience.ilike(dept_pattern),
                    Schedule.audience.ilike(sem_pattern),
                )
            )
        else:
            query = query.filter(
                or_(
                    Schedule.audience == None,
                    Schedule.audience == "",
                    Schedule.audience.ilike("All%"),
                )
            )

    return query.order_by(Schedule.start_date.asc()).all()


@router.get("/{schedule_id}", response_model=ScheduleOut)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Get a specific schedule"""
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.put("/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    schedule_id: int,
    schedule: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_staff),
):
    """Update a schedule (Staff or Admin required)"""
    db_schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if schedule.title:
        db_schedule.title = schedule.title
    if schedule.description is not None:
        db_schedule.description = schedule.description
    if schedule.event_type:
        db_schedule.event_type = schedule.event_type
    if schedule.start_date:
        db_schedule.start_date = schedule.start_date
    if schedule.end_date:
        db_schedule.end_date = schedule.end_date
    if schedule.location is not None:
        db_schedule.location = schedule.location
    if schedule.audience is not None:
        db_schedule.audience = schedule.audience
    if schedule.is_active is not None:
        db_schedule.is_active = schedule.is_active

    db_schedule.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_schedule)
    return db_schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_admin),
):
    """Delete a schedule (Admin required)"""
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(schedule)
    db.commit()
    return None
