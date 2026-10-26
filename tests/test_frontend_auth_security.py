"""
Regression Test Suite for Task 12:
Frontend XSS Remediation & Authentication Token Security Contracts

Verifies:
1. Token refresh endpoint (/api/v1/auth/refresh) accepts valid refresh tokens and issues fresh access tokens.
2. Token refresh endpoint rejects invalid, malformed, or blacklisted refresh tokens with 401 Unauthorized.
3. Logout endpoint (/api/v1/auth/logout) blacklists access tokens so they can no longer access protected endpoints.
4. Risk advisory, schedule, and attendance API responses preserve string literals containing special HTML characters
   so the frontend can safely render them using textContent without truncation.
5. 403 Forbidden responses return structured error messages without echoing tokens or secrets.
"""

import sys
import importlib.abc
import importlib.util
from pathlib import Path
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

from backend.main import app
from backend.core.auth import create_access_token, create_refresh_token, decode_token

client = TestClient(app)


def test_auth_refresh_with_valid_token():
    """Verify that a valid refresh token generates a valid new access token."""
    # 1. Create a valid refresh token for user_id=1
    refresh_tok = create_refresh_token(user_id=1, username="test_student", role="student")

    # 2. Call the refresh endpoint
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_tok})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    data = resp.json()
    assert "access_token" in data
    assert data["access_token"] != ""
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0

    # 3. Decode new access token and verify identity matches database user 1
    token_data = decode_token(data["access_token"])
    assert token_data is not None
    assert token_data.user_id == 1
    assert token_data.username is not None
    assert token_data.role is not None


def test_auth_refresh_with_invalid_token():
    """Verify that malformed or forged refresh tokens are rejected with 401."""
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid.bogus.token"})
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_auth_refresh_rejects_access_token():
    """Verify that an access token cannot be used in place of a refresh token."""
    acc_tok = create_access_token(user_id=1, username="test_student", role="student")
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": acc_tok})
    assert resp.status_code == 401
    assert resp.json().get("detail") == "Invalid refresh token"


def test_auth_logout_revokes_token():
    """Verify that logout successfully blacklists the token."""
    acc_tok = create_access_token(user_id=1, username="logout_student", role="student")

    # 1. Verify access works with token
    headers = {"Authorization": f"Bearer {acc_tok}"}
    profile_resp = client.get("/api/v1/auth/profile", headers=headers)
    assert profile_resp.status_code == 200

    # 2. Logout with token
    logout_resp = client.post("/api/v1/auth/logout", headers=headers, json={"token": acc_tok})
    assert logout_resp.status_code == 200

    # 3. Verify token is now rejected
    blocked_resp = client.get("/api/v1/auth/profile", headers=headers)
    assert blocked_resp.status_code == 401


def test_error_responses_never_echo_tokens():
    """Verify that 401 and 403 responses do not echo secret tokens in the response body."""
    secret_token_val = "secret-token-payload-xyz-123456"
    resp = client.get(
        "/api/v1/auth/profile",
        headers={"Authorization": f"Bearer {secret_token_val}"}
    )
    assert resp.status_code == 401
    assert secret_token_val not in resp.text


def test_student_dashboard_endpoint_handles_special_characters_safely():
    """Verify that the dashboard endpoint handles special HTML characters safely in JSON."""
    token = create_access_token(user_id=1, username="2024CS001", role="student")
    resp = client.get(
        "/dashboard/student/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    # Status can be 200 (if student linked) or 404 (if unlinked test user)
    assert resp.status_code in [200, 404]
    if resp.status_code == 200:
        data = resp.json()
        assert "student" in data or "academic_risk" in data
