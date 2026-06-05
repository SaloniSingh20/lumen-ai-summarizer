import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Send, Sparkles, User, Bot, ChevronRight, Loader2, X, Minus } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api, type ChatMessage, type SourceChip } from '@/lib/api'
import { formatTime } from '@/lib/utils'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: SourceChip[]
  seekTo?: number
  loading?: boolean
}

interface LumenChatProps {
  videoId: string
  onSeek: (seconds: number) => void
}

const SUGGESTIONS = [
  'Summarize the intro',
  'What are the main topics?',
  'What happened in the last 30s?',
  'What is shown visually?',
]

const WELCOME = "Hi! I'm **Lumen** — ask me anything about this video. Try time-range queries like *\"what happened from 0:30 to 1:00?\"* or *\"what's in the last 30 seconds?\"*"

export default function LumenChat({ videoId, onSeek }: LumenChatProps) {
  const [open,     setOpen]     = useState(false)
  const [messages, setMessages] = useState<Message[]>([{ role: 'assistant', content: WELCOME }])
  const [input,    setInput]    = useState('')
  const [sending,  setSending]  = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>(SUGGESTIONS)
  const bottomRef  = useRef<HTMLDivElement>(null)
  const inputRef   = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.getChatSuggestions(videoId).then((r) => setSuggestions(r.suggestions)).catch(() => {})
  }, [videoId])

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 200)
  }, [open])

  const send = async (text: string) => {
    if (!text.trim() || sending) return
    const userMsg: Message    = { role: 'user', content: text }
    const loadingMsg: Message = { role: 'assistant', content: '', loading: true }
    setMessages((prev) => [...prev, userMsg, loadingMsg])
    setInput('')
    setSending(true)

    const history: ChatMessage[] = messages
      .filter((m) => !m.loading && m.content)
      .slice(1).slice(-8)
      .map((m) => ({ role: m.role, content: m.content }))

    try {
      const res = await api.chat(videoId, text, history)
      setMessages((prev) => [
        ...prev.slice(0, -1),
        {
          role: 'assistant',
          content:  res.answer,
          sources:  res.sources,
          seekTo:   res.seek_to ?? undefined,
        },
      ])
    } catch {
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' },
      ])
    } finally {
      setSending(false)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }

  const showSuggestions = messages.filter((m) => m.role === 'user').length === 0

  return (
    <>
      {/* ── Desktop inline panel ── */}
      <div className="hidden xl:flex flex-col h-full rose-card overflow-hidden">
        <ChatHeader onMinimize={() => {}} showClose={false} />
        <ChatBody
          messages={messages}
          showSuggestions={showSuggestions}
          suggestions={suggestions}
          onSend={send}
          sending={sending}
          onSeek={onSeek}
          bottomRef={bottomRef}
          input={input}
          setInput={setInput}
          inputRef={inputRef}
        />
      </div>

      {/* ── Mobile: FAB + slide-up panel ── */}
      <div className="xl:hidden">
        <button
          onClick={() => setOpen(true)}
          className="lumen-fab fixed bottom-6 right-6 w-14 h-14 rounded-full flex items-center justify-center z-50"
          aria-label="Open Lumen chat"
          aria-expanded={open}
        >
          <Sparkles className="w-6 h-6 text-cream" aria-hidden />
        </button>

        <AnimatePresence>
          {open && (
            <>
              {/* Backdrop */}
              <motion.div
                className="fixed inset-0 bg-plum/25 z-40 backdrop-blur-sm"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setOpen(false)}
                aria-hidden="true"
              />
              {/* Panel */}
              <motion.div
                className="fixed bottom-0 left-0 right-0 z-50 rose-glass rounded-t-3xl border-t border-pink/40 flex flex-col"
                style={{ height: '80vh', maxHeight: 640 }}
                initial={{ y: '100%' }}
                animate={{ y: 0 }}
                exit={{ y: '100%' }}
                transition={{ type: 'spring', damping: 30, stiffness: 380 }}
                role="dialog"
                aria-label="Lumen chat"
                aria-modal="true"
              >
                <ChatHeader onMinimize={() => setOpen(false)} showClose={true} />
                <ChatBody
                  messages={messages}
                  showSuggestions={showSuggestions}
                  suggestions={suggestions}
                  onSend={send}
                  sending={sending}
                  onSeek={onSeek}
                  bottomRef={bottomRef}
                  input={input}
                  setInput={setInput}
                  inputRef={inputRef}
                />
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </div>
    </>
  )
}

// ── Sub-components ───────────────────────────────────────────────────────────

