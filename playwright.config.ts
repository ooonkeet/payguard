import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/ui',
  timeout: 60000,
  expect: {
    timeout: 15000,
  },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'reports/playwright-report', open: 'never' }],
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command:
        process.platform === 'win32'
          ? '.venv\\Scripts\\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000'
          : 'uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: '.',
      env: { ...process.env, PYTHONPATH: 'backend' },
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: true,
      timeout: 30000,
    },
    {
      command: 'npm run preview -- --host 127.0.0.1 --port 5173 --strictPort',
      cwd: './frontend',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 30000,
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
