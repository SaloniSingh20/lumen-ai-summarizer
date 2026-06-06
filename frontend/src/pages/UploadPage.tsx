import { useCallback, useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { motion } from 'framer-motion'
import { Upload, Link2, Zap, FileText, Search, Sparkles, AlertCircle, Loader2, LogOut, LayoutDashboard } from 'lucide-react'
import { Button } from '@/components/ui/button'
import OrbBackground from '@/components/OrbBackground'
import Footer from '@/components/Footer'
import { api, tokenStore } from '@/lib/api'
import { supabase } from '@/lib/supabase'
import { cn } from '@/lib/utils'

const ACCEPTED_TYPES = {
  'video/mp4':       ['.mp4'],
  'video/webm':      ['.webm'],
  'video/quicktime': ['.mov'],
  'video/x-msvideo': ['.avi'],
  'video/x-matroska':['.mkv'],
}

const FEATURES = [
  { icon: FileText, label: 'Structured Notes', desc: 'Detailed markdown — headings, concepts, takeaways' },
  { icon: Search,   label: 'Semantic Search',  desc: 'Ask anything. Jump to the exact moment.' },
  { icon: Sparkles, label: 'Lumen Chat',       desc: 'Talk to your video. Time-range queries.' },
  { icon: Zap,      label: 'Scene Analysis',   desc: 'Keyframes + visual descriptions, per scene.' },
]

const stagger = {
  container: { hidden: {}, show: { transition: { staggerChildren: 0.08 } } },
  item: { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } } },
}

