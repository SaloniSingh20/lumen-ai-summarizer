/**
 * My Videos — shows all past processed videos for the logged-in user.
 * Users can click any entry to view their notes again.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Film, Clock, Volume2, VolumeX, ArrowRight, Plus, Sparkles, LogOut, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import OrbBackground from '@/components/OrbBackground'
import Footer from '@/components/Footer'
import { api, tokenStore, type VideoData } from '@/lib/api'
import { supabase } from '@/lib/supabase'
import { formatDuration } from '@/lib/utils'

const stagger = {
  container: { hidden: {}, show: { transition: { staggerChildren: 0.06 } } },
  item: { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } } },
}

export default function DashboardPage() {
  const navigate   = useNavigate()
  const [videos,   setVideos]   = useState<VideoData[]>([])
  const [loading,  setLoading]  = useState(true)
  const [userEmail, setUserEmail] = useState('')

  useEffect(() => {
    api.getMe().then((me) => setUserEmail(me.email || '')).catch(() => {})
    api.listVideos()
      .then(setVideos)
      .catch(() => setVideos([]))
      .finally(() => setLoading(false))
  }, [])

  const handleSignOut = async () => {
    try { await supabase?.auth.signOut() } catch (_) {}
    tokenStore.clear()
    window.location.href = '/'
  }

  const completedVideos = videos.filter(v => v.notes)
  const processingVideos = videos.filter(v => !v.notes)

  return (
    <div className="min-h-screen relative">
      <OrbBackground variant="subtle" className="fixed" />

      {/* Header */}
      <header className="sticky top-0 z-40 rose-glass border-b border-pink/40 px-4 py-3">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <span className="font-script text-2xl text-prune">Lumen</span>
          <div className="flex items-center gap-3">
            {userEmail && (
              <span className="hidden sm:block text-xs text-plum-muted truncate max-w-[180px]">{userEmail}</span>
            )}
            <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
              <Plus className="w-4 h-4 mr-1.5" aria-hidden />
              New Video
            </Button>
            <Button variant="outline" size="sm" onClick={handleSignOut}>
              <LogOut className="w-4 h-4 mr-1.5" aria-hidden />
              Sign Out
            </Button>
          </div>
        </div>
      </header>

      <main className="relative z-10 max-w-5xl mx-auto px-4 py-10">
        {/* Hero line */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-10"
        >
          <h1 className="font-display text-3xl font-semibold text-plum mb-1">
            Your Video Summaries
          </h1>
          <p className="text-sm text-plum-muted">
            {loading ? 'Loading…' : `${completedVideos.length} summari${completedVideos.length !== 1 ? 'es' : 'y'} ready`}
          </p>
        </motion.div>

        {/* Loading skeletons */}
        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {[1,2,3,4,5,6].map(i => (
              <div key={i} className="rose-card p-5 space-y-3">
                <Skeleton className="h-4 w-3/4 rounded-full" />
                <Skeleton className="h-3 w-1/2 rounded-full" />
                <Skeleton className="h-3 w-1/3 rounded-full" />
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && videos.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="rose-card p-16 text-center"
          >
            <div className="w-16 h-16 rounded-2xl bg-pink/40 flex items-center justify-center mx-auto mb-5">
              <Film className="w-7 h-7 text-prune" aria-hidden />
            </div>
            <h2 className="font-display text-lg font-semibold text-plum mb-2">No summaries yet</h2>
            <p className="text-sm text-plum-muted mb-6 max-w-xs mx-auto">
              Upload a video or paste a YouTube URL to get structured AI notes, scene analysis, and Lumen Q&A.
            </p>
            <Button onClick={() => navigate('/')} size="lg">
              <Sparkles className="w-4 h-4 mr-2" aria-hidden />
              Summarize a Video
            </Button>
          </motion.div>
        )}

        {/* Completed videos grid */}
        {!loading && completedVideos.length > 0 && (
          <motion.div
            variants={stagger.container}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-8"
          >
            {completedVideos.map((video) => (
              <VideoCard key={video.id} video={video} onClick={() => navigate(`/results/${video.id}`)} />
            ))}
          </motion.div>
        )}

        {/* Processing videos (pending/running) */}
        {!loading && processingVideos.length > 0 && (
          <div className="mt-8">
            <h2 className="font-display text-sm font-semibold text-plum-muted uppercase tracking-wider mb-4">
              Currently Processing
            </h2>
            <div className="space-y-3">
              {processingVideos.map((video) => (
                <div key={video.id} className="rose-card px-5 py-4 flex items-center gap-4">
                  <div className="w-8 h-8 rounded-xl bg-pink/40 flex items-center justify-center shrink-0">
                    <Loader2 className="w-4 h-4 text-prune animate-spin" aria-hidden />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-plum truncate">{video.filename}</p>
                    <p className="text-xs text-plum-muted">Processing…</p>
                  </div>
                  {video.job_id && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => navigate(`/processing/${video.job_id}/${video.id}`)}
                    >
                      Watch <ArrowRight className="w-3.5 h-3.5 ml-1" aria-hidden />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
      <Footer />
    </div>
  )
}

function VideoCard({ video, onClick }: { video: VideoData; onClick: () => void }) {
  const notes    = video.notes
  const title    = notes?.title || video.filename || 'Untitled'
  const topics   = notes?.main_topics?.slice(0, 3) ?? []
  const date     = video.created_at
    ? new Date(video.created_at as unknown as string).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : ''

  return (
    <motion.div
      variants={{ hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } } }}
      className="rose-card rose-card-hover p-5 cursor-pointer group"
      onClick={onClick}
      role="button"
      tabIndex={0}
      aria-label={`View notes for ${title}`}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="w-9 h-9 rounded-xl bg-pink/40 flex items-center justify-center shrink-0">
          <Film className="w-4 h-4 text-prune" aria-hidden />
        </div>
        <ArrowRight className="w-4 h-4 text-plum-muted opacity-0 group-hover:opacity-100 transition-opacity mt-1 shrink-0" aria-hidden />
      </div>

      {/* Title */}
      <h3 className="font-display text-sm font-semibold text-plum mb-1 line-clamp-2 leading-snug">
        {title}
      </h3>

      {/* TL;DR */}
      {notes?.tldr && (
        <p className="text-xs text-plum-muted line-clamp-2 leading-relaxed mb-3">
          {notes.tldr}
        </p>
      )}

      {/* Topic pills */}
      {topics.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {topics.map(t => (
            <Badge key={t} variant="pink" className="text-xs py-0">{t}</Badge>
          ))}
        </div>
      )}

      {/* Meta row */}
      <div className="flex items-center gap-3 text-xs text-plum-muted mt-auto pt-2 border-t border-pink/30">
        {video.duration && (
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" aria-hidden />{formatDuration(video.duration)}
          </span>
        )}
        <span className="flex items-center gap-1">
          {video.has_audio
            ? <><Volume2 className="w-3 h-3" aria-hidden />Audio</>
            : <><VolumeX className="w-3 h-3" aria-hidden />Visual</>
          }
        </span>
        {notes?.content_type && <Badge variant="muted" className="text-xs py-0">{notes.content_type}</Badge>}
        {date && <span className="ml-auto">{date}</span>}
      </div>
    </motion.div>
  )
}
