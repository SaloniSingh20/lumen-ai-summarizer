"""
Centralised security helpers:

  1. get_owned_video / get_owned_job  — IDOR-safe resource lookups
  2. validate_ingest_url              — SSRF protection for URL ingest
  3. validate_upload_magic            — file-type validation via magic bytes
  4. generate_media_token /
     verify_media_token               — signed short-lived URLs for video streaming
  5. validate_message_length          — Lumen message cap

IDOR policy:  always 404 on ownership mismatch, never 403.
              (Never reveal that a resource exists to the wrong user.)
"""
import hashlib
import hmac
import ipaddress
import logging
import re
import time
from urllib.parse import urlparse

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from .auth import get_current_user, AuthUser
from .database import get_db, set_rls_context
from .models import Job, Video

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. IDOR-safe resource dependencies
# ---------------------------------------------------------------------------

def get_owned_video(
    video_id: str,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Video:
    """Return the video if it exists AND belongs to the current user.

    Also activates the PostgreSQL RLS session variable so every subsequent
    query in this request is subject to database-level row filtering too.
    Returns 404 in all failure cases — never 403.
    """
    # Layer 2: activate RLS on the DB connection for this request
    set_rls_context(db, current_user.id)

    # Layer 1: explicit application-level owner filter (works on SQLite too)
    video = (
        db.query(Video)
        .filter(Video.id == video_id, Video.owner_id == current_user.id)
        .first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Not found")
    return video


def get_owned_job(
    job_id: str,
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Job:
    """Return the job if it exists AND belongs to the current user."""
    set_rls_context(db, current_user.id)

    job = (
        db.query(Job)
        .filter(Job.id == job_id, Job.owner_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    return job


# ---------------------------------------------------------------------------
# 2. SSRF protection
# ---------------------------------------------------------------------------

_PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("169.254.0.0/16"),   # AWS/GCP metadata link-local
    ipaddress.ip_network("100.64.0.0/10"),    # Carrier-grade NAT
    ipaddress.ip_network("fd00::/8"),         # IPv6 ULA
]

_BLOCKED_HOSTNAMES = frozenset({
    "169.254.169.254",            # AWS EC2 metadata
    "metadata.google.internal",   # GCP metadata
    "metadata.azure.com",         # Azure metadata
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
})


def validate_ingest_url(url: str) -> None:
    """
    Reject URLs that could be used for SSRF attacks:
      - Non-http(s) schemes (file://, ftp://, gopher://, etc.)
      - Private / link-local / loopback IP addresses
      - Cloud metadata service hostnames
    Raises HTTP 400 on any violation.
    """
    if not url or len(url) > 2048:
        raise HTTPException(400, "Invalid URL")

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "Only http and https URLs are allowed for video ingest")

    host = (parsed.hostname or "").lower()
    if not host:
        raise HTTPException(400, "URL has no hostname")

    if host in _BLOCKED_HOSTNAMES:
        raise HTTPException(400, "URL not allowed")

    # Block bare IP addresses in private ranges
    try:
        addr = ipaddress.ip_address(host)
        if not addr.is_global:
            raise HTTPException(400, "Private or reserved IP addresses are not allowed")
        for private_range in _PRIVATE_RANGES:
            if addr in private_range:
                raise HTTPException(400, "Private or reserved IP addresses are not allowed")
    except ValueError:
        pass  # It's a hostname, not a raw IP — DNS resolution happens later


# ---------------------------------------------------------------------------
# 3. File-type validation (magic bytes)
# ---------------------------------------------------------------------------

# First 12 bytes → (offset, bytes_to_match, description)
_VIDEO_MAGIC: list[tuple[int, bytes, str]] = [
    (0,  b"\x00\x00\x00\x18ftyp",  "MP4/M4V"),
    (0,  b"\x00\x00\x00\x1cftyp",  "MP4"),
    (0,  b"\x00\x00\x00\x20ftyp",  "MP4"),
    (4,  b"ftyp",                   "MP4 (generic ftyp)"),
    (0,  b"\x1aE\xdf\xa3",         "MKV/WebM"),
    (0,  b"RIFF",                   "AVI"),
    (0,  b"\x30\x26\xb2\x75",      "WMV/ASF"),
    (0,  b"FLV",                    "FLV"),
    (0,  b"OggS",                   "OGG video"),
    (0,  b"\x47",                   "MPEG-TS"),   # 0x47 sync byte — loose check
]

_ALLOWED_EXTENSIONS = frozenset({
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
    ".m4v", ".flv", ".wmv", ".ogv", ".ts", ".m2ts",
})


def validate_upload_magic(filename: str, header: bytes) -> None:
    """
    Reject uploads that are not video files by checking:
      1. File extension is in the allowed set.
      2. Magic bytes match a known video container format.
    Raises HTTP 415 on violation.
    """
    import os
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{ext}' not supported. Upload a video file.",
        )

    if len(header) < 12:
        raise HTTPException(415, "File too small to be a valid video")

    for offset, magic, _label in _VIDEO_MAGIC:
        end = offset + len(magic)
        if len(header) >= end and header[offset:end] == magic:
            return  # Match found

    raise HTTPException(
        status_code=415,
        detail="File does not appear to be a valid video (magic byte mismatch)",
    )


# ---------------------------------------------------------------------------
# 4. Short-lived signed media tokens (for <video> src — can't send headers)
# ---------------------------------------------------------------------------

_MEDIA_TOKEN_TTL = 300  # 5 minutes


def generate_media_token(video_id: str, owner_id: str, secret: str) -> str:
    """Return a HMAC-signed token valid for _MEDIA_TOKEN_TTL seconds."""
    expiry = int(time.time()) + _MEDIA_TOKEN_TTL
    payload = f"{video_id}:{owner_id}:{expiry}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{sig}:{expiry}"


def verify_media_token(token: str, video_id: str, owner_id: str, secret: str) -> bool:
    """Return True iff the token is valid, not expired, and matches (video_id, owner_id)."""
    try:
        sig, expiry_str = token.rsplit(":", 1)
        expiry = int(expiry_str)
        if time.time() > expiry:
            return False
        payload = f"{video_id}:{owner_id}:{expiry}"
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# 5. Input length caps
# ---------------------------------------------------------------------------

def validate_message_length(message: str, max_len: int) -> None:
    if len(message) > max_len:
        raise HTTPException(
            status_code=422,
            detail=f"Message too long: max {max_len} characters",
        )
