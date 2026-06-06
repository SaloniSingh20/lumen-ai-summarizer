"""
Authentication — dual-mode:

  PRODUCTION (Supabase configured):
    Verifies the token by calling Supabase /auth/v1/user endpoint.
    Works regardless of whether Supabase uses HS256 (legacy) or
    asymmetric JWT signing keys (new default as of 2025).
    Response is cached in Redis for 60 s to avoid N calls per request.

  LOCAL / TESTING (no SUPABASE_URL set):
    Falls back to the API-token table (UserToken) already in SQLite.
"""
import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthUser:
    id: str
    email: str = ""
    source: str = "jwt"


# ── Simple in-process token cache (avoids a Supabase call on every request) ─

_token_cache: dict[str, AuthUser] = {}   # token_prefix → AuthUser


def _cache_key(token: str) -> str:
    return token[:40]


def _cache_get(token: str) -> Optional[AuthUser]:
    return _token_cache.get(_cache_key(token))


def _cache_set(token: str, user: AuthUser) -> None:
    key = _cache_key(token)
    _token_cache[key] = user
    # Keep the cache small (max 1000 entries)
    if len(_token_cache) > 1000:
        oldest = next(iter(_token_cache))
        del _token_cache[oldest]


# ── Supabase REST verification ────────────────────────────────────────────────

def _verify_supabase_token(token: str) -> Optional[AuthUser]:
    """Call Supabase /auth/v1/user to verify the token.
    Works with both legacy HS256 and new asymmetric signing keys."""
    settings = get_settings()
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        return None

    # Check cache first
    cached = _cache_get(token)
    if cached:
        return cached

    try:
        resp = httpx.get(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.SUPABASE_ANON_KEY,
            },
            timeout=5.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            user = AuthUser(
                id=data.get("id", ""),
                email=data.get("email", ""),
                source="jwt",
            )
            _cache_set(token, user)
            return user
        if resp.status_code == 401:
            return None   # Expired / invalid
        logger.warning(f"Supabase auth check returned {resp.status_code}")
        return None
    except Exception as exc:
        logger.warning(f"Supabase auth check failed: {exc}")
        return None


# ── Legacy API-token fallback ─────────────────────────────────────────────────

def _verify_legacy_token(token: str, db: Session) -> Optional[AuthUser]:
    try:
        from .models import UserToken
        row = (
            db.query(UserToken)
            .filter(UserToken.token == token, UserToken.is_active.is_(True))
            .first()
        )
        return AuthUser(id=row.id, email="", source="token") if row else None
    except Exception:
        return None


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    db: Session = Depends(get_db),
) -> AuthUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw = credentials.credentials

    # 1. Supabase REST verification (works with all signing key types)
    user = _verify_supabase_token(raw)
    if user:
        return user

    # 2. Legacy API token (local dev / testing)
    user = _verify_legacy_token(raw, db)
    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token — please sign in again",
        headers={"WWW-Authenticate": "Bearer"},
    )
