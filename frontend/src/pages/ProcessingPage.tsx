import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, Circle, AlertCircle } from 'lucide-react'
import { Progress } from '@/components/ui/progress'
import { api, type JobStatus } from '@/lib/api'
import { useReducedMotion } from '@/hooks/useReducedMotion'

const STAGES = [
  { label: 'Extracting audio',     hint: 'Pulling the audio track from your video.' },
  { label: 'Transcribing',          hint: 'Converting speech to text with Whisper AI.' },
  { label: 'Detecting scenes',      hint: 'Finding scene cuts and visual moments.' },
  { label: 'Understanding visuals', hint: 'Describing each keyframe with vision AI.' },
  { label: 'Writing notes',         hint: 'Synthesising audio and visuals into structured notes.' },
]

const STAGE_MAP: Record<string, number> = {
  'probing':    0, 'extracting': 0, 'detecting audio': 0,
  'transcrib':  1,
  'detecting s':2, 'keyframe':  2,
  'analyzing':  3, 'analysing': 3, 'visual': 3,
  'generating': 4, 'building':  4, 'building search': 4, 'complete': 5,
}

function stageIndex(stage: string): number {
  const l = stage.toLowerCase()
  for (const [key, idx] of Object.entries(STAGE_MAP)) {
    if (l.includes(key)) return idx
  }
  return -1
}

