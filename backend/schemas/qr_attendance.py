"""
Pydantic schemas for QR-Based Attendance System
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============== Faculty Panel Schemas ==============

class QRSessionCreate(BaseModel):
    """Schema for faculty to create QR attendance session"""
    faculty_id: str = Field(..., min_length=1)
    faculty_name: str = Field(..., min_length=2)
    faculty_email: Optional[EmailStr] = None
    
    subject_code: str = Field(..., min_length=2)
    subject_name: str = Field(..., min_length=3)
    branch: str = Field(..., min_length=2)
    semester: int = Field(..., ge=1, le=8)
    section: Optional[str] = None
    
    lecture_date: datetime
    lecture_start_time: datetime
    lecture_duration_minutes: int = Field(default=60, ge=30, le=180)
    
    center_latitude: float = Field(..., ge=-90, le=90)
    center_longitude: float = Field(..., ge=-180, le=180)
    geo_fence_radius_meters: float = Field(default=50.0, ge=10, le=200)
    location_name: Optional[str] = None
    
    qr_validity_minutes: int = Field(default=3, ge=1, le=10)
    total_students_expected: int = Field(default=0, ge=0)
    
    allow_screenshot_scan: bool = False
    require_device_verification: bool = True


class QRSessionResponse(BaseModel):
    """Response after creating QR session"""
    id: int
    session_id: str
    faculty_name: str
    subject_code: str
    subject_name: str
    branch: str
    semester: int
    section: Optional[str]
    
    qr_code_data: str
    qr_code_hash: str
    qr_generated_at: datetime
    qr_expires_at: datetime
    qr_validity_minutes: int
    
    center_latitude: float
    center_longitude: float
    geo_fence_radius_meters: float
    location_name: Optional[str]
    
    is_active: bool
    is_expired: bool
    total_students_expected: int
    total_students_present: int
    
    created_at: datetime

    class Config:
        from_attributes = True


class QRSessionSummary(BaseModel):
    """Simplified QR session info for lists"""
    id: int
    session_id: str
    subject_name: str
    branch: str
    semester: int
    lecture_date: datetime
    qr_generated_at: datetime
    qr_expires_at: datetime
    is_active: bool
    is_expired: bool
    total_students_present: int
    total_students_expected: int

    class Config:
        from_attributes = True


class QRSessionUpdate(BaseModel):
    """Update QR session status"""
    is_active: Optional[bool] = None
    is_cancelled: Optional[bool] = None
    notes: Optional[str] = None


# ============== Student Panel Schemas ==============

class StudentLocationData(BaseModel):
    """Student's GPS location data"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = Field(None, ge=0)  # GPS accuracy in meters


class DeviceData(BaseModel):
    """Student's device information"""
    device_id: str = Field(..., min_length=10)
    device_model: Optional[str] = None
    device_os: Optional[str] = None
    browser: Optional[str] = None
    screen_resolution: Optional[str] = None
    user_agent: Optional[str] = None


class QRScanRequest(BaseModel):
    """Student QR scan request"""
    session_id: str = Field(..., min_length=10)
    qr_code_hash: str = Field(..., min_length=64)
    
    student_id: str = Field(..., min_length=1)
    roll_number: str = Field(..., min_length=1)
    student_name: str = Field(..., min_length=2)
    student_email: Optional[EmailStr] = None
    branch: str = Field(..., min_length=2)
    semester: int = Field(..., ge=1, le=8)
    section: Optional[str] = None
    qr_code_hash: Optional[str] = Field(None, min_length=64)
    
    location: StudentLocationData
    device: DeviceData
    
    scan_timestamp: datetime
    scan_duration_ms: Optional[int] = None


class QRScanResponse(BaseModel):
    """Response after QR scan attempt"""
    success: bool
    message: str
    attendance_marked: bool
    
    session_info: Optional[Dict[str, Any]] = None
    attendance_record_id: Optional[int] = None
    
    validation_results: Dict[str, bool] = {
        "qr_valid": False,
        "location_valid": False,
        "device_valid": False,
        "time_valid": False
    }
    
    distance_from_center: Optional[float] = None
    is_within_geofence: Optional[bool] = None
    is_late_entry: Optional[bool] = None
    late_by_minutes: Optional[int] = None
    
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None


