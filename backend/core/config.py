import os
from enum import Enum
from pathlib import Path
from typing import Optional, List, Set, Any
from pydantic_settings import BaseSettings
from pydantic import Field
import logging

logger = logging.getLogger(__name__)

# Known insecure secret keys that must never be permitted in production
INSECURE_SECRET_KEYS: Set[str] = {
    "your-secret-key-change-in-production",
    "your-super-secret-key-change-this-in-production",
    "your-secret-key-here",
    "your-secret-key",
    "your-super-secret-key",
    "your-long-random-production-key-here",
    "your-long-random-production-key",
    "secret",
    "secretkey",
    "changeme",
    "password",
    "default",
    "dev-secret-key",
    "dev-secret-key-not-for-production",
    "dev-insecure-secret-key-never-use-in-production-campus-automation",
}

DEV_DEFAULT_SECRET_KEY = "dev-insecure-secret-key-never-use-in-production-campus-automation"

DEV_DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DOTENV_PATH = BASE_DIR / ".env"
BACKEND_DOTENV_PATH = BASE_DIR / "backend" / ".env"

_env_files = []
if DOTENV_PATH.is_file():
    _env_files.append(str(DOTENV_PATH))
if BACKEND_DOTENV_PATH.is_file():
    _env_files.append(str(BACKEND_DOTENV_PATH))
if not _env_files:
    _env_files.append(".env")