export default function ProcessingPage() {
  const { jobId, videoId } = useParams<{ jobId: string; videoId: string }>()
  const navigate = useNavigate()
  const reduced  = useReducedMotion()
  const [job, setJob]   = useState<JobStatus | null>(null)
  const [error, setError] = useState('')
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!jobId) return
    const poll = async () => {
      try {
        const data = await api.getJob(jobId)
        setJob(data)
        if (data.status === 'completed') {
          clearInterval(pollRef.current!)
          setTimeout(() => navigate(`/results/${videoId}`), 900)
        } else if (data.status === 'failed') {
          clearInterval(pollRef.current!)
          setError(data.error || 'Processing failed unexpectedly.')
        }
      } catch (e: unknown) {
        clearInterval(pollRef.current!)
        setError(e instanceof Error ? e.message : 'Could not reach the server.')
      }
    }
    poll()
    pollRef.current = setInterval(poll, 1500)
    return () => clearInterval(pollRef.current!)
  }, [jobId, videoId, navigate])

  const currentIdx = job ? stageIndex(job.stage) : -1
  const progress   = job?.progress ?? 0
  const done       = job?.status === 'completed'
  const activeStageName = currentIdx >= 0 && currentIdx < STAGES.length
    ? STAGES[currentIdx].label
    : (done ? 'Complete' : 'Starting up…')

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-16 relative overflow-hidden">
      {/* Background orb */}
      <div
        className="absolute rounded-full pointer-events-none"
        style={{
          width: 520, height: 520,
          left: '50%', top: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'radial-gradient(circle, rgba(229,197,193,0.4) 0%, rgba(244,225,224,0.2) 60%, transparent 80%)',
          filter: 'blur(60px)',
        }}
        aria-hidden="true"
      />

      <motion.div
        className="w-full max-w-md relative z-10"
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      >
        {/* Pulsing orb */}
        <div className="flex justify-center mb-10" aria-hidden="true">
          <div className="relative">
            {!reduced && !error && !done && (
              <>
                {[1, 2, 3].map((i) => (
                  <motion.div
                    key={i}
                    className="absolute inset-0 rounded-full border border-prune/20"
                    animate={{ scale: 1 + i * 0.28, opacity: 0 }}
                    transition={{ duration: 2.4, delay: i * 0.55, repeat: Infinity, ease: 'easeOut' }}
                    style={{ transformOrigin: 'center' }}
                  />
                ))}
              </>
            )}
            <div
              className={cn(
                'relative w-24 h-24 rounded-full flex items-center justify-center shadow-button-hover',
                !reduced && !done && !error && 'animate-pulse-glow',
              )}
              style={{
                background: done
                  ? 'linear-gradient(135deg, #7F6269, #9A7A82)'
                  : error
                  ? '#EF4444'
                  : 'linear-gradient(135deg, #7F6269 0%, #E5C5C1 100%)',
              }}
            >
              {error
                ? <AlertCircle className="w-10 h-10 text-white" aria-hidden />
                : done
                ? <CheckCircle2 className="w-10 h-10 text-cream" aria-hidden />
                : (
                  /* Animated waveform bars */
                  <div className="flex items-end gap-0.5 h-8" role="img" aria-label="Processing audio">
                    {[12,18,14,22,16,20,12].map((h, i) => (
                      <motion.span
                        key={i}
                        className="w-1 rounded-full bg-cream/90 inline-block"
                        style={{ height: h }}
                        animate={reduced ? {} : { scaleY: [0.35, 1, 0.35] }}
                        transition={{ duration: 0.9, delay: i * 0.12, repeat: Infinity, ease: 'easeInOut' }}
                      />
                    ))}
                  </div>
                )
              }
            </div>
          </div>
        </div>

        {/* Card */}
        <div className="rose-card px-7 py-6">
          <div className="text-center mb-6">
            <h1 className="font-display text-xl font-semibold text-plum mb-1">
              {error ? 'Something went wrong' : done ? 'All done!' : 'Analyzing your video…'}
            </h1>
            <p className="text-sm text-plum-muted">
              {error
                ? 'An error occurred during processing.'
                : done
                ? 'Redirecting to your notes…'
                : activeStageName
              }
            </p>
          </div>

          {!error && (
            <div className="mb-7">
              <div className="flex justify-between text-xs text-plum-muted mb-2">
                <span>Progress</span>
                <span className="font-mono tabular-nums">{Math.round(progress)}%</span>
              </div>
              <Progress value={progress} className="h-2" />
            </div>
          )}

          {error && (
            <div className="mb-6 flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-4 py-3" role="alert">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden />
              {error}
            </div>
          )}

          {/* Stage tracker */}
          <ol className="space-y-3" aria-label="Processing stages">
            {STAGES.map((stage, idx) => {
              const isDone   = currentIdx > idx || done
              const isActive = currentIdx === idx && !error
              const isPending= currentIdx < idx && !done

              return (
                <motion.li
                  key={stage.label}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.06, duration: 0.3 }}
                  className={cn('flex items-center gap-3 text-sm', isPending && 'opacity-35')}
                  aria-current={isActive ? 'step' : undefined}
                >
                  <div className="w-5 h-5 shrink-0 flex items-center justify-center" aria-hidden>
                    {isDone
                      ? <CheckCircle2 className="w-5 h-5 text-prune" />
                      : isActive
                      ? (
                        <motion.div
                          className="w-5 h-5 rounded-full border-2 border-prune border-t-transparent stage-dot-active"
                          animate={reduced ? {} : { rotate: 360 }}
                          transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
                        />
                      )
                      : <Circle className="w-5 h-5 text-pink-dark" />
                    }
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className={cn(
                      'font-medium',
                      isDone   && 'text-plum',
                      isActive && 'text-prune',
                      isPending && 'text-plum-muted',
                    )}>
                      {stage.label}
                    </span>
                    {isActive && (
                      <p className="text-xs text-plum-muted/80 mt-0.5 truncate">{stage.hint}</p>
                    )}
                  </div>
                  {isDone && (
                    <span className="text-xs text-prune/60 font-medium ml-auto">Done</span>
                  )}
                  {isActive && (
                    <span className="text-xs bg-pink text-plum rounded-full px-2 py-0.5 ml-auto font-medium">
                      Active
                    </span>
                  )}
                </motion.li>
              )
            })}
          </ol>
        </div>
      </motion.div>
    </div>
  )
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ')
}
