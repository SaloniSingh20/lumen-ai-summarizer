"""
Unit tests for pipeline utilities:
  A. Time parser (Lumen time-range queries)
  B. Scene detection fallback
  C. Media token signing
  D. SSRF URL validation
  E. File-type magic bytes
"""
import os
os.environ["TESTING"] = "1"

import time
import uuid
import pytest
from fastapi import HTTPException

from app.utils.time_parser import parse_time_range, parse_time_token
from app.security import generate_media_token, verify_media_token, validate_ingest_url, validate_upload_magic


# ── A. Time parser ────────────────────────────────────────────────────────────

class TestTimeParser:
    def test_seconds_range(self):
        r = parse_time_range("from 10s to 30s")
        assert r and r.start == 10.0 and r.end == 30.0

    def test_colon_format(self):
        r = parse_time_range("1:30 to 2:00")
        assert r and r.start == 90.0 and r.end == 120.0

    def test_last_n_seconds(self):
        r = parse_time_range("last 30 seconds", video_duration=120.0)
        assert r and r.start == 90.0 and r.end == 120.0

    def test_first_minute(self):
        r = parse_time_range("first minute")
        assert r and r.start == 0.0 and r.end == 60.0

    def test_beginning(self):
        r = parse_time_range("the beginning", video_duration=300.0)
        assert r and r.start == 0.0 and r.end > 0.0

    def test_the_end(self):
        r = parse_time_range("the end", video_duration=300.0)
        assert r and r.end == 300.0

    def test_minute_n(self):
        r = parse_time_range("minute 2")
        assert r and r.start == 60.0 and r.end == 120.0

    def test_no_range_general_question(self):
        assert parse_time_range("what are the main topics?") is None

    def test_between_and(self):
        r = parse_time_range("between 1:00 and 1:30")
        assert r and r.start == 60.0 and r.end == 90.0

    def test_plain_seconds_token(self):
        assert parse_time_token("45s")  == 45.0
        assert parse_time_token("2min") == 120.0
        assert parse_time_token("1:30") == 90.0


# ── B. Scene detection fallback ───────────────────────────────────────────────

class TestSceneDetectionFallback:
    def test_short_video_returns_one_scene(self, tmp_path):
        """_fallback_scenes should return 1 scene for <30 s videos."""
        from app.pipeline.scenes import _fallback_scenes
        import cv2, numpy as np

        # Create a tiny synthetic MP4
        out = str(tmp_path / "tiny.mp4")
        writer = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 64))
        for _ in range(50):  # 5 seconds at 10 fps
            frame = np.zeros((64, 64, 3), dtype=np.uint8)
            writer.write(frame)
        writer.release()

        scenes = _fallback_scenes(out)
        assert len(scenes) == 1
        assert scenes[0]["scene_number"] == 1
        assert scenes[0]["start_time"] == 0.0
        assert scenes[0]["end_time"] > 0

    def test_fallback_covers_full_duration(self):
        """Fallback scenes must cover the whole video without gaps."""
        from app.pipeline.scenes import _fallback_scenes
        from unittest.mock import patch

        # Mock cv2 to report 60 seconds
        with patch("app.pipeline.scenes.cv2.VideoCapture") as mock_cap:
            cap_instance = mock_cap.return_value
            cap_instance.get.side_effect = lambda prop: {
                0x05: 30.0,   # CAP_PROP_FPS
                0x07: 1800.0, # CAP_PROP_FRAME_COUNT → 60 s
            }.get(prop, 0)
            cap_instance.release.return_value = None

            scenes = _fallback_scenes("/fake/video.mp4")

        total = sum(s["end_time"] - s["start_time"] for s in scenes)
        assert abs(total - 60.0) < 0.5, "Fallback scenes don't cover full duration"


# ── C. Media token ────────────────────────────────────────────────────────────

