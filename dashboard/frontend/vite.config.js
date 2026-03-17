import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,  // Listen on 0.0.0.0 so accessible on intranet (e.g. http://<your-ip>:5173)
    proxy: {
      // In dev, /api/* is proxied to the backend so the same origin works from any device
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