export default function UploadPage() {
  const navigate  = useNavigate()
  const [mode, setMode]     = useState<'file' | 'url'>('file')
  const [url, setUrl]       = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState('')
  const [warming, setWarming] = useState(true)
  const [warmMsg, setWarmMsg] = useState('Connecting to server…')

  // Poll backend until it responds — Render free tier can take 50 s to wake
  useEffect(() => {
    let cancelled = false
    const wake = async () => {
      for (let i = 0; i < 18; i++) {          // up to ~90 s
        if (cancelled) return
        try {
          await api.health()
          if (!cancelled) setWarming(false)
          return
        } catch {
          if (!cancelled) setWarmMsg(`Server starting… (${(i + 1) * 5}s)`)
          await new Promise(r => setTimeout(r, 5000))
        }
      }
      if (!cancelled) setWarming(false)        // give up after 90 s
    }
    wake()
    return () => { cancelled = true }
  }, [])

  const handleFile = useCallback(async (file: File) => {
    setLoading(true); setError('')
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const { job_id, video_id } = await api.uploadFile(file)
        navigate(`/processing/${job_id}/${video_id}`)
        return
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'Upload failed'
        if (msg === 'Failed to fetch' && attempt < 2) {
          await new Promise(r => setTimeout(r, 10000))  // 10 s — Render wake takes ~50 s
          continue
        }
        setError(msg === 'Failed to fetch'
          ? 'Server is still starting up. Please wait 30 seconds then try again.'
          : msg)
        setLoading(false)
        return
      }
    }
  }, [navigate])

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    accept:      ACCEPTED_TYPES,
    maxFiles:    1,
    disabled:    loading || warming,
    onDropAccepted:  ([f]) => handleFile(f),
    onDropRejected:  ()    => setError('Invalid file type. Please drop a video file (MP4, MOV, MKV, AVI, WebM).'),
  })

  // Strip YouTube tracking params that cause yt-dlp to require auth
  const cleanYouTubeUrl = (raw: string): string => {
    try {
      const u = new URL(raw)
      for (const p of ['pp', 'si', 'feature', 'list', 'index', 'ab_channel']) u.searchParams.delete(p)
      return u.toString()
    } catch { return raw }
  }

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return
    const cleanUrl = cleanYouTubeUrl(url.trim())
    setLoading(true); setError('')
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const { job_id, video_id } = await api.submitUrl(cleanUrl)
        navigate(`/processing/${job_id}/${video_id}`)
        return
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'Failed to process URL'
        if (msg === 'Failed to fetch' && attempt < 2) {
          await new Promise(r => setTimeout(r, 10000))
          continue
        }
        let friendly = msg
        if (msg === 'Failed to fetch')
          friendly = 'Server is still starting up. Please wait 30 seconds then try again.'
        else if (msg.toLowerCase().includes('account') || msg.toLowerCase().includes('login') || msg.toLowerCase().includes('sign in') || msg.toLowerCase().includes('age'))
          friendly = 'This video requires sign-in or is age-restricted. Use a fully public video — paste just the youtube.com/watch?v=... URL without extra parameters.'
        else if (msg.toLowerCase().includes('private'))
          friendly = 'This video is private. Use a public YouTube video.'
        setError(friendly)
        setLoading(false)
        return
      }
    }
  }

  return (
    <div className="min-h-screen relative overflow-hidden">
      <OrbBackground variant="hero" className="fixed" />

      {/* Nav */}
      <header className="relative z-10 flex items-center justify-between px-6 py-5 max-w-5xl mx-auto">
        <span className="font-script text-2xl text-prune select-none" aria-label="Lumen">Lumen</span>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-1.5 text-xs text-plum-muted hover:text-plum transition-colors"
            aria-label="My videos"
          >
            <LayoutDashboard className="w-3.5 h-3.5" aria-hidden />
            My Videos
          </button>
          <button
            onClick={async () => {
            try { await supabase?.auth.signOut() } catch (_) {}
            tokenStore.clear()
            window.location.href = '/'
          }}
            className="flex items-center gap-1.5 text-xs text-plum-muted hover:text-plum transition-colors"
            aria-label="Sign out"
          >
            <LogOut className="w-3.5 h-3.5" aria-hidden />
            Sign out
          </button>
        </div>
      </header>

      <main className="relative z-10 flex flex-col items-center px-4 pt-8 pb-20 max-w-3xl mx-auto">
        {/* Hero */}
        <motion.div
          className="text-center mb-12"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: 'easeOut' }}
        >
          <p className="font-script text-lg text-prune/70 mb-2 select-none" aria-hidden="true">
            your AI video companion ✨
          </p>
          <h1 className="font-display text-4xl sm:text-5xl font-semibold text-plum leading-tight tracking-tight mb-4">
            Watch less.<br />
            <em className="italic text-prune">Understand more.</em>
          </h1>
          <p className="text-base text-plum-muted max-w-md mx-auto leading-relaxed">
            Drop any video. Get structured notes, visual insights, and a conversational AI — all from one video, in minutes.
          </p>
        </motion.div>

        {/* Upload card */}
        <motion.div
          className="w-full rose-card p-6 mb-8"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.12, ease: 'easeOut' }}
        >
          {/* Mode tabs */}
          <div className="flex gap-1 bg-blush rounded-xl p-1 mb-5">
            {(['file', 'url'] as const).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError('') }}
                aria-pressed={mode === m}
                className={cn(
                  'flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-all duration-150',
                  mode === m ? 'bg-cream text-plum shadow-sm' : 'text-plum-muted hover:text-plum',
                )}
              >
                {m === 'file'
                  ? <><Upload className="w-3.5 h-3.5" aria-hidden />Upload File</>
                  : <><Link2 className="w-3.5 h-3.5" aria-hidden />Paste URL</>
                }
              </button>
            ))}
          </div>

          {mode === 'file' ? (
            <div
              {...getRootProps()}
              className={cn(
                'relative border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer',
                'transition-all duration-200',
                isDragActive && !isDragReject && 'border-prune bg-prune/5 scale-[1.01]',
                isDragReject  && 'border-red-400 bg-red-50',
                !isDragActive && 'border-pink-dark/60 hover:border-prune/50 hover:bg-prune/3',
                loading && 'pointer-events-none opacity-60',
              )}
              role="button"
              aria-label="Upload video by dropping here or clicking to browse"
              tabIndex={0}
            >
              <input {...getInputProps()} aria-hidden="true" />
              <motion.div
                animate={isDragActive ? { scale: 1.08 } : { scale: 1 }}
                transition={{ duration: 0.15 }}
                className="flex flex-col items-center gap-4"
              >
                {loading
                  ? <Loader2 className="w-12 h-12 text-prune animate-spin" aria-hidden />
                  : (
                    <div className="w-16 h-16 rounded-2xl bg-pink/50 flex items-center justify-center">
                      <Upload className="w-7 h-7 text-prune" aria-hidden />
                    </div>
                  )
                }
                <div>
                  <p className="text-base font-semibold text-plum mb-1">
                    {loading ? 'Uploading…' : warming ? warmMsg : isDragActive ? 'Drop to analyze' : 'Drop your video here'}
                  </p>
                  <p className="text-sm text-plum-muted">
                    {warming
                      ? 'Free-tier server wakes up in ~30s — please wait'
                      : <> or <span className="text-prune font-semibold">browse files</span>{' '}· MP4, MOV, MKV, AVI, WebM · max 500 MB </>
                    }
                  </p>
                </div>
              </motion.div>
            </div>
          ) : (
            <form onSubmit={handleUrlSubmit} className="space-y-3">
              <div className="relative">
                <Link2 className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-plum-muted pointer-events-none" aria-hidden />
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://youtube.com/watch?v=… or any video URL"
                  disabled={loading}
                  aria-label="Video URL"
                  className="rose-input w-full pl-11 pr-4 py-3 text-sm"
                />
              </div>
              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={loading || !url.trim() || warming}
              >
                {loading
                  ? <><Loader2 className="w-4 h-4 animate-spin mr-2" aria-hidden />Processing…</>
                  : warming
                  ? <><Loader2 className="w-4 h-4 animate-spin mr-2" aria-hidden />{warmMsg}</>
                  : <><Zap className="w-4 h-4 mr-2" aria-hidden />Analyze Video</>
                }
              </Button>
            </form>
          )}

          {error && (
            <motion.p
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              role="alert"
              className="mt-4 flex items-center gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-4 py-3"
            >
              <AlertCircle className="w-4 h-4 shrink-0" aria-hidden />
              {error}
            </motion.p>
          )}
        </motion.div>

        {/* Feature pills */}
        <motion.div
          variants={stagger.container}
          initial="hidden"
          animate="show"
          className="grid grid-cols-2 sm:grid-cols-4 gap-3 w-full"
        >
          {FEATURES.map(({ icon: Icon, label, desc }) => (
            <motion.div
              key={label}
              variants={stagger.item}
              className="rose-card rose-card-hover p-4 text-center"
            >
              <div className="w-9 h-9 rounded-xl bg-pink/50 flex items-center justify-center mx-auto mb-2.5">
                <Icon className="w-4 h-4 text-prune" aria-hidden />
              </div>
              <p className="text-xs font-semibold text-plum mb-0.5">{label}</p>
              <p className="text-xs text-plum-muted leading-snug">{desc}</p>
            </motion.div>
          ))}
        </motion.div>

        <p className="mt-10 text-xs text-plum-muted/60 text-center">
          Powered by faster-whisper · PySceneDetect · Groq · FAISS
        </p>
      </main>
      <Footer />
    </div>
  )
}
