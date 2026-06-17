import { test, expect } from '@playwright/test';

// Page-health check: load the landing page and assert nothing is broken beneath
// the render — no uncaught JS exceptions, no failed asset/API requests. This
// catches broken bundles, dead endpoints, and missing assets that a render
// check alone would miss.
//
// We key off the two precise, URL-bearing signals — `pageerror` (uncaught
// exceptions) and responses/requests that fail — rather than console messages.
// Console "Failed to load resource" lines carry no URL, so they can't be told
// apart from expected noise; the request/response hooks below cover the same
// failures and can be filtered by URL.
//
// Some requests are expected to fail on an unauthenticated load and are not a
// health problem — the app probes for an existing session on startup, and that
// token refresh legitimately 401s when nobody is logged in.
const EXPECTED_FAILURES = [
  // Session probe on an unauthenticated load; a 401 is the correct response.
  /\/api\/login\/refresh\b/,
];

const isExpectedFailure = (url) => EXPECTED_FAILURES.some((re) => re.test(url));

test.describe('Page health', () => {
  test('landing page has no JS errors or unexpected failed requests', async ({ page }) => {
    const pageErrors = [];
    const failedRequests = [];

    page.on('pageerror', (err) => {
      pageErrors.push(`Uncaught: ${err.message}`);
    });

    page.on('requestfailed', (request) => {
      if (isExpectedFailure(request.url())) return;
      failedRequests.push(
        `${request.method()} ${request.url()} — ${request.failure()?.errorText ?? 'failed'}`
      );
    });

    page.on('response', (response) => {
      if (response.status() >= 400 && !isExpectedFailure(response.url())) {
        failedRequests.push(
          `${response.status()} ${response.request().method()} ${response.url()}`
        );
      }
    });

    await page.goto('/', { waitUntil: 'networkidle' });

    expect(
      pageErrors,
      `uncaught page errors detected:\n${pageErrors.join('\n')}`
    ).toEqual([]);
    expect(
      failedRequests,
      `failed requests detected:\n${failedRequests.join('\n')}`
    ).toEqual([]);
  });
});
