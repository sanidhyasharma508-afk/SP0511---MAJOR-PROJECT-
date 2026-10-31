from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from backend.core.auth import (
    create_tokens,
    create_access_token,
    decode_token,
    verify_password,
    hash_password,
    is_token_blacklisted,
    blacklist_token,
    Token,
    TokenData,
)
from backend.core.rbac import Role, get_current_user, require_admin, AuthContext
from backend.core.logging import get_logger
from backend.database import get_db
from backend.models.user import User
from backend.models.student import Student

# Create router
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

# Logger
logger = get_logger("auth_routes")

# Security scheme
security = HTTPBearer()


# Pydantic models
class LoginRequest(BaseModel):
    """Login credentials"""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class LoginResponse(BaseModel):
    """Login response"""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"
    user_id: int
    role: str


class RegisterRequest(BaseModel):
    """User registration"""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="student")


class AdminCreateUserRequest(BaseModel):
    """Admin-only user creation"""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="staff")  # student, staff, faculty, admin
    linked_student_id: Optional[int] = None


class RegisterResponse(BaseModel):
    """Registration response"""

    user_id: int
    username: str
    email: str
    role: str
    message: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""

    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Refresh token response"""

    access_token: str
    expires_in: int
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    """Logout request"""

    token: Optional[str] = None
    refresh_token: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    """Change password request"""

    old_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class UserProfile(BaseModel):
    """User profile"""

    user_id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    role: str
    created_at: datetime
    last_login: Optional[datetime]
    linked_student_id: Optional[int] = None
    avatar: Optional[str] = None
    roll_no: Optional[str] = None
    department: Optional[str] = None
    semester: Optional[int] = None
    section: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    """Profile update fields"""

    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    avatar: Optional[str] = None
    department: Optional[str] = Field(None, max_length=100)
    section: Optional[str] = Field(None, max_length=20)

    # Privileged fields to detect and reject student privilege escalations
    role: Optional[str] = None
    is_active: Optional[bool] = None
    linked_student_id: Optional[int] = None
    roll_no: Optional[str] = None


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """
    Login with username and password against persistent database
    """
    # Lookup by username or email
    user = (
        db.query(User)
        .filter((User.username == credentials.username) | (User.email == credentials.username))
        .first()
    )

    if not user:
        logger.log_event(
            "login_failed",
            level="WARNING",
            username=credentials.username,
            reason="user_not_found",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(credentials.password, user.hashed_password):
        logger.log_event(
            "login_failed",
            level="WARNING",
            username=credentials.username,
            reason="password_mismatch",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.log_event(
            "login_failed",
            level="WARNING",
            username=credentials.username,
            reason="inactive_account",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive. Please contact administration.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Normalize role string
    user_role = user.role.lower()

    # Create tokens
    tokens = create_tokens(
        user_id=user.id,
        username=user.username,
        role=user_role,
        linked_student_id=user.linked_student_id,
        email=user.email,
    )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    logger.log_event(
        "login_successful",
        level="INFO",
        user_id=user.id,
        username=user.username,
        role=user.role,
    )

    return LoginResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user_id=user.id,
        role=user.role,
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """
    Public registration for students only.
    Prevents privilege escalation to admin/staff/faculty roles.
    """
    # Enforce role restriction for public registration
    requested_role = data.role.strip().lower()
    if requested_role != "student":
        logger.log_event(
            "registration_rejected_privilege_escalation",
            level="WARNING",
            username=data.username,
            requested_role=data.role,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public self-registration is only permitted for students. Privileged accounts (admin/staff/faculty) must be provisioned by an administrator.",
        )

    # Check unique username
    if db.query(User).filter(User.username == data.username).first():
        logger.log_event(
            "registration_failed",
            level="WARNING",
            username=data.username,
            reason="username_exists",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # Check unique email
    if db.query(User).filter(User.email == data.email).first():
        logger.log_event(
            "registration_failed",
            level="WARNING",
            email=data.email,
            reason="email_exists",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Validate or associate with student record
    linked_student_id = None
    existing_student = db.query(Student).filter(
        (Student.roll_no == data.username) | (Student.name.ilike(data.full_name))
    ).first()
    if existing_student:
        linked_student_id = existing_student.id

    # Create user record
    new_user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role="student",
        is_active=True,
        linked_student_id=linked_student_id,
        created_at=datetime.utcnow(),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.log_event(
        "user_registered",
        level="INFO",
        user_id=new_user.id,
        username=new_user.username,
        role=new_user.role,
    )

    return RegisterResponse(
        user_id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        role=new_user.role,
        message="User registered successfully. You can now login.",
    )


@router.post("/admin/create-user", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    data: AdminCreateUserRequest,
    current_user: TokenData = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin-only endpoint to provision privileged staff, faculty, or admin accounts.
    """
    valid_roles = ["student", "staff", "faculty", "admin"]
    role_norm = data.role.strip().lower()
    if role_norm not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}",
        )

    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    new_user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=role_norm,
        is_active=True,
        linked_student_id=data.linked_student_id,
        created_at=datetime.utcnow(),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.log_event(
        "admin_created_user",
        level="INFO",
        created_by=current_user.sub,
        user_id=new_user.id,
        username=new_user.username,
        role=new_user.role,
    )

    return RegisterResponse(
        user_id=new_user.id,
        username=new_user.username,
        email=new_user.email,
        role=new_user.role,
        message="Account created successfully by administrator.",
    )


