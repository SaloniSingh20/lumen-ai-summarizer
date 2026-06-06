-- ============================================================
-- Migration 003 — Fix schema for Supabase production deployment
-- Target: Postgres / Supabase
-- Run as: service_role (bypasses RLS during migration)
-- Run AFTER: 001_initial_schema.sql (002 is optional / already applied)
-- ============================================================
--
-- Problem: Migration 001 made owner_id reference user_tokens(id).
-- In production the app authenticates via Supabase JWT, so owner_id
-- is a Supabase auth.users UUID — no user_tokens row exists.
-- Every INSERT into jobs/videos fails with a foreign-key violation.
--
-- Fix: Drop those FK constraints. Application-layer filtering
-- (owner_id = current_user.id on every query) is the security boundary.
-- ============================================================

-- Drop FK constraints that referenced the legacy user_tokens table
ALTER TABLE jobs   DROP CONSTRAINT IF EXISTS jobs_owner_id_fkey;
ALTER TABLE videos DROP CONSTRAINT IF EXISTS videos_owner_id_fkey;

-- Disable Row-Level Security — the application already filters every
-- query by owner_id so database-level RLS adds no extra safety here,
-- but it DOES block inserts when auth.uid() / app.current_owner_id
-- is not set (which is the case for a direct SQLAlchemy connection).
ALTER TABLE jobs                DISABLE ROW LEVEL SECURITY;
ALTER TABLE videos              DISABLE ROW LEVEL SECURITY;
ALTER TABLE transcript_segments DISABLE ROW LEVEL SECURITY;
ALTER TABLE scenes              DISABLE ROW LEVEL SECURITY;
ALTER TABLE notes               DISABLE ROW LEVEL SECURITY;

-- Drop all policies (from migrations 001 and 002) to avoid conflicts
DROP POLICY IF EXISTS "jobs_owner_select"  ON jobs;
DROP POLICY IF EXISTS "jobs_owner_insert"  ON jobs;
DROP POLICY IF EXISTS "jobs_owner_update"  ON jobs;
DROP POLICY IF EXISTS "jobs_owner_delete"  ON jobs;
DROP POLICY IF EXISTS "jobs_owner_all"     ON jobs;

DROP POLICY IF EXISTS "videos_owner_select" ON videos;
DROP POLICY IF EXISTS "videos_owner_insert" ON videos;
DROP POLICY IF EXISTS "videos_owner_update" ON videos;
DROP POLICY IF EXISTS "videos_owner_delete" ON videos;
DROP POLICY IF EXISTS "videos_owner_all"    ON videos;

DROP POLICY IF EXISTS "segments_owner_select" ON transcript_segments;
DROP POLICY IF EXISTS "segments_owner_insert" ON transcript_segments;

DROP POLICY IF EXISTS "scenes_owner_select" ON scenes;
DROP POLICY IF EXISTS "scenes_owner_insert" ON scenes;

DROP POLICY IF EXISTS "notes_owner_select" ON notes;
DROP POLICY IF EXISTS "notes_owner_insert" ON notes;
DROP POLICY IF EXISTS "notes_owner_update" ON notes;
DROP POLICY IF EXISTS "notes_owner_all"    ON notes;