class TestMediaToken:
    SECRET = "test-secret-key"

    def test_valid_token_accepted(self):
        vid = str(uuid.uuid4()); owner = str(uuid.uuid4())
        t = generate_media_token(vid, owner, self.SECRET)
        assert verify_media_token(t, vid, owner, self.SECRET)

    def test_expired_token_rejected(self):
        vid = str(uuid.uuid4()); owner = str(uuid.uuid4())
        # Build a token with an expiry already in the past
        import hmac as _hmac, hashlib as _hs
        past_expiry = int(time.time()) - 10   # 10 seconds ago
        payload = f"{vid}:{owner}:{past_expiry}"
        sig = _hmac.new(self.SECRET.encode(), payload.encode(), _hs.sha256).hexdigest()
        expired_token = f"{sig}:{past_expiry}"
        assert not verify_media_token(expired_token, vid, owner, self.SECRET)

    def test_wrong_video_rejected(self):
        owner = str(uuid.uuid4())
        t = generate_media_token("video-A", owner, self.SECRET)
        assert not verify_media_token(t, "video-B", owner, self.SECRET)

    def test_wrong_owner_rejected(self):
        vid = str(uuid.uuid4())
        t = generate_media_token(vid, "owner-A", self.SECRET)
        assert not verify_media_token(t, vid, "owner-B", self.SECRET)

    def test_tampered_token_rejected(self):
        vid = str(uuid.uuid4()); owner = str(uuid.uuid4())
        t = generate_media_token(vid, owner, self.SECRET)
        tampered = ("X" if t[0] != "X" else "Y") + t[1:]
        assert not verify_media_token(tampered, vid, owner, self.SECRET)


# ── D. SSRF validation ────────────────────────────────────────────────────────

class TestSSRF:
    def _ok(self, url): validate_ingest_url(url)   # must not raise
    def _bad(self, url):
        with pytest.raises(HTTPException) as exc:
            validate_ingest_url(url)
        assert exc.value.status_code == 400

    def test_public_https_ok(self):      self._ok("https://example.com/video.mp4")
    def test_youtube_ok(self):           self._ok("https://youtu.be/dQw4w9WgXcQ")
    def test_private_class_a(self):      self._bad("http://10.0.0.1/v.mp4")
    def test_private_class_b(self):      self._bad("http://172.16.0.1/v.mp4")
    def test_private_class_c(self):      self._bad("http://192.168.1.1/v.mp4")
    def test_loopback(self):             self._bad("http://127.0.0.1/v.mp4")
    def test_localhost(self):            self._bad("http://localhost/v.mp4")
    def test_aws_metadata(self):         self._bad("http://169.254.169.254/latest/")
    def test_gcp_metadata(self):         self._bad("http://metadata.google.internal/")
    def test_file_scheme(self):          self._bad("file:///etc/passwd")
    def test_ftp_scheme(self):           self._bad("ftp://example.com/v.mp4")
    def test_empty_url(self):            self._bad("")


# ── E. File-type validation ───────────────────────────────────────────────────

class TestFileMagic:
    def test_valid_mp4(self):
        validate_upload_magic("video.mp4", b"\x00\x00\x00\x18ftypisom" + b"\x00" * 8)

    def test_valid_mkv(self):
        validate_upload_magic("video.mkv", b"\x1aE\xdf\xa3" + b"\x00" * 8)

    def test_jpeg_disguised_as_mp4(self):
        with pytest.raises(HTTPException) as exc:
            validate_upload_magic("fake.mp4", b"\xff\xd8\xff\xe0" + b"\x00" * 8)
        assert exc.value.status_code == 415

    def test_python_file_rejected(self):
        with pytest.raises(HTTPException) as exc:
            validate_upload_magic("exploit.py", b"#!/usr/bin/env python3\n" + b"\x00" * 8)
        assert exc.value.status_code == 415

    def test_text_file_rejected(self):
        with pytest.raises(HTTPException) as exc:
            validate_upload_magic("notes.txt", b"Hello world" + b"\x00" * 8)
        assert exc.value.status_code == 415
