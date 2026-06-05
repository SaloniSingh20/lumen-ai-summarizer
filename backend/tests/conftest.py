"""
Test fixtures.

IMPORTANT: TESTING=1 must be set before app modules are imported so that
the rate limiter uses in-memory storage instead of Redis.
"""
import os
os.environ["TESTING"] = "1"
os.environ["RATELIMIT_UPLOAD"] = "2/minute"
os.environ["RATELIMIT_UPLOAD_HOURLY"] = "10/hour"
os.environ["RATELIMIT_CHAT"] = "2/minute"
os.environ["RATELIMIT_READ"] = "10/minute"
os.environ["MAX_AI_CALLS_PER_DAY"] = "3"
os.environ["ADMIN_SECRET"] = "test-admin-secret"
os.environ["SECRET_KEY"] = "test-secret-key-32-chars-xxxxxxxx"
os.environ["AI_PROVIDER"] = "api"

import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models import UserToken, Job, Video
from app import budget as bgt


def _make_fresh_engine():
    """Each call creates a new isolated temp-file SQLite database."""
    import tempfile, os as _os
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_file.close()
    db_path = db_file.name
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    # Store path for cleanup
    engine._test_db_path = db_path
    return engine


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate-limiter storage between tests."""
    from app.limiter import limiter
    storage = getattr(limiter, "_storage", None)
    if storage is not None and hasattr(storage, "reset"):
        storage.reset()
    yield


@pytest.fixture
def db():
    """Fresh in-memory SQLite database per test."""
    engine = _make_fresh_engine()
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        # Delete the temp DB file so each test is fully isolated
        import os as _os
        db_path = getattr(engine, "_test_db_path", None)
        if db_path and _os.path.exists(db_path):
            try:
                _os.remove(db_path)
            except Exception:
                pass


@pytest.fixture
def client(db):
    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    bgt.inject_redis_for_testing(FakeRedis())
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()
    bgt.reset_redis_for_testing()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_token(db, name="test") -> tuple[str, str]:
    raw = str(uuid.uuid4())
    user = UserToken(name=name, token=raw)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.id, raw


@pytest.fixture
def user1(db):
    return _make_token(db, "user1")


@pytest.fixture
def user2(db):
    return _make_token(db, "user2")


@pytest.fixture
def auth1(user1):
    _, tok = user1
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def auth2(user2):
    _, tok = user2
    return {"Authorization": f"Bearer {tok}"}


def _make_video(db, owner_id: str, filename: str = "test.mp4") -> tuple[str, str]:
    job_id   = str(uuid.uuid4())
    video_id = str(uuid.uuid4())
    job   = Job(id=job_id, owner_id=owner_id, status="completed", stage="Complete", progress=100.0)
    video = Video(id=video_id, job_id=job_id, owner_id=owner_id, filename=filename, file_path=f"/uploads/{video_id}/{filename}")
    db.add(job); db.add(video); db.commit()
    return job_id, video_id


@pytest.fixture
def owned_video(db, user1):
    owner_id, _ = user1
    return _make_video(db, owner_id)


# ── Fake Redis ────────────────────────────────────────────────────────────────

class FakeRedis:
    def __init__(self):
        self._store: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]

    def decr(self, key: str) -> int:
        self._store[key] = self._store.get(key, 1) - 1
        return self._store[key]

    def expire(self, key: str, ttl: int) -> None:
        pass

    def get(self, key: str):
        v = self._store.get(key)
        return str(v).encode() if v is not None else None

    def reset(self):
        self._store.clear()
