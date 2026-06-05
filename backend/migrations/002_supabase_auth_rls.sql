-- ============================================================
-- Migration 002 — Switch RLS from app.current_owner_id to auth.uid()
--
-- This migration upgrades Row-Level Security to use Supabase's built-in
-- auth.uid() function. This is more secure because:
--   • auth.uid() is set by Supabase's auth system, NOT by application code.
--   • No application-level SET LOCAL is required or trusted.
--   • Impossible to bypass by crafting a raw SQL request with a forged setting.
--
-- Run as: service_role (bypasses RLS during migration)
-- Run AFTER: 001_initial_schema.sql
-- ============================================================

-- Drop old app.current_owner_id-based policies
DROP POLICY IF EXISTS "jobs_owner_select"  ON jobs;
DROP POLICY IF EXISTS "jobs_owner_insert"  ON jobs;
DROP POLICY IF EXISTS "jobs_owner_update"  ON jobs;
DROP POLICY IF EXISTS "jobs_owner_delete"  ON jobs;

DROP POLICY IF EXISTS "videos_owner_select" ON videos;
DROP POLICY IF EXISTS "videos_owner_insert" ON videos;
DROP POLICY IF EXISTS "videos_owner_update" ON videos;
DROP POLICY IF EXISTS "videos_owner_delete" ON videos;

DROP POLICY IF EXISTS "segments_owner_select" ON transcript_segments;
DROP POLICY IF EXISTS "segments_owner_insert" ON transcript_segments;

DROP POLICY IF EXISTS "scenes_owner_select" ON scenes;
DROP POLICY IF EXISTS "scenes_owner_insert" ON scenes;

DROP POLICY IF EXISTS "notes_owner_select"  ON notes;
DROP POLICY IF EXISTS "notes_owner_insert"  ON notes;
DROP POLICY IF EXISTS "notes_owner_update"  ON notes;

-- ── New policies using auth.uid() ────────────────────────────────────────────
-- auth.uid() returns the UUID of the currently authenticated Supabase user.
-- When a user's JWT is verified, Supabase sets this automatically — no app code needed.

-- jobs
CREATE POLICY "jobs_owner_all" ON jobs
    FOR ALL
    USING      (owner_id::uuid = auth.uid())
    WITH CHECK (owner_id::uuid = auth.uid());

-- videos
CREATE POLICY "videos_owner_all" ON videos
    FOR ALL
    USING      (owner_id::uuid = auth.uid())
    WITH CHECK (owner_id::uuid = auth.uid());

-- transcript_segments (owned transitively via videos)
CREATE POLICY "segments_owner_select" ON transcript_segments
    FOR SELECT
    USING (
        video_id IN (SELECT id FROM videos WHERE owner_id::uuid = auth.uid())
    );

CREATE POLICY "segments_owner_insert" ON transcript_segments
    FOR INSERT
    WITH CHECK (
        video_id IN (SELECT id FROM videos WHERE owner_id::uuid = auth.uid())
    );

-- scenes
CREATE POLICY "scenes_owner_select" ON scenes
    FOR SELECT
    USING (
        video_id IN (SELECT id FROM videos WHERE owner_id::uuid = auth.uid())
    );

CREATE POLICY "scenes_owner_insert" ON scenes
    FOR INSERT
    WITH CHECK (
        video_id IN (SELECT id FROM videos WHERE owner_id::uuid = auth.uid())
    );

-- notes
CREATE POLICY "notes_owner_all" ON notes
    FOR ALL
    USING (
        video_id IN (SELECT id FROM videos WHERE owner_id::uuid = auth.uid())
    )
    WITH CHECK (
        video_id IN (SELECT id FROM videos WHERE owner_id::uuid = auth.uid())
    );

-- ── FORCE RLS (applies even to superuser / postgres role) ────────────────────
ALTER TABLE jobs                FORCE ROW LEVEL SECURITY;
ALTER TABLE videos              FORCE ROW LEVEL SECURITY;
ALTER TABLE transcript_segments FORCE ROW LEVEL SECURITY;
ALTER TABLE scenes              FORCE ROW LEVEL SECURITY;
ALTER TABLE notes               FORCE ROW LEVEL SECURITY;

-- ── user_tokens table: keep for local dev but not needed in production ────────
-- In production, Supabase manages users. The user_tokens table is only used
-- for local dev / CI testing without a real Supabase project.
