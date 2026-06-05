/**
 * Decorative background orbs — pure CSS animations (GPU-only, zero JS overhead).
 * Framer Motion was causing continuous JS re-renders; replaced with CSS keyframes
 * defined in tailwind.config.js (orb-drift / orb-drift-alt).
 */

interface OrbBackgroundProps {
  className?: string
  variant?: 'hero' | 'processing' | 'subtle'
}

type OrbDef = { size: number; left: string; top: string; color: string; animation: string; delay: string }

const ORBS: Record<string, OrbDef[]> = {
  hero: [
    { size: 560, left: '75%', top: '-5%',  color: 'rgba(229,197,193,0.38)', animation: 'orb-drift',     delay: '0s'   },
    { size: 480, left: '-5%', top: '60%',  color: 'rgba(244,225,224,0.45)', animation: 'orb-drift-alt', delay: '2s'   },
    { size: 280, left: '55%', top: '80%',  color: 'rgba(127,98,105,0.09)',  animation: 'orb-drift',     delay: '4s'   },
  ],
  processing: [
    { size: 480, left: '50%', top: '40%',  color: 'rgba(229,197,193,0.35)', animation: 'orb-drift',     delay: '0s'   },
    { size: 300, left: '50%', top: '40%',  color: 'rgba(244,225,224,0.28)', animation: 'orb-drift-alt', delay: '1s'   },
  ],
  subtle: [
    { size: 500, left: '80%', top: '10%',  color: 'rgba(229,197,193,0.22)', animation: 'orb-drift-alt', delay: '0s'   },
    { size: 360, left: '5%',  top: '70%',  color: 'rgba(127,98,105,0.09)',  animation: 'orb-drift',     delay: '3s'   },
  ],
}

export default function OrbBackground({ className = '', variant = 'hero' }: OrbBackgroundProps) {
  const orbs = ORBS[variant] ?? ORBS.hero

  return (
    <div
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}
      aria-hidden="true"
    >
      {orbs.map((orb, i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            width:    orb.size,
            height:   orb.size,
            left:     `calc(${orb.left} - ${orb.size / 2}px)`,
            top:      `calc(${orb.top}  - ${orb.size / 2}px)`,
            background: orb.color,
            filter: 'blur(72px)',
            borderRadius: '9999px',
            animationName:           orb.animation,
            animationDuration:       i % 2 === 0 ? '14s' : '18s',
            animationDelay:          orb.delay,
            animationIterationCount: 'infinite',
            animationTimingFunction: 'ease-in-out',
            willChange: 'transform',
          }}
        />
      ))}
    </div>
  )
}
