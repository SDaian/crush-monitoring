import { test, expect } from '@playwright/test';

// Page-health check: load the home page and assert there were no console
// errors and no failed network requests. This catches broken bundles, dead
// API calls, and missing assets that a render check alone would miss.
test.describe('Page health', () => {
  test('home page has no console errors or failed requests', async ({ page }) => {
    const consoleErrors = [];
    const failedRequests = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    page.on('pageerror', (err) => {
      consoleErrors.push(`Uncaught: ${err.message}`);
    });

    page.on('requestfailed', (request) => {
      failedRequests.push(
        `${request.method()} ${request.url()} — ${request.failure()?.errorText ?? 'failed'}`
      );
    });

    page.on('response', (response) => {
      if (response.status() >= 400) {
        failedRequests.push(
          `${response.status()} ${response.request().method()} ${response.url()}`
        );
      }
    });

    await page.goto('/', { waitUntil: 'networkidle' });

    expect(
      consoleErrors,
      `console errors detected:\n${consoleErrors.join('\n')}`
    ).toEqual([]);
    expect(
      failedRequests,
      `failed requests detected:\n${failedRequests.join('\n')}`
    ).toEqual([]);
  });
});
