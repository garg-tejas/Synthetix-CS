import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  // Backend origin used in connect-src. Falls back to localhost for dev.
  // In production set VITE_API_URL to your actual backend origin, e.g.
  //   VITE_API_URL=https://api.example.com
  const apiOrigin = (() => {
    const raw = env.VITE_API_URL || 'http://localhost:8000'
    try {
      return new URL(raw).origin
    } catch {
      return raw
    }
  })()

  return {
    plugins: [
      react(),
      // Inline plugin: replaces %VITE_API_URL% in index.html with the
      // resolved backend origin so connect-src is always correct, whether
      // the frontend and backend share an origin (reverse proxy) or not.
      {
        name: 'html-csp-inject',
        transformIndexHtml(html: string): string {
          return html.replace('%VITE_API_URL%', apiOrigin)
        },
      },
    ],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
        '/auth': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
