import { test, expect } from '@playwright/test';

// Regression guard for the boot-time silent session refresh.
//
// On an unauthenticated load the SPA fires GET /api/login/refresh to look for an
// existing session; with no session it returns 401. This test pins that known
// behavior so we are alerted if it changes — e.g. when the app stops firing the
// call unconditionally or stops logging it at ERROR level.
//
// See issue #2: the unauthenticated refresh is logged server-side at ERROR
// level and the client fires it even with no token. When that is fixed, the
// assertions below should be updated (and #2 closed).
test.describe('Boot-time session refresh', () => {
  test('unauthenticated load probes /api/login/refresh and gets a 401', async ({ page }) => {
    const refreshResponses = [];
    page.on('response', (res) => {
      if (res.url().includes('/api/login/refresh')) refreshResponses.push(res);
    });

    await page.goto('/login', { waitUntil: 'networkidle' });

    // The probe fires on an unauthenticated load (issue #2: it does so even with
    // no token). If a fix stops firing it, this drops to zero and the test trips.
    expect(
      refreshResponses.length,
      'expected a boot-time /api/login/refresh probe'
    ).toBeGreaterThanOrEqual(1);

    const unauthorized = refreshResponses.find((res) => res.status() === 401);
    expect(unauthorized, 'an unauthenticated refresh probe should 401').toBeTruthy();

    const body = await unauthorized.json();
    expect(body.event?.eventCode, 'refresh 401 should carry the unauthorized envelope').toBe(
      'unauthorized'
    );
    // Documents the known issue (#2): this expected probe is logged at ERROR
    // level. Flip this expectation once the app downgrades it to info/warn.
    expect(body.event?.logLevelName, 'see issue #2 — should be downgraded from error').toBe(
      'error'
    );
  });
});
