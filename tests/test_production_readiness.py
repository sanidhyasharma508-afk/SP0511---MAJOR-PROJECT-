"""
Automated Test Suite for Production Readiness and Deployment Hardening (Task 14)

Verifies:
1. Missing production SECRET_KEY causes configuration failure.
2. Known placeholder secrets are strictly rejected in production.
3. Strong production secrets (>= 32 chars) are accepted.
4. Wildcard CORS origins are rejected in production.
5. Explicit production origins are cleanly parsed and accepted.
6. Production startup validation fails closed when configuration is invalid.
7. Production startup and seeding strictly skip mock data generation.
8. Admin provisioning script (create_admin.py) enforces minimum password length,
   rejects duplicates, and fails on missing credentials.
9. Production error handlers do not leak stack traces or internal secrets.
10. Database URL configuration handles SQLite and PostgreSQL schemes cleanly.
11. Debug mode is guaranteed False in production regardless of settings.DEBUG flag.
"""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.config import (
    Settings,
    Environment,
    validate_production_settings,
    get_debug_mode,
    INSECURE_SECRET_KEYS,
    DEV_DEFAULT_SECRET_KEY,
    settings,
)
from backend.models.user import User
from backend.models.student import Student
from backend.database import Base
from backend.main import app
from backend.seed_data import seed_database, seed_default_users
from backend.scripts.create_admin import create_admin, main as create_admin_main

VALID_PROD_SECRET = "x" * 48
VALID_PROD_ORIGIN = "https://campus.college.edu,https://admin.college.edu"


# -----------------------------------------------------------------------------
# 1. Missing Secret Key in Production Fails Closed
# -----------------------------------------------------------------------------
def test_missing_secret_key_fails_closed_in_production():
    with pytest.raises(ValueError) as exc:
        Settings(
            ENV="production",
            SECRET_KEY=None,
            ALLOWED_ORIGINS=VALID_PROD_ORIGIN,
            DEBUG=False,
        )
    assert "SECRET_KEY" in str(exc.value)

    with pytest.raises(ValueError) as exc_empty:
        Settings(
            ENV="production",
            SECRET_KEY="",
            ALLOWED_ORIGINS=VALID_PROD_ORIGIN,
            DEBUG=False,
        )
    assert "SECRET_KEY" in str(exc_empty.value)


# -----------------------------------------------------------------------------
# 2. Known Placeholder Secrets Strictly Rejected
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("placeholder", list(INSECURE_SECRET_KEYS) + [
    "your-secret-key-change-in-production",
    DEV_DEFAULT_SECRET_KEY,
    "admin123",
    "password",
    "supersecret",
])
def test_placeholder_secrets_rejected_in_production(placeholder):
    with pytest.raises(ValueError) as exc:
        Settings(
            ENV="production",
            SECRET_KEY=placeholder,
            ALLOWED_ORIGINS=VALID_PROD_ORIGIN,
            DEBUG=False,
        )
    assert "insecure" in str(exc.value).lower() or "production" in str(exc.value).lower()


# -----------------------------------------------------------------------------
# 3. Strong Production Secret Accepted
# -----------------------------------------------------------------------------
def test_strong_production_secret_accepted():
    prod_settings = Settings(
        ENV="production",
        SECRET_KEY=VALID_PROD_SECRET,
        ALLOWED_ORIGINS=VALID_PROD_ORIGIN,
        DEBUG=False,
    )
    assert prod_settings.is_production is True
    assert prod_settings.SECRET_KEY == VALID_PROD_SECRET
    assert len(prod_settings.CORS_ORIGINS) == 2
    assert "https://campus.college.edu" in prod_settings.CORS_ORIGINS
    assert "https://admin.college.edu" in prod_settings.CORS_ORIGINS


# -----------------------------------------------------------------------------
# 4. Wildcard CORS Rejected in Production
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("wildcard", ["*", " * ", "https://foo.edu, *"])
def test_wildcard_cors_rejected_in_production(wildcard):
    with pytest.raises(ValueError) as exc:
        Settings(
            ENV="production",
            SECRET_KEY=VALID_PROD_SECRET,
            ALLOWED_ORIGINS=wildcard,
            DEBUG=False,
        )
    assert "wildcard" in str(exc.value).lower() or "ALLOWED_ORIGINS" in str(exc.value)


