"""Unit tests for validate_ingest_url — no HTTP server needed."""
import os
os.environ["TESTING"] = "1"

import pytest
from fastapi import HTTPException
from app.security import validate_ingest_url


class TestValidateIngestUrl:
    # --- Blocked ---

    def test_private_ipv4_class_a(self):
        with pytest.raises(HTTPException) as exc:
            validate_ingest_url("http://10.0.0.1/video.mp4")
        assert exc.value.status_code == 400

    def test_private_ipv4_class_b(self):
        with pytest.raises(HTTPException):
            validate_ingest_url("http://172.16.5.5/v.mp4")

    def test_private_ipv4_class_c(self):
        with pytest.raises(HTTPException):
            validate_ingest_url("http://192.168.0.1/v.mp4")

    def test_loopback_ip(self):
        with pytest.raises(HTTPException):
            validate_ingest_url("http://127.0.0.1/v.mp4")

    def test_loopback_hostname(self):
        with pytest.raises(HTTPException):
            validate_ingest_url("http://localhost/v.mp4")

    def test_aws_metadata(self):
        with pytest.raises(HTTPException):
            validate_ingest_url("http://169.254.169.254/latest/meta-data/")

    def test_gcp_metadata(self):
        with pytest.raises(HTTPException):
            validate_ingest_url("http://metadata.google.internal/")

    def test_file_scheme(self):
        with pytest.raises(HTTPException) as exc:
            validate_ingest_url("file:///etc/passwd")
        assert exc.value.status_code == 400

    def test_ftp_scheme(self):
        with pytest.raises(HTTPException):
            validate_ingest_url("ftp://example.com/video.mp4")

    def test_gopher_scheme(self):
        with pytest.raises(HTTPException):
            validate_ingest_url("gopher://evil.com/")

    def test_empty_url(self):
        with pytest.raises(HTTPException):
            validate_ingest_url("")

    def test_url_too_long(self):
        with pytest.raises(HTTPException):
            validate_ingest_url("http://example.com/" + "a" * 2048)

    # --- Allowed ---

    def test_public_http_allowed(self):
        validate_ingest_url("http://example.com/video.mp4")  # must not raise

    def test_public_https_allowed(self):
        validate_ingest_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_youtube_allowed(self):
        validate_ingest_url("https://youtu.be/dQw4w9WgXcQ")
