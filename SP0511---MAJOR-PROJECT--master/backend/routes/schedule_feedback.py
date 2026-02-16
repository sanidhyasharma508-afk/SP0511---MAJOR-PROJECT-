from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from backend.database import get_db
from backend.schemas.schedule_feedback import (
    ScheduleFeedbackCreate,
    ScheduleFeedbackOut,
    ScheduleFeedbackUpdate,
    AnnouncementCreate,
    AnnouncementOut,
    AnnouncementUpdate,
    NotificationResponse,
)
from backend.models.schedule_feedback import ScheduleFeedback, Announcement

router = APIRouter(prefix="/schedule-management", tags=["Schedule Management"])


def generate_notification_message(feedback: ScheduleFeedback) -> dict:
    """Generate professional notification messages for different platforms"""

    # WhatsApp Message
    whatsapp_msg = f"""📢 *Schedule Feedback Alert*

🔴 *Issue Type:* {feedback.issue_type}
👤 *Reported By:* {feedback.name} ({feedback.roll_number})
⏰ *Preferred Timing:* {feedback.preferred_timing or 'Not specified'}

💬 *Comments:*
{feedback.additional_comments or 'No additional comments'}

📅 *Reported On:* {feedback.created_at.strftime('%d %B %Y, %I:%M %p')}

_Please review and take necessary action. Thank you!_"""

    # Telegram Message
    telegram_msg = f"""🔔 <b>Schedule Feedback Notification</b>

<b>Issue:</b> {feedback.issue_type}
<b>Student:</b> {feedback.name} ({feedback.roll_number})
<b>Preferred Timing:</b> {feedback.preferred_timing or 'Not specified'}

<b>Additional Details:</b>
{feedback.additional_comments or 'No additional comments provided'}

<i>Reported: {feedback.created_at.strftime('%d %B %Y at %I:%M %p')}</i>

Action required: Please review and coordinate with the team."""

    # Email Subject & Body
    email_subject = f"Schedule Issue Report: {feedback.issue_type} - {feedback.roll_number}"

    email_body = f"""Dear Team,

A new schedule-related issue has been reported by a student. Please find the details below:

ISSUE DETAILS
═══════════════════════════════════════════
Issue Type: {feedback.issue_type}
Student Name: {feedback.name}
Roll Number: {feedback.roll_number}
Preferred Timing: {feedback.preferred_timing or 'Not specified'}

ADDITIONAL COMMENTS
═══════════════════════════════════════════
{feedback.additional_comments or 'No additional comments provided'}

SUBMISSION DETAILS
═══════════════════════════════════════════
Reported On: {feedback.created_at.strftime('%d %B %Y at %I:%M %p')}
Status: {feedback.status.upper()}

RECOMMENDED ACTIONS
═══════════════════════════════════════════
1. Review the reported timing conflict
2. Coordinate with relevant faculty members
3. Communicate alternative timings to students
4. Update the master schedule if necessary

Please acknowledge receipt of this notification and provide updates on resolution progress.

Best regards,
MBM University Schedule Management System
"""

    return {
        "whatsapp_message": whatsapp_msg,
        "telegram_message": telegram_msg,
        "email_subject": email_subject,
        "email_body": email_body,
    }


# ===================== FEEDBACK ROUTES =====================

