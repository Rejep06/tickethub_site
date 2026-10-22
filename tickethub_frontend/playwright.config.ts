import { defineConfig, devices } from '@playwright/test';
/** Uses a running frontend + a disposable real Django database. Never a mock API. */
export default defineConfig({
    testDir: './tests/e2e', timeout: 180000, expect: { timeout: 15000 },
    fullyParallel: false, workers: 1, retries: 0,
    reporter: [['list'], ['html', { open: 'never' }]],
    use: { baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000', trace: 'off', screenshot: 'off', video: 'off' },
    projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }]
});
