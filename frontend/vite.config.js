import { defineConfig } from 'vite';

// https://vite.dev/config/
export default defineConfig({
  base: '',
  server: {
    host: '127.0.0.1',
    port: 5173,
    hmr: false,
    proxy: {
      '/api': 'http://127.0.0.1:7860',
    },
  },
  build: {
    assetsDir: 'app-assets',
  },
  plugins: [],
  css: {
    postcss: './postcss.config.js',
  },
  resolve: {
    alias: {
      phaser: 'phaser/dist/phaser.js',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
    include: ['src/test/**/*.{test,spec}.ts'],
    testTimeout: 10000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
    },
  },
});
