import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full text-xs font-medium font-sans transition-colors',
  {
    variants: {
      variant: {
        default:  'bg-prune text-cream px-2.5 py-0.5',
        pink:     'bg-pink text-plum px-2.5 py-0.5 hover:bg-pink-dark',
        outline:  'border border-pink-dark/50 text-plum px-2.5 py-0.5',
        muted:    'bg-blush text-plum-muted px-2.5 py-0.5',
        success:  'bg-emerald-100 text-emerald-700 px-2.5 py-0.5',
        warning:  'bg-amber-100 text-amber-700 px-2.5 py-0.5',
        destructive: 'bg-red-100 text-red-700 px-2.5 py-0.5',
      },
    },
    defaultVariants: { variant: 'pink' },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
