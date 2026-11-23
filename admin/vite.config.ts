import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_BASE_URL || env.BOOKING_API_BASE_URL
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: target
        ? {
            '/api': {
              target: target.replace(/\/$/, ''),
              changeOrigin: true,
              rewrite: (path) => path.replace(/^\/api/, ''),
            },
          }
        : undefined,
    },
  }
})
