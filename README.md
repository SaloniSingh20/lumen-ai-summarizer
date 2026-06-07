# Lumen- AI Video Summarizer

An AI-powered video summarization platform that turns any video into structured notes, a searchable transcript, scene-by-scene visual breakdowns, and an interactive Q&A assistant — all in under two minutes.

**Live demo:** [lumen-ai-summarizer.vercel.app](https://lumen-ai-summarizer.vercel.app)
**Repository:** [github.com/SaloniSingh20/lumen-ai-summarizer](https://github.com/SaloniSingh20/lumen-ai-summarizer)

---

## Problem

Watching a one-hour lecture to find a five-minute answer wastes time. Existing tools either produce walls of raw transcript text, miss visual context entirely, or require expensive API subscriptions. There is no lightweight, free-to-use tool that combines:

- Timestamped transcript with semantic search
- Visual scene analysis from video keyframes
- Structured notes (TL;DR, key concepts, takeaways)
- A context-aware chat assistant grounded in the video's actual content
- PDF export for offline study

Lumen fills that gap.

---

## Solution

A multimodal video analysis pipeline that:

| Capability | What it means |
|---|---|
| Dual input modes | Upload a video file **or** paste a YouTube URL |
| YouTube transcript fallback | When server IP is blocked by YouTube's download restrictions, automatically fetches captions via the YouTube Captions API — no video download needed |
| Audio transcription | Groq Whisper API — fast, accurate, no local model required |
| Visual understanding | Scene detection + keyframe extraction + LLaMA 4 Vision description of each scene |
| Structured AI notes | LLaMA 3.3 70B generates title, TL;DR, key concepts, detailed notes, and takeaways |
| Semantic Q&A | Lumen chat assistant answers questions grounded in transcript and scene context |
| PDF export | Beautifully formatted notes downloadable as a PDF |
| Secure by design | Every endpoint is owner-scoped — no user can read another user's videos |

This is not a transcript dump. It is a full content intelligence layer on top of any video.

---

## Key Features

### Video Processing
- **File upload** — MP4, MOV, AVI, MKV, WebM, and more (up to 500 MB); validated by magic bytes, not just extension
- **YouTube URL** — paste any public YouTube link; Lumen downloads and processes it
- **Transcript-only fallback** — when yt-dlp is blocked by cloud server IP restrictions (common on all free hosting providers), automatically falls back to YouTube's captions API so the video is never silently rejected
- **Scene detection** — PySceneDetect finds natural scene boundaries
- **Keyframe extraction** — one representative JPEG per scene, served through an authenticated endpoint
- **Audio detection** — gracefully handles silent / visual-only videos

### AI Analysis
- **Transcription** — Groq Whisper (whisper-large-v3-turbo), timestamped to the segment level
- **Visual analysis** — LLaMA 4 Scout Vision (with automatic fallback to LLaMA 3.2 90B / 11B) describes each keyframe
- **Notes generation** — LLaMA 3.3 70B produces structured output: content type, language, title, TL;DR, main topics, key concepts with explanations, detailed markdown notes, key takeaways, visual summary, per-scene labels
- **Language detection** — auto-detects video language and surfaces it in the notes header

### Lumen Chat
- Ask anything about the video: "What did they say about X?", "What happened between 2:00 and 3:30?", "Summarize the intro"
- Grounded answers with timestamped source chips — click any chip to jump to that moment in the video
- Time-range queries parsed directly from natural language ("in the last 30 seconds", "from 1:00 to 2:00")
- Conversation history maintained across the session

### Dashboard and Results
- All processed videos in one place, newest first
- Thumbnail timeline with scene labels and descriptions
- Full transcript with word-level timestamps
- Analytics: word frequency chart, speaking ratio, words per minute, top topics
- Full-text semantic search across the entire video
- PDF export of all notes with styled headings, bullet lists, and scene table

### Security
- Supabase JWT authentication on every request
- IDOR protection — ownership checked at both application layer (SQLAlchemy filter) and database layer (PostgreSQL RLS); a wrong-owner request returns 404, never 403
- Short-lived signed media tokens for video streaming (5-minute TTL, HMAC-SHA256)
- SSRF protection on URL ingest — blocks private IP ranges, loopback, and cloud metadata endpoints
- File magic-byte validation — rejects non-video uploads regardless of file extension
- Rate limiting on all endpoints via slowapi

---

## Architecture

```
Browser (Vercel)
    │
    │  HTTPS + Supabase JWT
    ▼
FastAPI  ──────────────────►  Groq API
(Render)                      (Whisper + LLaMA Vision + LLaMA 3.3 70B)
    │
    ├──► PostgreSQL (Neon.tech)    ◄── all persistent data
    │
    ├──► Redis (Upstash, TLS)      ◄── Celery broker + result backend
    │                                   + response cache + daily budget guard
    │
    └──► Celery Worker (same container via supervisord)
             │
             └──► Pipeline stages:
                  probe → audio → transcribe → scenes
                  → keyframes → vision → notes → [FAISS optional]
```

| Layer | Stack |
|---|---|
| Frontend | React 19 + Vite + TypeScript + Tailwind CSS |
| Backend API | FastAPI + Pydantic v2 + SQLAlchemy 2 |
| Task queue | Celery 5 + Redis (Upstash, `rediss://` TLS) |
| Database | PostgreSQL — Neon.tech free tier (IPv4 compatible) |
| Auth | Supabase (JWT via REST, no server-side Supabase client needed) |
| AI — transcription | Groq Whisper API (whisper-large-v3-turbo) |
| AI — vision | Groq LLaMA 4 Scout Vision / LLaMA 3.2 Vision (fallback chain) |
| AI — notes + chat | Groq LLaMA 3.3 70B Versatile |
| Scene detection | PySceneDetect + OpenCV headless |
| Video download | yt-dlp (tv_embedded → mweb → ios strategy chain) |
| Transcript fallback | youtube-transcript-api (captions API, no download required) |
| PDF generation | ReportLab |
| Container | Docker + supervisord (gunicorn API + celery worker, one image) |
| Frontend deploy | Vercel |
| Backend deploy | Render free tier (512 MB RAM) |

---

## Data Model

```
UserToken (auth identity — Supabase user UUID)
    │
    ├── Job  (id, status: pending→processing→completed/failed, stage, progress, error)
    │
    └── Video (id, job_id, filename, original_url, file_path, duration, has_audio, language)
            │
            ├── TranscriptSegment[]   (id, start, end, text)
            ├── Scene[]               (id, scene_number, start_time, end_time,
            │                          keyframe_path, description, scene_label)
            └── Notes                 (title, tldr, main_topics, key_concepts,
                                       detailed_notes, key_takeaways, visual_summary,
                                       scenes_summary, confidence_notes,
                                       faiss_index_path, faiss_metadata_path)
```

---

## Processing Pipeline

**Full pipeline** (uploaded video file or successfully downloaded YouTube video):

```
1. Probe            ffprobe → duration, has_audio_stream, has_video_stream
2. Extract audio    ffmpeg → mono WAV at 16 kHz for Whisper
3. Detect audio     RMS energy check — gracefully handles silent videos
4. Transcribe       Groq Whisper API → timestamped TranscriptSegment rows
5. Scene detect     PySceneDetect → list of (start_time, end_time) boundaries
6. Keyframes        ffmpeg → one JPEG per scene into /tmp/keyframes/{video_id}/
7. Vision           Groq LLaMA Vision → text description per keyframe
8. Notes            Groq LLaMA 3.3 70B → full structured JSON notes
9. Search index     FAISS + fastembed (skipped when ENABLE_FAISS=False)
10. Finalize        Job → completed, cache invalidated
```

**Transcript-only pipeline** (YouTube URL when yt-dlp is blocked):

```
1. Captions         youtube-transcript-api → timestamped text segments
2. Store            TranscriptSegment rows written to DB directly in the request handler
3. Queue task       process_transcript_only_task enqueued to Celery
4. Notes            Groq LLaMA 3.3 70B generates notes from transcript alone
5. Finalize         Job → completed, cache invalidated
```

---

## Setup

### Prerequisites

- Python 3.11+
- Node 18+
- PostgreSQL (or a free [Neon.tech](https://neon.tech) account)
- Redis (or a free [Upstash](https://upstash.com) account — use the `rediss://` URL)
- Groq API key — free at [console.groq.com](https://console.groq.com)
- Supabase project — free at [supabase.com](https://supabase.com)
- ffmpeg installed locally (or included in Docker for Render)

### Backend (local)

```bash
git clone https://github.com/SaloniSingh20/lumen-ai-summarizer.git
cd lumen-ai-summarizer/backend

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — fill in DATABASE_URL, REDIS_URL, GROQ_API_KEY,
# SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET

uvicorn app.main:app --reload --port 8000
```

Start the Celery worker in a second terminal:

```bash
celery -A worker.tasks worker --loglevel=info
```

API docs available at `http://localhost:8000/docs`

### Frontend (local)

```bash
cd frontend
npm install
cp .env.example .env.local
# Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY
# Leave VITE_API_URL empty — Vite's proxy forwards /api → :8000

npm run dev
```

Open `http://localhost:5173`. Sign up, then start uploading videos.

---

## Deploy

### Frontend — Vercel

1. Connect the repo; set the root directory to `frontend/`
2. Add environment variables in the Vercel dashboard:

| Variable | Value |
|---|---|
| `VITE_SUPABASE_URL` | Your Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Your Supabase anon key |
| `VITE_API_URL` | Your Render backend URL (e.g. `https://lumen-ai-backend-xxxx.onrender.com`) |

### Backend — Render (Docker)

1. New Web Service → Docker → point to `backend/Dockerfile.render`
2. Add environment variables:

| Variable | Where to get it |
|---|---|
| `DATABASE_URL` | Neon.tech → Connection Details → Connection string (port 5432, direct) |
| `REDIS_URL` | Upstash → Redis database → `rediss://` connection string |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |
| `SUPABASE_URL` | Supabase → Settings → API |
| `SUPABASE_ANON_KEY` | Supabase → Settings → API |
| `SUPABASE_JWT_SECRET` | Supabase → Settings → API → JWT Settings |
| `ENABLE_FAISS` | Set to `False` on free tier (prevents OOM from 130 MB ONNX model) |
| `AI_PROVIDER` | `groq` |
| `LOG_FORMAT` | `json` |

### Database migration

Run once in the Neon SQL editor (`console.neon.tech`):

```sql
CREATE TABLE IF NOT EXISTS user_tokens (
    id VARCHAR PRIMARY KEY,
    token VARCHAR UNIQUE NOT NULL,
    name VARCHAR DEFAULT 'default',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs (
    id VARCHAR PRIMARY KEY,
    owner_id VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'pending',
    stage VARCHAR DEFAULT '',
    progress FLOAT DEFAULT 0.0,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS videos (
    id VARCHAR PRIMARY KEY,
    job_id VARCHAR UNIQUE REFERENCES jobs(id),
    owner_id VARCHAR NOT NULL,
    filename VARCHAR,
    original_url VARCHAR,
    file_path VARCHAR,
    duration FLOAT,
    has_audio BOOLEAN DEFAULT TRUE,
    language_detected VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR REFERENCES videos(id),
    start FLOAT,
    "end" FLOAT,
    text TEXT,
    embedding_id INTEGER
);

CREATE TABLE IF NOT EXISTS scenes (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR REFERENCES videos(id),
    scene_number INTEGER,
    start_time FLOAT,
    end_time FLOAT,
    keyframe_path VARCHAR,
    description TEXT,
    scene_label VARCHAR,
    embedding_id INTEGER
);

CREATE TABLE IF NOT EXISTS notes (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR UNIQUE REFERENCES videos(id),
    content_type VARCHAR,
    language_detected VARCHAR,
    has_audio BOOLEAN DEFAULT TRUE,
    title VARCHAR,
    tldr TEXT,
    main_topics JSONB,
    key_concepts JSONB,
    detailed_notes TEXT,
    key_takeaways JSONB,
    visual_summary TEXT,
    scenes_summary JSONB,
    confidence_notes TEXT,
    faiss_index_path VARCHAR,
    faiss_metadata_path VARCHAR
);
```

---

## Environment Variables Reference

### Backend (`backend/.env`)

```env
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis (Upstash — always use rediss:// for TLS)
REDIS_URL=rediss://default:password@host.upstash.io:6379

# AI
GROQ_API_KEY=gsk_...
AI_PROVIDER=groq

# Auth (Supabase)
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_JWT_SECRET=your-jwt-secret

# Processing
ENABLE_FAISS=False          # False on Render free tier (512 MB RAM)
MAX_UPLOAD_SIZE_MB=500
MAX_SCENES=100

# Optional
SENTRY_DSN=                 # leave empty to disable error tracking
LOG_FORMAT=json             # json for production, pretty for local dev
MAX_AI_CALLS_PER_DAY=500    # 0 = unlimited
```

### Frontend (`frontend/.env.local`)

```env
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_API_URL=https://lumen-ai-backend-xxxx.onrender.com
# Leave VITE_API_URL empty for local dev — Vite proxy handles /api → :8000
```

---

## Free Tier Constraints and Workarounds

| Constraint | Workaround |
|---|---|
| Render 512 MB RAM limit | `ENABLE_FAISS=False` skips the 130 MB fastembed ONNX model load entirely |
| YouTube downloads blocked on cloud server IPs | `youtube-transcript-api` fallback fetches captions without downloading the video |
| Render container sleeps after 15 min inactivity | Upload page polls `/health` in a retry loop and enables the submit button only when the server is awake |
| Upstash Redis requires TLS (`rediss://`) | All Redis clients (Celery broker, cache module, budget guard) explicitly pass `ssl_cert_reqs=CERT_NONE` |
| Neon PostgreSQL serverless pooler (port 6543) | SQLAlchemy uses `NullPool` when port 6543 is detected in `DATABASE_URL` |
| Render ephemeral filesystem | Video files go to `/tmp/uploads/`, keyframes to `/tmp/keyframes/` |
| Pydantic v2 rejects `uuid.UUID` as `str` | All ID fields use `field_validator(mode='before')` to coerce UUID objects to strings |

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe — confirms process is alive |
| `GET` | `/ready` | Readiness probe — checks DB and Redis connectivity |
| `POST` | `/jobs/upload` | Upload a video file (multipart/form-data) |
| `POST` | `/jobs/url` | Submit a YouTube or direct video URL |
| `GET` | `/jobs/{job_id}` | Poll job status, stage, and progress |
| `GET` | `/videos` | List all videos for the authenticated user |
| `GET` | `/videos/{video_id}` | Full video data: transcript, scenes, notes |
| `GET` | `/videos/{video_id}/analytics` | Word frequency, speaking ratio, scene count |
| `POST` | `/videos/{video_id}/chat` | Ask Lumen a question about the video |
| `GET` | `/videos/{video_id}/search?q=` | Semantic search across transcript and scenes |
| `GET` | `/videos/{video_id}/export/pdf` | Download notes as a styled PDF |
| `GET` | `/videos/{video_id}/media-token` | Get a short-lived signed stream token (5 min TTL) |
| `GET` | `/videos/{video_id}/stream?token=` | Stream the video file (requires signed token) |
| `GET` | `/videos/{video_id}/keyframes/{scene_number}` | Serve a scene keyframe image |

All endpoints require `Authorization: Bearer <supabase_jwt>`. All video and job endpoints return 404 (not 403) on ownership mismatch to avoid leaking resource existence.

---

## Future Work

- **FAISS semantic search on free tier** — host embeddings externally or use a quantized model that fits in 512 MB RAM
- **Whisper local model option** — `faster-whisper` for self-hosted deployments without Groq dependency
- **Chapters** — auto-generate YouTube-style chapter markers from scene labels and notes structure
- **Share links** — optional public read-only link for a processed video
- **Batch processing** — queue multiple videos with progress notifications per item
- **Webhook support** — POST to a user-configured URL when processing completes
- **Export to Notion / Obsidian** — push structured notes directly to knowledge management tools
- **Mobile PWA** — install as a home-screen app on iOS and Android

---

## Troubleshooting

**"Server is starting up" on first use**
Render free tier sleeps after 15 minutes of inactivity. The upload page automatically polls `/health` and enables the button once the server is awake (~30–60 seconds on a cold start).

**YouTube video fails even after retrying**
Lumen tries four yt-dlp client strategies (tv_embedded, mweb, ios, default) then falls back to the YouTube Captions API. If all fail, the video likely has no captions and the server IP is blocked — upload the video file directly as a workaround.

**Chat returns "Sorry, something went wrong"**
Usually a Redis SSL issue. Confirm `REDIS_URL` in Render starts with `rediss://` (not `redis://`) and matches exactly what Upstash shows.

**PDF download does nothing**
`VITE_API_URL` in Vercel is probably empty or wrong. It must point to the full Render backend URL (e.g. `https://lumen-ai-backend-xxxx.onrender.com`). Without it the PDF request hits Vercel's CDN, not the backend.

**Processing stuck at "Processing..." forever**
The Celery worker shares the container with the API. If Render restarted mid-task, clear stuck jobs in the Neon SQL editor:
```sql
UPDATE jobs
SET status = 'failed', error = 'Cancelled — container restarted'
WHERE status IN ('pending', 'processing');
```

---

## License

All rights reserved unless otherwise stated.