@router.post("/refresh", response_model=RefreshTokenResponse, status_code=status.HTTP_200_OK)
def refresh(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using valid refresh token
    """
    token_data = decode_token(request.refresh_token)

    if not token_data or token_data.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if is_token_blacklisted(request.refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    new_access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        linked_student_id=user.linked_student_id,
        email=user.email,
    )

    logger.log_event(
        "token_refreshed",
        level="INFO",
        user_id=user.id,
        username=user.username,
    )

    from backend.core.auth import ACCESS_TOKEN_EXPIRE_MINUTES
    return RefreshTokenResponse(
        access_token=new_access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    request: Optional[LogoutRequest] = None,
    current_user: TokenData = Depends(get_current_user),
    raw_credentials: Optional[object] = Depends(security),
):
    """
    Logout user by blacklisting the provided access token and refresh token
    """
    token_to_blacklist = None
    if request and request.token:
        token_to_blacklist = request.token
    elif raw_credentials and hasattr(raw_credentials, "credentials"):
        token_to_blacklist = raw_credentials.credentials

    if token_to_blacklist:
        blacklist_token(token_to_blacklist)

    # Blacklist refresh token if provided
    if request and request.refresh_token:
        blacklist_token(request.refresh_token)

    logger.log_event(
        "logout_successful",
        level="INFO",
        user_id=current_user.user_id,
        username=current_user.sub,
    )

    return {"message": "Logged out successfully"}


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    request: ChangePasswordRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change user password for authenticated user
    """
    if request.new_password != request.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match",
        )

    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(request.old_password, user.hashed_password):
        logger.log_event(
            "password_change_failed",
            level="WARNING",
            user_id=current_user.user_id,
            reason="invalid_old_password",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Old password is incorrect",
        )

    user.hashed_password = hash_password(request.new_password)
    user.updated_at = datetime.utcnow()
    db.commit()

    logger.log_event(
        "password_changed",
        level="INFO",
        user_id=current_user.user_id,
        username=current_user.sub,
    )

    return {"message": "Password changed successfully"}


