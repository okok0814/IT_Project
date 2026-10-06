import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendTarget = process.env.BACKEND_URL || 'http://127.0.0.1:5000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': backendTarget,
      '/dataset2': backendTarget,
    },
  },
  preview: {
    proxy: {
      '/api': backendTarget,
      '/dataset2': backendTarget,
    },
  },
})