class Environment(str, Enum):
    """Application environments"""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application settings from environment variables"""

    model_config = {
        "env_file": _env_files,
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    # Environment
    ENVIRONMENT: Environment = Field(default=Environment.DEVELOPMENT, alias="ENV")
    DEBUG: bool = Field(default=True)

    # Server
    HOST: str = Field(default="127.0.0.1")
    PORT: int = Field(default=8000)
    API_PREFIX: str = Field(default="/api/v1")

    # Database
    DATABASE_URL: str = Field(default="sqlite:///./campus_automation.db")
    DB_ECHO: bool = Field(default=False)
    DB_POOL_SIZE: int = Field(default=5)
    DB_MAX_OVERFLOW: int = Field(default=10)

    # Authentication - No insecure default in production
    SECRET_KEY: Optional[str] = Field(default=None)
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    # CORS - Explicit frontend origins
    ALLOWED_ORIGINS: Optional[str] = Field(default=None)
    ALLOWED_METHODS: str = Field(default="GET,POST,PUT,DELETE,PATCH,OPTIONS")
    ALLOWED_HEADERS: str = Field(
        default="Content-Type,Authorization,Accept,Origin,X-Requested-With"
    )

    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE: str = Field(default="logs/app.log")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Caching (Redis)
    REDIS_URL: Optional[str] = Field(default=None)
    CACHE_TTL: int = Field(default=300)  # seconds

    # Background jobs
    CELERY_BROKER_URL: Optional[str] = Field(default=None)
    CELERY_RESULT_BACKEND: Optional[str] = Field(default=None)

    # Email (for notifications)
    SMTP_SERVER: Optional[str] = Field(default=None)
    SMTP_PORT: int = Field(default=587)
    SMTP_USERNAME: Optional[str] = Field(default=None)
    SMTP_PASSWORD: Optional[str] = Field(default=None)
    SENDER_EMAIL: Optional[str] = Field(default=None)

    # Feature flags
    ENABLE_CACHING: bool = Field(default=False)
    ENABLE_BACKGROUND_TASKS: bool = Field(default=False)
    ENABLE_EMAIL_NOTIFICATIONS: bool = Field(default=False)

    # Performance
    MAX_POOL_SIZE: int = Field(default=10)
    WORKER_THREADS: int = Field(default=4)
    REQUEST_TIMEOUT: int = Field(default=30)

    # Monitoring
    ENABLE_METRICS: bool = Field(default=True)
    METRICS_PORT: int = Field(default=9090)

    def model_post_init(self, __context: Any) -> None:
        """Validate settings and establish environment defaults"""
        if self.is_development or self.is_testing:
            if not self.SECRET_KEY:
                self.SECRET_KEY = DEV_DEFAULT_SECRET_KEY
                logger.info("Using development default SECRET_KEY. Set SECRET_KEY in .env for production.")
        elif self.is_production:
            validate_production_settings(self)

    @property
    def ENV(self) -> str:
        """Get environment name"""
        return self.ENVIRONMENT.value

    @property
    def CORS_ORIGINS(self) -> list:
        """Get CORS origins as list. In development defaults to local dev servers; in production requires explicit list."""
        if self.ALLOWED_ORIGINS:
            if self.ALLOWED_ORIGINS.strip() == "*":
                return ["*"]
            return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        if self.is_production:
            return []
        return list(DEV_DEFAULT_ORIGINS)

    @property
    def CORS_METHODS(self) -> list:
        """Get CORS methods as list"""
        if self.ALLOWED_METHODS == "*":
            return ["*"]
        return [m.strip() for m in self.ALLOWED_METHODS.split(",") if m.strip()]

    @property
    def CORS_HEADERS(self) -> list:
        """Get CORS headers as list"""
        if self.ALLOWED_HEADERS == "*":
            return ["*"]
        return [h.strip() for h in self.ALLOWED_HEADERS.split(",") if h.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENVIRONMENT == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.ENVIRONMENT == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        """Check if running in testing"""
        return self.ENVIRONMENT == Environment.TESTING

    def get_database_url(self) -> str:
        """Get database URL based on environment, resolving relative SQLite paths to project root"""
        if self.is_testing:
            return "sqlite:///:memory:"
        if self.DATABASE_URL.startswith("sqlite:///./"):
            rel_name = self.DATABASE_URL[len("sqlite:///./") :]
            abs_db_path = (BASE_DIR / rel_name).resolve().as_posix()
            return f"sqlite:///{abs_db_path}"
        return self.DATABASE_URL


def validate_production_settings(cfg: Optional[Settings] = None) -> bool:
    """Validate settings for production. Raises ValueError if configuration is insecure."""
    target = cfg or settings
    if not target.is_production:
        return True

    errors = []

    # 1. JWT SECRET_KEY validation
    secret = target.SECRET_KEY
    if not secret or not str(secret).strip():
        errors.append("SECRET_KEY environment variable is required in production")
    else:
        cleaned_secret = str(secret).strip()
        if cleaned_secret.lower() in {k.lower() for k in INSECURE_SECRET_KEYS}:
            errors.append("SECRET_KEY cannot use a known insecure default or placeholder in production")
        elif len(cleaned_secret) < 32:
            errors.append("SECRET_KEY must be at least 32 characters long in production")

    # 2. DEBUG mode validation
    if target.DEBUG:
        errors.append("DEBUG must be False in production")

    # 3. CORS validation: no wildcards with credentials
    if not target.ALLOWED_ORIGINS or not target.ALLOWED_ORIGINS.strip():
        errors.append(
            "ALLOWED_ORIGINS environment variable is required and must list explicit frontend origins in production"
        )
    elif target.ALLOWED_ORIGINS.strip() == "*":
        errors.append("ALLOWED_ORIGINS cannot be '*' in production when credentials are enabled")
    else:
        origins = target.CORS_ORIGINS
        if "*" in origins:
            errors.append("ALLOWED_ORIGINS cannot contain wildcard '*' in production when credentials are enabled")
        if not origins:
            errors.append("ALLOWED_ORIGINS must contain at least one valid frontend origin in production")

    if target.DATABASE_URL.startswith("sqlite"):
        logger.warning(
            "Production note: SQLite is configured. For high-concurrency production, PostgreSQL is recommended."
        )

    if errors:
        for err in errors:
            logger.error(f"Production configuration error: {err}")
        raise ValueError(f"Production configuration errors: {'; '.join(errors)}")

    return True


# Load settings
try:
    settings = Settings()
    logger.info(f"Settings loaded. Environment: {settings.ENVIRONMENT}")
except Exception as e:
    logger.critical(f"Fatal configuration error: {str(e)}")
    raise


# Helper functions for environment-specific configuration
def get_log_level() -> str:
    """Get appropriate log level"""
    if settings.is_production:
        return "WARNING"
    elif settings.is_testing:
        return "DEBUG"
    return settings.LOG_LEVEL


def get_database_echo() -> bool:
    """Get database echo setting"""
    return settings.DB_ECHO and settings.is_development


def get_debug_mode() -> bool:
    """Get debug mode"""
    return settings.DEBUG and not settings.is_production
