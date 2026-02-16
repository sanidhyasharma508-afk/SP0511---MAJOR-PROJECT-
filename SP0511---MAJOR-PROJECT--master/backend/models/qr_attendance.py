"""
QR-Based Attendance System Models with Geo-Fencing
Ensures proxy-free attendance with location validation
"""

from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from backend.database import Base
import uuid
import hashlib


class QRAttendanceSession(Base):
    """
    QR Attendance Session - Faculty generates time-bound QR codes
    """
    __tablename__ = "qr_attendance_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)  # Unique QR session ID
    
    # Faculty information
    faculty_id = Column(String(50), nullable=False, index=True)
    faculty_name = Column(String(200), nullable=False)
    faculty_email = Column(String(200), nullable=True)
    
    # Class details
    subject_code = Column(String(50), nullable=False)
    subject_name = Column(String(200), nullable=False)
    branch = Column(String(100), nullable=False)
    semester = Column(String(20), nullable=False)
    section = Column(String(50), nullable=True)
    
    # Lecture details
    lecture_date = Column(DateTime, nullable=False)
    lecture_start_time = Column(DateTime, nullable=False)
    lecture_end_time = Column(DateTime, nullable=True)
    lecture_duration_minutes = Column(Integer, default=60)
    
    # QR Code configuration
    qr_code_data = Column(Text, nullable=False)  # Encrypted QR data
    qr_code_hash = Column(String(256), nullable=False)  # SHA-256 hash for validation
    qr_generated_at = Column(DateTime, default=datetime.utcnow)
    qr_expires_at = Column(DateTime, nullable=False)  # Auto-expire in 2-5 minutes
    qr_validity_minutes = Column(Integer, default=3)  # Default 3 minutes
    
    # Geo-fencing data
    center_latitude = Column(Float, nullable=False)  # Faculty's GPS location
    center_longitude = Column(Float, nullable=False)
    geo_fence_radius_meters = Column(Float, default=50.0)  # 50 meters radius
    location_name = Column(String(300), nullable=True)  # e.g., "Room 201, CS Block"
    
    # Session status
    is_active = Column(Boolean, default=True)
    is_expired = Column(Boolean, default=False)
    is_cancelled = Column(Boolean, default=False)
    
    # Statistics
    total_students_expected = Column(Integer, default=0)
    total_students_present = Column(Integer, default=0)
    total_students_absent = Column(Integer, default=0)
    total_late_entries = Column(Integer, default=0)
    
    # Security
    max_scan_attempts_per_student = Column(Integer, default=1)
    allow_screenshot_scan = Column(Boolean, default=False)
    require_device_verification = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    attendance_records = relationship("QRAttendanceRecord", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<QRAttendanceSession(id={self.id}, subject='{self.subject_code}', faculty='{self.faculty_name}')>"

    def is_qr_valid(self):
        """Check if QR code is still valid"""
        if not self.is_active or self.is_expired or self.is_cancelled:
            return False
        if datetime.utcnow() > self.qr_expires_at:
            return False
        return True

    def calculate_distance(self, student_lat, student_lon):
        """Calculate distance between student and class center using Haversine formula"""
        from math import radians, sin, cos, sqrt, atan2
        
        # Earth radius in meters
        R = 6371000
        
        lat1 = radians(self.center_latitude)
        lon1 = radians(self.center_longitude)
        lat2 = radians(student_lat)
        lon2 = radians(student_lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        distance = R * c  # Distance in meters
        return distance

    def is_within_geofence(self, student_lat, student_lon):
        """Check if student is within the geo-fenced area"""
        distance = self.calculate_distance(student_lat, student_lon)
        return distance <= self.geo_fence_radius_meters

    def generate_qr_hash(self):
        """Generate secure hash for QR validation"""
        data = f"{self.session_id}{self.faculty_id}{self.qr_generated_at.timestamp()}{self.subject_code}"
        return hashlib.sha256(data.encode()).hexdigest()

    def mark_expired(self):
        """Mark session as expired"""
        self.is_expired = True
        self.is_active = False
        self.closed_at = datetime.utcnow()


class QRAttendanceRecord(Base):
    """
    QR Attendance Record - Individual student attendance with location
    """
    __tablename__ = "qr_attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("qr_attendance_sessions.id", ondelete="CASCADE"), nullable=False)
    
    # Student information
    student_id = Column(String(50), nullable=False, index=True)
    roll_number = Column(String(50), nullable=False, index=True)
    student_name = Column(String(200), nullable=False)
    student_email = Column(String(200), nullable=True)
    branch = Column(String(100), nullable=False)
    semester = Column(String(20), nullable=False)
    section = Column(String(50), nullable=True)
    
    # Attendance details
    marked_at = Column(DateTime, default=datetime.utcnow)
    attendance_status = Column(String(20), default="present")  # present, late, absent
    is_late_entry = Column(Boolean, default=False)
    late_by_minutes = Column(Integer, default=0)
    
    # Location data
    student_latitude = Column(Float, nullable=False)
    student_longitude = Column(Float, nullable=False)
    distance_from_center = Column(Float, nullable=False)  # Distance in meters
    is_within_geofence = Column(Boolean, default=True)
    location_accuracy = Column(Float, nullable=True)  # GPS accuracy in meters
    
    # Device information
    device_id = Column(String(200), nullable=True)  # Unique device identifier
    device_model = Column(String(200), nullable=True)
    device_os = Column(String(100), nullable=True)
    browser = Column(String(200), nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Security checks
    scan_attempt_number = Column(Integer, default=1)
    is_screenshot_scan = Column(Boolean, default=False)  # Detected screenshot
    is_duplicate_device = Column(Boolean, default=False)
    is_proxy_suspected = Column(Boolean, default=False)
    
    # Validation results
    qr_validation_passed = Column(Boolean, default=True)
    location_validation_passed = Column(Boolean, default=True)
    device_validation_passed = Column(Boolean, default=True)
    time_validation_passed = Column(Boolean, default=True)
    
    # Additional data
    scan_duration_ms = Column(Integer, nullable=True)  # Time taken to scan
    remarks = Column(Text, nullable=True)
    validation_errors = Column(Text, nullable=True)  # JSON array of errors
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    session = relationship("QRAttendanceSession", back_populates="attendance_records")

    def __repr__(self):
        return f"<QRAttendanceRecord(id={self.id}, student='{self.student_name}', status='{self.attendance_status}')>"

    def calculate_late_minutes(self, lecture_start_time):
        """Calculate how many minutes late the student is"""
        if self.marked_at > lecture_start_time:
            delta = self.marked_at - lecture_start_time
            return int(delta.total_seconds() / 60)
        return 0

    def is_valid_attendance(self):
        """Check if attendance record is valid"""
        return (
            self.qr_validation_passed and
            self.location_validation_passed and
            self.device_validation_passed and
            self.time_validation_passed and
            not self.is_proxy_suspected
        )


class QRAttendanceLog(Base):
    """
    QR Attendance Log - Track all scan attempts (successful and failed)
    """
    __tablename__ = "qr_attendance_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, nullable=False, index=True)
    student_id = Column(String(50), nullable=False, index=True)
    
    # Attempt details
    attempt_time = Column(DateTime, default=datetime.utcnow)
    attempt_status = Column(String(50), nullable=False)  # success, failed, blocked, denied
    failure_reason = Column(String(500), nullable=True)
    
    # Location at attempt
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    distance_from_center = Column(Float, nullable=True)
    
    # Device at attempt
    device_id = Column(String(200), nullable=True)
    ip_address = Column(String(50), nullable=True)
    
    # Validation checks
    qr_valid = Column(Boolean, default=False)
    location_valid = Column(Boolean, default=False)
    device_valid = Column(Boolean, default=False)
    time_valid = Column(Boolean, default=False)
    
    # Additional data
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<QRAttendanceLog(id={self.id}, student='{self.student_id}', status='{self.attempt_status}')>"


class DeviceFingerprint(Base):
    """
    Device Fingerprint - Track unique devices to prevent proxy
    """
    __tablename__ = "device_fingerprints"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(200), unique=True, nullable=False, index=True)
    
    # Student association
    student_id = Column(String(50), nullable=False, index=True)
    student_name = Column(String(200), nullable=False)
    
    # Device details
    device_model = Column(String(200), nullable=True)
    device_os = Column(String(100), nullable=True)
    browser = Column(String(200), nullable=True)
    screen_resolution = Column(String(50), nullable=True)
    
    # Registration
    first_registered = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, default=datetime.utcnow)
    total_scans = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_blocked = Column(Boolean, default=False)
    block_reason = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<DeviceFingerprint(id={self.id}, student='{self.student_id}', device='{self.device_id}')>"