# ============== Attendance Record Schemas ==============

class AttendanceRecordResponse(BaseModel):
    """Individual attendance record"""
    id: int
    session_id: int
    
    student_id: str
    roll_number: str
    student_name: str
    branch: str
    semester: int
    
    marked_at: datetime
    attendance_status: str
    is_late_entry: bool
    late_by_minutes: int
    
    distance_from_center: float
    is_within_geofence: bool
    
    device_id: Optional[str]
    device_model: Optional[str]
    
    is_valid_attendance: bool = True
    
    created_at: datetime

    class Config:
        from_attributes = True


class AttendanceRecordSummary(BaseModel):
    """Simplified attendance record for lists"""
    id: int
    roll_number: str
    student_name: str
    marked_at: datetime
    attendance_status: str
    is_late_entry: bool
    late_by_minutes: int
    distance_from_center: float

    class Config:
        from_attributes = True


# ============== Dashboard & Analytics Schemas ==============

class LiveAttendanceStats(BaseModel):
    """Real-time attendance statistics"""
    session_id: int
    subject_name: str
    branch: str
    semester: int
    
    total_expected: int
    total_present: int
    total_absent: int
    total_late: int
    
    attendance_percentage: float
    on_time_percentage: float
    
    qr_expires_at: datetime
    is_active: bool
    time_remaining_seconds: int


class StudentAttendanceHistory(BaseModel):
    """Student's attendance history"""
    student_id: str
    student_name: str
    roll_number: str
    
    subject_code: str
    subject_name: str
    
    total_classes: int
    classes_attended: int
    classes_missed: int
    late_entries: int
    
    attendance_percentage: float
    status: str  # good, warning, critical
    
    recent_records: List[AttendanceRecordSummary]


class FacultyDashboard(BaseModel):
    """Faculty dashboard overview"""
    faculty_id: str
    faculty_name: str
    
    active_sessions_count: int
    today_sessions_count: int
    total_sessions_created: int
    
    recent_sessions: List[QRSessionSummary]
    
    today_attendance_stats: Optional[Dict[str, int]] = None


class StudentDashboard(BaseModel):
    """Student dashboard overview"""
    student_id: str
    student_name: str
    roll_number: str
    
    today_classes: int
    today_attended: int
    today_missed: int
    
    overall_attendance_percentage: float
    attendance_status: str  # good, warning, critical
    
    low_attendance_subjects: List[Dict[str, Any]]
    recent_attendance: List[AttendanceRecordSummary]


# ============== Validation & Security Schemas ==============

class ValidationResult(BaseModel):
    """Validation check result"""
    check_name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class SecurityAlert(BaseModel):
    """Security alert for suspicious activities"""
    alert_type: str  # proxy_detected, multiple_devices, location_mismatch, etc.
    severity: str  # low, medium, high, critical
    student_id: str
    session_id: int
    timestamp: datetime
    details: Dict[str, Any]
    action_taken: str


class AbsentStudentInfo(BaseModel):
    """Information about absent students"""
    roll_number: str
    student_name: str
    branch: str
    semester: int
    section: Optional[str]
    contact_email: Optional[str]


class AbsentListResponse(BaseModel):
    """Auto-generated absent list"""
    session_id: int
    subject_name: str
    lecture_date: datetime
    total_expected: int
    total_present: int
    total_absent: int
    absent_students: List[AbsentStudentInfo]


# ============== Device Management Schemas ==============

class DeviceFingerprintResponse(BaseModel):
    """Device fingerprint information"""
    id: int
    device_id: str
    student_id: str
    student_name: str
    device_model: Optional[str]
    device_os: Optional[str]
    first_registered: datetime
    last_used: datetime
    total_scans: int
    is_active: bool
    is_blocked: bool

    class Config:
        from_attributes = True


# ============== Utility Schemas ==============

class MessageResponse(BaseModel):
    """Generic message response"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class QRCodeImage(BaseModel):
    """QR code image data"""
    session_id: str
    qr_code_base64: str  # Base64 encoded PNG image
    expires_at: datetime
    metadata: Dict[str, Any]
