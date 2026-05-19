/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    css: true,
    include: ['src/**/*.test.{js,jsx}'],
    restoreMocks: true,
    setupFiles: ['./src/setupTests.js'],
    server: {
      deps: {
        inline: [/react-markdown/, /remark-/, /rehype-/, /unified/, /vfile/, /devlop/, /hast-/, /mdast-/, /micromark/, /bail/, /is-plain-obj/, /trough/, /zwitch/, /longest-streak/, /property-information/],
      },
    },
  },
})
