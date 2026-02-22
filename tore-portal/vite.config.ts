import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/admin-api': {
        target: process.env.VITE_ADMIN_PROXY_TARGET || 'http://localhost:8787',
        changeOrigin: true,
      },
    },
  },
})
