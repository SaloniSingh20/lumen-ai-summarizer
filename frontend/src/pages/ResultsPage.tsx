import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import {
  ArrowLeft, Download, Volume2, VolumeX, Languages,
  FileText, Image, Search, BarChart2, FileDown,
  ChevronRight, Lightbulb, PlayCircle, BookOpen,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie,
} from 'recharts'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import AnimatedCounter from '@/components/AnimatedCounter'
import LumenChat from '@/components/LumenChat'
import AuthedImage from '@/components/AuthedImage'
import { api, tokenStore, type VideoData, type AnalyticsData, type SearchResult } from '@/lib/api'
import { getAccessToken } from '@/lib/supabase'
import { formatTime, formatDuration } from '@/lib/utils'
import { MOCK_NOTES, MOCK_SCENES, MOCK_ANALYTICS } from '@/lib/mockData'

const stagger = {
  container: { hidden: {}, show: { transition: { staggerChildren: 0.07 } } },
  item: { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } } },
}

const CHART_COLORS = ['#7F6269','#9A7A82','#B39198','#C8AEAD','#D4B5B1','#E5C5C1']

export default function ResultsPage() {
  const { videoId } = useParams<{ videoId: string }>()
  const navigate = useNavigate()
  const videoRef = useRef<HTMLVideoElement>(null)

  const [video,     setVideo]     = useState<VideoData | null>(null)
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState('')
  const [streamUrl, setStreamUrl] = useState('')
  const [searchQ,   setSearchQ]   = useState('')
  const [results,   setResults]   = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [activeTab, setActiveTab] = useState('notes')
  const [pdfLoading, setPdfLoading] = useState(false)

  useEffect(() => {
    if (!videoId) return
    Promise.all([api.getVideo(videoId), api.getAnalytics(videoId)])
      .then(([v, a]) => { setVideo(v); setAnalytics(a) })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [videoId])

  useEffect(() => {
    if (!videoId) return
    api.getMediaToken(videoId)
      .then(({ token }) => setStreamUrl(api.buildStreamUrl(videoId, token)))
      .catch(() => {})
  }, [videoId])

  const seekTo = (s: number) => {
    if (videoRef.current) { videoRef.current.currentTime = s; videoRef.current.play() }
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQ.trim() || !videoId) return
    setSearching(true)
    try {
      const { results: r } = await api.searchVideo(videoId, searchQ)
      setResults(r)
    } catch { setResults([]) }
    finally { setSearching(false) }
  }

  const downloadPdf = async () => {
    if (!videoId || pdfLoading) return
    setPdfLoading(true)
    try {
      const token = (await getAccessToken()) ?? tokenStore.get()
      const res = await fetch(api.exportPdfUrl(videoId), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `Export failed (${res.status})`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `lumen-notes-${videoId.slice(0, 8)}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to download PDF')
    } finally {
      setPdfLoading(false)
    }
  }

  // Use real data when available, fall back to mock for demo
  const notes  = video?.notes  || MOCK_NOTES
  const scenes = (video?.scenes && video.scenes.length > 0) ? video.scenes : MOCK_SCENES
  const stats  = analytics || MOCK_ANALYTICS

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-9 h-9 rounded-full border-2 border-prune/30 border-t-prune animate-spin" role="status" aria-label="Loading results" />
        <p className="text-sm text-plum-muted">Loading your notes…</p>
      </div>
    </div>
  )

  if (error && !video) return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="text-center space-y-4">
        <p className="text-red-600 text-sm">{error}</p>
        <Button variant="outline" onClick={() => navigate('/')}>← Back</Button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen">
      {/* Sticky header */}
      <header className="sticky top-0 z-40 rose-glass border-b border-pink/40 px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate('/')} aria-label="New video">
            <ArrowLeft className="w-4 h-4 mr-1" aria-hidden />
            <span className="hidden sm:inline">New video</span>
          </Button>

          <div className="flex-1 min-w-0">
            <h1 className="font-display text-sm font-semibold text-plum truncate">
              {notes.title || video?.filename || 'Video Notes'}
            </h1>
            <div className="flex items-center flex-wrap gap-x-3 gap-y-1 mt-0.5">
              {notes.content_type && (
                <Badge variant="pink" className="text-xs">{notes.content_type}</Badge>
              )}
              {notes.language_detected && (
                <span className="flex items-center gap-1 text-xs text-plum-muted">
                  <Languages className="w-3 h-3" aria-hidden />{notes.language_detected.toUpperCase()}
                </span>
              )}
              {(video?.has_audio ?? notes.has_audio)
                ? <span className="flex items-center gap-1 text-xs text-prune"><Volume2 className="w-3 h-3" aria-hidden />Audio</span>
                : <span className="flex items-center gap-1 text-xs text-plum-muted"><VolumeX className="w-3 h-3" aria-hidden />No audio</span>
              }
              {video?.duration && (
                <span className="text-xs text-plum-muted">{formatDuration(video.duration)}</span>
              )}
            </div>
          </div>

          <Button variant="outline" size="sm" onClick={downloadPdf} disabled={pdfLoading} aria-label="Export PDF">
            {pdfLoading
              ? <span className="w-3.5 h-3.5 mr-1.5 rounded-full border-2 border-prune/30 border-t-prune animate-spin inline-block" />
              : <Download className="w-3.5 h-3.5 mr-1.5" aria-hidden />}
            PDF
          </Button>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-6 grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6">
        {/* ── Left column ── */}
        <div className="space-y-5 min-w-0">
          {/* Video player */}
          <div className="rose-card overflow-hidden">
            {streamUrl
              ? (
                <video
                  ref={videoRef}
                  controls
                  src={streamUrl}
                  className="w-full aspect-video bg-plum"
                  aria-label={`Video: ${notes.title || 'uploaded video'}`}
                />
              )
              : (
                <div className="w-full aspect-video bg-blush flex items-center justify-center">
                  <div className="text-center text-plum-muted">
                    <PlayCircle className="w-10 h-10 mx-auto mb-2 opacity-40" aria-hidden />
                    <p className="text-sm">{loading ? 'Loading video…' : 'Video unavailable'}</p>
                  </div>
                </div>
              )
            }
          </div>

          {/* TL;DR */}
          {notes.tldr && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="rose-card p-5 border-l-4 border-prune/50"
            >
              <p className="text-xs font-semibold text-prune/70 uppercase tracking-widest mb-2 font-sans">TL;DR</p>
              <p className="text-sm leading-relaxed text-plum">{notes.tldr}</p>
            </motion.div>
          )}

          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="overflow-x-auto flex-nowrap scrollbar-none">
              <TabsTrigger value="notes"><FileText className="w-3.5 h-3.5" aria-hidden />Notes</TabsTrigger>
              <TabsTrigger value="scenes"><Image className="w-3.5 h-3.5" aria-hidden />Scenes</TabsTrigger>
              <TabsTrigger value="search"><Search className="w-3.5 h-3.5" aria-hidden />Search</TabsTrigger>
              <TabsTrigger value="analytics"><BarChart2 className="w-3.5 h-3.5" aria-hidden />Analytics</TabsTrigger>
              <TabsTrigger value="export"><FileDown className="w-3.5 h-3.5" aria-hidden />Export</TabsTrigger>
            </TabsList>

            {/* ── NOTES ── */}
            <TabsContent value="notes">
              <AnimatePresence mode="wait">
                <motion.div
                  key="notes"
                  variants={stagger.container}
                  initial="hidden"
                  animate="show"
                  className="space-y-5"
                >
                  {/* Topics */}
                  {notes.main_topics && notes.main_topics.length > 0 && (
                    <motion.div variants={stagger.item} className="rose-card p-5">
                      <h2 className="font-display text-sm font-semibold text-plum-muted uppercase tracking-wider mb-3">
                        <BookOpen className="w-3.5 h-3.5 inline mr-1.5 text-prune" aria-hidden />
                        Main Topics
                      </h2>
                      <div className="flex flex-wrap gap-2">
                        {notes.main_topics.map((t) => (
                          <Badge key={t} variant="pink">{t}</Badge>
                        ))}
                      </div>
                    </motion.div>
                  )}

                  {/* Detailed Notes */}
                  {notes.detailed_notes && (
                    <motion.div variants={stagger.item} className="rose-card p-6">
                      <h2 className="font-display text-base font-semibold text-plum mb-4">
                        Detailed Notes
                      </h2>
                      <div className="prose-rose text-sm">
                        <ReactMarkdown>{notes.detailed_notes}</ReactMarkdown>
                      </div>
                    </motion.div>
                  )}

                  {/* Key Concepts */}
                  {notes.key_concepts && notes.key_concepts.length > 0 && (
                    <motion.div variants={stagger.item} className="rose-card p-5">
                      <h2 className="font-display text-sm font-semibold text-plum-muted uppercase tracking-wider mb-4">
                        <Lightbulb className="w-3.5 h-3.5 inline mr-1.5 text-prune" aria-hidden />
                        Key Concepts
                      </h2>
                      <div className="space-y-3">
                        {notes.key_concepts.map((kc, i) => (
                          <div key={i} className="bg-blush/60 rounded-xl p-4">
                            <p className="text-sm font-semibold text-prune mb-1">{kc.concept}</p>
                            <p className="text-sm text-plum/80 leading-relaxed">{kc.explanation}</p>
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  )}

                  {/* Takeaways */}
                  {notes.key_takeaways && notes.key_takeaways.length > 0 && (
                    <motion.div variants={stagger.item} className="rose-card p-5">
                      <h2 className="font-display text-sm font-semibold text-plum-muted uppercase tracking-wider mb-3">
                        Key Takeaways
                      </h2>
                      <ul className="space-y-2" role="list">
                        {notes.key_takeaways.map((t, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm text-plum">
                            <ChevronRight className="w-4 h-4 text-prune shrink-0 mt-0.5" aria-hidden />
                            {t}
                          </li>
                        ))}
                      </ul>
                    </motion.div>
                  )}

                  {/* Visual Summary */}
                  {notes.visual_summary && (
                    <motion.div variants={stagger.item} className="rose-card p-5">
                      <h2 className="font-display text-sm font-semibold text-plum-muted uppercase tracking-wider mb-2">
                        Visual Summary
                      </h2>
                      <p className="text-sm text-plum leading-relaxed">{notes.visual_summary}</p>
                    </motion.div>
                  )}

                  {notes.confidence_notes && (
                    <p className="text-xs text-plum-muted italic px-1">{notes.confidence_notes}</p>
                  )}
                </motion.div>
              </AnimatePresence>
            </TabsContent>

            {/* ── SCENES ── */}
            <TabsContent value="scenes">
              {scenes.length === 0
                ? <EmptyState icon={Image} text="No scenes detected yet." />
                : (
                  <motion.div
                    variants={stagger.container}
                    initial="hidden"
                    animate="show"
                    className="grid grid-cols-1 sm:grid-cols-2 gap-4"
                  >
                    {scenes.map((scene) => (
                      <motion.div
                        key={scene.id}
                        variants={stagger.item}
                        className="rose-card rose-card-hover overflow-hidden cursor-pointer group"
                        onClick={() => seekTo(scene.start_time)}
                        role="button"
                        tabIndex={0}
                        aria-label={`Jump to ${scene.scene_label || `Scene ${scene.scene_number}`} at ${formatTime(scene.start_time)}`}
                        onKeyDown={(e) => e.key === 'Enter' && seekTo(scene.start_time)}
                      >
                        <div className="relative aspect-video bg-pink/20 overflow-hidden">
                          {videoId
                            ? (
                              <AuthedImage
                                src={`/videos/${videoId}/keyframes/${scene.scene_number}`}
                                alt={scene.scene_label || `Scene ${scene.scene_number}`}
                                className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                              />
                            )
                            : <Skeleton className="w-full h-full" />
                          }
                          <div className="absolute inset-0 bg-gradient-to-t from-plum/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-end p-3">
                            <span className="text-cream text-xs font-medium">
                              ▶ Jump to {formatTime(scene.start_time)}
                            </span>
                          </div>
                          <Badge
                            variant="pink"
                            className="absolute top-2 left-2 text-xs shadow-sm"
                          >
                            {formatTime(scene.start_time)}–{formatTime(scene.end_time)}
                          </Badge>
                        </div>
                        <div className="p-3.5">
                          <p className="text-sm font-semibold text-plum mb-1 truncate">
                            {scene.scene_label || `Scene ${scene.scene_number}`}
                          </p>
                          {scene.description && (
                            <p className="text-xs text-plum-muted line-clamp-2 leading-relaxed">
                              {scene.description}
                            </p>
                          )}
                        </div>
                      </motion.div>
                    ))}
                  </motion.div>
                )
              }
            </TabsContent>

            {/* ── SEARCH ── */}
            <TabsContent value="search">
              <form onSubmit={handleSearch} className="flex gap-2 mb-5">
                <div className="relative flex-1">
                  <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-plum-muted pointer-events-none" aria-hidden />
                  <input
                    type="search"
                    value={searchQ}
                    onChange={(e) => setSearchQ(e.target.value)}
                    placeholder="Where did they explain CNNs? What's shown visually?"
                    aria-label="Search video content"
                    className="rose-input w-full pl-10 pr-4 py-2.5 text-sm"
                  />
                </div>
                <Button type="submit" disabled={searching || !searchQ.trim()}>
                  {searching ? 'Searching…' : 'Search'}
                </Button>
              </form>

              {results.length > 0 && (
                <motion.div
                  variants={stagger.container}
                  initial="hidden"
                  animate="show"
                  className="space-y-3"
                >
                  <p className="text-xs text-plum-muted">{results.length} result{results.length !== 1 ? 's' : ''}</p>
                  {results.map((r, i) => (
                    <motion.div
                      key={i}
                      variants={stagger.item}
                      className="rose-card rose-card-hover p-4 cursor-pointer"
                      onClick={() => seekTo(r.start)}
                      role="button"
                      tabIndex={0}
                      aria-label={`Search result: ${r.text.slice(0, 60)}… at ${formatTime(r.start)}`}
                      onKeyDown={(e) => e.key === 'Enter' && seekTo(r.start)}
                    >
                      <div className="flex items-start justify-between gap-3 mb-2">
                        <Badge variant={r.type === 'transcript' ? 'default' : 'pink'} className="text-xs shrink-0">
                          {r.type === 'transcript' ? '🎙 Transcript' : '🖼 Visual'}
                        </Badge>
                        <span className="text-xs text-plum-muted font-mono">
                          {formatTime(r.start)} → {formatTime(r.end)}
                        </span>
                      </div>
                      <p className="text-sm text-plum leading-relaxed mb-3">{r.text}</p>
                      <button
                        className="text-xs text-prune font-medium hover:underline flex items-center gap-1"
                        onClick={(e) => { e.stopPropagation(); seekTo(r.start) }}
                      >
                        ▶ Jump to {formatTime(r.start)}
                      </button>
                    </motion.div>
                  ))}
                </motion.div>
              )}

              {results.length === 0 && searchQ && !searching && (
                <EmptyState icon={Search} text={`No results for "${searchQ}"`} />
              )}

              {results.length === 0 && !searchQ && (
                <div className="text-center py-16 text-plum-muted">
                  <Search className="w-10 h-10 mx-auto mb-3 opacity-30" aria-hidden />
                  <p className="text-sm font-medium text-plum mb-1">Semantic search</p>
                  <p className="text-xs">Ask a question and jump straight to the answer in the video.</p>
                </div>
              )}
            </TabsContent>

            {/* ── ANALYTICS ── */}
            <TabsContent value="analytics">
              <AnalyticsPanel analytics={stats} />
            </TabsContent>

            {/* ── EXPORT ── */}
            <TabsContent value="export">
              <div className="rose-card p-10 text-center">
                <div className="w-16 h-16 rounded-2xl bg-pink/40 flex items-center justify-center mx-auto mb-5">
                  <FileDown className="w-7 h-7 text-prune" aria-hidden />
                </div>
                <h2 className="font-display text-lg font-semibold text-plum mb-2">Export your notes</h2>
                <p className="text-sm text-plum-muted mb-6 max-w-sm mx-auto leading-relaxed">
                  Download a beautifully formatted PDF with the title, TL;DR, all notes, key concepts, takeaways, and scene descriptions.
                </p>
                <Button size="lg" onClick={downloadPdf} disabled={pdfLoading} className="gap-2">
                  {pdfLoading
                    ? <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin inline-block" />
                    : <Download className="w-4 h-4" aria-hidden />}
                  {pdfLoading ? 'Generating…' : 'Download PDF'}
                </Button>
                <p className="text-xs text-plum-muted mt-4">Formatted with Fraunces serif headings · ready to share</p>
              </div>
            </TabsContent>
          </Tabs>
        </div>

        {/* ── Right column: Lumen chat ── */}
        <div className="xl:sticky xl:top-20 xl:h-[calc(100vh-5.5rem)]">
          <LumenChat videoId={videoId!} onSeek={seekTo} />
        </div>
      </div>
    </div>
  )
}

// ── Sub-components ──────────────────────────────────────────────────────────

function EmptyState({ icon: Icon, text }: { icon: React.ElementType; text: string }) {
  return (
    <div className="text-center py-16 text-plum-muted">
      <Icon className="w-10 h-10 mx-auto mb-3 opacity-30" aria-hidden />
      <p className="text-sm">{text}</p>
    </div>
  )
}

function AnalyticsPanel({ analytics }: { analytics: AnalyticsData }) {
  const stats = [
    { label: 'Scenes',   value: analytics.scene_count,  suffix: '',   decimals: 0 },
    { label: 'Words',    value: analytics.total_words,   suffix: '',   decimals: 0 },
    { label: 'WPM',      value: analytics.words_per_minute ?? 0, suffix: '', decimals: 0 },
    { label: 'Speaking', value: (analytics.speaking_ratio ?? 0) * 100, suffix: '%', decimals: 0 },
  ]

  const donutData = [
    { name: 'Speaking', value: Math.round((analytics.speaking_ratio ?? 0.85) * 100), fill: '#7F6269' },
    { name: 'Silence',  value: Math.round((1 - (analytics.speaking_ratio ?? 0.85)) * 100), fill: '#E5C5C1' },
  ]

  return (
    <div className="space-y-5">
      {/* Stats grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {stats.map(({ label, value, suffix, decimals }) => (
          <div key={label} className="rose-card p-4 text-center">
            <p className="font-display text-2xl font-semibold text-plum tabular-nums">
              <AnimatedCounter value={value} suffix={suffix} decimals={decimals} />
            </p>
            <p className="text-xs text-plum-muted mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* Word frequency chart */}
      {analytics.word_frequency.length > 0 && (
        <div className="rose-card p-5">
          <h3 className="font-display text-sm font-semibold text-plum mb-4">Top Words</h3>
          <ResponsiveContainer width="100%" height={210}>
            <BarChart
              data={analytics.word_frequency.slice(0, 12)}
              layout="vertical"
              margin={{ left: 0, right: 20, top: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(229,197,193,0.5)" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: '#8C7178' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="word"
                tick={{ fontSize: 11, fill: '#3E2E33' }}
                axisLine={false}
                tickLine={false}
                width={80}
              />
              <Tooltip
                contentStyle={{
                  background: '#FFFBFA',
                  border: '1px solid rgba(229,197,193,0.6)',
                  borderRadius: 10,
                  fontSize: 12,
                  color: '#3E2E33',
                  boxShadow: '0 4px 16px rgba(62,46,51,0.1)',
                }}
                cursor={{ fill: 'rgba(229,197,193,0.2)' }}
              />
              <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                {analytics.word_frequency.slice(0, 12).map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Speaking ratio + donut */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {analytics.speaking_ratio != null && (
          <div className="rose-card p-5">
            <h3 className="font-display text-sm font-semibold text-plum mb-3">Speaking Ratio</h3>
            <div className="flex items-center justify-center">
              <PieChart width={140} height={140} aria-label={`Speaking ${Math.round(analytics.speaking_ratio * 100)}%`}>
                <Pie
                  data={donutData}
                  cx={65} cy={65}
                  innerRadius={38}
                  outerRadius={58}
                  dataKey="value"
                  startAngle={90}
                  endAngle={-270}
                  stroke="none"
                >
                  {donutData.map((d, i) => (
                    <Cell key={i} fill={d.fill} />
                  ))}
                </Pie>
                <text x={65} y={60} textAnchor="middle" className="font-display" style={{ fontSize: 18, fontWeight: 600, fill: '#3E2E33', fontFamily: 'Fraunces, serif' }}>
                  {Math.round((analytics.speaking_ratio ?? 0) * 100)}%
                </text>
                <text x={65} y={78} textAnchor="middle" style={{ fontSize: 10, fill: '#8C7178', fontFamily: 'Inter, sans-serif' }}>
                  speech
                </text>
              </PieChart>
            </div>
          </div>
        )}

        {analytics.top_topics.length > 0 && (
          <div className="rose-card p-5">
            <h3 className="font-display text-sm font-semibold text-plum mb-3">Topics</h3>
            <div className="flex flex-wrap gap-2">
              {analytics.top_topics.map((t) => (
                <Badge key={t} variant="pink">{t}</Badge>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Duration + WPM bar */}
      {analytics.words_per_minute && (
        <div className="rose-card p-5">
          <h3 className="font-display text-sm font-semibold text-plum mb-3">Content Density</h3>
          <div className="flex items-center gap-4">
            <span className="text-xs text-plum-muted w-20 shrink-0">Words / min</span>
            <div className="flex-1">
              <Progress value={Math.min((analytics.words_per_minute / 200) * 100, 100)} className="h-3" />
            </div>
            <span className="text-xs font-mono text-plum-muted w-14 text-right tabular-nums">
              {analytics.words_per_minute} wpm
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
