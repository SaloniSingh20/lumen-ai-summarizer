"""
Rate-limiting via slowapi + Redis (or in-memory for tests).

Usage in route:
    from .limiter import limiter

    @router.post("/upload")
    @limiter.limit(lambda _: get_settings().RATELIMIT_UPLOAD)
    async def upload_video(request: Request, ...):

The custom key function uses the Bearer token when present so limits are
per-user rather than per-IP (IP-spoofing resistant).
"""
import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def _rate_key(request: Request) -> str:
    """Per-user key: token hash when authenticated, IP fallback for anonymous."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        tok = auth[7:].strip()
        if tok:
            # Use first 40 chars — long enough to identify, avoids huge Redis keys
            return f"tok:{tok[:40]}"
    ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}"


# Tests set TESTING=1 to use in-memory storage (no Redis dependency).
# The flag must be set BEFORE this module is first imported.
_storage_uri = (
    "memory://"
    if os.environ.get("TESTING") == "1"
    else os.environ.get("REDIS_URL", "redis://localhost:6379/0")
)

limiter = Limiter(
    key_func=_rate_key,
    storage_uri=_storage_uri,
)
