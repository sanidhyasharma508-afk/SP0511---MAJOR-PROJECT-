from backend.models.user import User
from backend.models.student import Student
from backend.models.study_task import StudyTask
from backend.models.club import Club, ClubActivity, ClubMember, ClubAttendance
from backend.models.events import (
    Event,
    EventRegistration,
    EventLeaderboard,
    EventAnnouncement,
    EventCategory,
    EventStatus,
    RegistrationStatus
)
from backend.models.attendance import Attendance
from backend.models.complaint import Complaint, ComplaintHistory
from backend.models.risk import RiskLog
from backend.models.schedule import Schedule
from backend.models.schedule_feedback import ScheduleFeedback, Announcement
from backend.models.qr_attendance import (
    QRAttendanceSession,
    QRAttendanceRecord,
    QRAttendanceLog,
    DeviceFingerprint
)

__all__ = [
    "User",
    "Student",
    "StudyTask",
    "Club",
    "ClubActivity",
    "ClubMember",
    "ClubAttendance",
    "Event",
    "EventRegistration",
    "EventLeaderboard",
    "EventAnnouncement",
    "EventCategory",
    "EventStatus",
    "RegistrationStatus",
    "Attendance",
    "Complaint",
    "ComplaintHistory",
    "RiskLog",
    "Schedule",
    "ScheduleFeedback",
    "Announcement",
    "QRAttendanceSession",
    "QRAttendanceRecord",
    "QRAttendanceLog",
    "DeviceFingerprint",
]