@router.get("/profile", response_model=UserProfile, status_code=status.HTTP_200_OK)
@router.get("/me", response_model=UserProfile, status_code=status.HTTP_200_OK)
def get_profile(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current authenticated user profile with linked student details
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

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

    return UserProfile(
        user_id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        created_at=user.created_at,
        last_login=user.last_login,
        linked_student_id=user.linked_student_id,
        avatar=user.avatar,
        roll_no=student.roll_no if student else None,
        department=student.department if student else None,
        semester=student.semester if student else None,
        section=student.section if student else None,
    )


@router.put("/profile", response_model=UserProfile, status_code=status.HTTP_200_OK)
def update_profile(
    data: ProfileUpdateRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update profile fields (full_name, email, avatar, department, section).
    Enforces that students cannot modify privileged fields (role, is_active, linked_student_id, roll_no).
    """
    user = db.query(User).filter(User.id == current_user.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    student = None
    if user.linked_student_id:
        student = db.query(Student).filter(Student.id == user.linked_student_id).first()
    if not student:
        student = db.query(Student).filter(
            (Student.roll_no == user.username) | (Student.name.ilike(user.full_name or ""))
        ).first()
        if student and not user.linked_student_id:
            user.linked_student_id = student.id

    is_student = user.role.lower() == "student"

    # Enforce role restrictions for students
    if is_student:
        if data.role is not None and data.role.strip().lower() != user.role.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students cannot change their role",
            )
        if data.is_active is not None and data.is_active != user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students cannot change their account status",
            )
        if data.linked_student_id is not None and data.linked_student_id != user.linked_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students cannot change their linked student ID",
            )
        if data.roll_no is not None:
            if not student or data.roll_no.strip() != student.roll_no:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Students cannot change their roll number",
                )

    # If updating student-specific academic fields, verify student record exists
    if (data.department is not None or data.section is not None) and not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked student record not found for this account",
        )

    # Update User fields
    if data.full_name is not None and data.full_name.strip():
        user.full_name = data.full_name.strip()
        if student:
            student.name = user.full_name

    if data.email is not None:
        new_email = str(data.email).strip().lower()
        existing = db.query(User).filter(User.email == new_email, User.id != user.id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already in use by another account",
            )
        user.email = new_email

    if data.avatar is not None:
        user.avatar = data.avatar

    # Update linked Student fields
    if data.department is not None and student:
        student.department = data.department.strip()

    if data.section is not None and student:
        student.section = data.section.strip()

    # If staff/admin is updating and passed privileged fields, apply them
    if not is_student:
        if data.role is not None:
            user.role = data.role.strip().lower()
        if data.is_active is not None:
            user.is_active = data.is_active
        if data.linked_student_id is not None:
            user.linked_student_id = data.linked_student_id
        if data.roll_no is not None and student:
            student.roll_no = data.roll_no.strip()

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    if student:
        db.refresh(student)

    logger.log_event(
        "profile_updated",
        level="INFO",
        user_id=current_user.user_id,
        username=current_user.sub,
    )

    return UserProfile(
        user_id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        created_at=user.created_at,
        last_login=user.last_login,
        linked_student_id=user.linked_student_id,
        avatar=user.avatar,
        roll_no=student.roll_no if student else None,
        department=student.department if student else None,
        semester=student.semester if student else None,
        section=student.section if student else None,
    )


@router.get("/verify", status_code=status.HTTP_200_OK)
def verify_token(current_user: TokenData = Depends(get_current_user)):
    """
    Verify that the provided bearer token is valid and active
    """
    return {
        "valid": True,
        "user_id": current_user.user_id,
        "username": current_user.sub,
        "role": current_user.role,
        "linked_student_id": current_user.linked_student_id,
        "message": "Token is valid",
    }


def get_user_by_username(username: str, db: Optional[Session] = None):
    """
    Backward-compatible helper for user lookup.
    Queries persistent database and returns a user dictionary or None.
    """
    close_db = False
    if db is None:
        from backend.database import SessionLocal
        db = SessionLocal()
        close_db = True
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "linked_student_id": user.linked_student_id,
        }
    finally:
        if close_db:
            db.close()
