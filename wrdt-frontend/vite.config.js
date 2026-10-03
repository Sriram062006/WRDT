import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the UI calls the relative path /api/v1, proxied to the
// local FastAPI server so no CORS configuration is needed. In production
// either serve the built files from the same origin as the API (reverse
// proxy /api to the backend) or set VITE_API_BASE_URL at build time.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
