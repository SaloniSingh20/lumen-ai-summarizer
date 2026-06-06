"""
Redis response cache.

Caches expensive read endpoints (video results, analytics, search) so
repeated requests don't hit the database or FAISS index every time.

Cache keys are namespaced by video_id only — ownership is already enforced
by the get_owned_video dependency before the cache is ever consulted.

TTLs:
  video notes / full result  → 1 hour   (pipeline output, rarely changes)
  analytics                  → 1 hour
  search results             → 10 min   (keyed by query too)
  media token                → not cached (always fresh — has its own 5-min TTL)
"""
import json
import logging
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Module-level Redis client — set once at startup, replaced in tests
_client = None

TTL_NOTES    = 3600        # 1 hour
TTL_ANALYTICS = 3600       # 1 hour
TTL_SEARCH   = 600         # 10 minutes


def init_cache(redis_url: str) -> None:
    """Call once at app startup to connect the cache client."""
    global _client
    try:
        import ssl as _ssl
        import redis as redis_lib
        kwargs: dict = {"decode_responses": True}
        if redis_url.startswith("rediss://"):
            kwargs["ssl_cert_reqs"] = _ssl.CERT_NONE
        _client = redis_lib.from_url(redis_url, **kwargs)
        _client.ping()
        logger.info("Redis cache connected at %s", redis_url)
    except Exception as exc:
        logger.warning("Redis cache unavailable (%s) — responses will not be cached.", exc)
        _client = None


def inject_client_for_testing(fake) -> None:
    global _client
    _client = fake


def reset_client() -> None:
    global _client
    _client = None


# ── Low-level helpers ──────────────────────────────────────────────────────

def _get(key: str) -> Any | None:
    if _client is None:
        return None
    try:
        raw = _client.get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.debug("Cache GET error for %s: %s", key, exc)
        return None


def _set(key: str, value: Any, ttl: int) -> None:
    if _client is None:
        return
    try:
        _client.setex(key, ttl, json.dumps(value, default=str))
    except Exception as exc:
        logger.debug("Cache SET error for %s: %s", key, exc)


def _delete_pattern(pattern: str) -> None:
    """Delete all keys matching a glob pattern. Used for cache invalidation."""
    if _client is None:
        return
    try:
        keys = _client.keys(pattern)
        if keys:
            _client.delete(*keys)
    except Exception as exc:
        logger.debug("Cache DELETE error for pattern %s: %s", pattern, exc)


# ── Domain-level cache operations ─────────────────────────────────────────

def get_video(video_id: str) -> dict | None:
    return _get(f"video:{video_id}")


def set_video(video_id: str, data: dict) -> None:
    _set(f"video:{video_id}", data, TTL_NOTES)


def get_analytics(video_id: str) -> dict | None:
    return _get(f"analytics:{video_id}")


def set_analytics(video_id: str, data: dict) -> None:
    _set(f"analytics:{video_id}", data, TTL_ANALYTICS)


def get_search(video_id: str, query: str) -> list | None:
    import hashlib
    q_hash = hashlib.md5(query.encode()).hexdigest()[:12]
    return _get(f"search:{video_id}:{q_hash}")


def set_search(video_id: str, query: str, results: list) -> None:
    import hashlib
    q_hash = hashlib.md5(query.encode()).hexdigest()[:12]
    _set(f"search:{video_id}:{q_hash}", results, TTL_SEARCH)


def invalidate_video(video_id: str) -> None:
    """
    Bust all cache entries for a video.
    Called by the pipeline when processing completes so the fresh
    notes/analytics are served immediately on the next request.
    """
    _delete_pattern(f"video:{video_id}")
    _delete_pattern(f"analytics:{video_id}")
    _delete_pattern(f"search:{video_id}:*")
    logger.info("Cache invalidated for video %s", video_id)
