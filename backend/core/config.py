import os
from enum import Enum
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import logging

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Application environments"""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application settings from environment variables"""

    model_config = {"env_file": ".env", "case_sensitive": False}

    # Environment
    ENVIRONMENT: Environment = Field(default=Environment.DEVELOPMENT, alias="ENV")
    DEBUG: bool = Field(default=True)

    # Server
    HOST: str = Field(default="127.0.0.1", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    API_PREFIX: str = Field(default="/api/v1", env="API_PREFIX")

    # Database
    DATABASE_URL: str = Field(default="sqlite:///./test.db", env="DATABASE_URL")
    DB_ECHO: bool = Field(default=False, env="DB_ECHO")
    DB_POOL_SIZE: int = Field(default=5, env="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(default=10, env="DB_MAX_OVERFLOW")

    # Authentication
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production", env="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")

    # CORS
    ALLOWED_ORIGINS: str = Field(default="*", env="ALLOWED_ORIGINS")
    ALLOWED_METHODS: str = Field(default="*", env="ALLOWED_METHODS")
    ALLOWED_HEADERS: str = Field(default="*", env="ALLOWED_HEADERS")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FILE: str = Field(default="logs/app.log", env="LOG_FILE")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", env="LOG_FORMAT"
    )

    # Caching (Redis)
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    CACHE_TTL: int = Field(default=300, env="CACHE_TTL")  # seconds

    # Background jobs
    CELERY_BROKER_URL: Optional[str] = Field(default=None, env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: Optional[str] = Field(default=None, env="CELERY_RESULT_BACKEND")

    # Email (for notifications)
    SMTP_SERVER: Optional[str] = Field(default=None, env="SMTP_SERVER")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USERNAME: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    SENDER_EMAIL: Optional[str] = Field(default=None, env="SENDER_EMAIL")

    # Feature flags
    ENABLE_CACHING: bool = Field(default=False, env="ENABLE_CACHING")
    ENABLE_BACKGROUND_TASKS: bool = Field(default=False, env="ENABLE_BACKGROUND_TASKS")
    ENABLE_EMAIL_NOTIFICATIONS: bool = Field(default=False, env="ENABLE_EMAIL_NOTIFICATIONS")

    # Gemini AI Chatbot (Phase 5 Enhancement)
    GEMINI_API_KEY: Optional[str] = Field(default=None, env="GEMINI_API_KEY")
    GEMINI_MODEL: str = Field(default="gemini-pro", env="GEMINI_MODEL")
    ENABLE_GEMINI_CHATBOT: bool = Field(default=True, env="ENABLE_GEMINI_CHATBOT")
    CHATBOT_RATE_LIMIT: int = Field(default=100, env="CHATBOT_RATE_LIMIT")

    # Performance
    MAX_POOL_SIZE: int = Field(default=10, env="MAX_POOL_SIZE")
    WORKER_THREADS: int = Field(default=4, env="WORKER_THREADS")
    REQUEST_TIMEOUT: int = Field(default=30, env="REQUEST_TIMEOUT")

    # Monitoring
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    METRICS_PORT: int = Field(default=9090, env="METRICS_PORT")

    @property
    def ENV(self) -> str:
        """Get environment name"""
        return self.ENVIRONMENT.value

    @property
    def CORS_ORIGINS(self) -> list:
        """Get CORS origins as list"""
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @property
    def CORS_METHODS(self) -> list:
        """Get CORS methods as list"""
        if self.ALLOWED_METHODS == "*":
            return ["*"]
        return [m.strip() for m in self.ALLOWED_METHODS.split(",")]

    @property
    def CORS_HEADERS(self) -> list:
        """Get CORS headers as list"""
        if self.ALLOWED_HEADERS == "*":
            return ["*"]
        return [h.strip() for h in self.ALLOWED_HEADERS.split(",")]

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
        """Get database URL based on environment"""
        if self.is_testing:
            return "sqlite:///:memory:"
        return self.DATABASE_URL


# Load settings
try:
    settings = Settings()
    logger.info(f"Settings loaded. Environment: {settings.ENVIRONMENT}")
except Exception as e:
    logger.warning(f"Error loading settings from .env: {str(e)}")
    settings = Settings()


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


def validate_production_settings():
    """Validate settings for production"""
    errors = []

    if settings.is_production:
        if settings.SECRET_KEY == "your-secret-key-change-in-production":
            errors.append("SECRET_KEY must be changed in production")
        if settings.DEBUG:
            errors.append("DEBUG must be False in production")
        if settings.DATABASE_URL.startswith("sqlite"):
            errors.append("SQLite cannot be used in production")
        if not settings.ALLOWED_ORIGINS or settings.ALLOWED_ORIGINS == "*":
            errors.append("ALLOWED_ORIGINS must be restricted in production")

    if errors:
        for error in errors:
            logger.error(f"Production configuration error: {error}")
        raise ValueError(f"Production configuration errors: {', '.join(errors)}")

    return True
