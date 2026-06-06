"""FastAPI application entry point."""
import logging
import os
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import get_settings
from .database import init_db, engine
from .limiter import limiter
from .api import jobs, videos, chat
from .api.auth_router import router as auth_router
from . import cache

settings = get_settings()

# ── Structured logging ────────────────────────────────────────────────────
def _configure_logging() -> None:
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.LOG_FORMAT == "json":
        # Machine-readable JSON for production / log aggregators (Datadog, Logtail, etc.)
        renderer = structlog.processors.JSONRenderer()
    else:
        # Human-readable coloured output for local dev
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # structlog >= 21.2 uses processors= (plural); fall back to processor= for older versions.
    try:
        formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
            foreign_pre_chain=shared_processors,
        )
    except TypeError:
        formatter = structlog.stdlib.ProcessorFormatter(  # type: ignore[call-arg]
            processor=renderer,
            foreign_pre_chain=shared_processors,
        )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Quiet noisy libraries
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

_configure_logging()
logger = structlog.get_logger(__name__)


# ── Sentry ────────────────────────────────────────────────────────────────
def _init_sentry() -> None:
    if not settings.SENTRY_DSN:
        logger.info("Sentry disabled (SENTRY_DSN not set)")
        return
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
            CeleryIntegration(),
        ],
        environment="production" if not settings.DEBUG else "development",
        # Never send raw AI API keys or tokens to Sentry
        send_default_pii=False,
    )
    logger.info("Sentry initialised", dsn_prefix=settings.SENTRY_DSN[:20] + "…")

_init_sentry()


# ── App lifespan ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.KEYFRAMES_DIR, exist_ok=True)
    os.makedirs("data", exist_ok=True)
    init_db()
    cache.init_cache(settings.REDIS_URL)
    logger.info(
        "Application started",
        provider=settings.AI_PROVIDER,
        workers=settings.WEB_WORKERS,
    )

    yield   # ── serving ──

    # ── Graceful shutdown ──
    # Gunicorn sends SIGTERM; uvicorn workers finish in-flight requests
    # before this hook runs. We use it to close the DB connection pool
    # cleanly so Postgres doesn't hold idle connections.
    logger.info("Shutting down — closing DB connection pool")
    engine.dispose()
    logger.info("Shutdown complete")


# ── FastAPI app ───────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Video Summarizer",
    description="Multimodal video analysis: transcription + visual understanding + structured notes",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# ── Rate limiting ─────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    try:
        limit_obj = getattr(exc, "limit", None)
        reset_time = getattr(limit_obj, "reset_time", None) if limit_obj is not None else None
        retry = str(int(reset_time)) if reset_time else "60"
    except Exception:
        retry = "60"
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded", "retry_after": retry},
        headers={"Retry-After": retry},
    )


# ── Generic error handler — no stack traces to clients ───────────────────
_ALLOWED_ORIGINS = {
    "https://lumen-ai-summarizer.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
}

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled error",
        method=request.method,
        path=request.url.path,
        exc_type=type(exc).__name__,
    )
    origin = request.headers.get("origin", "")
    extra_headers = {}
    if origin in _ALLOWED_ORIGINS:
        extra_headers["Access-Control-Allow-Origin"] = origin
        extra_headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred"},
        headers=extra_headers,
    )


# ── Request timing middleware (adds X-Response-Time header) ──────────────
@app.middleware("http")
async def add_response_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time"] = f"{ms:.1f}ms"
    return response


# ── CORS ─────────────────────────────────────────────────────────────────
# allow_credentials must be False when allow_origins=["*"]; browsers reject
# the combination of wildcard origin + credentials. We use JWT in the
# Authorization header (not cookies) so credentials=False is correct.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lumen-ai-summarizer.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(jobs.router)
app.include_router(videos.router)
app.include_router(chat.router)


# ── Health & readiness ────────────────────────────────────────────────────
@app.get("/health", tags=["ops"])
def health():
    """Liveness probe — confirms the process is alive."""
    return {"status": "ok", "provider": settings.AI_PROVIDER}


@app.get("/ready", tags=["ops"])
def ready():
    """
    Readiness probe — confirms the app can serve requests.
    Checks: database connectivity + Redis connectivity.
    Returns 503 if any dependency is unavailable.
    """
    checks: dict[str, str] = {}
    ok = True

    # Database
    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        ok = False

    # Redis
    try:
        import ssl as _ssl
        import redis as redis_lib
        _redis_kwargs: dict = {"socket_connect_timeout": 2}
        if settings.REDIS_URL.startswith("rediss://"):
            _redis_kwargs["ssl_cert_reqs"] = _ssl.CERT_NONE
        r = redis_lib.from_url(settings.REDIS_URL, **_redis_kwargs)
        r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        ok = False

    status_code = 200 if ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if ok else "unavailable", "checks": checks},
    )


@app.get("/", tags=["ops"])
def root():
    return {"message": "AI Video Summarizer API"}
