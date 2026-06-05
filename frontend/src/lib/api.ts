/**
 * Typed API client.
 *
 * Auth priority:
 *   1. Supabase session JWT  — when VITE_SUPABASE_URL is configured (production)
 *   2. Legacy API token      — stored in localStorage (local dev / fallback)
 *
 * Every request automatically includes Authorization: Bearer <token>.
 */
import { getAccessToken, supabase } from './supabase'

const BASE = `${import.meta.env.VITE_API_URL ?? ''}/api`

// --------------------------------------------------------------------------
// Legacy token storage (used when Supabase is not configured)
// --------------------------------------------------------------------------

const TOKEN_KEY = 'api_token'

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),   // Callers handle supabase.signOut() separately
}

// --------------------------------------------------------------------------
// Types
// --------------------------------------------------------------------------

export interface JobStatus {
  id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  stage: string
  progress: number
  error?: string
}

export interface TranscriptSegment {
  id: number
  start: number
  end: number
  text: string
}

export interface Scene {
  id: number
  scene_number: number
  start_time: number
  end_time: number
  keyframe_path?: string
  description?: string
  scene_label?: string
}

export interface KeyConcept {
  concept: string
  explanation: string
}

export interface Notes {
  content_type?: string
  language_detected?: string
  has_audio: boolean
  title?: string
  tldr?: string
  main_topics?: string[]
  key_concepts?: KeyConcept[]
  detailed_notes?: string
  key_takeaways?: string[]
  visual_summary?: string
  scenes?: Array<{ scene_label: string; description: string }>
  confidence_notes?: string
}

export interface VideoData {
  id: string
  job_id: string
  filename: string
  original_url?: string
  duration?: number
  has_audio: boolean
  language_detected?: string
  created_at?: string
  transcript_segments: TranscriptSegment[]
  scenes: Scene[]
  notes?: Notes
}

export interface SearchResult {
  type: 'transcript' | 'scene'
  text: string
  start: number
  end: number
  score: number
  label?: string
}

export interface AnalyticsData {
  word_frequency: Array<{ word: string; count: number }>
  top_topics: string[]
  scene_count: number
  duration?: number
  words_per_minute?: number
  speaking_ratio?: number
  total_words: number
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface SourceChip {
  label: string
  start: number
  end: number
}

export interface ChatResponse {
  answer: string
  sources: SourceChip[]
  seek_to?: number
}

// --------------------------------------------------------------------------
// Core fetch wrapper
// --------------------------------------------------------------------------

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Supabase JWT takes priority; fall back to legacy token
  const token = (await getAccessToken()) ?? tokenStore.get()
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...init, headers })

  if (res.status === 401) {
    tokenStore.clear()
    throw new ApiError(401, 'Authentication required')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      // ignore parse error
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

// --------------------------------------------------------------------------
// API surface
// --------------------------------------------------------------------------

export const api = {
  // Auth
  createToken: (adminSecret: string, name = 'default'): Promise<{ owner_id: string; token: string; name: string }> =>
    fetch(`${BASE}/auth/tokens?name=${encodeURIComponent(name)}`, {
      method: 'POST',
      headers: { 'X-Admin-Secret': adminSecret },
    }).then((r) => {
      if (!r.ok) throw new ApiError(r.status, 'Invalid admin secret')
      return r.json()
    }),

  getMe: (): Promise<{ owner_id: string; email: string; auth_source: string }> =>
    request('/auth/me'),

  // Dashboard
  listVideos: (): Promise<VideoData[]> =>
    request('/videos'),

  // Jobs
  uploadFile: async (file: File): Promise<{ job_id: string; video_id: string }> => {
    const form = new FormData()
    form.append('file', file)
    return request('/jobs/upload', { method: 'POST', body: form })
  },

  submitUrl: async (url: string): Promise<{ job_id: string; video_id: string }> => {
    const form = new FormData()
    form.append('url', url)
    return request('/jobs/url', { method: 'POST', body: form })
  },

  getJob: (jobId: string): Promise<JobStatus> =>
    request(`/jobs/${jobId}`),

  // Videos
  getVideo: (videoId: string): Promise<VideoData> =>
    request(`/videos/${videoId}`),

  searchVideo: (videoId: string, q: string): Promise<{ results: SearchResult[] }> =>
    request(`/videos/${videoId}/search?q=${encodeURIComponent(q)}`),

  getAnalytics: (videoId: string): Promise<AnalyticsData> =>
    request(`/videos/${videoId}/analytics`),

  exportPdfUrl: (videoId: string): string =>
    `${BASE}/videos/${videoId}/export/pdf`,

  getKeyframeUrl: (videoId: string, sceneNumber: number): string =>
    `${BASE}/videos/${videoId}/keyframes/${sceneNumber}`,

  /** Get a short-lived signed token for the video <video> element src. */
  getMediaToken: (videoId: string): Promise<{ token: string; ttl: number }> =>
    request(`/videos/${videoId}/media-token`),

  /** Build the video stream src URL using a signed token. */
  buildStreamUrl: (videoId: string, signedToken: string): string =>
    `${BASE}/videos/${videoId}/stream?token=${encodeURIComponent(signedToken)}`,

  // Lumen
  chat: (videoId: string, message: string, history: ChatMessage[]): Promise<ChatResponse> =>
    request(`/videos/${videoId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history }),
    }),

  getChatSuggestions: (videoId: string): Promise<{ suggestions: string[] }> =>
    request(`/videos/${videoId}/chat/suggestions`),

  // Health
  health: (): Promise<{ status: string; provider: string }> =>
    request('/health'),
}

export { ApiError }
