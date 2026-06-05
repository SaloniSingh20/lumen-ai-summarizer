/**
 * Fetches an image through the authenticated API (img elements can't send
 * Authorization headers) and renders it as a blob URL.
 * Shows a skeleton loader while fetching; fades in on load.
 */
import { useEffect, useState } from 'react'
import { tokenStore } from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface AuthedImageProps {
  src: string
  alt: string
  className?: string
  onError?: () => void
}

export default function AuthedImage({ src, alt, className, onError }: AuthedImageProps) {
  const [objectUrl, setObjectUrl] = useState<string>('')
  const [status, setStatus]       = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    let url = ''
    const token = tokenStore.get()

    fetch(`/api${src}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => {
        if (!r.ok) throw new Error('fetch failed')
        return r.blob()
      })
      .then((blob) => {
        url = URL.createObjectURL(blob)
        setObjectUrl(url)
        setStatus('ready')
      })
      .catch(() => {
        setStatus('error')
        onError?.()
      })

    return () => { if (url) URL.revokeObjectURL(url) }
  }, [src, onError])

  if (status === 'loading') return <Skeleton className={cn('w-full h-full', className)} />

  if (status === 'error') {
    return (
      <div
        className={cn('w-full h-full bg-pink/20 flex items-center justify-center', className)}
        role="img"
        aria-label={`${alt} — preview unavailable`}
      >
        <span className="text-xs text-plum-muted">No preview</span>
      </div>
    )
  }

  return (
    <img
      src={objectUrl}
      alt={alt}
      className={cn('transition-opacity duration-300', status === 'ready' ? 'opacity-100' : 'opacity-0', className)}
      loading="lazy"
    />
  )
}
