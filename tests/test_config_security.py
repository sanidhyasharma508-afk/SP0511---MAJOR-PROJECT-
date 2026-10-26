"""
Regression Test Suite for Task 11:
Secure JWT Configuration, CORS, and Environment Variables

Verifies:
1. Missing JWT secret in production configuration is rejected.
2. Known insecure default secrets are rejected in production.
3. Sufficiently strong (>= 32 chars) configured secret in production is accepted.
4. Production CORS configuration rejects unrestricted wildcard origins when credentials are enabled.
5. Allowed frontend origins receive appropriate CORS headers (Access-Control-Allow-Origin, Access-Control-Allow-Credentials).
6. Disallowed browser origins are not granted CORS permission.
7. Development configuration provides safe local defaults without crashing or leaking into production.
8. Sensitive secrets are never exposed in validation errors or exception messages.
"""

import sys
import importlib.abc
import importlib.util
from pathlib import Path
import secrets
import pytest
from fastapi.testclient import TestClient

# Sourceless pyc finder for runtime loading of compiled pyc models
class SourcelessPycFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if not path:
            return None
        name = fullname.split(".")[-1]
        for p in path:
            py = Path(p) / f"{name}.py"
            pyc = Path(p) / "__pycache__" / f"{name}.cpython-313.pyc"
            if not py.is_file() and pyc.is_file():
                return importlib.util.spec_from_file_location(fullname, pyc)
        return None

if not any(isinstance(f, SourcelessPycFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, SourcelessPycFinder())

from backend.core.config import (
    Settings,
    Environment,
    validate_production_settings,
    INSECURE_SECRET_KEYS,
    DEV_DEFAULT_SECRET_KEY,
    DEV_DEFAULT_ORIGINS,
)
from backend.core.auth import create_access_token, decode_token
from backend.main import app

client = TestClient(app)

VALID_PROD_SECRET = "a" * 32  # 32-character non-default secret
VALID_PROD_ORIGIN = "https://campus.college.edu"


# -----------------------------------------------------------------------------
# 1. Missing JWT Secret in Production
# -----------------------------------------------------------------------------
def test_production_missing_jwt_secret_rejected():
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENV="production",
            SECRET_KEY="",
            ALLOWED_ORIGINS=VALID_PROD_ORIGIN,
            DEBUG=False,
        )
    assert "SECRET_KEY" in str(excinfo.value)
    assert "required in production" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo_none:
        Settings(
            ENV="production",
            SECRET_KEY=None,
            ALLOWED_ORIGINS=VALID_PROD_ORIGIN,
            DEBUG=False,
        )
    assert "SECRET_KEY" in str(excinfo_none.value)


# -----------------------------------------------------------------------------
# 2. Known Insecure Default Secrets Rejected in Production
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "insecure_secret",
    [
        "your-secret-key-change-in-production",
        "your-super-secret-key-change-this-in-production",
        "your-secret-key",
        "secret",
        "changeme",
        "password",
        "dev-secret-key",
        DEV_DEFAULT_SECRET_KEY,
    ],
)
def test_production_insecure_default_secret_rejected(insecure_secret):
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENV="production",
            SECRET_KEY=insecure_secret,
            ALLOWED_ORIGINS=VALID_PROD_ORIGIN,
            DEBUG=False,
        )
    assert "SECRET_KEY" in str(excinfo.value)
    assert "cannot use a known insecure default" in str(excinfo.value)


# -----------------------------------------------------------------------------
# 3. Secret Length Validation (< 32 chars rejected in production)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "short_secret",
    [
        "too-short",
        "only-20-chars-here!!",
        "31-chars-long-secret-key-here-x",
    ],
)
def test_production_short_secret_rejected(short_secret):
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENV="production",
            SECRET_KEY=short_secret,
            ALLOWED_ORIGINS=VALID_PROD_ORIGIN,
            DEBUG=False,
        )
    assert "SECRET_KEY" in str(excinfo.value)
    assert "at least 32 characters long" in str(excinfo.value)


# -----------------------------------------------------------------------------
# 4. Valid Configured Secret Accepted in Production
# -----------------------------------------------------------------------------
def test_production_valid_configured_secret_accepted():
    random_secret = secrets.token_hex(32)  # 64-char cryptographically strong
    prod_settings = Settings(
        ENV="production",
        SECRET_KEY=random_secret,
        ALLOWED_ORIGINS=VALID_PROD_ORIGIN,
        DEBUG=False,
    )
    assert prod_settings.is_production is True
    assert prod_settings.SECRET_KEY == random_secret
    assert validate_production_settings(prod_settings) is True


