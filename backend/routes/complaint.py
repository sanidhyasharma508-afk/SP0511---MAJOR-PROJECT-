from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
from typing import List, Optional

from backend.database import get_db
from backend.schemas.complaint import ComplaintCreate, ComplaintOut, ComplaintUpdate, ComplaintHistoryOut
from backend.models.complaint import Complaint, ComplaintHistory
from backend.models.student import Student
from backend.core.event_bus import EventType, event_bus, Event
from backend.core.rbac import get_current_user, require_staff, require_admin
from backend.core.auth import TokenData

router = APIRouter(prefix="/complaints", tags=["Complaints"])

VALID_TRANSITIONS = {
    "Pending": ["Under Review", "In Progress", "Rejected", "Closed"],
    "Under Review": ["In Progress", "Resolved", "Rejected", "Closed"],
    "In Progress": ["Resolved", "Under Review", "Closed"],
    "Resolved": ["Closed", "In Progress"],
    "Rejected": ["Closed", "Under Review"],
    "Closed": ["In Progress", "Under Review"],
}


def resolve_student_id(current_user: TokenData, db: Session) -> Optional[int]:
    """
    Safely resolve the authenticated user's linked student ID.
    Checks linked_student_id on TokenData first, then looks up by roll number (current_user.sub).
    Never treats current_user.user_id as Student.id.
    """
    if current_user.linked_student_id is not None:
        st = db.query(Student).filter(Student.id == current_user.linked_student_id).first()
        if st:
            return st.id
    if current_user.sub:
        st = db.query(Student).filter(Student.roll_no == current_user.sub).first()
        if st:
            return st.id
    return None


@router.post("/", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
def file_complaint(
    complaint: ComplaintCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    File a new complaint.
    Enforces student identity: students cannot file complaints under another student's ID.
    """
    valid_categories = ["Academic", "Conduct", "Health", "Other"]
    if complaint.category not in valid_categories:
        raise HTTPException(
            status_code=400, detail=f"Invalid category. Must be one of {valid_categories}"
        )

    # Validate student ownership if caller is a student
    student_id_to_use = complaint.student_id
    if current_user.role.lower() == "student":
        resolved_student_id = resolve_student_id(current_user, db)
        if not resolved_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No student record linked to the authenticated user account.",
            )

        if complaint.student_id is not None and complaint.student_id != resolved_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot file complaint on behalf of another student",
            )
        student_id_to_use = resolved_student_id
    else:
        if student_id_to_use is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="student_id is required when staff files a complaint",
            )

    new_complaint = Complaint(
        student_id=student_id_to_use,
        title=complaint.title,
        description=complaint.description,
        category=complaint.category,
        priority=complaint.priority or "Normal",
        status="Pending",
    )
    db.add(new_complaint)
    db.commit()
    db.refresh(new_complaint)

    # Record creation in ComplaintHistory
    history = ComplaintHistory(
        complaint_id=new_complaint.id,
        old_status=None,
        new_status="Pending",
        remarks="Complaint filed",
        changed_by_user_id=current_user.user_id,
        changed_by_name=current_user.sub or current_user.email,
        created_at=datetime.utcnow()
    )
    db.add(history)
    db.commit()

    # Publish event to trigger complaint triage agent
    event = Event(
        EventType.COMPLAINT_FILED,
        {
            "complaint_id": new_complaint.id,
            "student_id": new_complaint.student_id,
            "title": complaint.title,
            "description": complaint.description,
            "category": complaint.category,
        },
    )
    event_bus.publish(event)

    return new_complaint


@router.get("/", response_model=list[ComplaintOut])
def get_all_complaints(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Get complaints. Staff/Admin view all complaints; students view only their own.
    """
    if current_user.role.lower() in ["admin", "staff", "faculty"]:
        return db.query(Complaint).all()

    # Filter strictly for student's own complaints
    resolved_student_id = resolve_student_id(current_user, db)
    if not resolved_student_id:
        return []

    return db.query(Complaint).filter(Complaint.student_id == resolved_student_id).all()


@router.get("/student/{student_id}", response_model=list[ComplaintOut])
def get_student_complaints(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Get complaints filed by a specific student.
    Enforces ownership: students can only view their own complaints.
    """
    if current_user.role.lower() == "student":
        resolved_student_id = resolve_student_id(current_user, db)
        if resolved_student_id is None or resolved_student_id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students can only view their own complaints",
            )

    complaints = db.query(Complaint).filter(Complaint.student_id == student_id).all()
    return complaints


@router.get("/{complaint_id}", response_model=ComplaintOut)
def get_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Get a specific complaint"""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if current_user.role.lower() == "student":
        resolved_student_id = resolve_student_id(current_user, db)
        if resolved_student_id is None or resolved_student_id != complaint.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only view your own complaints",
            )

    return complaint


@router.get("/{complaint_id}/history", response_model=list[ComplaintHistoryOut])
def get_complaint_history(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """Get audit history for a specific complaint"""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if current_user.role.lower() == "student":
        resolved_student_id = resolve_student_id(current_user, db)
        if resolved_student_id is None or resolved_student_id != complaint.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only view history for your own complaints",
            )

    history_records = db.query(ComplaintHistory).filter(
        ComplaintHistory.complaint_id == complaint_id
    ).order_by(ComplaintHistory.created_at.asc()).all()

    return history_records


@router.put("/{complaint_id}", response_model=ComplaintOut)
def update_complaint(
    complaint_id: int,
    complaint: ComplaintUpdate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Update a complaint. Staff and Admin can update status, priority, and resolution notes.
    """
    db_complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not db_complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    is_staff = current_user.role.lower() in ["admin", "staff", "faculty"]

    if not is_staff:
        resolved_student_id = resolve_student_id(current_user, db)
        if resolved_student_id is None or resolved_student_id != db_complaint.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot edit another student's complaint",
            )

        if complaint.status or complaint.priority or complaint.resolution_notes or complaint.assigned_to:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only staff or administrators can update complaint status or priority",
            )

    if complaint.title:
        db_complaint.title = complaint.title
    if complaint.description:
        db_complaint.description = complaint.description

    if is_staff:
        if complaint.status and complaint.status != db_complaint.status:
            allowed = VALID_TRANSITIONS.get(db_complaint.status, [])
            if complaint.status not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status transition from '{db_complaint.status}' to '{complaint.status}'"
                )
            old_status = db_complaint.status
            db_complaint.status = complaint.status

            # Record status change in ComplaintHistory
            history = ComplaintHistory(
                complaint_id=db_complaint.id,
                old_status=old_status,
                new_status=complaint.status,
                remarks=complaint.resolution_notes or f"Status changed to {complaint.status}",
                changed_by_user_id=current_user.user_id,
                changed_by_name=current_user.sub or current_user.email,
                created_at=datetime.utcnow()
            )
            db.add(history)

        if complaint.priority:
            db_complaint.priority = complaint.priority
        if complaint.resolution_notes:
            db_complaint.resolution_notes = complaint.resolution_notes
        if complaint.assigned_to:
            db_complaint.assigned_to = complaint.assigned_to

    db_complaint.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_complaint)
    return db_complaint


@router.delete("/{complaint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_admin),
):
    """Delete a complaint (Admin only)"""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    db.delete(complaint)
    db.commit()
    return None
