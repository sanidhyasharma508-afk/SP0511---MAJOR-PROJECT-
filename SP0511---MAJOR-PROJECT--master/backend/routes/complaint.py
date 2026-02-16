from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas.complaint import ComplaintCreate, ComplaintOut, ComplaintUpdate
from backend.models.complaint import Complaint
from backend.core.event_bus import EventType, event_bus, Event
from datetime import datetime

router = APIRouter(prefix="/complaints", tags=["Complaints"])


@router.post("/", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
def file_complaint(complaint: ComplaintCreate, db: Session = Depends(get_db)):
    """File a new complaint"""
    valid_categories = ["Academic", "Conduct", "Health", "Other"]
    if complaint.category not in valid_categories:
        raise HTTPException(
            status_code=400, detail=f"Invalid category. Must be one of {valid_categories}"
        )

    new_complaint = Complaint(
        student_id=complaint.student_id,
        title=complaint.title,
        description=complaint.description,
        category=complaint.category,
        priority=complaint.priority or "Normal",
    )
    db.add(new_complaint)
    db.commit()
    db.refresh(new_complaint)

    # Publish event to trigger complaint triage agent
    event = Event(
        EventType.COMPLAINT_FILED,
        {
            "complaint_id": new_complaint.id,
            "student_id": complaint.student_id,
            "title": complaint.title,
            "description": complaint.description,
            "category": complaint.category,
        },
    )
    event_bus.publish(event)

    return new_complaint


@router.get("/", response_model=list[ComplaintOut])
def get_all_complaints(db: Session = Depends(get_db)):
    """Get all complaints"""
    return db.query(Complaint).all()


@router.get("/student/{student_id}", response_model=list[ComplaintOut])
def get_student_complaints(student_id: int, db: Session = Depends(get_db)):
    """Get complaints filed by a specific student"""
    complaints = db.query(Complaint).filter(Complaint.student_id == student_id).all()
    if not complaints:
        raise HTTPException(status_code=404, detail="No complaints found")
    return complaints


@router.get("/{complaint_id}", response_model=ComplaintOut)
def get_complaint(complaint_id: int, db: Session = Depends(get_db)):
    """Get a specific complaint"""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint


@router.put("/{complaint_id}", response_model=ComplaintOut)
def update_complaint(complaint_id: int, complaint: ComplaintUpdate, db: Session = Depends(get_db)):
    """Update a complaint"""
    db_complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not db_complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if complaint.title:
        db_complaint.title = complaint.title
    if complaint.description:
        db_complaint.description = complaint.description
    if complaint.status:
        db_complaint.status = complaint.status
    if complaint.priority:
        db_complaint.priority = complaint.priority

    db_complaint.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_complaint)
    return db_complaint


@router.delete("/{complaint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_complaint(complaint_id: int, db: Session = Depends(get_db)):
    """Delete a complaint"""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    db.delete(complaint)
    db.commit()
    return None
