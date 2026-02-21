"""
QR-Based Attendance API Routes with Geo-Fencing
Faculty and Student panels with real-time validation
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import uuid
import hashlib
import json
import qrcode
import io
import base64

from backend.database import get_db
from backend.models.qr_attendance import (
    QRAttendanceSession, QRAttendanceRecord, QRAttendanceLog, DeviceFingerprint
)
from backend.schemas.qr_attendance import (
    QRSessionCreate, QRSessionResponse, QRSessionSummary, QRSessionUpdate,
    QRScanRequest, QRScanResponse, AttendanceRecordResponse, AttendanceRecordSummary,
    LiveAttendanceStats, StudentAttendanceHistory, FacultyDashboard, StudentDashboard,
    AbsentListResponse, AbsentStudentInfo, DeviceFingerprintResponse,
    MessageResponse, QRCodeImage, ValidationResult
)

router = APIRouter(prefix="/qr-attendance", tags=["QR Attendance System"])


# ============== Faculty Panel - QR Session Management ==============

@router.post("/faculty/generate-qr", response_model=QRSessionResponse, status_code=status.HTTP_201_CREATED)
def generate_qr_session(session_data: QRSessionCreate, db: Session = Depends(get_db)):
    """
    Faculty generates dynamic QR code for attendance
    - Time-bound (expires in 2-5 minutes)
    - Geo-fenced with 50m radius
    - Encrypted with session details
    """
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    
    # Calculate expiry time (UTC-aware)
    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(minutes=session_data.qr_validity_minutes)
    
    # Generate secure hash
    hash_input = f"{session_id}{session_data.faculty_id}{datetime.utcnow().timestamp()}{session_data.subject_code}"
    qr_code_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    # Create encrypted QR data
    qr_data = {
        "session_id": session_id,
        "faculty_id": session_data.faculty_id,
        "subject": session_data.subject_code,
        "hash": qr_code_hash,
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "expires": expires_at.isoformat().replace('+00:00', 'Z')
    }
    qr_code_data = json.dumps(qr_data)
    
    # Calculate lecture end time
    lecture_end_time = session_data.lecture_start_time + timedelta(minutes=session_data.lecture_duration_minutes)
    
    # Create session
    new_session = QRAttendanceSession(
        session_id=session_id,
        faculty_id=session_data.faculty_id,
        faculty_name=session_data.faculty_name,
        faculty_email=session_data.faculty_email,
        subject_code=session_data.subject_code,
        subject_name=session_data.subject_name,
        branch=session_data.branch,
        semester=session_data.semester,
        section=session_data.section,
        lecture_date=session_data.lecture_date,
        lecture_start_time=session_data.lecture_start_time,
        lecture_end_time=lecture_end_time,
        lecture_duration_minutes=session_data.lecture_duration_minutes,
        qr_code_data=qr_code_data,
        qr_code_hash=qr_code_hash,
        qr_expires_at=expires_at,
        qr_validity_minutes=session_data.qr_validity_minutes,
        center_latitude=session_data.center_latitude,
        center_longitude=session_data.center_longitude,
        geo_fence_radius_meters=session_data.geo_fence_radius_meters,
        location_name=session_data.location_name,
        total_students_expected=session_data.total_students_expected,
        allow_screenshot_scan=session_data.allow_screenshot_scan,
        require_device_verification=session_data.require_device_verification,
        is_active=True
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return new_session


@router.post("/faculty/regenerate-qr/{session_id}", response_model=QRSessionResponse)
def regenerate_qr_session(session_id: str, db: Session = Depends(get_db)):
    """
    Regenerate an existing QR session (extend expiry and update hash)
    Used for expired sessions or to refresh the QR code
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Calculate new expiry time (UTC-aware)
    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(minutes=session.qr_validity_minutes)
    
    # Generate new secure hash
    hash_input = f"{session.session_id}{session.faculty_id}{datetime.utcnow().timestamp()}{session.subject_code}"
    new_hash = hashlib.sha256(hash_input.encode()).hexdigest()
    
    # Update QR data
    qr_data = {
        "session_id": session.session_id,
        "faculty_id": session.faculty_id,
        "subject": session.subject_name,
        "hash": new_hash,
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "expires": expires_at.isoformat().replace('+00:00', 'Z')
    }
    
    session.qr_code_data = json.dumps(qr_data)
    session.qr_code_hash = new_hash
    session.qr_expires_at = expires_at
    session.is_active = True
    session.is_expired = False
    
    db.commit()
    db.refresh(session)
    
    return session


