-- ============================================================
-- Migration 001 — Initial schema with Row-Level Security
-- Target: Postgres / Supabase
-- Run as: service role (bypasses RLS during migration)
-- ============================================================

-- ---------------------------------------------------------------------------
-- Core tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS user_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token       UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL DEFAULT 'default',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id   UUID NOT NULL REFERENCES user_tokens(id) ON DELETE CASCADE,
    status     TEXT NOT NULL DEFAULT 'pending',
    stage      TEXT NOT NULL DEFAULT '',
    progress   FLOAT NOT NULL DEFAULT 0,
    error      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_jobs_owner_id ON jobs(owner_id);

CREATE TABLE IF NOT EXISTS videos (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id            UUID UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    owner_id          UUID NOT NULL REFERENCES user_tokens(id) ON DELETE CASCADE,
    filename          TEXT NOT NULL,
    original_url      TEXT,
    file_path         TEXT NOT NULL,
    duration          FLOAT,
    has_audio         BOOLEAN NOT NULL DEFAULT TRUE,
    language_detected TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_videos_owner_id ON videos(owner_id);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id           SERIAL PRIMARY KEY,
    video_id     UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    start        FLOAT NOT NULL,
    "end"        FLOAT NOT NULL,
    text         TEXT NOT NULL,
    embedding_id INT
);

CREATE TABLE IF NOT EXISTS scenes (
    id             SERIAL PRIMARY KEY,
    video_id       UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    scene_number   INT NOT NULL,
    start_time     FLOAT NOT NULL,
    end_time       FLOAT NOT NULL,
    keyframe_path  TEXT,
    description    TEXT,
    scene_label    TEXT,
    embedding_id   INT
);

CREATE TABLE IF NOT EXISTS notes (
    id                  SERIAL PRIMARY KEY,
    video_id            UUID UNIQUE NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    content_type        TEXT,
    language_detected   TEXT,
    has_audio           BOOLEAN NOT NULL DEFAULT TRUE,
    title               TEXT,
    tldr                TEXT,
    main_topics         JSONB,
    key_concepts        JSONB,
    detailed_notes      TEXT,
    key_takeaways       JSONB,
    visual_summary      TEXT,
    scenes_summary      JSONB,
    confidence_notes    TEXT,
    faiss_index_path    TEXT,
    faiss_metadata_path TEXT
);


-- ---------------------------------------------------------------------------
-- Row-Level Security
--
-- IMPORTANT: The application must connect as a ROLE THAT IS SUBJECT TO RLS
-- (i.e. NOT the postgres superuser or service_role).
-- Create an application role:
--
--   CREATE ROLE app_user WITH LOGIN PASSWORD '...';
--   GRANT CONNECT ON DATABASE <db> TO app_user;
--   GRANT USAGE ON SCHEMA public TO app_user;
--   GRANT SELECT, INSERT, UPDATE, DELETE
--       ON ALL TABLES IN SCHEMA public TO app_user;
--   GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
--
-- Then set DATABASE_URL to use app_user credentials.
-- The service_role (used for admin/migrations) bypasses RLS.
-- ---------------------------------------------------------------------------

ALTER TABLE jobs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE videos    ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcript_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE scenes    ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes     ENABLE ROW LEVEL SECURITY;

-- FORCE RLS applies policies even to the table owner / superuser role.
-- This is critical on Supabase where the default postgres user is a superuser
-- that would otherwise bypass RLS entirely.
ALTER TABLE jobs      FORCE ROW LEVEL SECURITY;
ALTER TABLE videos    FORCE ROW LEVEL SECURITY;
ALTER TABLE transcript_segments FORCE ROW LEVEL SECURITY;
ALTER TABLE scenes    FORCE ROW LEVEL SECURITY;
ALTER TABLE notes     FORCE ROW LEVEL SECURITY;

-- user_tokens: not RLS-protected (no cross-user risk; tokens are unique secrets)

-- ---------------------------------------------------------------------------
-- RLS policies
--
-- current_setting('app.current_owner_id') is set per-request by the
-- application layer via:  SET LOCAL app.current_owner_id = '<owner_id>';
-- (wrapped in a transaction for each request)
-- ---------------------------------------------------------------------------

-- jobs
CREATE POLICY "jobs_owner_select" ON jobs FOR SELECT
    USING (owner_id = current_setting('app.current_owner_id', TRUE)::UUID);

CREATE POLICY "jobs_owner_insert" ON jobs FOR INSERT
    WITH CHECK (owner_id = current_setting('app.current_owner_id', TRUE)::UUID);

CREATE POLICY "jobs_owner_update" ON jobs FOR UPDATE
    USING (owner_id = current_setting('app.current_owner_id', TRUE)::UUID);

CREATE POLICY "jobs_owner_delete" ON jobs FOR DELETE
    USING (owner_id = current_setting('app.current_owner_id', TRUE)::UUID);

-- videos
CREATE POLICY "videos_owner_select" ON videos FOR SELECT
    USING (owner_id = current_setting('app.current_owner_id', TRUE)::UUID);

CREATE POLICY "videos_owner_insert" ON videos FOR INSERT
    WITH CHECK (owner_id = current_setting('app.current_owner_id', TRUE)::UUID);

CREATE POLICY "videos_owner_update" ON videos FOR UPDATE
    USING (owner_id = current_setting('app.current_owner_id', TRUE)::UUID);

CREATE POLICY "videos_owner_delete" ON videos FOR DELETE
    USING (owner_id = current_setting('app.current_owner_id', TRUE)::UUID);

-- transcript_segments (owned transitively via video)
CREATE POLICY "segments_owner_select" ON transcript_segments FOR SELECT
    USING (
        video_id IN (
            SELECT id FROM videos
            WHERE owner_id = current_setting('app.current_owner_id', TRUE)::UUID
        )
    );

CREATE POLICY "segments_owner_insert" ON transcript_segments FOR INSERT
    WITH CHECK (
        video_id IN (
            SELECT id FROM videos
            WHERE owner_id = current_setting('app.current_owner_id', TRUE)::UUID
        )
    );

-- scenes
CREATE POLICY "scenes_owner_select" ON scenes FOR SELECT
    USING (
        video_id IN (
            SELECT id FROM videos
            WHERE owner_id = current_setting('app.current_owner_id', TRUE)::UUID
        )
    );

CREATE POLICY "scenes_owner_insert" ON scenes FOR INSERT
    WITH CHECK (
        video_id IN (
            SELECT id FROM videos
            WHERE owner_id = current_setting('app.current_owner_id', TRUE)::UUID
        )
    );

-- notes
CREATE POLICY "notes_owner_select" ON notes FOR SELECT
    USING (
        video_id IN (
            SELECT id FROM videos
            WHERE owner_id = current_setting('app.current_owner_id', TRUE)::UUID
        )
    );

CREATE POLICY "notes_owner_insert" ON notes FOR INSERT
    WITH CHECK (
        video_id IN (
            SELECT id FROM videos
            WHERE owner_id = current_setting('app.current_owner_id', TRUE)::UUID
        )
    );

CREATE POLICY "notes_owner_update" ON notes FOR UPDATE
    USING (
        video_id IN (
            SELECT id FROM videos
            WHERE owner_id = current_setting('app.current_owner_id', TRUE)::UUID
        )
    );
