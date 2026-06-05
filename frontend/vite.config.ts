import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    // Split the 1.2 MB bundle into smaller cached chunks
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('@supabase'))         return 'supabase'
          if (id.includes('framer-motion'))     return 'framer'
          if (id.includes('recharts') || id.includes('d3-') || id.includes('victory'))
                                                return 'charts'
          if (id.includes('react-markdown') || id.includes('remark') || id.includes('micromark'))
                                                return 'markdown'
          if (id.includes('react-dom') || id.includes('react-router') || id.includes('scheduler'))
                                                return 'react-vendor'
          if (id.includes('lucide'))            return 'icons'
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p: string) => p.replace(/^\/api/, ''),
      },
      '/keyframes': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
