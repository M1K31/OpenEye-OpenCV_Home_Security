import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    // Unit tests only. Vitest's default include also matches e2e/*.spec.js,
    // which are Playwright tests — vitest cannot run them and each one failed
    // with "Playwright Test did not expect test.describe() to be called here".
    // Eight of the eleven reported failures were this, which left the suite
    // permanently red and therefore useless as a signal. Playwright specs run
    // under `npm run test:e2e`.
    include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}'],
    exclude: ['node_modules/**', 'dist/**', 'e2e/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.test.{js,jsx}',
        '**/*.spec.{js,jsx}',
        'dist/',
      ],
    },
  },
});
