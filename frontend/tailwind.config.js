/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Fraunces', 'Georgia', '"Times New Roman"', 'serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
        script: ['Caveat', 'cursive'],
      },
      colors: {
        // Rose theme tokens
        blush:  '#F4E1E0',
        pink:   { DEFAULT: '#E5C5C1', light: '#EDD5D3', dark: '#D4A8A3' },
        prune:  { DEFAULT: '#7F6269', light: '#9A7A82', dark: '#6B5059', foreground: '#FFFBFA' },
        plum:   { DEFAULT: '#3E2E33', light: '#5A434A', muted: '#8C7178' },
        cream:  { DEFAULT: '#FFFBFA', dark: '#F5EFED' },
        // Shadcn compatibility via CSS variables
        border:      'hsl(var(--border))',
        input:       'hsl(var(--input))',
        ring:        'hsl(var(--ring))',
        background:  'hsl(var(--background))',
        foreground:  'hsl(var(--foreground))',
        primary:     { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        secondary:   { DEFAULT: 'hsl(var(--secondary))', foreground: 'hsl(var(--secondary-foreground))' },
        destructive: { DEFAULT: 'hsl(var(--destructive))', foreground: 'hsl(var(--destructive-foreground))' },
        muted:       { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        accent:      { DEFAULT: 'hsl(var(--accent))', foreground: 'hsl(var(--accent-foreground))' },
        card:        { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      boxShadow: {
        'card': '0 2px 16px 0 rgba(62,46,51,0.07), 0 1px 3px 0 rgba(62,46,51,0.05)',
        'card-hover': '0 8px 32px 0 rgba(62,46,51,0.12), 0 2px 8px 0 rgba(62,46,51,0.07)',
        'prune-sm': '0 0 0 2px rgba(127,98,105,0.25)',
        'prune-md': '0 0 0 3px rgba(127,98,105,0.3)',
        'button': '0 2px 8px rgba(127,98,105,0.25)',
        'button-hover': '0 4px 16px rgba(127,98,105,0.35)',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to:   { opacity: '1' },
        },
        'orb-drift': {
          '0%,100%': { transform: 'translate(0,0) scale(1)' },
          '33%':     { transform: 'translate(20px,-15px) scale(1.05)' },
          '66%':     { transform: 'translate(-12px,10px) scale(0.97)' },
        },
        'orb-drift-alt': {
          '0%,100%': { transform: 'translate(0,0) scale(1)' },
          '33%':     { transform: 'translate(-18px,12px) scale(1.04)' },
          '66%':     { transform: 'translate(14px,-8px) scale(0.98)' },
        },
        'pulse-glow': {
          '0%,100%': { boxShadow: '0 0 20px 4px rgba(127,98,105,0.25)', transform: 'scale(1)' },
          '50%':     { boxShadow: '0 0 40px 12px rgba(127,98,105,0.4)', transform: 'scale(1.06)' },
        },
        'shimmer': {
          from: { backgroundPosition: '-200% 0' },
          to:   { backgroundPosition: '200% 0' },
        },
        'accordion-down': {
          from: { height: '0' },
          to:   { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to:   { height: '0' },
        },
      },
      animation: {
        'fade-up':       'fade-up 0.4s ease-out both',
        'fade-in':       'fade-in 0.3s ease-out both',
        'orb-drift':     'orb-drift 12s ease-in-out infinite',
        'orb-drift-alt': 'orb-drift-alt 15s ease-in-out infinite',
        'pulse-glow':    'pulse-glow 2.5s ease-in-out infinite',
        'shimmer':       'shimmer 2s linear infinite',
        'accordion-down':'accordion-down 0.2s ease-out',
        'accordion-up':  'accordion-up 0.2s ease-out',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
}
