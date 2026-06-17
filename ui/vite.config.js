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
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return null;
          if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('/react-router')) {
            return 'vendor-react';
          }
          if (id.includes('/react-markdown/')
            || id.includes('/remark-')
            || id.includes('/rehype-')
            || id.includes('/unified/')
            || id.includes('/micromark/')) {
            return 'vendor-markdown';
          }
          if (id.includes('/lucide-react/')) {
            return 'vendor-icons';
          }
          return 'vendor';
        },
      },
    },
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