function ChatHeader({ onMinimize, showClose }: { onMinimize: () => void; showClose: boolean }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3.5 border-b border-pink/40 shrink-0">
      <div className="w-9 h-9 rounded-full bg-prune flex items-center justify-center shadow-button shrink-0">
        <Sparkles className="w-4 h-4 text-cream" aria-hidden />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-script text-lg text-prune leading-none">Lumen</p>
        <p className="text-xs text-plum-muted">AI Video Assistant</p>
      </div>
      <span className="text-xs bg-emerald-100 text-emerald-700 rounded-full px-2 py-0.5 font-medium">Online</span>
      {showClose && (
        <button
          onClick={onMinimize}
          className="ml-1 w-7 h-7 rounded-full bg-pink/50 flex items-center justify-center hover:bg-pink transition-colors"
          aria-label="Close chat"
        >
          <X className="w-3.5 h-3.5 text-plum" aria-hidden />
        </button>
      )}
    </div>
  )
}

interface ChatBodyProps {
  messages: Message[]
  showSuggestions: boolean
  suggestions: string[]
  onSend: (text: string) => void
  sending: boolean
  onSeek: (s: number) => void
  bottomRef: React.RefObject<HTMLDivElement>
  input: string
  setInput: (v: string) => void
  inputRef: React.RefObject<HTMLInputElement>
}

function ChatBody({ messages, showSuggestions, suggestions, onSend, sending, onSeek, bottomRef, input, setInput, inputRef }: ChatBodyProps) {
  return (
    <>
      {/* Messages */}
      <ScrollArea className="flex-1 px-4 py-3">
        <div className="space-y-4">
          <AnimatePresence initial={false}>
            {messages.map((msg, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className={`flex gap-2.5 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                {/* Avatar */}
                <div
                  className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-xs ${
                    msg.role === 'user' ? 'bg-prune' : 'bg-pink'
                  }`}
                  aria-hidden="true"
                >
                  {msg.role === 'user'
                    ? <User className="w-3.5 h-3.5 text-cream" />
                    : <Bot className="w-3.5 h-3.5 text-prune" />
                  }
                </div>

                {/* Bubble */}
                <div className={`flex flex-col gap-1.5 max-w-[85%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  <div
                    className={`rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-prune text-cream rounded-tr-sm'
                        : 'bg-cream border border-pink/50 text-plum rounded-tl-sm shadow-sm'
                    }`}
                  >
                    {msg.loading
                      ? (
                        <div className="flex items-center gap-1.5" aria-label="Thinking…">
                          {[0, 0.15, 0.3].map((d, i) => (
                            <motion.div
                              key={i}
                              className="w-1.5 h-1.5 rounded-full bg-prune/40"
                              animate={{ scale: [1, 1.4, 1], opacity: [0.5, 1, 0.5] }}
                              transition={{ duration: 0.8, delay: d, repeat: Infinity }}
                            />
                          ))}
                        </div>
                      )
                      : <BubbleText content={msg.content} />
                    }
                  </div>

                  {/* Sources */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {msg.sources.map((src, si) => (
                        <button
                          key={si}
                          onClick={() => onSeek(src.start)}
                          className="flex items-center gap-1 text-xs bg-pink/50 text-prune border border-pink/60 rounded-full px-2.5 py-1 hover:bg-pink transition-colors focus-visible:ring-2 focus-visible:ring-prune/30"
                          aria-label={`Jump to ${src.label}`}
                        >
                          <ChevronRight className="w-3 h-3" aria-hidden />
                          {src.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Suggestions */}
      {showSuggestions && (
        <div className="px-4 py-2 border-t border-pink/30">
          <div className="flex flex-wrap gap-1.5">
            {suggestions.slice(0, 4).map((s) => (
              <button
                key={s}
                onClick={() => onSend(s)}
                disabled={sending}
                className="text-xs bg-blush text-plum border border-pink/50 rounded-full px-3 py-1.5 hover:bg-pink/40 hover:border-prune/40 transition-colors disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <form
        onSubmit={(e) => { e.preventDefault(); onSend(input) }}
        className="flex gap-2 px-4 py-3 border-t border-pink/40 shrink-0"
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about any moment, topic or time…"
          disabled={sending}
          aria-label="Chat with Lumen"
          className="rose-input flex-1 px-3.5 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="w-9 h-9 rounded-xl bg-prune flex items-center justify-center shrink-0 hover:bg-prune-dark transition-colors disabled:opacity-40 focus-visible:ring-2 focus-visible:ring-prune/40"
          aria-label="Send message"
        >
          {sending
            ? <Loader2 className="w-4 h-4 text-cream animate-spin" aria-hidden />
            : <Send className="w-4 h-4 text-cream" aria-hidden />
          }
        </button>
      </form>
    </>
  )
}

/** Minimal inline markdown renderer for chat bubbles */
function BubbleText({ content }: { content: string }) {
  const parts = content.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g)
  return (
    <>
      {parts.map((p, i) => {
        if (p.startsWith('**') && p.endsWith('**')) return <strong key={i}>{p.slice(2,-2)}</strong>
        if (p.startsWith('*')  && p.endsWith('*'))  return <em key={i}>{p.slice(1,-1)}</em>
        return p.split('\n').map((line, j) => (
          <span key={`${i}-${j}`}>{j > 0 && <br />}{line}</span>
        ))
      })}
    </>
  )
}