# -----------------------------------------------------------------------------
# 5. Production Startup Fails Closed on Invalid Configuration
# -----------------------------------------------------------------------------
def test_production_startup_validation_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)
    monkeypatch.setattr(settings, "SECRET_KEY", "too-short")
    with pytest.raises(ValueError) as exc:
        validate_production_settings()
    assert "SECRET_KEY" in str(exc.value)


# -----------------------------------------------------------------------------
# 6. Production Mode Skips Mock Data Seeding
# -----------------------------------------------------------------------------
def test_production_seeding_strictly_skipped(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)

    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine)
    db = TestingSession()

    try:
        seed_default_users(db)
        assert db.query(User).count() == 0, "Users should NOT be seeded in production mode"

        seed_database()
        assert db.query(Student).count() == 0, "Students should NOT be seeded in production mode"
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 7. Admin Provisioning Script (create_admin.py)
# -----------------------------------------------------------------------------
def test_create_admin_enforces_rules_and_creates_user():
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine)

    with patch("backend.scripts.create_admin.SessionLocal", TestingSession), \
         patch("backend.scripts.create_admin.engine", test_engine):

        # 1. Success on valid inputs
        success = create_admin("superadmin", "superadmin@college.edu", "StrongAdminPass123!")
        assert success is True

        db = TestingSession()
        admin_rec = db.query(User).filter_by(username="superadmin").first()
        assert admin_rec is not None
        assert admin_rec.role == "admin"
        assert admin_rec.email == "superadmin@college.edu"
        assert admin_rec.hashed_password != "StrongAdminPass123!"  # Must be hashed!
        db.close()

        # 2. Reject duplicate username
        dup_user = create_admin("superadmin", "other@college.edu", "StrongAdminPass123!")
        assert dup_user is False

        # 3. Reject duplicate email
        dup_email = create_admin("newadmin", "superadmin@college.edu", "StrongAdminPass123!")
        assert dup_email is False


def test_create_admin_cli_validation():
    # Test short password rejection
    with patch("sys.argv", ["create_admin", "--username", "testadmin", "--email", "test@edu.com", "--password", "short"]):
        with pytest.raises(SystemExit) as exit_exc:
            create_admin_main()
        assert exit_exc.value.code == 1

    # Test missing field rejection
    with patch("sys.argv", ["create_admin", "--username", "", "--email", "", "--password", ""]):
        with patch("builtins.input", return_value=""):
            with patch("getpass.getpass", return_value=""):
                with pytest.raises(SystemExit) as exit_exc:
                    create_admin_main()
                assert exit_exc.value.code == 1


# -----------------------------------------------------------------------------
# 8. Error Responses Do Not Expose Stack Traces
# -----------------------------------------------------------------------------
def test_error_responses_do_not_leak_stack_traces():
    client = TestClient(app, raise_server_exceptions=False)
    # 404 for unmapped route
    response = client.get("/api/v1/nonexistent-route-endpoint-xyz")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "Traceback (most recent call last)" not in str(data)
    assert "sqlite3" not in str(data)
    assert "OperationalError" not in str(data)

    # 401 unauthenticated
    auth_resp = client.get("/students/1")
    assert auth_resp.status_code == 401
    auth_data = auth_resp.json()
    assert "detail" in auth_data
    assert "Traceback" not in str(auth_data)


# -----------------------------------------------------------------------------
# 9. Database URL Handling (SQLite and PostgreSQL)
# -----------------------------------------------------------------------------
def test_database_url_handling():
    # SQLite relative path is resolved to absolute posix path
    sqlite_settings = Settings(
        ENV="development",
        DATABASE_URL="sqlite:///./data/campus.db"
    )
    url = sqlite_settings.get_database_url()
    assert url.startswith("sqlite:///")
    assert url.endswith("data/campus.db")

    # Standard PostgreSQL
    pg_settings = Settings(
        ENV="development",
        DATABASE_URL="postgresql://user:pass@localhost:5432/campus_db"
    )
    assert pg_settings.get_database_url() == "postgresql://user:pass@localhost:5432/campus_db"


# -----------------------------------------------------------------------------
# 10. Debug Mode Guaranteed False in Production
# -----------------------------------------------------------------------------
def test_debug_mode_strictly_false_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)
    monkeypatch.setattr(settings, "DEBUG", True)
    assert get_debug_mode() is False

    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.DEVELOPMENT)
    monkeypatch.setattr(settings, "DEBUG", True)
    assert get_debug_mode() is True

    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.DEVELOPMENT)
    monkeypatch.setattr(settings, "DEBUG", False)
    assert get_debug_mode() is False
