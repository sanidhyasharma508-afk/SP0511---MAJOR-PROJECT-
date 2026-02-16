from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

from backend.core.auth import (
    create_tokens,
    decode_token,
    verify_password,
    hash_password,
    is_token_blacklisted,
    blacklist_token,
    Token,
)
from backend.core.rbac import Role, get_current_user, AuthContext
from backend.core.logging import get_logger
from backend.database import SessionLocal
from sqlalchemy import Column, String, DateTime, Boolean, create_engine
from sqlalchemy.orm import declarative_base, Session

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
    role: str = Field(default="student")  # student, staff, or admin


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

    token: str


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


# Simple in-memory user storage for demo (replace with database in production)
USERS_DB = {
    1: {
        "user_id": 1,
        "username": "admin",
        "email": "admin@campus.edu",
        "password_hash": hash_password("admin123"),
        "full_name": "Administrator",
        "role": "admin",
        "created_at": datetime.utcnow(),
        "last_login": None,
    },
    2: {
        "user_id": 2,
        "username": "staff1",
        "email": "staff1@campus.edu",
        "password_hash": hash_password("staff123"),
        "full_name": "Staff Member",
        "role": "staff",
        "created_at": datetime.utcnow(),
        "last_login": None,
    },
    3: {
        "user_id": 3,
        "username": "student1",
        "email": "student1@campus.edu",
        "password_hash": hash_password("student123"),
        "full_name": "Student One",
        "role": "student",
        "created_at": datetime.utcnow(),
        "last_login": None,
    },
}

NEXT_USER_ID = 4
TOKEN_BLACKLIST = set()


def get_user_by_username(username: str):
    """Get user by username"""
    for user in USERS_DB.values():
        if user["username"] == username:
            return user
    return None


def get_user_by_id(user_id: int):
    """Get user by ID"""
    return USERS_DB.get(user_id)


@router.post("/login", response_model=LoginResponse, status_code=200)
async def login(credentials: LoginRequest):
    """
    Login with username and password

    Returns access token and refresh token
    """
    # Find user
    user = get_user_by_username(credentials.username)

    if not user or not verify_password(credentials.password, user["password_hash"]):
        logger.log_event(
            "login_failed",
            level="WARNING",
            username=credentials.username,
            reason="invalid_credentials",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password"
        )

    # Convert role string to Role enum
    try:
        role = Role[user["role"].upper()]
    except KeyError:
        role = Role.STUDENT

    # Create tokens
    tokens = create_tokens(user_id=user["user_id"], username=user["username"], role=role)

    # Update last login
    user["last_login"] = datetime.utcnow()

    logger.log_event(
        "login_successful",
        level="INFO",
        user_id=user["user_id"],
        username=user["username"],
        role=user["role"],
    )

    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in=tokens["expires_in"],
        user_id=user["user_id"],
        role=user["role"],
    )


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(data: RegisterRequest):
    """
    Register a new user

    Requires: username, email, password, full_name
    Optional: role (defaults to 'student')
    """
    global NEXT_USER_ID

    # Check if username exists
    if get_user_by_username(data.username):
        logger.log_event(
            "registration_failed", level="WARNING", username=data.username, reason="username_exists"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists"
        )

    # Validate role
    valid_roles = ["student", "staff", "admin"]
    if data.role.lower() not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}",
        )

    # Create new user
    user_id = NEXT_USER_ID
    NEXT_USER_ID += 1

    new_user = {
        "user_id": user_id,
        "username": data.username,
        "email": data.email,
        "password_hash": hash_password(data.password),
        "full_name": data.full_name,
        "role": data.role.lower(),
        "created_at": datetime.utcnow(),
        "last_login": None,
    }

    USERS_DB[user_id] = new_user

    logger.log_event(
        "user_registered", level="INFO", user_id=user_id, username=data.username, role=data.role
    )

    return RegisterResponse(
        user_id=user_id,
        username=data.username,
        email=data.email,
        role=data.role.lower(),
        message="User registered successfully. You can now login.",
    )


@router.post("/refresh", response_model=RefreshTokenResponse, status_code=200)
async def refresh(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token

    Returns new access token
    """
    try:
        # Decode refresh token
        token_data = decode_token(request.refresh_token)

        # Verify it's a refresh token
        if token_data.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )

        # Check if token is blacklisted
        if is_token_blacklisted(request.refresh_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked"
            )

        # Get user
        user = get_user_by_id(token_data.get("user_id"))
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Create new access token
        try:
            role = Role[user["role"].upper()]
        except KeyError:
            role = Role.STUDENT

        tokens = create_tokens(user_id=user["user_id"], username=user["username"], role=role)

        logger.log_event(
            "token_refreshed", level="INFO", user_id=user["user_id"], username=user["username"]
        )

        return RefreshTokenResponse(
            access_token=tokens["access_token"], expires_in=tokens["expires_in"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("token_refresh_failed", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )


@router.post("/logout", status_code=200)
async def logout(request: LogoutRequest, current_user: AuthContext = Depends(get_current_user)):
    """
    Logout user by blacklisting token

    Requires: valid access token
    """
    # Blacklist the token
    blacklist_token(request.token)

    logger.log_event(
        "logout_successful",
        level="INFO",
        user_id=current_user.user_id,
        username=current_user.username,
    )

    return {"message": "Logged out successfully"}


@router.post("/change-password", status_code=200)
async def change_password(
    request: ChangePasswordRequest, current_user: AuthContext = Depends(get_current_user)
):
    """
    Change user password

    Requires: valid access token and old password
    """
    # Verify passwords match
    if request.new_password != request.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="New passwords do not match"
        )

    # Get user
    user = get_user_by_id(current_user.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Verify old password
    if not verify_password(request.old_password, user["password_hash"]):
        logger.log_event(
            "password_change_failed",
            level="WARNING",
            user_id=current_user.user_id,
            reason="invalid_old_password",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Old password is incorrect"
        )

    # Update password
    user["password_hash"] = hash_password(request.new_password)

    logger.log_event(
        "password_changed",
        level="INFO",
        user_id=current_user.user_id,
        username=current_user.username,
    )

    return {"message": "Password changed successfully"}


@router.get("/profile", response_model=UserProfile, status_code=200)
async def get_profile(current_user: AuthContext = Depends(get_current_user)):
    """
    Get current user profile

    Requires: valid access token
    """
    user = get_user_by_id(current_user.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserProfile(
        user_id=user["user_id"],
        username=user["username"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        created_at=user["created_at"],
        last_login=user["last_login"],
    )


@router.put("/profile", response_model=UserProfile, status_code=200)
async def update_profile(data: dict, current_user: AuthContext = Depends(get_current_user)):
    """
    Update user profile

    Can update: full_name, email
    Requires: valid access token
    """
    user = get_user_by_id(current_user.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Update allowed fields
    if "full_name" in data:
        user["full_name"] = data["full_name"]

    if "email" in data:
        user["email"] = data["email"]

    logger.log_event(
        "profile_updated",
        level="INFO",
        user_id=current_user.user_id,
        username=current_user.username,
    )

    return UserProfile(
        user_id=user["user_id"],
        username=user["username"],
        email=user["email"],
        full_name=user["full_name"],
        role=user["role"],
        created_at=user["created_at"],
        last_login=user["last_login"],
    )


@router.get("/verify", status_code=200)
async def verify_token(current_user: AuthContext = Depends(get_current_user)):
    """
    Verify that the provided token is valid

    Requires: valid access token
    """
    return {
        "valid": True,
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role,
        "message": "Token is valid",
    }
