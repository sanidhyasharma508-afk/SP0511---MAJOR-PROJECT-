import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
import hashlib
import hmac
from passlib.context import CryptContext
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

# Password hashing - Use simple SHA256 with salt for compatibility
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto", argon2__memory_cost=65536)


class TokenData(BaseModel):
    """JWT token payload"""

    sub: str  # Subject (username or user ID)
    user_id: int
    role: str  # Admin, Staff, Student
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None
    type: str = "access"  # access or refresh


class Token(BaseModel):
    """Token response"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class User(BaseModel):
    """User info"""

    id: int
    username: str
    email: str
    role: str
    is_active: bool


class Credentials(BaseModel):
    """Login credentials"""

    username: str
    password: str


class PasswordChange(BaseModel):
    """Password change request"""

    current_password: str
    new_password: str
    confirm_password: str


def hash_password(password: str) -> str:
    """Hash a password using Argon2"""
    try:
        return pwd_context.hash(password)
    except:
        # Fallback to manual hash if argon2 fails
        import secrets

        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return f"{salt}${pwd_hash.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against hash"""
    try:
        # Try using pwd_context first
        return pwd_context.verify(plain_password, hashed_password)
    except:
        # Fallback to manual verification
        try:
            if "$" in hashed_password:
                salt, pwd_hash = hashed_password.split("$")
                computed_hash = hashlib.pbkdf2_hmac(
                    "sha256", plain_password.encode(), salt.encode(), 100000
                )
                return hmac.compare_digest(computed_hash.hex(), pwd_hash)
        except Exception as e:
            logger.error(f"Error verifying password: {str(e)}")
        return False


def create_access_token(
    user_id: int, username: str, role: str, expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": username,
        "user_id": user_id,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
    }

    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: int, username: str, role: str) -> str:
    """Create JWT refresh token"""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": username,
        "user_id": user_id,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
    }

    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_tokens(user_id: int, username: str, role: str) -> Token:
    """Create both access and refresh tokens"""
    access_token = create_access_token(user_id, username, role)
    refresh_token = create_refresh_token(user_id, username, role)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def decode_token(token: str) -> Optional[TokenData]:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        role: str = payload.get("role")
        token_type: str = payload.get("type", "access")

        if username is None or user_id is None:
            logger.warning(f"Invalid token: missing required fields")
            return None

        return TokenData(sub=username, user_id=user_id, role=role, type=token_type)
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.JWTClaimsError:
        logger.warning("Invalid token claims")
        return None
    except jwt.JWTError as e:
        logger.warning(f"Error decoding token: {str(e)}")
        return None


def verify_token_type(token_data: TokenData, expected_type: str = "access") -> bool:
    """Verify token type"""
    return token_data.type == expected_type


# Token cache for blacklisting (revoked tokens)
_token_blacklist = set()


def blacklist_token(token: str) -> None:
    """Add token to blacklist (for logout)"""
    _token_blacklist.add(token)
    logger.info(f"Token blacklisted. Current blacklist size: {len(_token_blacklist)}")


def is_token_blacklisted(token: str) -> bool:
    """Check if token is blacklisted"""
    return token in _token_blacklist


def clear_expired_tokens() -> None:
    """Clear expired tokens from blacklist (call periodically)"""
    global _token_blacklist
    initial_size = len(_token_blacklist)

    # In production, implement proper token expiry cleanup
    # For now, keep blacklist in memory

    logger.info(f"Token blacklist cleanup: {initial_size} tokens checked")
