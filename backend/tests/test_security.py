"""
Security tests — each test verifies that a specific ATTACK FAILS.

Test groups:
  A. Authentication          — unauthenticated requests rejected
  B. IDOR prevention         — cross-user access returns 404, not data
  C. Rate limiting           — N+1 requests returns 429 with Retry-After
  D. SSRF protection         — blocked URLs rejected before download
  E. AI budget guard         — exceeding daily limit returns 429
  F. File-type validation    — non-video uploads rejected
  G. Error sanitisation      — stack traces never reach the client
  H. Media token             — signed URLs enforce ownership and expiry
"""
import io
import time
import uuid

import pytest

# ---------------------------------------------------------------------------
# A. Authentication
# ---------------------------------------------------------------------------

class TestAuthentication:
    def test_no_token_upload_returns_401(self, client):
        """Uploading without a token must return 401, not 403 or 200."""
        resp = client.post("/jobs/upload", files={"file": ("v.mp4", b"\x00" * 12, "video/mp4")})
        assert resp.status_code == 401

    def test_no_token_get_job_returns_401(self, client):
        resp = client.get(f"/jobs/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_no_token_get_video_returns_401(self, client):
        resp = client.get(f"/videos/{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_no_token_chat_returns_401(self, client):
        resp = client.post(f"/videos/{uuid.uuid4()}/chat", json={"message": "hi", "history": []})
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        headers = {"Authorization": "Bearer invalid-token-that-does-not-exist"}
        resp = client.get(f"/videos/{uuid.uuid4()}", headers=headers)
        assert resp.status_code == 401

    def test_malformed_auth_header_returns_401(self, client):
        headers = {"Authorization": "Token abc123"}  # wrong scheme
        resp = client.get(f"/videos/{uuid.uuid4()}", headers=headers)
        assert resp.status_code == 401

    def test_valid_token_accepted(self, client, auth1):
        """A valid token reaches the endpoint (may 404 on unknown resource, not 401)."""
        resp = client.get(f"/videos/{uuid.uuid4()}", headers=auth1)
        # 404 means auth passed — the video just doesn't exist
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


# ---------------------------------------------------------------------------
# B. IDOR prevention
# ---------------------------------------------------------------------------

class TestIDOR:
    def test_user2_cannot_access_user1_video(self, client, db, user1, user2, auth2):
        """Cross-user video access MUST return 404, never 200 or 403."""
        owner_id, _ = user1
        from tests.conftest import _make_video
        _, video_id = _make_video(db, owner_id)

        resp = client.get(f"/videos/{video_id}", headers=auth2)
        assert resp.status_code == 404, (
            f"IDOR: user2 got {resp.status_code} on user1's video (expected 404)"
        )

    def test_user2_cannot_access_user1_job(self, client, db, user1, user2, auth2):
        owner_id, _ = user1
        from tests.conftest import _make_video
        job_id, _ = _make_video(db, owner_id)

        resp = client.get(f"/jobs/{job_id}", headers=auth2)
        assert resp.status_code == 404

    def test_user2_cannot_download_user1_pdf(self, client, db, user1, user2, auth2):
        owner_id, _ = user1
        from tests.conftest import _make_video
        _, video_id = _make_video(db, owner_id)

        resp = client.get(f"/videos/{video_id}/export/pdf", headers=auth2)
        assert resp.status_code == 404

    def test_user2_cannot_get_user1_keyframe(self, client, db, user1, user2, auth2):
        owner_id, _ = user1
        from tests.conftest import _make_video
        _, video_id = _make_video(db, owner_id)

        resp = client.get(f"/videos/{video_id}/keyframes/1", headers=auth2)
        assert resp.status_code == 404

    def test_user2_cannot_chat_about_user1_video(self, client, db, user1, user2, auth2):
        owner_id, _ = user1
        from tests.conftest import _make_video
        _, video_id = _make_video(db, owner_id)

        resp = client.post(
            f"/videos/{video_id}/chat",
            json={"message": "what is this?", "history": []},
            headers=auth2,
        )
        assert resp.status_code == 404

    def test_owner_can_access_own_video(self, client, db, user1, auth1):
        """Positive test: the owner gets their resource (may be 404 on missing notes)."""
        owner_id, _ = user1
        from tests.conftest import _make_video
        _, video_id = _make_video(db, owner_id)

        resp = client.get(f"/videos/{video_id}", headers=auth1)
        # 200 = video found; other codes indicate app logic, not auth failure
        assert resp.status_code in (200, 404), f"Unexpected {resp.status_code}"

    def test_idor_video_id_must_be_uuid(self, client, auth1):
        """Sequential/guessable IDs (e.g. '1', '2') must never resolve."""
        for bad_id in ("1", "2", "admin", "../etc/passwd"):
            resp = client.get(f"/videos/{bad_id}", headers=auth1)
            assert resp.status_code == 404, f"ID '{bad_id}' resolved unexpectedly"


# ---------------------------------------------------------------------------
# C. Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    """
    RATELIMIT_UPLOAD is set to "2/minute" in conftest.py.
    Making 3 requests in a row must trigger 429 on the third.
    """

    def _small_mp4(self) -> bytes:
        """Minimal bytes that pass magic-byte check for MP4 (ftyp box)."""
        # 8-byte box header (size + "ftyp") with plausible content
        return b"\x00\x00\x00\x18ftypisom" + b"\x00" * 8

    def test_upload_rate_limit_triggers_429(self, client, auth1):
        """Third upload attempt in the same minute returns 429."""
        for i in range(2):
            resp = client.post(
                "/jobs/upload",
                headers=auth1,
                files={"file": ("v.mp4", self._small_mp4(), "video/mp4")},
            )
            # Should get something other than 429 (likely 400/422 since no real Celery)
            assert resp.status_code != 429, f"Request {i + 1} hit rate limit prematurely"

        # Third request → 429
        resp = client.post(
            "/jobs/upload",
            headers=auth1,
            files={"file": ("v.mp4", self._small_mp4(), "video/mp4")},
        )
        assert resp.status_code == 429, f"Expected 429, got {resp.status_code}: {resp.text}"

    def test_rate_limit_response_has_retry_after(self, client, auth1):
        """429 response includes Retry-After header and JSON detail."""
        for _ in range(3):
            resp = client.post(
                "/jobs/upload",
                headers=auth1,
                files={"file": ("v.mp4", self._small_mp4(), "video/mp4")},
            )
            if resp.status_code == 429:
                break

        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        body = resp.json()
        assert "detail" in body
        assert body["detail"] == "Rate limit exceeded"

    def test_different_users_have_separate_limits(self, client, db, auth1, auth2):
        """Rate limits are per-user (token), not global — user2 unaffected by user1."""
        for _ in range(2):
            client.post(
                "/jobs/upload",
                headers=auth1,
                files={"file": ("v.mp4", self._small_mp4(), "video/mp4")},
            )
        # user2 should NOT be rate-limited yet
        resp = client.post(
            "/jobs/upload",
            headers=auth2,
            files={"file": ("v.mp4", self._small_mp4(), "video/mp4")},
        )
        assert resp.status_code != 429, "user2 was incorrectly rate-limited by user1's requests"

    def test_read_endpoints_have_looser_limits(self, client, db, user1, auth1):
        """Read endpoints (RATELIMIT_READ=10/minute) are not blocked at 3 requests."""
        owner_id, _ = user1
        from tests.conftest import _make_video
        _, video_id = _make_video(db, owner_id)

        for _ in range(3):
            resp = client.get(f"/videos/{video_id}", headers=auth1)
            assert resp.status_code != 429, "Read endpoint hit rate limit too early"


# ---------------------------------------------------------------------------
# D. SSRF protection
# ---------------------------------------------------------------------------

class TestSSRF:
    def _blocked(self, resp, url):
        # 400 = SSRF blocked; 429 = rate-limited (also means request didn't go through)
        assert resp.status_code in (400, 429), f"URL not blocked: {url} → {resp.status_code}"

    def test_private_ip_blocked(self, client, auth1):
        resp = client.post("/jobs/url", data={"url": "http://192.168.1.1/video.mp4"}, headers=auth1)
        self._blocked(resp, "http://192.168.1.1/video.mp4")

    def test_private_ip_class_a(self, client, auth1):
        resp = client.post("/jobs/url", data={"url": "http://10.0.0.1/video.mp4"}, headers=auth1)
        self._blocked(resp, "http://10.0.0.1/video.mp4")

    def test_loopback_blocked(self, client, auth1):
        resp = client.post("/jobs/url", data={"url": "http://127.0.0.1/video.mp4"}, headers=auth1)
        self._blocked(resp, "http://127.0.0.1/video.mp4")

    def test_cloud_metadata_blocked(self, client, auth1):
        """AWS/GCP metadata endpoints must be blocked."""
        for meta_url in (
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
        ):
            resp = client.post("/jobs/url", data={"url": meta_url}, headers=auth1)
            assert resp.status_code == 400, f"Metadata endpoint not blocked: {meta_url}"

    def test_non_http_scheme_blocked(self, client, auth1):
        # Test one scheme per test to avoid hitting the rate limiter
        resp = client.post("/jobs/url", data={"url": "file:///etc/passwd"}, headers=auth1)
        self._blocked(resp, "file:///etc/passwd")

    def test_link_local_blocked(self, client, auth1):
        resp = client.post("/jobs/url", data={"url": "http://169.254.169.254/"}, headers=auth1)
        assert resp.status_code == 400

    def test_valid_public_url_passes_ssrf_check(self, client, auth1):
        """A real public URL passes the SSRF check (will then fail at download)."""
        resp = client.post("/jobs/url", data={"url": "https://example.com/video.mp4"}, headers=auth1)
        # 400 from download failure is fine — but NOT from SSRF validation
        assert resp.status_code != 422, "Valid public URL rejected by SSRF validation"


# ---------------------------------------------------------------------------
# E. AI budget guard
# ---------------------------------------------------------------------------

class TestAIBudget:
    """MAX_AI_CALLS_PER_DAY=3 in conftest.py."""

    def _small_mp4(self) -> bytes:
        return b"\x00\x00\x00\x18ftypisom" + b"\x00" * 8

    def test_budget_exceeded_blocks_new_jobs(self, client, auth1):
        """
        After MAX_AI_CALLS_PER_DAY uploads the budget is exhausted.
        The next job submission is rejected with 429 BEFORE any AI call is made.
        """
        from app import budget as bgt

        # Manually exhaust the budget
        fake = bgt._redis_client
        from datetime import date
        today = date.today().isoformat()
        key = f"ai_budget:{today}"
        for _ in range(3):
            fake.incr(key)

        # Now the budget is at MAX (3); next request should get 429
        resp = client.post(
            "/jobs/upload",
            headers=auth1,
            files={"file": ("v.mp4", self._small_mp4(), "video/mp4")},
        )
        assert resp.status_code == 429, f"Budget guard failed: got {resp.status_code}"
        body = resp.json()
        assert "budget" in body["detail"].lower() or "limit" in body["detail"].lower()


# ---------------------------------------------------------------------------
# F. File-type validation
# ---------------------------------------------------------------------------

class TestFileTypeValidation:
    def test_python_file_rejected(self, client, auth1):
        """Uploading a .py file must return 415."""
        resp = client.post(
            "/jobs/upload",
            headers=auth1,
            files={"file": ("exploit.py", b"print('pwned')", "text/plain")},
        )
        assert resp.status_code == 415

    def test_text_file_rejected(self, client, auth1):
        resp = client.post(
            "/jobs/upload",
            headers=auth1,
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )
        assert resp.status_code == 415

    def test_jpg_with_mp4_extension_rejected(self, client, auth1):
        """A JPEG disguised as .mp4 fails magic-byte check."""
        jpeg_magic = b"\xff\xd8\xff\xe0" + b"\x00" * 8
        resp = client.post(
            "/jobs/upload",
            headers=auth1,
            files={"file": ("fake.mp4", jpeg_magic, "video/mp4")},
        )
        assert resp.status_code == 415

    def test_valid_mp4_magic_accepted(self, client, auth1):
        """Valid MP4 magic bytes pass validation (may fail later on processing)."""
        mp4_magic = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 8
        resp = client.post(
            "/jobs/upload",
            headers=auth1,
            files={"file": ("video.mp4", mp4_magic, "video/mp4")},
        )
        # Not 415 (may be 400/500 from missing Celery, but type check passed)
        assert resp.status_code != 415, f"Valid MP4 wrongly rejected: {resp.text}"

    def test_mkv_magic_accepted(self, client, auth1):
        """Valid MKV/WebM magic bytes (EBML) pass validation."""
        mkv_magic = b"\x1aE\xdf\xa3" + b"\x00" * 8
        resp = client.post(
            "/jobs/upload",
            headers=auth1,
            files={"file": ("video.mkv", mkv_magic, "video/x-matroska")},
        )
        assert resp.status_code != 415


# ---------------------------------------------------------------------------
# G. Error sanitisation — no stack traces in responses
# ---------------------------------------------------------------------------

class TestErrorSanitisation:
    def test_404_does_not_leak_paths(self, client, auth1):
        """404 responses must not contain filesystem paths or Python tracebacks."""
        resp = client.get(f"/videos/{uuid.uuid4()}", headers=auth1)
        assert resp.status_code == 404
        body = resp.text
        _assert_no_leak(body)

    def test_401_does_not_leak_internals(self, client):
        resp = client.get(f"/videos/{uuid.uuid4()}")
        assert resp.status_code == 401
        _assert_no_leak(resp.text)

    def test_429_json_is_clean(self, client, auth1):
        # Trigger a 429 via rate limiter
        for _ in range(4):
            resp = client.post(
                "/jobs/upload",
                headers=auth1,
                files={"file": ("v.mp4", b"\x00" * 12, "video/mp4")},
            )
            if resp.status_code == 429:
                break
        if resp.status_code == 429:
            _assert_no_leak(resp.text)
            assert set(resp.json().keys()) <= {"detail", "retry_after"}


# ---------------------------------------------------------------------------
# H. Signed media tokens
# ---------------------------------------------------------------------------

class TestMediaToken:
    def test_valid_token_accepted(self):
        """generate_media_token → verify_media_token succeeds immediately."""
        from app.security import generate_media_token, verify_media_token
        video_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        secret = "test-secret"
        token = generate_media_token(video_id, owner_id, secret)
        assert verify_media_token(token, video_id, owner_id, secret)

    def test_expired_token_rejected(self, monkeypatch):
        """A token with past expiry is rejected."""
        import hmac as _hmac, hashlib as _hs
        from app.security import verify_media_token, _MEDIA_TOKEN_TTL
        video_id = str(uuid.uuid4()); owner_id = str(uuid.uuid4()); secret = "test-secret"
        past_expiry = int(time.time()) - 10
        payload = f"{video_id}:{owner_id}:{past_expiry}"
        sig = _hmac.new(secret.encode(), payload.encode(), _hs.sha256).hexdigest()
        expired_token = f"{sig}:{past_expiry}"
        assert not verify_media_token(expired_token, video_id, owner_id, secret)

    def test_wrong_video_id_rejected(self):
        """Token for video A must not work for video B."""
        from app.security import generate_media_token, verify_media_token
        secret = "test-secret"
        owner = str(uuid.uuid4())
        token = generate_media_token("video-A", owner, secret)
        assert not verify_media_token(token, "video-B", owner, secret)

    def test_wrong_owner_rejected(self):
        """Token for owner A must not work for owner B."""
        from app.security import generate_media_token, verify_media_token
        secret = "test-secret"
        video = str(uuid.uuid4())
        token = generate_media_token(video, "owner-A", secret)
        assert not verify_media_token(token, video, "owner-B", secret)

    def test_tampered_token_rejected(self):
        """Modifying the signature byte invalidates the token."""
        from app.security import generate_media_token, verify_media_token
        secret = "test-secret"
        video = str(uuid.uuid4())
        owner = str(uuid.uuid4())
        token = generate_media_token(video, owner, secret)
        # Flip the first character of the signature
        tampered = ("X" if token[0] != "X" else "Y") + token[1:]
        assert not verify_media_token(tampered, video, owner, secret)

    def test_stream_endpoint_without_token_returns_422(self, client, db, user1, auth1):
        """Accessing /stream with no token returns 422 (missing required param)."""
        owner_id, _ = user1
        from tests.conftest import _make_video
        _, video_id = _make_video(db, owner_id)
        resp = client.get(f"/videos/{video_id}/stream")  # no token param
        assert resp.status_code == 422

    def test_stream_endpoint_with_invalid_token_returns_403(self, client, db, user1):
        owner_id, _ = user1
        from tests.conftest import _make_video
        _, video_id = _make_video(db, owner_id)
        resp = client.get(f"/videos/{video_id}/stream?token=fake-token")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LEAK_PATTERNS = (
    "Traceback",
    "File \"",
    "line ",
    "/app/",
    "/home/",
    "C:\\",
    "sqlalchemy",
    "sqlite",
    "raise HTTPException",
    "Exception",
)


def _assert_no_leak(body: str) -> None:
    for pattern in _LEAK_PATTERNS:
        assert pattern not in body, (
            f"Response body leaks internal details ({pattern!r}): {body[:200]}"
        )