# -----------------------------------------------------------------------------
# 5. Production CORS Rejects Wildcard Origins When Credentials Enabled
# -----------------------------------------------------------------------------
def test_production_cors_wildcard_rejected():
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENV="production",
            SECRET_KEY=VALID_PROD_SECRET,
            ALLOWED_ORIGINS="*",
            DEBUG=False,
        )
    assert "ALLOWED_ORIGINS" in str(excinfo.value)
    assert "cannot be '*'" in str(excinfo.value)

    # Also reject wildcard mixed with specific origins
    with pytest.raises(ValueError) as excinfo_mixed:
        Settings(
            ENV="production",
            SECRET_KEY=VALID_PROD_SECRET,
            ALLOWED_ORIGINS="https://campus.college.edu, *",
            DEBUG=False,
        )
    assert "ALLOWED_ORIGINS" in str(excinfo_mixed.value)
    assert "cannot contain wildcard '*'" in str(excinfo_mixed.value)


def test_production_cors_missing_origins_rejected():
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENV="production",
            SECRET_KEY=VALID_PROD_SECRET,
            ALLOWED_ORIGINS="",
            DEBUG=False,
        )
    assert "ALLOWED_ORIGINS" in str(excinfo.value)
    assert "required" in str(excinfo.value)


# -----------------------------------------------------------------------------
# 6. Development Configuration Provides Safe Defaults
# -----------------------------------------------------------------------------
def test_development_defaults_safe_and_functional():
    dev_settings = Settings(
        ENV="development",
        SECRET_KEY=None,
        ALLOWED_ORIGINS=None,
        DEBUG=True,
    )
    assert dev_settings.is_development is True
    assert dev_settings.is_production is False
    assert dev_settings.SECRET_KEY == DEV_DEFAULT_SECRET_KEY
    assert "http://localhost:3000" in dev_settings.CORS_ORIGINS
    assert "http://127.0.0.1:3000" in dev_settings.CORS_ORIGINS
    assert "http://localhost:8000" in dev_settings.CORS_ORIGINS


# -----------------------------------------------------------------------------
# 7. Allowed Frontend Origins Receive Proper CORS Headers
# -----------------------------------------------------------------------------
def test_allowed_frontend_origin_receives_cors_headers():
    allowed_origin = "http://localhost:3000"
    headers = {
        "Origin": allowed_origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type,Authorization",
    }
    # Preflight OPTIONS request
    response = client.options("/api/v1/auth/login", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == allowed_origin
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert "POST" in response.headers.get("access-control-allow-methods", "")

    # Normal GET request
    get_resp = client.get("/health", headers={"Origin": allowed_origin})
    assert get_resp.status_code == 200
    assert get_resp.headers.get("access-control-allow-origin") == allowed_origin
    assert get_resp.headers.get("access-control-allow-credentials") == "true"


# -----------------------------------------------------------------------------
# 8. Disallowed Browser Origins Are Not Granted CORS Permission
# -----------------------------------------------------------------------------
def test_disallowed_origin_not_granted_cors_permission():
    disallowed_origin = "http://malicious-attacker.com"
    headers = {
        "Origin": disallowed_origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type,Authorization",
    }
    # Preflight OPTIONS request
    response = client.options("/api/v1/auth/login", headers=headers)
    # Disallowed origin must not receive Access-Control-Allow-Origin granting access
    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin != disallowed_origin

    # Normal GET request
    get_resp = client.get("/health", headers={"Origin": disallowed_origin})
    assert get_resp.status_code == 200
    allow_origin_get = get_resp.headers.get("access-control-allow-origin")
    assert allow_origin_get != disallowed_origin


# -----------------------------------------------------------------------------
# 9. JWT Token Generation and Verification Integrity
# -----------------------------------------------------------------------------
def test_jwt_token_creation_and_verification_integrity():
    token = create_access_token(
        user_id=42,
        username="security_tester",
        role="student",
        linked_student_id=99,
        email="security@campus.edu",
    )
    assert isinstance(token, str)

    # Valid token decodes correctly
    token_data = decode_token(token)
    assert token_data is not None
    assert token_data.user_id == 42
    assert token_data.username == "security_tester"
    assert token_data.role == "student"
    assert token_data.linked_student_id == 99
    assert token_data.email == "security@campus.edu"

    # Tampered token fails
    tampered_token = token[:-5] + ("ABCDE" if not token.endswith("ABCDE") else "XYZ12")
    assert decode_token(tampered_token) is None


# -----------------------------------------------------------------------------
# 10. Secrets Are Never Disclosed in Validation Errors
# -----------------------------------------------------------------------------
def test_secrets_never_disclosed_in_validation_errors():
    secret_value = "my-secret-attempt-12345"
    with pytest.raises(ValueError) as excinfo:
        Settings(
            ENV="production",
            SECRET_KEY=secret_value,
            ALLOWED_ORIGINS=VALID_PROD_ORIGIN,
            DEBUG=False,
        )
    error_message = str(excinfo.value)
    # Verify the secret value itself is NOT printed or reflected
    assert secret_value not in error_message