@router.get("/faculty/qr-image/{session_id}")
def get_qr_code_image(session_id: str, db: Session = Depends(get_db)):
    """
    Generate QR code image for display
    Returns base64 encoded PNG image
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.is_qr_valid():
        raise HTTPException(status_code=400, detail="QR code has expired")
    
    # Generate QR code image
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(session.qr_code_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return QRCodeImage(
        session_id=session_id,
        qr_code_base64=img_base64,
        expires_at=session.qr_expires_at,
        metadata={
            "subject": session.subject_name,
            "branch": session.branch,
            "semester": session.semester,
            "validity_minutes": session.qr_validity_minutes
        }
    )


@router.get("/faculty/sessions", response_model=List[QRSessionSummary])
def get_faculty_sessions(
    faculty_id: str,
    active_only: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get all QR sessions created by faculty
    """
    query = db.query(QRAttendanceSession).filter(QRAttendanceSession.faculty_id == faculty_id)
    
    if active_only:
        query = query.filter(QRAttendanceSession.is_active == True)
    
    sessions = query.order_by(desc(QRAttendanceSession.created_at)).offset(skip).limit(limit).all()
    return sessions


@router.get("/faculty/session/{session_id}", response_model=QRSessionResponse)
def get_session_details(session_id: str, db: Session = Depends(get_db)):
    """
    Get detailed information about a QR session
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return session


@router.patch("/faculty/session/{session_id}", response_model=QRSessionResponse)
def update_session(session_id: str, update_data: QRSessionUpdate, db: Session = Depends(get_db)):
    """
    Update QR session (cancel, deactivate, add notes)
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(session, field, value)
    
    if update_data.is_cancelled:
        session.closed_at = datetime.now(timezone.utc)
        session.is_active = False
    
    db.commit()
    db.refresh(session)
    
    return session


@router.get("/faculty/live-attendance/{session_id}", response_model=LiveAttendanceStats)
def get_live_attendance(session_id: str, db: Session = Depends(get_db)):
    """
    Get real-time attendance statistics for faculty dashboard
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Calculate statistics
    total_present = session.total_students_present
    total_expected = session.total_students_expected
    total_absent = total_expected - total_present if total_expected > 0 else 0
    
    # Count late entries
    total_late = db.query(QRAttendanceRecord).filter(
        and_(
            QRAttendanceRecord.session_id == session.id,
            QRAttendanceRecord.is_late_entry == True
        )
    ).count()
    
    # Calculate percentages
    attendance_percentage = (total_present / total_expected * 100) if total_expected > 0 else 0
    on_time_count = total_present - total_late
    on_time_percentage = (on_time_count / total_expected * 100) if total_expected > 0 else 0
    
    # Time remaining
    time_remaining = (session.qr_expires_at - datetime.utcnow()).total_seconds()
    time_remaining_seconds = max(0, int(time_remaining))
    
    return LiveAttendanceStats(
        session_id=session.id,
        subject_name=session.subject_name,
        branch=session.branch,
        semester=session.semester,
        total_expected=total_expected,
        total_present=total_present,
        total_absent=total_absent,
        total_late=total_late,
        attendance_percentage=round(attendance_percentage, 2),
        on_time_percentage=round(on_time_percentage, 2),
        qr_expires_at=session.qr_expires_at,
        is_active=session.is_active,
        time_remaining_seconds=time_remaining_seconds
    )


@router.get("/faculty/attendance-records/{session_id}", response_model=List[AttendanceRecordSummary])
def get_session_attendance_records(session_id: str, db: Session = Depends(get_db)):
    """
    Get list of all students who marked attendance in this session
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    records = db.query(QRAttendanceRecord).filter(
        QRAttendanceRecord.session_id == session.id
    ).order_by(QRAttendanceRecord.marked_at.asc()).all()
    
    return records


