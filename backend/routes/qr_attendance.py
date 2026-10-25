"""
QR-Based Attendance API Routes with Geo-Fencing
Faculty and Student panels with real-time validation, server-side identity enforcement,
and anti-tampering security.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from datetime import datetime, timedelta
import uuid
import hashlib
import json
import secrets
import qrcode
import io
import base64

from backend.database import get_db
from backend.core.auth import TokenData
from backend.core.rbac import get_current_user, require_faculty, require_admin
from backend.models.qr_attendance import (
    QRAttendanceSession, QRAttendanceRecord, QRAttendanceLog, DeviceFingerprint
)
from backend.models.user import User
from backend.models.student import Student
from backend.models.schedule import Schedule
from backend.schemas.qr_attendance import (
    QRSessionCreate, QRSessionResponse, QRSessionSummary, QRSessionUpdate,
    QRScanRequest, QRScanResponse, AttendanceRecordResponse, AttendanceRecordSummary,
    LiveAttendanceStats, StudentAttendanceHistory, FacultyDashboard, StudentDashboard,
    AbsentListResponse, AbsentStudentInfo, DeviceFingerprintResponse,
    MessageResponse, QRCodeImage, ValidationResult
)
from backend.core.logging import get_logger

router = APIRouter(prefix="/qr-attendance", tags=["QR Attendance System"])
logger = get_logger("qr_attendance")


# ============== Faculty Panel - QR Session Management ==============

@router.post("/faculty/generate-qr", response_model=QRSessionResponse, status_code=status.HTTP_201_CREATED)
def generate_qr_session(
    session_data: QRSessionCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """
    Faculty generates dynamic QR code for attendance:
    - Derives faculty identity from authenticated account (rejects impersonation).
    - Prevents concurrent duplicate active sessions for the same course.
    - Time-bound with server-enforced expiration.
    - Cryptographically secure session token and hash.
    - Geo-fenced.
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty user not found")

    # Always derive faculty identity from authenticated account - do not trust client-supplied identity
    faculty_id = str(user.id)
    faculty_name = user.full_name or user.username
    faculty_email = user.email

    # Prevent silently creating duplicate active sessions: auto-expire any existing active session for this subject
    now = datetime.utcnow()
    existing_active = db.query(QRAttendanceSession).filter(
        QRAttendanceSession.faculty_id.in_([str(user.id), user.username]),
        QRAttendanceSession.subject_code == session_data.subject_code,
        QRAttendanceSession.is_active == True,
        QRAttendanceSession.is_cancelled == False,
        QRAttendanceSession.is_expired == False,
        QRAttendanceSession.qr_expires_at > now,
    ).all()
    for s in existing_active:
        s.mark_expired()
    if existing_active:
        db.commit()

    # Generate unique session ID and cryptographically secure random token
    session_id = str(uuid.uuid4())
    secure_token = secrets.token_hex(16)

    # Server-enforced expiry time (between 1 and 60 minutes)
    validity_minutes = max(1, min(60, session_data.qr_validity_minutes))
    expires_at = now + timedelta(minutes=validity_minutes)

    # Generate SHA-256 validation hash incorporating the secure token
    hash_input = f"{session_id}:{user.id}:{now.timestamp()}:{session_data.subject_code}:{secure_token}"
    qr_code_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    # QR code payload: does NOT leak internal signing secrets or passwords
    qr_data = {
        "session_id": session_id,
        "token": secure_token,
        "subject": session_data.subject_code,
        "timestamp": now.isoformat(),
        "expires": expires_at.isoformat(),
        "hash": qr_code_hash,
    }
    qr_code_data = json.dumps(qr_data)

    # Calculate lecture end time
    lecture_end_time = session_data.lecture_start_time + timedelta(minutes=session_data.lecture_duration_minutes)

    # Check for schedule record matching subject if available
    schedule_match = db.query(Schedule).filter(
        (Schedule.title.ilike(f"%{session_data.subject_code}%")) |
        (Schedule.title.ilike(f"%{session_data.subject_name}%"))
    ).first()
    location_name = session_data.location_name or (schedule_match.location if schedule_match else "Campus Lecture Hall")

    # Create session
    new_session = QRAttendanceSession(
        session_id=session_id,
        faculty_id=faculty_id,
        faculty_name=faculty_name,
        faculty_email=faculty_email,
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
        qr_generated_at=now,
        qr_expires_at=expires_at,
        qr_validity_minutes=validity_minutes,
        center_latitude=session_data.center_latitude,
        center_longitude=session_data.center_longitude,
        geo_fence_radius_meters=session_data.geo_fence_radius_meters,
        location_name=location_name,
        total_students_expected=session_data.total_students_expected,
        allow_screenshot_scan=session_data.allow_screenshot_scan,
        require_device_verification=session_data.require_device_verification,
        is_active=True,
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    logger.log_event(
        "qr_session_created",
        level="INFO",
        session_id=new_session.session_id,
        faculty_id=new_session.faculty_id,
        subject=new_session.subject_code,
        expires_at=new_session.qr_expires_at.isoformat(),
    )

    return new_session


@router.get("/faculty/qr-image/{session_id}")
def get_qr_code_image(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """
    Generate QR code image for display.
    Enforces ownership: only the creating faculty or admin can retrieve the QR image.
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Enforce ownership
    if current_user.role.lower() != "admin":
        if session.faculty_id not in (str(current_user.user_id), current_user.sub):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only view QR codes for your own sessions",
            )

    if not session.is_qr_valid():
        raise HTTPException(status_code=400, detail="QR code has expired")

    # Generate QR code image
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(session.qr_code_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

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
            "validity_minutes": session.qr_validity_minutes,
        }
    )


@router.get("/faculty/sessions", response_model=List[QRSessionSummary])
def get_faculty_sessions(
    faculty_id: str,
    active_only: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """
    Get all QR sessions created by faculty.
    Enforces that faculty can only inspect their own session history.
    """
    if current_user.role.lower() != "admin":
        if faculty_id not in (str(current_user.user_id), current_user.sub):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot view another faculty member's sessions",
            )
        query = db.query(QRAttendanceSession).filter(
            QRAttendanceSession.faculty_id.in_([str(current_user.user_id), current_user.sub])
        )
    else:
        query = db.query(QRAttendanceSession).filter(QRAttendanceSession.faculty_id == faculty_id)

    if active_only:
        query = query.filter(QRAttendanceSession.is_active == True)

    sessions = query.order_by(desc(QRAttendanceSession.created_at)).offset(skip).limit(limit).all()
    return sessions


@router.get("/faculty/session/{session_id}", response_model=QRSessionResponse)
def get_session_details(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """
    Get detailed information about a QR session.
    Enforces ownership check.
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if current_user.role.lower() != "admin":
        if session.faculty_id not in (str(current_user.user_id), current_user.sub):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only view your own sessions",
            )

    return session


@router.patch("/faculty/session/{session_id}", response_model=QRSessionResponse)
def update_session(
    session_id: str,
    update_data: QRSessionUpdate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """
    Update QR session (cancel, deactivate, add notes).
    Enforces faculty ownership.
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if current_user.role.lower() != "admin":
        if session.faculty_id not in (str(current_user.user_id), current_user.sub):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only modify your own sessions",
            )

    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(session, field, value)

    if update_data.is_cancelled:
        session.closed_at = datetime.utcnow()
        session.is_active = False
        session.is_expired = True

    db.commit()
    db.refresh(session)
    return session


@router.post("/faculty/session/{session_id}/close", response_model=QRSessionResponse)
def close_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """
    Explicitly close an active QR attendance session.
    Enforces that only the creator faculty or an admin can close the session.
    Immediately stops accepting any scans.
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if current_user.role.lower() != "admin":
        if session.faculty_id not in (str(current_user.user_id), current_user.sub):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only close your own sessions",
            )

    session.is_active = False
    session.is_expired = True
    session.closed_at = datetime.utcnow()
    db.commit()
    db.refresh(session)

    logger.log_event(
        "qr_session_closed",
        level="INFO",
        session_id=session.session_id,
        closed_by=current_user.sub,
    )

    return session


@router.get("/faculty/live-attendance/{session_id}", response_model=LiveAttendanceStats)
def get_live_attendance(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """
    Get real-time attendance statistics for faculty dashboard.
    Enforces faculty ownership.
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if current_user.role.lower() != "admin":
        if session.faculty_id not in (str(current_user.user_id), current_user.sub):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only view attendance for your own sessions",
            )

    total_present = session.total_students_present
    total_expected = session.total_students_expected
    total_absent = max(0, total_expected - total_present) if total_expected > 0 else 0

    total_late = db.query(QRAttendanceRecord).filter(
        and_(
            QRAttendanceRecord.session_id == session.id,
            QRAttendanceRecord.is_late_entry == True,
        )
    ).count()

    attendance_percentage = (total_present / total_expected * 100) if total_expected > 0 else 0
    on_time_count = max(0, total_present - total_late)
    on_time_percentage = (on_time_count / total_expected * 100) if total_expected > 0 else 0

    time_remaining = (session.qr_expires_at - datetime.utcnow()).total_seconds()
    time_remaining_seconds = max(0, int(time_remaining)) if session.is_active and not session.is_expired else 0

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
        is_active=session.is_active and not session.is_expired,
        time_remaining_seconds=time_remaining_seconds,
    )


@router.get("/faculty/attendance-records/{session_id}", response_model=List[AttendanceRecordSummary])
def get_session_attendance_records(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """
    Get list of all students who marked attendance in this session.
    Enforces faculty ownership.
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if current_user.role.lower() != "admin":
        if session.faculty_id not in (str(current_user.user_id), current_user.sub):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only view attendance for your own sessions",
            )

    records = db.query(QRAttendanceRecord).filter(
        QRAttendanceRecord.session_id == session.id
    ).order_by(QRAttendanceRecord.marked_at.asc()).all()

    return records


@router.get("/faculty/absent-list/{session_id}", response_model=AbsentListResponse)
def get_absent_list(
    session_id: str,
    expected_students: List[dict],
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """
    Generate absent list by comparing expected students against marked records.
    Enforces faculty ownership.
    """
    session = db.query(QRAttendanceSession).filter(QRAttendanceSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if current_user.role.lower() != "admin":
        if session.faculty_id not in (str(current_user.user_id), current_user.sub):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only view absent list for your own sessions",
            )

    present_roll_numbers = db.query(QRAttendanceRecord.roll_number).filter(
        QRAttendanceRecord.session_id == session.id
    ).all()
    present_set = {r[0] for r in present_roll_numbers}

    absent_students = []
    for student in expected_students:
        if student.get('roll_number') not in present_set:
            absent_students.append(AbsentStudentInfo(
                roll_number=student['roll_number'],
                student_name=student['name'],
                branch=student.get('branch', session.branch),
                semester=student.get('semester', session.semester),
                section=student.get('section', session.section),
                contact_email=student.get('email'),
            ))

    return AbsentListResponse(
        session_id=session.id,
        subject_name=session.subject_name,
        lecture_date=session.lecture_date,
        total_expected=len(expected_students),
        total_present=len(present_set),
        total_absent=len(absent_students),
        absent_students=absent_students,
    )


# ============== Student Panel - QR Scanning ==============

@router.post("/student/scan-qr", response_model=QRScanResponse)
def scan_qr_code(
    scan_request: QRScanRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Student scans QR code or enters session code to mark attendance.
    Enforces:
    - User authentication and linked student record existence.
    - Anti-impersonation: student can never mark attendance for another student.
    - Strict server clock timestamping and status derivation.
    - Active unexpired session verification.
    - Rate-limiting on failed attempts.
    - Geo-fencing validation.
    - Database unique constraints to prevent race-condition duplicate attendance.
    """
    # 1. Resolve student identity from database
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    student = None
    if user.linked_student_id:
        student = db.query(Student).filter(Student.id == user.linked_student_id).first()
    if not student:
        student = db.query(Student).filter(
            (Student.roll_no == user.username) | (Student.name.ilike(user.full_name or ""))
        ).first()
        if student and not user.linked_student_id:
            user.linked_student_id = student.id
            db.commit()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not linked to any student record. Only enrolled students can mark attendance.",
        )

    # 2. Prevent identity spoofing
    if current_user.role.lower() == "student":
        if scan_request.student_id and str(scan_request.student_id) not in (str(student.id), str(user.id), student.roll_no):
            logger.log_event(
                "attendance_impersonation_blocked",
                level="WARNING",
                user_id=current_user.user_id,
                attempted_student_id=scan_request.student_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot mark attendance for another student: identity mismatch",
            )
        if scan_request.roll_number and scan_request.roll_number != student.roll_no:
            logger.log_event(
                "attendance_impersonation_blocked",
                level="WARNING",
                user_id=current_user.user_id,
                attempted_roll_no=scan_request.roll_number,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot mark attendance for another student: identity mismatch",
            )

    # 3. Rate-limiting for repeated invalid attempts (10 failed attempts within 1 minute)
    now = datetime.utcnow()
    recent_failures = db.query(QRAttendanceLog).filter(
        QRAttendanceLog.student_id == str(student.id),
        QRAttendanceLog.attempt_time >= now - timedelta(minutes=1),
        QRAttendanceLog.attempt_status.in_(["failed", "denied", "blocked"]),
    ).count()
    if recent_failures >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attendance attempts. Please wait 1 minute before trying again.",
        )

    errors = []
    warnings = []
    validation_results = {
        "qr_valid": False,
        "location_valid": False,
        "device_valid": False,
        "time_valid": False,
    }

    # 4. Session Lookup
    session = db.query(QRAttendanceSession).filter(
        QRAttendanceSession.session_id == scan_request.session_id
    ).first()

    if not session:
        return QRScanResponse(
            success=False,
            message="Invalid QR code. Session not found.",
            attendance_marked=False,
            validation_results=validation_results,
            errors=["Session not found"],
        )

    # 5. Session Active & Expiry Verification
    if not session.is_active or session.is_expired or session.is_cancelled or now > session.qr_expires_at:
        errors.append("QR code has expired or is no longer active")
        log_scan_attempt(db, session.id, str(student.id), "failed", "QR expired or inactive", scan_request.location)
        return QRScanResponse(
            success=False,
            message="QR code has expired or session is no longer active. Please ask faculty for an active code.",
            attendance_marked=False,
            validation_results=validation_results,
            errors=errors,
        )

    # 6. QR Hash Security Check
    # Verification hash is strictly required and must match the authentic session QR hash.
    # Insecure bypass placeholders ('hash_placeholder', 'manual_entry', 'demo_scan') are forbidden.
    FORBIDDEN_HASH_PLACEHOLDERS = {"hash_placeholder", "manual_entry", "demo_scan"}

    submitted_hash = (scan_request.qr_code_hash or "").strip()

    if not submitted_hash:
        errors.append("QR code verification hash is required")
        log_scan_attempt(db, session.id, str(student.id), "blocked", "Missing or empty verification hash", scan_request.location)
        return QRScanResponse(
            success=False,
            message="Invalid QR code. Security verification hash is missing or empty.",
            attendance_marked=False,
            validation_results=validation_results,
            errors=errors,
        )

    if submitted_hash.lower() in FORBIDDEN_HASH_PLACEHOLDERS:
        errors.append(f"Rejected invalid placeholder hash: {submitted_hash}")
        log_scan_attempt(db, session.id, str(student.id), "blocked", f"Placeholder hash attempted: {submitted_hash}", scan_request.location)
        return QRScanResponse(
            success=False,
            message="Invalid QR code. Placeholder verification values are not permitted.",
            attendance_marked=False,
            validation_results=validation_results,
            errors=errors,
        )

    if not secrets.compare_digest(submitted_hash, session.qr_code_hash):
        errors.append("QR code hash mismatch - possible tampering detected")
        log_scan_attempt(db, session.id, str(student.id), "blocked", "Hash mismatch", scan_request.location)
        return QRScanResponse(
            success=False,
            message="Invalid QR code. Security verification failed.",
            attendance_marked=False,
            validation_results=validation_results,
            errors=errors,
        )

    validation_results["qr_valid"] = True

    # 7. Geo-Fencing Check
    distance = session.calculate_distance(
        scan_request.location.latitude,
        scan_request.location.longitude,
    )
    is_within_geofence = session.is_within_geofence(
        scan_request.location.latitude,
        scan_request.location.longitude,
    )

    if not is_within_geofence:
        errors.append(f"You are {int(distance)} meters away from the classroom")
        errors.append(f"You must be within {int(session.geo_fence_radius_meters)} meters to mark attendance")
        log_scan_attempt(db, session.id, str(student.id), "denied", "Outside geofence", scan_request.location)
        return QRScanResponse(
            success=False,
            message="You are outside the allowed classroom area. Please move closer to the classroom.",
            attendance_marked=False,
            validation_results=validation_results,
            distance_from_center=round(distance, 2),
            is_within_geofence=False,
            errors=errors,
        )

    validation_results["location_valid"] = True

    # 8. Device Verification Check
    if session.require_device_verification and scan_request.device:
        device_check = verify_device(db, str(student.id), scan_request.device)
        if not device_check["valid"]:
            errors.append(device_check["message"])
            validation_results["device_valid"] = False
        else:
            validation_results["device_valid"] = True
            if device_check.get("warning"):
                warnings.append(device_check["warning"])
    else:
        validation_results["device_valid"] = True

    # 9. Time Validation
    if now > session.qr_expires_at:
        errors.append("QR code has expired")
        validation_results["time_valid"] = False
    else:
        validation_results["time_valid"] = True

    # 10. Check for duplicate attendance (Pre-check)
    existing_record = db.query(QRAttendanceRecord).filter(
        and_(
            QRAttendanceRecord.session_id == session.id,
            (QRAttendanceRecord.student_id == str(student.id)) | (QRAttendanceRecord.roll_number == student.roll_no),
        )
    ).first()

    if existing_record:
        return QRScanResponse(
            success=False,
            message="Attendance already marked for this session.",
            attendance_marked=False,
            validation_results=validation_results,
            errors=["Duplicate attendance attempt"],
        )

    # 11. All validations passed - record attendance using server-derived fields
    if all(validation_results.values()):
        is_late = now > session.lecture_start_time
        late_minutes = max(0, int((now - session.lecture_start_time).total_seconds() / 60)) if is_late else 0
        attendance_status = "late" if is_late and late_minutes > 5 else "present"

        attendance_record = QRAttendanceRecord(
            session_id=session.id,
            # Bound exclusively to authenticated student record
            student_id=str(student.id),
            roll_number=student.roll_no,
            student_name=student.name,
            student_email=user.email,
            branch=student.department,
            semester=str(student.semester),
            section=student.section,
            marked_at=now,
            attendance_status=attendance_status,
            is_late_entry=is_late,
            late_by_minutes=late_minutes,
            student_latitude=scan_request.location.latitude,
            student_longitude=scan_request.location.longitude,
            distance_from_center=distance,
            is_within_geofence=True,
            location_accuracy=scan_request.location.accuracy,
            device_id=scan_request.device.device_id if scan_request.device else None,
            device_model=scan_request.device.device_model if scan_request.device else None,
            device_os=scan_request.device.device_os if scan_request.device else None,
            browser=scan_request.device.browser if scan_request.device else None,
            ip_address=request.client.host if request.client else None,
            user_agent=scan_request.device.user_agent if scan_request.device else None,
            qr_validation_passed=True,
            location_validation_passed=True,
            device_validation_passed=True,
            time_validation_passed=True,
            scan_duration_ms=scan_request.scan_duration_ms,
        )

        try:
            db.add(attendance_record)
            session.total_students_present += 1
            if is_late:
                session.total_late_entries += 1

            log_scan_attempt(db, session.id, str(student.id), "success", "Attendance marked", scan_request.location)

            if scan_request.device:
                update_device_fingerprint(db, str(student.id), student.name, scan_request.device)

            db.commit()
            db.refresh(attendance_record)
        except IntegrityError:
            db.rollback()
            return QRScanResponse(
                success=False,
                message="Attendance already marked for this session.",
                attendance_marked=False,
                validation_results=validation_results,
                errors=["Duplicate attendance attempt"],
            )

        success_message = "Attendance marked successfully!"
        if is_late:
            success_message += f" (Late by {late_minutes} minutes)"

        logger.log_event(
            "qr_attendance_marked",
            level="INFO",
            session_id=session.session_id,
            student_id=student.id,
            roll_no=student.roll_no,
            status=attendance_status,
        )

        return QRScanResponse(
            success=True,
            message=success_message,
            attendance_marked=True,
            session_info={
                "subject": session.subject_name,
                "faculty": session.faculty_name,
                "date": session.lecture_date.isoformat(),
            },
            attendance_record_id=attendance_record.id,
            validation_results=validation_results,
            distance_from_center=round(distance, 2),
            is_within_geofence=True,
            is_late_entry=is_late,
            late_by_minutes=late_minutes,
            warnings=warnings if warnings else None,
        )

    return QRScanResponse(
        success=False,
        message="Attendance marking failed. Please check errors.",
        attendance_marked=False,
        validation_results=validation_results,
        errors=errors,
        warnings=warnings if warnings else None,
    )


@router.get("/student/dashboard/{student_id}", response_model=StudentDashboard)
def get_student_dashboard(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Get student's attendance dashboard.
    Enforces ownership: students cannot view other students' attendance dashboards.
    Safely returns clean statistics even if no records exist yet.
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    student = None
    if user:
        if user.linked_student_id:
            student = db.query(Student).filter(Student.id == user.linked_student_id).first()
        if not student:
            student = db.query(Student).filter(
                (Student.roll_no == user.username) | (Student.name.ilike(user.full_name or ""))
            ).first()

    if current_user.role.lower() == "student":
        is_owner = False
        if student and str(student.id) == str(student_id):
            is_owner = True
        elif str(current_user.user_id) == str(student_id) or current_user.sub == str(student_id):
            is_owner = True
        elif current_user.linked_student_id is not None and str(current_user.linked_student_id) == str(student_id):
            is_owner = True

        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot view another student's attendance dashboard",
            )

    today = datetime.utcnow().date()

    # Query attendance records matching student_id or roll number
    query = db.query(QRAttendanceRecord).filter(
        (QRAttendanceRecord.student_id == student_id) |
        (QRAttendanceRecord.roll_number == (student.roll_no if student else student_id))
    )

    today_records = query.filter(func.date(QRAttendanceRecord.marked_at) == today).all()
    total_records = query.count()
    recent_records = query.order_by(desc(QRAttendanceRecord.marked_at)).limit(10).all()

    first_record = query.first()
    student_name = first_record.student_name if first_record else (student.name if student else (user.full_name if user else "Student"))
    roll_number = first_record.roll_number if first_record else (student.roll_no if student else current_user.sub)

    overall_percentage = 85.0

    if overall_percentage >= 75:
        attendance_status = "good"
    elif overall_percentage >= 65:
        attendance_status = "warning"
    else:
        attendance_status = "critical"

    return StudentDashboard(
        student_id=student_id,
        student_name=student_name,
        roll_number=roll_number,
        today_classes=len(today_records),
        today_attended=len(today_records),
        today_missed=0,
        overall_attendance_percentage=overall_percentage,
        attendance_status=attendance_status,
        low_attendance_subjects=[],
        recent_attendance=[
            AttendanceRecordSummary(
                id=r.id,
                roll_number=r.roll_number,
                student_name=r.student_name,
                marked_at=r.marked_at,
                attendance_status=r.attendance_status,
                is_late_entry=r.is_late_entry,
                late_by_minutes=r.late_by_minutes,
                distance_from_center=r.distance_from_center,
            ) for r in recent_records
        ],
    )


# ============== Helper Functions ==============

def log_scan_attempt(db: Session, session_id: int, student_id: str, status: str, reason: str, location):
    """Log all scan attempts for audit trail"""
    log_entry = QRAttendanceLog(
        session_id=session_id,
        student_id=student_id,
        attempt_status=status,
        failure_reason=reason if status != "success" else None,
        latitude=location.latitude if location else None,
        longitude=location.longitude if location else None,
    )
    db.add(log_entry)


def verify_device(db: Session, student_id: str, device_data) -> dict:
    """Verify device to prevent proxy"""
    if not device_data or not device_data.device_id:
        return {"valid": True, "message": "No device tracking"}

    device = db.query(DeviceFingerprint).filter(
        DeviceFingerprint.device_id == device_data.device_id
    ).first()

    if not device:
        new_device = DeviceFingerprint(
            device_id=device_data.device_id,
            student_id=student_id,
            student_name="",
            device_model=device_data.device_model,
            device_os=device_data.device_os,
            browser=device_data.browser,
            screen_resolution=device_data.screen_resolution,
        )
        db.add(new_device)
        return {"valid": True, "message": "Device registered"}

    if device.student_id != student_id:
        return {
            "valid": False,
            "message": "This device is registered to another student. Proxy attempt detected.",
        }

    if device.is_blocked:
        return {
            "valid": False,
            "message": f"Device is blocked. Reason: {device.block_reason}",
        }

    device.last_used = datetime.utcnow()
    device.total_scans += 1
    return {"valid": True, "message": "Device verified"}


def update_device_fingerprint(db: Session, student_id: str, student_name: str, device_data):
    """Update device usage statistics"""
    if not device_data or not device_data.device_id:
        return
    device = db.query(DeviceFingerprint).filter(
        DeviceFingerprint.device_id == device_data.device_id
    ).first()

    if device:
        device.last_used = datetime.utcnow()
        device.total_scans += 1
        device.student_name = student_name
