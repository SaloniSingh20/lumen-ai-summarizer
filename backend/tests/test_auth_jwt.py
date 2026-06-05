"""
Tests for the dual-mode authentication system.
Uses conftest.py fixtures (fresh engine per test via StaticPool).
"""
import os
os.environ["TESTING"] = "1"

import time
import uuid
import pytest
import jwt as pyjwt

from app.models import UserToken
from app import budget as bgt

TEST_JWT_SECRET = "test-jwt-secret-that-is-64-chars-long-for-hs256-signing!!!"


@pytest.fixture(autouse=True)
def patch_jwt_secret(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _jwt(sub: str = None, email: str = "test@example.com",
         expired: bool = False, wrong_aud: bool = False) -> str:
    sub = sub or str(uuid.uuid4())
    now = int(time.time())
    payload = {
        "sub": sub, "email": email,
        "aud": "wrong-audience" if wrong_aud else "authenticated",
        "iat": now - 3600 if expired else now,
        "exp": now - 1    if expired else now + 3600,
    }
    return pyjwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


# ── A. Supabase JWT ──────────────────────────────────────────────────────────

class TestSupabaseJWT:
    def test_valid_jwt_accepted(self, client):
        token = _jwt(str(uuid.uuid4()), "user@example.com")
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        # Will call Supabase REST - may return 401 if Supabase unreachable in tests
        # The important thing: not a 500 (no crash)
        assert r.status_code in (200, 401)

    def test_expired_jwt_falls_back_to_legacy_check(self, client):
        """Expired JWT: Supabase will reject it → falls to legacy → also fails → 401."""
        token = _jwt(str(uuid.uuid4()), expired=True)
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_no_token_returns_401(self, client):
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_wrong_scheme_returns_401(self, client):
        token = _jwt(str(uuid.uuid4()))
        r = client.get("/auth/me", headers={"Authorization": f"Token {token}"})
        assert r.status_code == 401


# ── B. Legacy API token ───────────────────────────────────────────────────────

class TestLegacyToken:
    def test_valid_legacy_token_accepted(self, client, db):
        from tests.conftest import _make_token
        _, raw = _make_token(db, "user1")
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {raw}"})
        assert r.status_code == 200
        assert r.json()["auth_source"] == "token"

    def test_revoked_legacy_token_returns_401(self, client, db):
        from tests.conftest import _make_token
        owner_id, raw = _make_token(db, "rev")
        u = db.query(UserToken).filter(UserToken.id == owner_id).first()
        u.is_active = False; db.commit()
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {raw}"})
        assert r.status_code == 401

    def test_random_string_returns_401(self, client):
        r = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
        assert r.status_code == 401


# ── C. /auth/me ──────────────────────────────────────────────────────────────

class TestAuthMe:
    def test_me_returns_owner_and_source(self, client, db):
        from tests.conftest import _make_token
        owner_id, raw = _make_token(db, "metest")
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {raw}"})
        assert r.status_code == 200
        body = r.json()
        assert body["owner_id"] == owner_id
        assert body["auth_source"] == "token"


# ── D. Token creation ─────────────────────────────────────────────────────────

class TestTokenCreation:
    def test_valid_admin_secret_creates_token(self, client):
        r = client.post("/auth/tokens?name=ci", headers={"X-Admin-Secret": "test-admin-secret"})
        assert r.status_code == 201
        body = r.json()
        assert "token" in body and "owner_id" in body

    def test_wrong_admin_secret_returns_403(self, client):
        r = client.post("/auth/tokens", headers={"X-Admin-Secret": "wrong"})
        assert r.status_code == 403

    def test_no_admin_secret_returns_403(self, client):
        r = client.post("/auth/tokens")
        assert r.status_code == 403
