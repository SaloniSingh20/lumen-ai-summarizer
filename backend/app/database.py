"""
Database setup — supports both SQLite (local dev) and PostgreSQL (Supabase).

Set DATABASE_URL in .env to a PostgreSQL connection string to use Supabase.
Leave it empty to fall back to the SQLite DB_URL.

Row-Level Security:
  When using PostgreSQL, call set_rls_context(db, owner_id) at the start of
  every request that reads or writes user data.  This sets the session-local
  variable that the RLS policies in migrations/001_initial_schema.sql key on.
  On SQLite this is a no-op (SQLite has no native RLS).
"""
import os
import logging
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Choose the database URL
# ---------------------------------------------------------------------------

def _resolve_db_url() -> str:
    if settings.DATABASE_URL:
        return settings.DATABASE_URL
    # SQLite fallback — make sure the directory exists
    sqlite_path = settings.DB_URL.replace("sqlite:///", "")
    if sqlite_path and sqlite_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(sqlite_path)), exist_ok=True)
    return settings.DB_URL


_db_url = _resolve_db_url()
_is_sqlite = _db_url.startswith("sqlite")
_is_postgres = _db_url.startswith("postgresql") or _db_url.startswith("postgres")

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

_engine_kwargs: dict = {"echo": settings.DEBUG}

if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
elif _is_postgres:
    # Connection pool tuned for a long-running web server + Celery worker
    _engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,      # detect stale connections
        "pool_recycle": 1800,       # recycle every 30 min (avoids idle timeouts)
    })

engine = create_engine(_db_url, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Row-Level Security context (PostgreSQL / Supabase only)
# ---------------------------------------------------------------------------

def set_rls_context(db: Session, owner_id: str) -> None:
    """
    Set the PostgreSQL session variable consumed by our RLS policies:

        SET LOCAL app.current_owner_id = '<owner_id>';

    Must be called inside an open transaction so SET LOCAL takes effect.
    SQLAlchemy's autobegin (default) guarantees a transaction is open by the
    time the first query runs, so this is safe to call right after get_db().

    On SQLite this is silently skipped — ownership is enforced entirely by the
    application-layer owner_id filter in get_owned_video / get_owned_job.
    """
    if not _is_postgres:
        return
    # Use parameter binding to avoid any injection risk on the owner_id value
    db.execute(
        text("SELECT set_config('app.current_owner_id', :owner_id, TRUE)"),
        {"owner_id": str(owner_id)},
    )


# ---------------------------------------------------------------------------
# Schema init
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    SQLite: create tables automatically via SQLAlchemy metadata.
    PostgreSQL / Supabase: tables are created by running the SQL migration:
        backend/migrations/001_initial_schema.sql
    (paste it into the Supabase SQL editor — no manual steps needed here).
    """
    if _is_sqlite:
        from . import models  # noqa: F401 — registers all models with Base
        Base.metadata.create_all(bind=engine)
        logger.info("SQLite schema created / verified.")
    else:
        logger.info(
            "PostgreSQL detected — skipping auto schema creation. "
            "Run migrations/001_initial_schema.sql in the Supabase SQL editor."
        )
