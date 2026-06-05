# Lumen — AI Video Summarizer

> *Watch less. Understand more.*

A production-quality, full-stack AI web application that transforms any video into structured notes, scene-by-scene visual analysis, semantic search, and a conversational Q&A assistant — all powered by multimodal AI.

---

## Table of Contents

1. [What it does](#what-it-does)
2. [System Architecture](#system-architecture)
3. [Processing Pipeline](#processing-pipeline)
4. [Tech Stack](#tech-stack)
5. [Quick Start (Docker)](#quick-start-docker)
6. [Local Development](#local-development)
7. [Authentication](#authentication)
8. [Environment Variables](#environment-variables)
9. [Security](#security)
10. [Deployment](#deployment)
11. [Running Tests](#running-tests)
12. [API Reference](#api-reference)
13. [Resume Bullet Points](#resume-bullet-points)

---

## What it does

Upload any video (file upload or YouTube URL) and get:

| Feature | Description |
|---|---|
| **Structured Notes** | Title, TL;DR, topics, key concepts, detailed markdown, takeaways |
| **Scene Analysis** | Keyframe gallery with AI-generated visual descriptions per scene |
| **Semantic Search** | FAISS vector search — ask anything, jump to the exact moment |
| **Lumen Chat** | Conversational Q&A grounded in the video's content + time-range queries |
| **Analytics** | Word frequency, WPM, speaking ratio, topic breakdown |
| **PDF Export** | Beautifully formatted downloadable notes |
| **My Videos** | Dashboard showing all your past summaries |
| **Multi-language** | Auto-detects language via Whisper |

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                             │
│  React + Vite + TypeScript  ·  Tailwind CSS  ·  Framer Motion      │
│  Supabase JS Client (auth)  ·  @supabase/supabase-js               │
└──────────────────────────────┬─────────────────────────────────────┘
                               │  HTTPS · JWT Bearer token
┌──────────────────────────────▼─────────────────────────────────────┐
│                       NGINX (port 3000)                             │
│  Static file server  +  reverse proxy → API                        │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
┌──────────────────────────────▼─────────────────────────────────────┐
│                   FastAPI  (port 8000)                              │
│  Gunicorn + UvicornWorker  ·  2 workers  ·  graceful shutdown       │
│                                                                     │
│  Auth:  validate Supabase JWT (HS256, auth.uid())                  │
│         or legacy API token (UserToken table, local dev)            │
│  Rate:  slowapi + Redis  (per-user token key)                      │
│  IDOR:  get_owned_video / get_owned_job → always 404 on mismatch   │
│  SSRF:  validate_ingest_url → block private IPs + metadata         │
│  Magic: validate_upload_magic → file-type via header bytes         │
│  Budget: Redis daily AI-call counter                               │
└──────────┬─────────────────────────────────────────┬───────────────┘
           │  SQLAlchemy ORM                          │  Celery task
           │                                          │
┌──────────▼──────────┐                  ┌────────────▼───────────────┐
│  Supabase / SQLite  │                  │      Celery Worker          │
│                     │                  │   (processes pipeline)      │
│  Tables:            │                  │                             │
│  · jobs             │                  │  faster-whisper (CPU)       │
│  · videos           │                  │  PySceneDetect + OpenCV     │
│  · transcript_segs  │                  │  Groq Vision (llama-4)      │
│  · scenes           │                  │  Groq LLM (llama-3.3-70b)  │
│  · notes            │                  │  FAISS index builder        │
│  · user_tokens      │                  └────────────────────────────┘
│                     │
│  RLS via auth.uid() │                  ┌────────────────────────────┐
│  (Supabase only)    │                  │           Redis             │
└─────────────────────┘                  │  · Celery broker/results    │
                                         │  · Rate limit counters      │
                                         │  · AI budget counter        │
                                         │  · Response cache           │
                                         └────────────────────────────┘
```

---

## Processing Pipeline

Each video goes through 10 ordered, resumable stages:

```
Upload / URL
    │
    ▼
[1] Probe         ffprobe → duration, stream info
    │
    ▼
[2] Extract Audio ffmpeg → 16 kHz mono WAV
    │
    ▼
[3] Detect Audio  RMS energy check → has_audio flag
    │                                (silent/music-only → visual-only mode)
    ▼
[4] Transcribe    faster-whisper (CPU/GPU) → segments + detected language
    │
    ▼
[5] Scene Detect  PySceneDetect (ContentDetector) → scene list
    │             Fallback: evenly-spaced scenes for short/uniform clips
    ▼
[6] Keyframes     OpenCV → 1 mid-scene JPG per scene (max 640 px wide)
    │
    ▼
[7] Visual AI     Groq Vision (llama-4-scout or llama-3.2-90b) →
    │             factual description of each keyframe
    │             Anti-hallucination: describe only literally visible content
    ▼
[8] Generate Notes Groq LLM (llama-3.3-70b) →
    │             JSON: title, TL;DR, topics, concepts, markdown notes,
    │             takeaways, visual summary, scene labels, confidence notes
    ▼
[9] Build Index   sentence-transformers → float32 embeddings
    │             FAISS IndexFlatIP → persisted to disk
    ▼
[10] Persist      All data written to DB · cache invalidated · job = completed
```

Each stage updates `jobs.progress` (0–100 %) — the frontend polls every 1.5 s and shows a live stage tracker.

---

## Tech Stack

### Backend
| Layer | Technology |
|---|---|
| API framework | FastAPI 0.111 + Uvicorn + Gunicorn |
| Task queue | Celery 5.4 + Redis 7 |
| Database | SQLite (local) / Supabase PostgreSQL (production) |
| ORM | SQLAlchemy 2.0 |
| Auth | Supabase JWT (HS256) + legacy API tokens |
| Transcription | faster-whisper (CPU, `base` model default) |
| Scene detection | PySceneDetect 0.6 |
| Keyframe extraction | OpenCV 4 |
| AI provider | Groq (llama-4-scout for vision, llama-3.3-70b for LLM) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` |
| Vector search | FAISS (IndexFlatIP, cosine after L2 norm) |
| PDF export | ReportLab |
| Rate limiting | slowapi + Redis |
| Error tracking | Sentry SDK |
| Logging | structlog (JSON in prod, pretty in dev) |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 18 + Vite 5 + TypeScript |
| Styling | TailwindCSS 3 (custom rose design system) |
| Auth UI | Supabase JS client (`@supabase/supabase-js`) |
| Animation | Framer Motion |
| Charts | Recharts |
| Icons | lucide-react |
| Routing | React Router v6 |

---

## Quick Start (Docker)

**Prerequisites:** Docker Desktop installed and running.

```bash
# 1. Clone / open the project
cd "AI Video-Summarizer"

# 2. Set environment variables
cp .env.example .env
# Edit .env — at minimum set:
#   GROQ_API_KEY=gsk_...       (free at console.groq.com)
#   SUPABASE_URL=...           (optional — enables email/password auth)
#   SUPABASE_ANON_KEY=...
#   SUPABASE_JWT_SECRET=...

# 3. Export your YouTube cookies (fixes YouTube download 403s)
# Install "Get cookies.txt LOCALLY" in your browser, go to youtube.com,
# export cookies, and save as:  youtube_cookies.txt  in this folder.

# 4. Start everything
docker compose up --build

# 5. Open
# App:      http://localhost:3000
# API docs: http://localhost:8000/docs  (only in DEBUG=true mode)
# Health:   http://localhost:8000/health
# Readiness:http://localhost:8000/ready
```

**First login:**
- Without Supabase: Click "Developer access" → enter `my-local-demo-secret`
- With Supabase: Click "Sign Up" → create an account with your email

---

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- Redis (`redis-server` or Docker)
- ffmpeg

```bash
# Backend
cd backend
pip install -r requirements.txt

# Copy env
cp ../.env.example ../.env
# Edit .env

# Start Redis
redis-server &

# Start API
uvicorn app.main:app --reload --port 8000

# Start Celery worker (new terminal)
PYTHONPATH=. celery -A worker.tasks.celery_app worker --loglevel=info -c 2

# Frontend (new terminal)
cd frontend
npm install
# Create frontend/.env.local with VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY
npm run dev
# → http://localhost:3000
```

---

## Authentication

Lumen uses a dual-mode authentication system:

### Production: Supabase Auth
1. Users sign up / sign in via the Login page (email + password, or Google OAuth)
2. Supabase issues a short-lived **JWT** (1 hour, auto-refreshed)
3. The JWT is passed as `Authorization: Bearer <jwt>` on every API request
4. FastAPI validates the JWT using `SUPABASE_JWT_SECRET` (HS256)
5. The `sub` claim (Supabase user UUID) becomes `owner_id` on all data rows
6. Row-Level Security (`migration 002`) enforces isolation at the database level using `auth.uid()`

### Local Dev / Testing: Legacy API Token
When `SUPABASE_JWT_SECRET` is not set:
1. Call `POST /auth/tokens` with `X-Admin-Secret: <your ADMIN_SECRET>`
2. Store the returned UUID token in `localStorage`
3. Pass it as `Authorization: Bearer <token>`

### Why this design?
- **No passwords stored** — Supabase handles all credential storage
- **Token forgery impossible** — 64-char HS256 secret, expiring JWTs
- **Defence in depth** — application-level owner filter AND database-level RLS
- **Tests work without Supabase** — legacy token path keeps CI green

---

## Environment Variables

### Backend (`.env`)

| Variable | Default | Required | Description |
|---|---|---|---|
| `AI_PROVIDER` | `groq` | ✅ | `groq` (free), `api` (Gemini), `local` (Ollama) |
| `GROQ_API_KEY` | — | ✅ for groq | Get free key at console.groq.com |
| `SUPABASE_URL` | — | prod | Supabase project URL |
| `SUPABASE_ANON_KEY` | — | prod | Supabase anon key |
| `SUPABASE_JWT_SECRET` | — | prod | From Supabase Settings → API → JWT Secret |
| `DATABASE_URL` | — | prod | Supabase PostgreSQL URI (Session mode, port 5432) |
| `GOOGLE_API_KEY` | — | if `api` | Gemini API key |
| `REDIS_URL` | `redis://localhost:6379/0` | ✅ | Redis connection |
| `ADMIN_SECRET` | `my-local-demo-secret` | ✅ | Secret to create legacy tokens |
| `SECRET_KEY` | random | ✅ | HMAC key for signed media URLs |
| `WHISPER_MODEL_SIZE` | `base` | | `tiny`/`base`/`small`/`medium`/`large` |
| `WHISPER_DEVICE` | `cpu` | | `cpu` or `cuda` |
| `MAX_UPLOAD_SIZE_MB` | `500` | | Max video file size |
| `MAX_AI_CALLS_PER_DAY` | `500` | | Daily AI call budget (0=unlimited) |
| `RATELIMIT_UPLOAD` | `5/minute` | | Upload rate limit |
| `RATELIMIT_CHAT` | `20/minute` | | Lumen chat rate limit |
| `SENTRY_DSN` | — | | Sentry error tracking DSN |
| `LOG_FORMAT` | `pretty` | | `json` for production |
| `WEB_WORKERS` | `2` | | Gunicorn worker count |

### Frontend (`.env.local`)

| Variable | Description |
|---|---|
| `VITE_SUPABASE_URL` | Supabase project URL (from Settings → API) |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon/public key |

---

## Security

### 1. Authentication
- Supabase JWTs validated server-side (HS256, 1-hour expiry, auto-refresh)
- Legacy tokens (local dev) stored in `user_tokens` table
- All 401 responses use the `WWW-Authenticate: Bearer` header

### 2. Row-Level Security (Supabase / PostgreSQL)
`migration 002` enables RLS on all 5 user-data tables using `auth.uid()`:
```sql
CREATE POLICY "videos_owner_all" ON videos
    FOR ALL USING (owner_id::uuid = auth.uid());
```
`FORCE ROW LEVEL SECURITY` applies even to the Supabase superuser role.
For SQLite (local dev), ownership is enforced at the application layer via mandatory `owner_id` filters.

### 3. IDOR Prevention
- All resource IDs are **UUIDv4** (non-guessable)
- Every endpoint uses `get_owned_video` / `get_owned_job` dependencies
- Returns **404** on ownership mismatch — never 403 (prevents enumeration)
- Files served only through authenticated endpoints (no public static mounts)

### 4. Rate Limiting
- slowapi + Redis, keyed by Bearer token (per-user, not per-IP)
- Upload: 5/min + 30/hour · Chat: 20/min · Read: 60/minute
- All 429 responses include `Retry-After` header
- Daily AI-call budget guard prevents runaway costs

### 5. SSRF Protection
URL ingest validates every URL before making any network request:
- Only `http://` and `https://` schemes
- Blocks private IPv4 (10.x, 172.16.x, 192.168.x), loopback, link-local
- Blocks cloud metadata endpoints (169.254.169.254, metadata.google.internal)

### 6. Input Validation
- File uploads: magic-byte check (not just extension)
- Filenames: `os.path.basename` prevents path traversal
- Lumen messages: capped at 1000 characters
- Generic 500 handler: stack traces never reach clients

---

## Deployment

### Cloud (Recommended: Render/Railway + Supabase + Vercel)

```
Backend API  → Render Web Service   (Docker, backend/Dockerfile)
Worker       → Render Background    (Docker, backend/Dockerfile.worker)
Redis        → Render Redis         (or Upstash)
Database     → Supabase PostgreSQL  (free tier, 500 MB)
Frontend     → Vercel               (npm run build)
```

**Environment variables for cloud:**
```env
AI_PROVIDER=groq
GROQ_API_KEY=gsk_...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_JWT_SECRET=your-64-char-secret
DATABASE_URL=postgresql://postgres.xxx:password@aws-0-region.pooler.supabase.com:5432/postgres
REDIS_URL=redis://...
LOG_FORMAT=json
WEB_WORKERS=2
```

**Supabase setup steps:**
1. Create project at supabase.com
2. Enable email auth: Authentication → Providers → Email
3. (Optional) Enable Google OAuth: Authentication → Providers → Google
4. Run `backend/migrations/001_initial_schema.sql` in SQL Editor
5. Run `backend/migrations/002_supabase_auth_rls.sql` in SQL Editor
6. Copy `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` from Settings → API

**Frontend Vercel setup:**
```bash
cd frontend
vercel deploy
# Set env vars in Vercel dashboard:
#   VITE_SUPABASE_URL
#   VITE_SUPABASE_ANON_KEY
```

### Local / Offline (Ollama)

For fully offline use without any API keys:
```bash
# Install Ollama from ollama.com
ollama pull llama3.1:8b
ollama pull llava:7b   # or llama-3.2-vision

# In .env:
AI_PROVIDER=local
OLLAMA_BASE_URL=http://localhost:11434
```

---

## Running Tests

```bash
cd backend

# Install test dependencies (if not already installed)
pip install pytest pytest-asyncio httpx

# Run all tests (no Redis, no Supabase needed — uses in-memory mocks)
python -m pytest tests/ -v

# Run specific suites
python -m pytest tests/test_auth_jwt.py      -v   # JWT auth tests
python -m pytest tests/test_api_endpoints.py -v   # API + IDOR tests
python -m pytest tests/test_pipeline_utils.py -v  # Pipeline utils
python -m pytest tests/test_security.py      -v   # Security tests
python -m pytest tests/test_ssrf.py          -v   # SSRF unit tests
python -m pytest tests/test_time_parser.py   -v   # Time parser
```

**Test coverage:**
- ✅ JWT validation (valid, expired, tampered, wrong audience)
- ✅ Legacy token auth (valid, revoked, random string)
- ✅ IDOR — cross-user access always returns 404
- ✅ Rate limiting — 3rd request returns 429 with Retry-After
- ✅ SSRF — 15+ blocked URL patterns
- ✅ File-type magic bytes — valid MP4/MKV pass, JPEG/Python reject
- ✅ AI budget guard — exceeding limit blocks new jobs
- ✅ Error sanitisation — no stack traces in responses
- ✅ Time parser — 12 query formats
- ✅ Scene detection fallback — always ≥1 scene
- ✅ Media token — sign, verify, expiry, tamper

---

## API Reference

### Authentication
| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/auth/me` | ✅ | Current user info |
| `POST` | `/auth/tokens` | Admin secret | Create legacy token (local dev) |
| `DELETE` | `/auth/tokens/self` | ✅ | Revoke own token |

### Jobs
| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/jobs/upload` | ✅ | Upload video file |
| `POST` | `/jobs/url` | ✅ | Submit YouTube/video URL |
| `GET` | `/jobs/{id}` | ✅ (owner) | Poll job status + progress |
| `GET` | `/jobs` | ✅ | List own jobs |

### Videos
| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/videos` | ✅ | List own videos (dashboard) |
| `GET` | `/videos/{id}` | ✅ (owner) | Full video data + notes |
| `GET` | `/videos/{id}/search?q=...` | ✅ (owner) | Semantic search |
| `GET` | `/videos/{id}/analytics` | ✅ (owner) | Analytics data |
| `GET` | `/videos/{id}/export/pdf` | ✅ (owner) | Download PDF |
| `GET` | `/videos/{id}/keyframes/{n}` | ✅ (owner) | Serve keyframe image |
| `GET` | `/videos/{id}/media-token` | ✅ (owner) | Issue signed video stream token |
| `GET` | `/videos/{id}/stream?token=...` | Signed token | Stream video file |

### Lumen Chat
| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/videos/{id}/chat` | ✅ (owner) | Q&A with time-range support |
| `GET` | `/videos/{id}/chat/suggestions` | ✅ (owner) | Quick-reply suggestions |

### Ops
| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/ready` | Readiness probe (checks DB + Redis) |

---

## Resume Bullet Points

- Architected a **full-stack multimodal AI platform** (FastAPI + React/TypeScript) that fuses audio transcription (faster-whisper) with visual scene understanding (Groq Vision) to generate structured notes, semantic search, and a conversational Q&A assistant

- Implemented **Supabase Auth** with JWT validation and PostgreSQL **Row-Level Security** (`auth.uid()` policies + `FORCE ROW LEVEL SECURITY`) ensuring users can only access their own data even under direct database access or SQL injection

- Built a **defence-in-depth security layer**: Supabase JWT authentication, per-user rate limiting (slowapi + Redis), IDOR prevention (always-404 ownership checks on all endpoints), SSRF URL validation blocking 15+ attack patterns, magic-byte file-type validation, and daily AI-call budget guard

- Designed a **resumable 10-stage async pipeline** (Celery + Redis) with live progress updates; processes video from raw URL → structured JSON notes in minutes using yt-dlp, ffmpeg, Whisper, PySceneDetect, and Groq

- Shipped **semantic search** with FAISS + sentence-transformers; users can ask natural questions and jump directly to the relevant moment in the video

- Implemented **Lumen**, a video-aware chat assistant with robust time-range parsing ("what happened from 1:30 to 2:00?"), RAG over transcript + visual descriptions, and anti-hallucination prompting

- Wrote **comprehensive test suite** (46+ tests) covering JWT security, IDOR attacks, rate limiting, SSRF, file-type validation, scene detection, and time-range parsing — all run without external services via in-memory mocks

- Containerised with **Docker + docker-compose** (4 services); documented full deployment pipeline to Supabase + Render + Vercel with environment-specific configuration