@router.post("/feedback", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def submit_schedule_feedback(feedback: ScheduleFeedbackCreate, db: Session = Depends(get_db)):
    """Submit schedule feedback/issue and generate notifications"""

    # Create feedback record
    new_feedback = ScheduleFeedback(
        name=feedback.name,
        roll_number=feedback.roll_number,
        issue_type=feedback.issue_type,
        preferred_timing=feedback.preferred_timing,
        additional_comments=feedback.additional_comments,
        status="pending",
    )

    db.add(new_feedback)
    db.commit()
    db.refresh(new_feedback)

    # Generate notification messages
    notifications = generate_notification_message(new_feedback)

    return NotificationResponse(
        message=f"Feedback submitted successfully! ID: {new_feedback.id}",
        whatsapp_message=notifications["whatsapp_message"],
        telegram_message=notifications["telegram_message"],
        email_subject=notifications["email_subject"],
        email_body=notifications["email_body"],
    )


@router.get("/feedback", response_model=List[ScheduleFeedbackOut])
def get_all_feedback(
    status_filter: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get all schedule feedback with optional status filter"""
    query = db.query(ScheduleFeedback)

    if status_filter:
        query = query.filter(ScheduleFeedback.status == status_filter)

    feedbacks = query.order_by(ScheduleFeedback.created_at.desc()).offset(skip).limit(limit).all()
    return feedbacks


@router.get("/feedback/{feedback_id}", response_model=ScheduleFeedbackOut)
def get_feedback_by_id(feedback_id: int, db: Session = Depends(get_db)):
    """Get specific feedback by ID"""
    feedback = db.query(ScheduleFeedback).filter(ScheduleFeedback.id == feedback_id).first()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    return feedback


@router.patch("/feedback/{feedback_id}", response_model=ScheduleFeedbackOut)
def update_feedback_status(
    feedback_id: int,
    update_data: ScheduleFeedbackUpdate,
    db: Session = Depends(get_db),
):
    """Update feedback status"""
    feedback = db.query(ScheduleFeedback).filter(ScheduleFeedback.id == feedback_id).first()

    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    if update_data.status:
        feedback.status = update_data.status

    if update_data.resolved_at:
        feedback.resolved_at = update_data.resolved_at
    elif update_data.status == "resolved":
        feedback.resolved_at = datetime.utcnow()

    db.commit()
    db.refresh(feedback)
    return feedback


# ===================== ANNOUNCEMENT ROUTES =====================

@router.post("/announcements", response_model=AnnouncementOut, status_code=status.HTTP_201_CREATED)
def create_announcement(announcement: AnnouncementCreate, db: Session = Depends(get_db)):
    """Create a new announcement (Faculty to Students)"""

    new_announcement = Announcement(
        title=announcement.title,
        content=announcement.content,
        author=announcement.author,
        priority=announcement.priority,
        target_audience=announcement.target_audience,
        expires_at=announcement.expires_at,
        is_active=1,
    )

    db.add(new_announcement)
    db.commit()
    db.refresh(new_announcement)
    return new_announcement


@router.get("/announcements", response_model=List[AnnouncementOut])
def get_all_announcements(
    active_only: bool = True,
    priority: str = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get all announcements with filters"""
    query = db.query(Announcement)

    if active_only:
        query = query.filter(Announcement.is_active == 1)

    if priority:
        query = query.filter(Announcement.priority == priority)

    # Filter out expired announcements
    if active_only:
        now = datetime.utcnow()
        query = query.filter(
            (Announcement.expires_at.is_(None)) | (Announcement.expires_at > now)
        )

    announcements = query.order_by(Announcement.created_at.desc()).offset(skip).limit(limit).all()
    return announcements


@router.get("/announcements/{announcement_id}", response_model=AnnouncementOut)
def get_announcement_by_id(announcement_id: int, db: Session = Depends(get_db)):
    """Get specific announcement by ID"""
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()

    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return announcement


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementOut)
def update_announcement(
    announcement_id: int,
    update_data: AnnouncementUpdate,
    db: Session = Depends(get_db),
):
    """Update an announcement"""
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()

    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    if update_data.title is not None:
        announcement.title = update_data.title
    if update_data.content is not None:
        announcement.content = update_data.content
    if update_data.priority is not None:
        announcement.priority = update_data.priority
    if update_data.is_active is not None:
        announcement.is_active = update_data.is_active
    if update_data.expires_at is not None:
        announcement.expires_at = update_data.expires_at

    db.commit()
    db.refresh(announcement)
    return announcement


@router.delete("/announcements/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_announcement(announcement_id: int, db: Session = Depends(get_db)):
    """Soft delete an announcement (set is_active to 0)"""
    announcement = db.query(Announcement).filter(Announcement.id == announcement_id).first()

    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    announcement.is_active = 0
    db.commit()
    return None


# ===================== STATS & ANALYTICS =====================

@router.get("/feedback/stats/summary")
def get_feedback_stats(db: Session = Depends(get_db)):
    """Get feedback statistics"""
    total = db.query(ScheduleFeedback).count()
    pending = db.query(ScheduleFeedback).filter(ScheduleFeedback.status == "pending").count()
    resolved = db.query(ScheduleFeedback).filter(ScheduleFeedback.status == "resolved").count()
    in_progress = db.query(ScheduleFeedback).filter(ScheduleFeedback.status == "in_progress").count()

    return {
        "total_feedback": total,
        "pending": pending,
        "resolved": resolved,
        "in_progress": in_progress,
        "resolution_rate": round((resolved / total * 100) if total > 0 else 0, 2),
    }
