/**
 * Supabase client — handles auth (sign up, sign in, sign out, session refresh).
 *
 * Configure VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in frontend/.env
 * (or frontend/.env.local for local overrides).
 *
 * If either var is missing the client is null and the app falls back to
 * the legacy API-token login (for local dev without a Supabase project).
 */
import { createClient, type SupabaseClient, type User } from '@supabase/supabase-js'

/* eslint-disable @typescript-eslint/no-explicit-any */
const env = (import.meta as any).env ?? {}
const url  = env.VITE_SUPABASE_URL  as string | undefined
const key  = env.VITE_SUPABASE_ANON_KEY as string | undefined

export const supabase: SupabaseClient | null =
  url && key ? createClient(url, key) : null

export const supabaseConfigured = Boolean(supabase)

/** Get the current user synchronously from the cached session. */
export async function getSession() {
  if (!supabase) return null
  const { data } = await supabase.auth.getSession()
  return data.session
}

/** Get the JWT access token to pass as Authorization: Bearer <token>. */
export async function getAccessToken(): Promise<string | null> {
  const session = await getSession()
  return session?.access_token ?? null
}

export type { User }
