import { useState, useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import UploadPage     from '@/pages/UploadPage'
import ProcessingPage from '@/pages/ProcessingPage'
import ResultsPage    from '@/pages/ResultsPage'
import AuthPage       from '@/pages/AuthPage'
import DashboardPage  from '@/pages/DashboardPage'
import { tokenStore, api } from '@/lib/api'
import { supabase, getAccessToken } from '@/lib/supabase'

type AuthState = 'loading' | 'authed' | 'unauthed'

function PageWrapper({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  )
}

export default function App() {
  const [authState, setAuthState] = useState<AuthState>('loading')
  const location = useLocation()

  useEffect(() => {
    // 1. Initial auth check
    checkAuth()

    // 2. Supabase session listener — fires on login/logout/token-refresh
    if (!supabase) return
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        if (session) {
          setAuthState('authed')
        } else if (_event === 'SIGNED_OUT') {
          tokenStore.clear()
          setAuthState('unauthed')
        }
      }
    )
    return () => { subscription.unsubscribe() }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const checkAuth = async () => {
    try {
      // Priority 1: Supabase session JWT
      const supabaseToken = await getAccessToken()
      if (supabaseToken) { setAuthState('authed'); return }

      // Priority 2: Legacy local token
      const legacy = tokenStore.get()
      if (!legacy) { setAuthState('unauthed'); return }

      await api.getMe()
      setAuthState('authed')
    } catch {
      tokenStore.clear()
      setAuthState('unauthed')
    }
  }

  if (authState === 'loading') {
    return (
      <div className="rose-bg min-h-screen flex items-center justify-center">
        <div
          className="w-9 h-9 rounded-full border-2 border-prune/30 border-t-prune animate-spin"
          role="status"
          aria-label="Loading"
        />
      </div>
    )
  }

  if (authState === 'unauthed') {
    return (
      <div className="rose-bg min-h-screen">
        <AuthPage onAuthenticated={() => setAuthState('authed')} />
      </div>
    )
  }

  return (
    <div className="rose-bg min-h-screen">
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route path="/"                           element={<PageWrapper><UploadPage /></PageWrapper>} />
          <Route path="/dashboard"                  element={<PageWrapper><DashboardPage /></PageWrapper>} />
          <Route path="/processing/:jobId/:videoId" element={<PageWrapper><ProcessingPage /></PageWrapper>} />
          <Route path="/results/:videoId"           element={<PageWrapper><ResultsPage /></PageWrapper>} />
        </Routes>
      </AnimatePresence>
    </div>
  )
}
