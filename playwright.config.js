import { defineConfig, devices } from '@playwright/test';
import config from './config.js';

// Single Playwright config exposing two projects:
//   - api: REST endpoint + JSON Schema checks (no browser needed)
//   - ui:  Chromium-driven critical user journeys
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 1,
  workers: process.env.CI ? 2 : undefined,

  reporter: [
    ['line'],
    ['html', { outputFolder: 'reports/html', open: 'never' }],
    ['json', { outputFile: 'results.json' }],
  ],

  use: {
    baseURL: config.baseURL,
    // Certs are validated by default so a TLS problem on the real site fails
    // the check. Set PLAYWRIGHT_IGNORE_HTTPS_ERRORS=1 only to run locally from
    // behind a TLS-intercepting egress proxy (e.g. a Claude Code on the web
    // cloud session); leave it unset in CI.
    ignoreHTTPSErrors: process.env.PLAYWRIGHT_IGNORE_HTTPS_ERRORS === '1',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    extraHTTPHeaders: {
      Accept: 'application/json',
    },
  },

  outputDir: 'reports/results',

  projects: [
    {
      name: 'api',
      testDir: './tests/api',
      use: {
        // API checks only need the request context, not a browser.
        baseURL: config.baseURL,
      },
    },
    {
      name: 'ui',
      testDir: './tests/ui',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: config.baseURL,
      },
    },
  ],
});
