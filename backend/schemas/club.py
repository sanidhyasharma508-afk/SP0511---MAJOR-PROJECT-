from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List


class ClubMemberResponse(BaseModel):
    id: int
    student_id: int
    position: Optional[str]
    join_date: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ClubBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: str
    advisor: str
    president: Optional[str] = None


class ClubCreate(ClubBase):
    pass


class ClubUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    advisor: Optional[str] = None
    president: Optional[str] = None
    is_active: Optional[bool] = None


class ClubResponse(ClubBase):
    id: int
    member_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClubDetailResponse(ClubResponse):
    activities: List["ClubActivityResponse"] = []
    members: List[ClubMemberResponse] = []


class ClubActivityBase(BaseModel):
    club_id: int
    title: str
    description: Optional[str] = None
    activity_type: str
    start_date: datetime
    end_date: Optional[datetime] = None
    location: Optional[str] = None
    expected_participants: Optional[int] = 0


class ClubActivityCreate(ClubActivityBase):
    pass


class ClubActivityUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    activity_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    location: Optional[str] = None
    expected_participants: Optional[int] = None
    actual_participants: Optional[int] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


class ClubActivityResponse(ClubActivityBase):
    id: int
    actual_participants: int
    status: str
    remarks: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClubActivityDetailResponse(ClubActivityResponse):
    club: ClubResponse


class ClubMemberBase(BaseModel):
    club_id: int
    student_id: int
    position: Optional[str] = None


class ClubMemberCreate(ClubMemberBase):
    pass


class ClubMemberUpdate(BaseModel):
    position: Optional[str] = None
    is_active: Optional[bool] = None


class ClubMemberDetailResponse(ClubMemberResponse):
    club: Optional[ClubResponse] = None


# ----------------- Club Attendance Schemas -----------------
class ClubAttendanceItem(BaseModel):
    student_name: str
    roll_number: Optional[str] = None
    section: Optional[str] = None
    present: bool


class ClubAttendanceCreate(BaseModel):
    attendance_date: datetime
    roster: List[ClubAttendanceItem]


class ClubAttendanceResponse(BaseModel):
    id: int
    club_id: int
    student_name: str
    roll_number: Optional[str] = None
    section: Optional[str] = None
    status: str
    attendance_date: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


ClubDetailResponse.model_rebuild()