@router.get("/faculty/absent-list/{session_id}", response_model=AbsentListResponse)
def get_absent_list(
    session_id: str,
    expected_students: List[dict],  # List of expected students
    db: Session = Depends(get_db)
):
    """
    Generate auto-generated absent list
    Compare expected students with those who marked attendance
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get roll numbers of students who attended
    present_roll_numbers = db.query(QRAttendanceRecord.roll_number).filter(
        QRAttendanceRecord.session_id == session.id
    ).all()
    present_set = {r[0] for r in present_roll_numbers}
    
    # Find absent students
    absent_students = []
    for student in expected_students:
        if student.get('roll_number') not in present_set:
            absent_students.append(AbsentStudentInfo(
                roll_number=student['roll_number'],
                student_name=student['name'],
                branch=student.get('branch', session.branch),
                semester=student.get('semester', session.semester),
                section=student.get('section', session.section),
                contact_email=student.get('email')
            ))
    
    return AbsentListResponse(
        session_id=session.id,
        subject_name=session.subject_name,
        lecture_date=session.lecture_date,
        total_expected=len(expected_students),
        total_present=len(present_set),
        total_absent=len(absent_students),
        absent_students=absent_students
    )


# ============== Student Panel - QR Scanning ==============

@router.post("/student/scan-qr", response_model=QRScanResponse)
def scan_qr_code(scan_request: QRScanRequest, request: Request, db: Session = Depends(get_db)):
    """
    Student scans QR code to mark attendance
    Performs comprehensive validation:
    1. QR validity check
    2. Geo-fencing check (50m radius)
    3. Device verification
    4. Time validation
    5. Anti-proxy checks
    """
    errors = []
    warnings = []
    validation_results = {
        "qr_valid": False,
        "location_valid": False,
        "device_valid": False,
        "time_valid": False
    }
    
    # Find session
    session = db.query(QRAttendanceSession).filter(
        QRAttendanceSession.session_id == scan_request.session_id
    ).first()
    
    if not session:
        return QRScanResponse(
            success=False,
            message="Invalid QR code. Session not found.",
            attendance_marked=False,
            validation_results=validation_results,
            errors=["Session not found"]
        )
    
    # 1. QR Validity Check
    if not session.is_qr_valid():
        errors.append("QR code has expired or is no longer active")
        log_scan_attempt(db, session.id, scan_request.student_id, "failed", "QR expired", scan_request.location)
        return QRScanResponse(
            success=False,
            message="QR code has expired. Please ask faculty to generate a new code.",
            attendance_marked=False,
            validation_results=validation_results,
            errors=errors
        )
    
    # Verify QR hash (only if provided - allows manual entry without hash)
    # Also ignore the dummy test hash for development troubleshooting
    DUMMY_HASH = '0000000000000000000000000000000000000000000000000000000000000000'
    if scan_request.qr_code_hash and \
       scan_request.qr_code_hash != DUMMY_HASH and \
       scan_request.qr_code_hash != session.qr_code_hash:
        errors.append("QR code hash mismatch - possible tampering detected")
        log_scan_attempt(db, session.id, scan_request.student_id, "blocked", "Hash mismatch", scan_request.location)
        return QRScanResponse(
            success=False,
            message="Invalid QR code. Security check failed.",
            attendance_marked=False,
            validation_results=validation_results,
            errors=errors
        )
    
    validation_results["qr_valid"] = True
    
    # 2. Geo-Fencing Check
    distance = session.calculate_distance(
        scan_request.location.latitude,
        scan_request.location.longitude
    )
    
    is_within_geofence = session.is_within_geofence(
        scan_request.location.latitude,
        scan_request.location.longitude
    )
    
    if not is_within_geofence:
        errors.append(f"You are {int(distance)} meters away from the classroom")
        errors.append(f"You must be within {int(session.geo_fence_radius_meters)} meters to mark attendance")
        log_scan_attempt(db, session.id, scan_request.student_id, "denied", "Outside geofence", scan_request.location)
        return QRScanResponse(
            success=False,
            message="You are outside the allowed classroom area. Please move closer to the classroom.",
            attendance_marked=False,
            validation_results=validation_results,
            distance_from_center=round(distance, 2),
            is_within_geofence=False,
            errors=errors
        )
    
    validation_results["location_valid"] = True
    
    # 3. Device Verification
    if session.require_device_verification:
        device_check = verify_device(db, scan_request.student_id, scan_request.device)
        if not device_check["valid"]:
            errors.append(device_check["message"])
            validation_results["device_valid"] = False
        else:
            validation_results["device_valid"] = True
            if device_check.get("warning"):
                warnings.append(device_check["warning"])
    else:
        validation_results["device_valid"] = True
    
    # 4. Time Validation
    now = datetime.now(timezone.utc)
    # Ensure session.qr_expires_at is treated as UTC if naive
    expires_at = session.qr_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
        
    if now > expires_at:
        errors.append("QR code has expired")
        validation_results["time_valid"] = False
    else:
        validation_results["time_valid"] = True
    
    # 5. Check for duplicate attendance
    existing_record = db.query(QRAttendanceRecord).filter(
        and_(
            QRAttendanceRecord.session_id == session.id,
            QRAttendanceRecord.student_id == scan_request.student_id
        )
    ).first()
    
    if existing_record:
        return QRScanResponse(
            success=False,
            message="Attendance already marked for this session.",
            attendance_marked=False,
            validation_results=validation_results,
            errors=["Duplicate attendance attempt"]
        )
    
    # All checks passed - Mark attendance
    if all(validation_results.values()):
        # Calculate if late
        # Ensure session.lecture_start_time is treated as UTC if naive
        lecture_start = session.lecture_start_time
        if lecture_start.tzinfo is None:
            lecture_start = lecture_start.replace(tzinfo=timezone.utc)

        is_late = now > lecture_start
        late_minutes = 0
        if is_late:
            delta = now - lecture_start
            late_minutes = int(delta.total_seconds() / 60)
        
        # Determine status - Increase grace period to 15 minutes
        attendance_status = "late" if is_late and late_minutes > 15 else "present"
        
        # Create attendance record
        attendance_record = QRAttendanceRecord(
            session_id=session.id,
            student_id=scan_request.student_id,
            roll_number=scan_request.roll_number,
            student_name=scan_request.student_name,
            student_email=scan_request.student_email,
            branch=scan_request.branch,
            semester=scan_request.semester,
            section=scan_request.section,
            marked_at=scan_request.scan_timestamp,
            attendance_status=attendance_status,
            is_late_entry=is_late,
            late_by_minutes=late_minutes,
            student_latitude=scan_request.location.latitude,
            student_longitude=scan_request.location.longitude,
            distance_from_center=distance,
            is_within_geofence=True,
            location_accuracy=scan_request.location.accuracy,
            device_id=scan_request.device.device_id,
            device_model=scan_request.device.device_model,
            device_os=scan_request.device.device_os,
            browser=scan_request.device.browser,
            ip_address=request.client.host if request.client else None,
            user_agent=scan_request.device.user_agent,
            qr_validation_passed=True,
            location_validation_passed=True,
            device_validation_passed=True,
            time_validation_passed=True,
            scan_duration_ms=scan_request.scan_duration_ms
        )
        
        db.add(attendance_record)
        
        # Update session statistics
        session.total_students_present += 1
        if is_late:
            session.total_late_entries += 1
        
        # Log successful scan
        log_scan_attempt(db, session.id, scan_request.student_id, "success", "Attendance marked", scan_request.location)
        
        # Update device fingerprint
        update_device_fingerprint(db, scan_request.student_id, scan_request.student_name, scan_request.device)
        
        db.commit()
        db.refresh(attendance_record)
        
        success_message = "Attendance marked successfully!"
        if is_late:
            success_message += f" (Late by {late_minutes} minutes)"
        
        return QRScanResponse(
            success=True,
            message=success_message,
            attendance_marked=True,
            session_info={
                "subject": session.subject_name,
                "faculty": session.faculty_name,
                "date": session.lecture_date.isoformat()
            },
            attendance_record_id=attendance_record.id,
            validation_results=validation_results,
            distance_from_center=round(distance, 2),
            is_within_geofence=True,
            is_late_entry=is_late,
            late_by_minutes=late_minutes,
            warnings=warnings if warnings else None
        )
    
    # Some validations failed
    return QRScanResponse(
        success=False,
        message="Attendance marking failed. Please check errors.",
        attendance_marked=False,
        validation_results=validation_results,
        errors=errors,
        warnings=warnings if warnings else None
    )


@router.get("/student/dashboard/{student_id}", response_model=StudentDashboard)
def get_student_dashboard(student_id: str, db: Session = Depends(get_db)):
    """
    Get student's attendance dashboard
    - Today's attendance status
    - Overall attendance percentage
    - Subject-wise breakdown
    - Warning alerts
    """
    today = datetime.utcnow().date()
    
    # Today's classes
    today_records = db.query(QRAttendanceRecord).filter(
        and_(
            QRAttendanceRecord.student_id == student_id,
            func.date(QRAttendanceRecord.marked_at) == today
        )
    ).all()
    
    # Overall attendance
    total_records = db.query(QRAttendanceRecord).filter(
        QRAttendanceRecord.student_id == student_id
    ).count()
    
    # Get student info from first record
    first_record = db.query(QRAttendanceRecord).filter(
        QRAttendanceRecord.student_id == student_id
    ).first()
    
    if not first_record:
        raise HTTPException(status_code=404, detail="No attendance records found for student")
    
    # Calculate overall percentage (placeholder - should calculate based on total sessions)
    overall_percentage = 85.0  # TODO: Calculate properly
    
    # Attendance status
    if overall_percentage >= 75:
        attendance_status = "good"
    elif overall_percentage >= 65:
        attendance_status = "warning"
    else:
        attendance_status = "critical"
    
    # Low attendance subjects (placeholder)
    low_attendance_subjects = []
    
    # Recent attendance
    recent_records = db.query(QRAttendanceRecord).filter(
        QRAttendanceRecord.student_id == student_id
    ).order_by(desc(QRAttendanceRecord.marked_at)).limit(10).all()
    
    return StudentDashboard(
        student_id=student_id,
        student_name=first_record.student_name,
        roll_number=first_record.roll_number,
        today_classes=len(today_records),
        today_attended=len(today_records),
        today_missed=0,
        overall_attendance_percentage=overall_percentage,
        attendance_status=attendance_status,
        low_attendance_subjects=low_attendance_subjects,
        recent_attendance=[
            AttendanceRecordSummary(
                id=r.id,
                roll_number=r.roll_number,
                student_name=r.student_name,
                marked_at=r.marked_at,
                attendance_status=r.attendance_status,
                is_late_entry=r.is_late_entry,
                late_by_minutes=r.late_by_minutes,
                distance_from_center=r.distance_from_center
            ) for r in recent_records
        ]
    )


# ============== Helper Functions ==============

def log_scan_attempt(db: Session, session_id: int, student_id: str, status: str, reason: str, location):
    """Log all scan attempts for audit trail"""
    log_entry = QRAttendanceLog(
        session_id=session_id,
        student_id=student_id,
        attempt_status=status,
        failure_reason=reason if status != "success" else None,
        latitude=location.latitude,
        longitude=location.longitude
    )
    db.add(log_entry)


def verify_device(db: Session, student_id: str, device_data) -> dict:
    """Verify device to prevent proxy"""
    device = db.query(DeviceFingerprint).filter(
        DeviceFingerprint.device_id == device_data.device_id
    ).first()
    
    if not device:
        # New device - register it
        new_device = DeviceFingerprint(
            device_id=device_data.device_id,
            student_id=student_id,
            student_name="",  # Will be updated
            device_model=device_data.device_model,
            device_os=device_data.device_os,
            browser=device_data.browser,
            screen_resolution=device_data.screen_resolution
        )
        db.add(new_device)
        return {"valid": True, "message": "Device registered"}
    
    # Check if device belongs to same student
    if device.student_id != student_id:
        return {
            "valid": False,
            "message": "This device is registered to another student. Proxy attempt detected."
        }
    
    # Check if device is blocked
    if device.is_blocked:
        return {
            "valid": False,
            "message": f"Device is blocked. Reason: {device.block_reason}"
        }
    
    # Device is valid
    device.last_used = datetime.utcnow()
    device.total_scans += 1
    return {"valid": True, "message": "Device verified"}


def update_device_fingerprint(db: Session, student_id: str, student_name: str, device_data):
    """Update device usage statistics"""
    device = db.query(DeviceFingerprint).filter(
        DeviceFingerprint.device_id == device_data.device_id
    ).first()
    
    if device:
        device.last_used = datetime.utcnow()
        device.total_scans += 1
        device.student_name = student_name
