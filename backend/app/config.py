from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache
import secrets


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AI Video Summarizer"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Supabase Auth ──────────────────────────────────────────────────
    # Get from: Supabase Dashboard → Settings → API
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    # Get from: Supabase Dashboard → Settings → API → JWT Settings → JWT Secret
    SUPABASE_JWT_SECRET: str = ""

    # Provider: "groq" (free), "api" (Gemini), or "local" (Ollama)
    AI_PROVIDER: str = "groq"

    # Paths
    UPLOAD_DIR: str = "./uploads"
    KEYFRAMES_DIR: str = "./keyframes"
    DB_URL: str = "sqlite:///./data/app.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Ollama (local mode)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "llama3.1:8b"
    OLLAMA_VLM_MODEL: str = "llava:7b"

    # Groq (groq mode — free tier, no credit card needed)
    # Sign up: https://console.groq.com
    GROQ_API_KEY: str = ""

    # Google Gemini (api mode)
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # YouTube Data API v3 — optional metadata fallback when captions are
    # unavailable (title/description/chapters). Get a key from:
    # https://console.cloud.google.com/apis/credentials (enable "YouTube Data API v3")
    YOUTUBE_API_KEY: str = ""

    # OpenAI Whisper API (optional, api mode)
    OPENAI_API_KEY: str = ""
    USE_OPENAI_WHISPER: bool = False

    # Whisper
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # Processing
    MAX_UPLOAD_SIZE_MB: int = 500
    MAX_SCENES: int = 100
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    FAISS_TOP_K: int = 5
    # Set to False on memory-constrained hosts (Render free tier 512 MB).
    # fastembed loads a ~130 MB ONNX model that causes OOM on free tier.
    ENABLE_FAISS: bool = True

    # Celery — defaults to REDIS_URL if not explicitly set
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    @model_validator(mode="after")
    def _set_celery_defaults(self):
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL
        return self

    # Database — set DATABASE_URL to a PostgreSQL URI to use Supabase.
    # Falls back to DB_URL (SQLite) when DATABASE_URL is empty.
    # Supabase format: postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres
    DATABASE_URL: str = ""

    # ----------------------------------------------------------------
    # Security
    # ----------------------------------------------------------------
    # Token used to create new API keys (keep secret, rotate regularly)
    ADMIN_SECRET: str = "change-me-in-production"

    # HMAC key for signing short-lived media URLs (video streaming)
    SECRET_KEY: str = secrets.token_hex(32)

    # Rate limits (slowapi format: "N/period", period = second|minute|hour|day)
    RATELIMIT_UPLOAD: str = "5/minute"
    RATELIMIT_UPLOAD_HOURLY: str = "30/hour"
    RATELIMIT_CHAT: str = "20/minute"
    RATELIMIT_READ: str = "60/minute"

    # Daily AI-call budget guard (0 = unlimited)
    MAX_AI_CALLS_PER_DAY: int = 500

    # Lumen message max length (chars)
    LUMEN_MAX_MSG_LEN: int = 1000

    # SSRF: comma-separated extra allowed domains (empty = all public hosts allowed)
    INGEST_ALLOWED_DOMAINS: str = ""

    # Error tracking — Sentry (leave empty to disable)
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1   # 10 % of requests traced

    # Logging — "json" for production (structured), "pretty" for local dev
    LOG_FORMAT: str = "pretty"

    # Gunicorn worker count (overridden by WEB_WORKERS env var in Docker)
    WEB_WORKERS: int = 2

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
