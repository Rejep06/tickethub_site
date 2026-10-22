import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';
export default defineConfig({
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    esbuild: { jsx: 'automatic' },
    test: { environment: 'jsdom', include: ['tests/components/**/*.test.tsx'], setupFiles: ['tests/components/setup.tsx'], restoreMocks: true, clearMocks: true }
});
