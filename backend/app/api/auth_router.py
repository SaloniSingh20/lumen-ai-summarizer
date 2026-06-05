"""
Auth management endpoints.

  GET  /auth/me              — return current user info (works for both JWT and token users)
  POST /auth/tokens          — create legacy API token (admin only, for local dev / testing)
  DELETE /auth/tokens/self   — revoke own legacy token
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import UserToken
from ..auth import get_current_user, AuthUser
from ..config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class MeOut(BaseModel):
    owner_id: str
    email: str
    auth_source: str   # "jwt" (Supabase) or "token" (legacy)


class TokenOut(BaseModel):
    owner_id: str
    token: str
    name: str
    message: str


@router.get("/me", response_model=MeOut)
def get_me(current_user: AuthUser = Depends(get_current_user)):
    return MeOut(
        owner_id=current_user.id,
        email=current_user.email,
        auth_source=current_user.source,
    )


# ── Legacy token management (local dev / testing only) ───────────────────────

@router.post("/tokens", response_model=TokenOut, status_code=201)
def create_token(
    name: str = "default",
    x_admin_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    Create a legacy API token.
    Requires X-Admin-Secret header matching ADMIN_SECRET in .env.
    Only useful when SUPABASE_JWT_SECRET is not configured (local dev).
    """
    settings = get_settings()
    if not x_admin_secret or x_admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    user = UserToken(name=name[:80])
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenOut(
        owner_id=user.id,
        token=user.token,
        name=user.name,
        message="Legacy token created. For local dev only — use Supabase Auth in production.",
    )


@router.delete("/tokens/self", status_code=204)
def revoke_own_token(
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the currently used legacy token (no-op for JWT users)."""
    if current_user.source != "token":
        return  # JWT users are managed by Supabase
    row = db.query(UserToken).filter(UserToken.id == current_user.id).first()
    if row:
        row.is_active = False
        db.commit()
