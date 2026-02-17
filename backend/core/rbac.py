from enum import Enum
from typing import List, Optional, Callable
from functools import wraps
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from starlette.authentication import AuthCredentials
import logging

from backend.core.auth import decode_token, TokenData, is_token_blacklisted

logger = logging.getLogger(__name__)


# Role definitions
class Role(str, Enum):
    """User roles"""

    ADMIN = "admin"
    STAFF = "staff"
    STUDENT = "student"
    GUEST = "guest"


class RoleHierarchy:
    """Role hierarchy for permission checking"""

    # Higher numbers = more permissions
    hierarchy = {Role.GUEST: 0, Role.STUDENT: 1, Role.STAFF: 2, Role.ADMIN: 3}

    @classmethod
    def has_role(cls, user_role: str, required_role: str) -> bool:
        """Check if user role has permission for required role"""
        user_level = cls.hierarchy.get(user_role, 0)
        required_level = cls.hierarchy.get(required_role, 0)
        return user_level >= required_level

    @classmethod
    def has_any_role(cls, user_role: str, required_roles: List[str]) -> bool:
        """Check if user role matches any of required roles"""
        return any(cls.has_role(user_role, role) for role in required_roles)


# HTTP Bearer security
security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: Optional[object] = Depends(security)) -> "TokenData":
    """
    Dependency to get current authenticated user
    Validates JWT token and returns user info
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Check if token is blacklisted
    if is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode token
    token_data = decode_token(token)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Ensure it's an access token
    if token_data.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


def require_role(*roles: str):
    """
    Dependency for role-based access control
    Usage: @app.get("/admin", dependencies=[Depends(require_role(Role.ADMIN))])
    """

    async def role_checker(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        if not RoleHierarchy.has_any_role(current_user.role, list(roles)):
            logger.warning(
                f"User {current_user.sub} attempted unauthorized access with role {current_user.role}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(roles)}",
            )
        return current_user

    return role_checker


def require_admin(current_user: TokenData = Depends(require_role(Role.ADMIN))) -> TokenData:
    """Dependency for admin-only endpoints"""
    return current_user


def require_staff(current_user: TokenData = Depends(require_role(Role.STAFF))) -> TokenData:
    """Dependency for staff and admin endpoints"""
    return current_user


def require_student(current_user: TokenData = Depends(require_role(Role.STUDENT))) -> TokenData:
    """Dependency for student, staff, and admin endpoints"""
    return current_user


def require_any_auth(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Dependency for authenticated users (any role)"""
    return current_user


# Permission-based access control
class Permission(str, Enum):
    """System permissions"""

    # Student management
    VIEW_STUDENT = "view_student"
    CREATE_STUDENT = "create_student"
    UPDATE_STUDENT = "update_student"
    DELETE_STUDENT = "delete_student"

    # Attendance
    VIEW_ATTENDANCE = "view_attendance"
    MARK_ATTENDANCE = "mark_attendance"
    UPDATE_ATTENDANCE = "update_attendance"

    # Complaints
    FILE_COMPLAINT = "file_complaint"
    VIEW_COMPLAINTS = "view_complaints"
    RESOLVE_COMPLAINT = "resolve_complaint"

    # Risk management
    VIEW_RISKS = "view_risks"
    CREATE_RISKS = "create_risks"
    RESOLVE_RISKS = "resolve_risks"

    # Reports
    VIEW_REPORTS = "view_reports"
    GENERATE_REPORTS = "generate_reports"

    # System
    MANAGE_USERS = "manage_users"
    VIEW_LOGS = "view_logs"
    MANAGE_SETTINGS = "manage_settings"


# Role to permissions mapping
ROLE_PERMISSIONS = {
    Role.ADMIN: [
        # Full access
        Permission.VIEW_STUDENT,
        Permission.CREATE_STUDENT,
        Permission.UPDATE_STUDENT,
        Permission.DELETE_STUDENT,
        Permission.VIEW_ATTENDANCE,
        Permission.MARK_ATTENDANCE,
        Permission.UPDATE_ATTENDANCE,
        Permission.FILE_COMPLAINT,
        Permission.VIEW_COMPLAINTS,
        Permission.RESOLVE_COMPLAINT,
        Permission.VIEW_RISKS,
        Permission.CREATE_RISKS,
        Permission.RESOLVE_RISKS,
        Permission.VIEW_REPORTS,
        Permission.GENERATE_REPORTS,
        Permission.MANAGE_USERS,
        Permission.VIEW_LOGS,
        Permission.MANAGE_SETTINGS,
    ],
    Role.STAFF: [
        # Read and manage core functions
        Permission.VIEW_STUDENT,
        Permission.UPDATE_STUDENT,
        Permission.VIEW_ATTENDANCE,
        Permission.MARK_ATTENDANCE,
        Permission.UPDATE_ATTENDANCE,
        Permission.FILE_COMPLAINT,
        Permission.VIEW_COMPLAINTS,
        Permission.RESOLVE_COMPLAINT,
        Permission.VIEW_RISKS,
        Permission.CREATE_RISKS,
        Permission.VIEW_REPORTS,
        Permission.GENERATE_REPORTS,
    ],
    Role.STUDENT: [
        # Limited access - view own data
        Permission.VIEW_ATTENDANCE,
        Permission.FILE_COMPLAINT,
        Permission.VIEW_REPORTS,
    ],
    Role.GUEST: [
        # Public/minimal access
        Permission.VIEW_REPORTS
    ],
}


def has_permission(permission: Permission):
    """
    Dependency for permission-based access control
    Usage: @app.get("/data", dependencies=[Depends(has_permission(Permission.VIEW_STUDENT))])
    """

    async def permission_checker(current_user: TokenData = Depends(get_current_user)):
        user_permissions = ROLE_PERMISSIONS.get(current_user.role, [])

        if permission not in user_permissions:
            logger.warning(f"User {current_user.sub} denied permission {permission}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission denied: {permission}"
            )

        return current_user

    return permission_checker


def get_user_permissions(role: str) -> List[Permission]:
    """Get all permissions for a role"""
    return ROLE_PERMISSIONS.get(role, [])


class AuthContext:
    """Context holder for authentication info"""

    def __init__(self, user: TokenData):
        self.user = user
        self.user_id = user.user_id
        self.username = user.sub
        self.role = user.role

    def has_role(self, *roles: str) -> bool:
        """Check if user has role"""
        return RoleHierarchy.has_any_role(self.role, list(roles))

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has permission"""
        user_perms = ROLE_PERMISSIONS.get(self.role, [])
        return permission in user_perms

    def is_admin(self) -> bool:
        """Check if user is admin"""
        return self.role == Role.ADMIN

    def is_staff(self) -> bool:
        """Check if user is staff"""
        return self.role in [Role.ADMIN, Role.STAFF]

    def is_student(self) -> bool:
        """Check if user is student"""
        return self.role in [Role.ADMIN, Role.STAFF, Role.STUDENT]
