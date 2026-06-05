import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mail, Lock, Eye, EyeOff, Sparkles, AlertCircle, Loader2, CheckCircle2, KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import OrbBackground from '@/components/OrbBackground'
import { supabase, supabaseConfigured } from '@/lib/supabase'
import { api, tokenStore } from '@/lib/api'

interface AuthPageProps {
  onAuthenticated: () => void
}

type Mode = 'login' | 'signup' | 'forgot' | 'legacy'

export default function AuthPage({ onAuthenticated }: AuthPageProps) {
  const [mode, setMode] = useState<Mode>(supabaseConfigured ? 'login' : 'legacy')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [adminSecret, setAdminSecret] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const reset = () => { setError(''); setSuccess('') }

  // ── Supabase sign in ──────────────────────────────────────────────────────
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault(); reset()
    if (!supabase) return
    setLoading(true)
    const { error: err } = await supabase.auth.signInWithPassword({ email, password })
    setLoading(false)
    if (err) { setError(err.message); return }
    onAuthenticated()
  }

  // ── Supabase sign up ──────────────────────────────────────────────────────
  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault(); reset()
    if (!supabase) return
    if (password !== confirmPassword) { setError('Passwords do not match.'); return }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
    setLoading(true)
    const { error: err } = await supabase.auth.signUp({ email, password })
    setLoading(false)
    if (err) { setError(err.message); return }
    setSuccess('Check your email for a confirmation link, then sign in.')
    setMode('login')
  }

  // ── Forgot password ───────────────────────────────────────────────────────
  const handleForgot = async (e: React.FormEvent) => {
    e.preventDefault(); reset()
    if (!supabase) return
    setLoading(true)
    const { error: err } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/auth/reset`,
    })
    setLoading(false)
    if (err) { setError(err.message); return }
    setSuccess('Password reset email sent. Check your inbox.')
  }

  // ── Legacy API token (local dev) ──────────────────────────────────────────
  const handleLegacy = async (e: React.FormEvent) => {
    e.preventDefault(); reset()
    setLoading(true)
    try {
      const result = await api.createToken(adminSecret, 'user')
      tokenStore.set(result.token)
      onAuthenticated()
    } catch {
      setError('Invalid admin secret — check the ADMIN_SECRET in your .env file.')
    } finally { setLoading(false) }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-16 relative overflow-hidden">
      <OrbBackground variant="hero" className="fixed" />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: 'easeOut' }}
        className="w-full max-w-md relative z-10"
      >
        {/* Logo */}
        <div className="text-center mb-10">
          <span className="font-script text-4xl text-prune block mb-3">Lumen</span>
          <p className="font-display text-lg font-semibold text-plum">
            {mode === 'login'  ? 'Welcome back'
           : mode === 'signup' ? 'Create your account'
           : mode === 'forgot' ? 'Reset your password'
           : 'Developer access'}
          </p>
          <p className="text-sm text-plum-muted mt-1">
            {mode === 'login'  ? 'Sign in to access your video summaries'
           : mode === 'signup' ? 'Start summarising videos for free'
           : mode === 'forgot' ? "We'll send you a reset link"
           : 'Enter admin secret to create a local token'}
          </p>
        </div>

        <div className="rose-card p-7">
          {/* Tab toggle (login / signup) */}
          {supabaseConfigured && (mode === 'login' || mode === 'signup') && (
            <div className="flex mb-6 bg-blush rounded-xl p-1">
              {(['login', 'signup'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => { setMode(m); reset() }}
                  aria-pressed={mode === m}
                  className={[
                    'flex-1 py-2 text-sm font-medium rounded-lg transition-all duration-150',
                    mode === m ? 'bg-cream text-plum shadow-sm' : 'text-plum-muted hover:text-plum',
                  ].join(' ')}
                >
                  {m === 'login' ? 'Sign In' : 'Sign Up'}
                </button>
              ))}
            </div>
          )}

          {/* Success banner */}
          <AnimatePresence>
            {success && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mb-4 flex items-start gap-2 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3"
                role="status"
              >
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" aria-hidden />
                {success}
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── LOGIN ── */}
          {mode === 'login' && supabaseConfigured && (
            <form onSubmit={handleLogin} className="space-y-4">
              <EmailField value={email} onChange={setEmail} />
              <PasswordField value={password} onChange={setPassword} show={showPassword} onToggle={() => setShowPassword(!showPassword)} label="Password" />
              <div className="text-right">
                <button type="button" onClick={() => { setMode('forgot'); reset() }} className="text-xs text-prune hover:underline">
                  Forgot password?
                </button>
              </div>
              {error && <ErrorBanner msg={error} />}
              <Button type="submit" size="lg" className="w-full" disabled={loading || !email || !password}>
                {loading ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Signing in…</> : 'Sign In'}
              </Button>
            </form>
          )}

          {/* ── SIGN UP ── */}
          {mode === 'signup' && supabaseConfigured && (
            <form onSubmit={handleSignup} className="space-y-4">
              <EmailField value={email} onChange={setEmail} />
              <PasswordField value={password} onChange={setPassword} show={showPassword} onToggle={() => setShowPassword(!showPassword)} label="Password" hint="Min. 8 characters" />
              <PasswordField value={confirmPassword} onChange={setConfirmPassword} show={showPassword} onToggle={() => setShowPassword(!showPassword)} label="Confirm Password" />
              {error && <ErrorBanner msg={error} />}
              <Button type="submit" size="lg" className="w-full" disabled={loading || !email || !password || !confirmPassword}>
                {loading ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Creating account…</> : 'Create Account'}
              </Button>
            </form>
          )}

          {/* ── FORGOT PASSWORD ── */}
          {mode === 'forgot' && (
            <form onSubmit={handleForgot} className="space-y-4">
              <EmailField value={email} onChange={setEmail} />
              {error && <ErrorBanner msg={error} />}
              <Button type="submit" size="lg" className="w-full" disabled={loading || !email}>
                {loading ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Sending…</> : 'Send Reset Link'}
              </Button>
              <button type="button" onClick={() => { setMode('login'); reset() }} className="w-full text-sm text-prune hover:underline text-center">
                ← Back to Sign In
              </button>
            </form>
          )}

          {/* ── LEGACY TOKEN (local dev) ── */}
          {mode === 'legacy' && (
            <form onSubmit={handleLegacy} className="space-y-4">
              <p className="text-xs text-plum-muted bg-blush rounded-xl p-3 leading-relaxed">
                Enter the <code className="font-mono text-prune bg-pink/30 px-1 rounded">ADMIN_SECRET</code> from your{' '}
                <code className="font-mono text-prune bg-pink/30 px-1 rounded">.env</code> file
                {' '}(default: <code className="font-mono text-prune">my-local-demo-secret</code>).
              </p>
              <div>
                <label htmlFor="admin-secret" className="block text-xs font-semibold text-plum mb-1.5">Admin Secret</label>
                <div className="relative">
                  <KeyRound className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-plum-muted" aria-hidden />
                  <input
                    id="admin-secret"
                    type="password"
                    value={adminSecret}
                    onChange={(e) => setAdminSecret(e.target.value)}
                    placeholder="my-local-demo-secret"
                    autoComplete="off"
                    className="rose-input w-full pl-11 pr-4 py-2.5 text-sm"
                  />
                </div>
              </div>
              {error && <ErrorBanner msg={error} />}
              <Button type="submit" size="lg" className="w-full" disabled={loading || !adminSecret.trim()}>
                {loading ? <><Loader2 className="w-4 h-4 animate-spin mr-2" />Signing in…</> : <><Sparkles className="w-4 h-4 mr-2" />Sign In</>}
              </Button>
            </form>
          )}

          {/* Footer: toggle between Supabase and legacy mode */}
          {supabaseConfigured && mode !== 'forgot' && (
            <p className="mt-5 text-xs text-center text-plum-muted">
              {mode === 'legacy'
                ? <button onClick={() => { setMode('login'); reset() }} className="text-prune hover:underline">Use email/password instead</button>
                : <button onClick={() => { setMode('legacy'); reset() }} className="hover:underline">Using local dev? Sign in with admin token</button>
              }
            </p>
          )}
        </div>

        <p className="text-xs text-center text-plum-muted mt-6">
          Your data is encrypted and accessible only to you.
        </p>
      </motion.div>
    </div>
  )
}

// ── Reusable form field components ───────────────────────────────────────────

function EmailField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label htmlFor="email" className="block text-xs font-semibold text-plum mb-1.5">Email</label>
      <div className="relative">
        <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-plum-muted" aria-hidden />
        <input
          id="email"
          type="email"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="you@example.com"
          autoComplete="email"
          required
          className="rose-input w-full pl-11 pr-4 py-2.5 text-sm"
        />
      </div>
    </div>
  )
}

function PasswordField({
  value, onChange, show, onToggle, label, hint,
}: {
  value: string; onChange: (v: string) => void
  show: boolean; onToggle: () => void
  label: string; hint?: string
}) {
  return (
    <div>
      <label className="block text-xs font-semibold text-plum mb-1.5">
        {label}{hint && <span className="font-normal text-plum-muted ml-1">— {hint}</span>}
      </label>
      <div className="relative">
        <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-plum-muted" aria-hidden />
        <input
          type={show ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="••••••••"
          autoComplete="current-password"
          required
          className="rose-input w-full pl-11 pr-11 py-2.5 text-sm"
        />
        <button
          type="button"
          onClick={onToggle}
          className="absolute right-3.5 top-1/2 -translate-y-1/2 text-plum-muted hover:text-plum transition-colors"
          aria-label={show ? 'Hide password' : 'Show password'}
        >
          {show ? <EyeOff className="w-4 h-4" aria-hidden /> : <Eye className="w-4 h-4" aria-hidden />}
        </button>
      </div>
    </div>
  )
}


function ErrorBanner({ msg }: { msg: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-4 py-3"
      role="alert"
    >
      <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden />
      {msg}
    </motion.div>
  )
}
