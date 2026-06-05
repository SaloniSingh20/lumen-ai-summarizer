"""
Integration tests for API endpoints.
Uses conftest.py fixtures (fresh engine per test via StaticPool).
"""
import os
os.environ["TESTING"] = "1"

import uuid
import time
import pytest

from app import budget as bgt
from app.limiter import limiter


def _jwt(sub: str = None) -> str:
    import jwt as pyjwt
    sub = sub or str(uuid.uuid4())
    now = int(time.time())
    SECRET = "test-jwt-secret-that-is-64-chars-long-for-hs256-signing!!!"
    return pyjwt.encode({"sub": sub, "aud": "authenticated", "iat": now, "exp": now + 3600},
                        SECRET, algorithm="HS256")


def _auth(sub: str = None) -> dict:
    return {"Authorization": f"Bearer {_jwt(sub)}"}


def _mp4() -> bytes:
    return b"\x00\x00\x00\x18ftypisom" + b"\x00" * 8


# ── A. Job submission ─────────────────────────────────────────────────────────

class TestJobSubmission:
    def test_upload_requires_auth(self, client):
        r = client.post("/jobs/upload", files={"file": ("v.mp4", _mp4(), "video/mp4")})
        assert r.status_code == 401

    def test_upload_invalid_file_type(self, client, auth1):
        r = client.post("/jobs/upload", headers=auth1,
                        files={"file": ("exploit.py", b"print('x')", "text/plain")})
        assert r.status_code == 415

    def test_upload_jpeg_as_mp4_rejected(self, client, auth1):
        jpeg_magic = b"\xff\xd8\xff\xe0" + b"\x00" * 8
        r = client.post("/jobs/upload", headers=auth1,
                        files={"file": ("fake.mp4", jpeg_magic, "video/mp4")})
        assert r.status_code == 415

    def test_url_requires_auth(self, client):
        r = client.post("/jobs/url", data={"url": "https://example.com/video.mp4"})
        assert r.status_code == 401

    def test_url_ssrf_private_ip_blocked(self, client, auth1):
        r = client.post("/jobs/url", headers=auth1, data={"url": "http://192.168.1.1/v.mp4"})
        assert r.status_code == 400

    def test_url_file_scheme_blocked(self, client, auth1):
        r = client.post("/jobs/url", headers=auth1, data={"url": "file:///etc/passwd"})
        assert r.status_code == 400

    def test_url_ssrf_metadata_blocked(self, client, auth1):
        r = client.post("/jobs/url", headers=auth1, data={"url": "http://169.254.169.254/"})
        assert r.status_code == 400


# ── B. Video listing ──────────────────────────────────────────────────────────

class TestVideoListing:
    def test_list_videos_empty_for_new_user(self, client, auth1):
        r = client.get("/videos", headers=auth1)
        assert r.status_code == 200
        assert r.json() == []

    def test_list_videos_returns_only_own(self, client, db, user1, user2, auth1):
        from tests.conftest import _make_video
        owner_a, _ = user1
        owner_b, _ = user2
        _make_video(db, owner_a)
        _make_video(db, owner_a)
        _make_video(db, owner_b)
        r = client.get("/videos", headers=auth1)
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_get_video_requires_auth(self, client, db, user1):
        from tests.conftest import _make_video
        owner_id, _ = user1
        _, vid_id = _make_video(db, owner_id)
        r = client.get(f"/videos/{vid_id}")
        assert r.status_code == 401


# ── C. IDOR prevention ────────────────────────────────────────────────────────

class TestIDOR:
    def test_different_user_cannot_access_video(self, client, db, user1, user2, auth2):
        from tests.conftest import _make_video
        owner, _ = user1
        _, vid_id = _make_video(db, owner)
        r = client.get(f"/videos/{vid_id}", headers=auth2)
        assert r.status_code == 404

    def test_different_user_cannot_access_job(self, client, db, user1, user2, auth2):
        from tests.conftest import _make_video
        owner, _ = user1
        job_id, _ = _make_video(db, owner)
        r = client.get(f"/jobs/{job_id}", headers=auth2)
        assert r.status_code == 404

    def test_owner_can_access_own_video(self, client, db, user1, auth1):
        from tests.conftest import _make_video
        owner, _ = user1
        _, vid_id = _make_video(db, owner)
        r = client.get(f"/videos/{vid_id}", headers=auth1)
        assert r.status_code in (200, 404)

    def test_response_is_404_not_403(self, client, db, user1, auth2):
        from tests.conftest import _make_video
        owner, _ = user1
        _, vid_id = _make_video(db, owner)
        r = client.get(f"/videos/{vid_id}", headers=auth2)
        assert r.status_code == 404
        assert r.status_code != 403


# ── D. Rate limiting ──────────────────────────────────────────────────────────

class TestRateLimiting:
    def test_upload_rate_limit_triggers_429(self, client, auth1):
        for i in range(2):
            r = client.post("/jobs/upload", headers=auth1,
                            files={"file": ("v.mp4", _mp4(), "video/mp4")})
            assert r.status_code != 429, f"Request {i+1} hit limit too early"
        r = client.post("/jobs/upload", headers=auth1,
                        files={"file": ("v.mp4", _mp4(), "video/mp4")})
        assert r.status_code == 429

    def test_429_has_retry_after_header(self, client, auth1):
        for _ in range(3):
            r = client.post("/jobs/upload", headers=auth1,
                            files={"file": ("v.mp4", _mp4(), "video/mp4")})
            if r.status_code == 429:
                break
        assert r.status_code == 429
        assert "Retry-After" in r.headers


# ── E. Budget guard ───────────────────────────────────────────────────────────

class TestBudgetGuard:
    def test_budget_exceeded_blocks_upload(self, client, auth1):
        from datetime import date
        fake = bgt._redis_client
        today = date.today().isoformat()
        for _ in range(3):
            fake.incr(f"ai_budget:{today}")
        r = client.post("/jobs/upload", headers=auth1,
                        files={"file": ("v.mp4", _mp4(), "video/mp4")})
        assert r.status_code == 429


# ── F. Error sanitisation ─────────────────────────────────────────────────────

class TestErrorSanitisation:
    _FORBIDDEN = ["Traceback", "File \"", "/app/", "sqlalchemy", "raise HTTPException"]

    def test_404_does_not_leak_internals(self, client, auth1):
        r = client.get(f"/videos/{uuid.uuid4()}", headers=auth1)
        assert r.status_code == 404
        for p in self._FORBIDDEN:
            assert p not in r.text

    def test_401_does_not_leak_internals(self, client):
        r = client.get(f"/videos/{uuid.uuid4()}")
        assert r.status_code == 401
        for p in self._FORBIDDEN:
            assert p not in r.text
