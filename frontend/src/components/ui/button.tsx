import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  [
    'inline-flex items-center justify-center whitespace-nowrap rounded-xl',
    'text-sm font-medium font-sans',
    'transition-all duration-150 ease-out',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-prune/40 focus-visible:ring-offset-2 focus-visible:ring-offset-cream',
    'disabled:pointer-events-none disabled:opacity-40',
    'active:scale-[0.97]',
  ].join(' '),
  {
    variants: {
      variant: {
        default: [
          'bg-prune text-cream',
          'shadow-button hover:shadow-button-hover',
          'hover:bg-prune-dark hover:-translate-y-px',
        ].join(' '),
        outline: [
          'border border-pink-dark/60 bg-cream text-plum',
          'hover:bg-pink/30 hover:border-prune/40',
        ].join(' '),
        ghost: 'text-plum hover:bg-pink/40',
        secondary: 'bg-pink text-plum hover:bg-pink-dark',
        destructive: 'bg-red-500 text-white hover:bg-red-600 shadow-sm',
        link: 'text-prune underline-offset-4 hover:underline p-0 h-auto',
      },
      size: {
        sm:      'h-8 px-3 text-xs rounded-lg',
        default: 'h-10 px-5 py-2',
        lg:      'h-12 px-8 text-base rounded-xl',
        xl:      'h-14 px-10 text-base rounded-2xl',
        icon:    'h-10 w-10 rounded-xl',
        'icon-sm':'h-8 w-8 rounded-lg',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  },
)
Button.displayName = 'Button'

export { Button, buttonVariants }
