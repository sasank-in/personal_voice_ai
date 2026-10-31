import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Same-origin in the browser, so the session cookie and <audio src> just work.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
