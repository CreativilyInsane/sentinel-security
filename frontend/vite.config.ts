// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: true,
    port: 5173,
    // Proxy /api/* to the local backend during development so the
    // frontend can talk to FastAPI on :8000 without CORS issues.
    // In production (Docker) nginx handles this routing instead.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // SSE / streaming — disable proxy buffering so streamed events
        // arrive immediately at the browser.
        ws: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            // Don't wait for the full response before forwarding chunks.
            proxyReq.setHeader('Connection', 'keep-alive');
          });
        },
      },
    },
  },
})