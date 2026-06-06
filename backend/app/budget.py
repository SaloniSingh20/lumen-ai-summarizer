"""
Daily AI-call budget guard.

Tracks every call that hits the AI provider (transcribe, VLM, notes, chat)
in Redis with a midnight-rolling 24-hour TTL.  When the budget is exhausted
the endpoint raises 429 before any API cost is incurred.

Set MAX_AI_CALLS_PER_DAY=0 to disable the guard entirely.
"""
import logging
from datetime import date

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Sentinel so unit-tests can inject a fake Redis without real connection
_redis_client = None


def _get_redis(redis_url: str):
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    import ssl as _ssl
    import redis as redis_lib
    kwargs: dict = {"decode_responses": True}
    if redis_url.startswith("rediss://"):
        kwargs["ssl_cert_reqs"] = _ssl.CERT_NONE
    return redis_lib.from_url(redis_url, **kwargs)


def check_budget(redis_url: str, max_calls: int) -> int:
    """
    Atomically increment today's AI-call counter and raise 429 if over budget.

    Returns the counter value AFTER incrementing (useful for monitoring).
    Call this BEFORE hitting any AI provider.
    """
    if max_calls <= 0:
        return 0  # Budget guard disabled

    r = _get_redis(redis_url)
    today = date.today().isoformat()
    key = f"ai_budget:{today}"

    count = r.incr(key)
    if count == 1:
        # First call today — set TTL so the key auto-expires at 24 h
        r.expire(key, 86400)

    if count > max_calls:
        # Roll back so the counter stays accurate
        r.decr(key)
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily AI call budget of {max_calls} calls has been reached. "
                "Requests will resume tomorrow."
            ),
            headers={"Retry-After": "86400"},
        )
    return count


def inject_redis_for_testing(fake_client) -> None:
    """Allow tests to swap in a fake Redis client."""
    global _redis_client
    _redis_client = fake_client


def reset_redis_for_testing() -> None:
    """Restore real Redis after a test."""
    global _redis_client
    _redis_client = None
