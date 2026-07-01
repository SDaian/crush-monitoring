import { test, expect } from '@playwright/test';
import { TARGET_ENV } from '../../config.js';

// Boot-time session refresh — per-environment rollout guard.
//
// Originally the SPA fired GET /api/login/refresh on every load, including
// anonymous ones with no token: a guaranteed 401, logged server-side at ERROR
// level (issue #2). The client fix stops firing that probe when there is no
// refresh-token cookie.
//
// The fix rolls out per environment. This map records where it has landed; flip
// an entry to `false` once the fix reaches that environment (its legacy probe
// stops firing on an anonymous load), then issue #2 point 2 can be closed.
//
//   true  = pre-fix:  still probes unconditionally on an anonymous load
//   false = fixed:    no probe when there is no token
const PROBES_WHEN_ANONYMOUS = {
  dev: false,
  stg: false,
  prod: true,
};

test.describe('Boot-time session refresh', () => {
  test(`unauthenticated load matches the no-token refresh rollout (${TARGET_ENV})`, async ({ page }) => {
    const refreshResponses = [];
    page.on('response', (res) => {
      if (res.url().includes('/api/login/refresh')) refreshResponses.push(res);
    });

    await page.goto('/login', { waitUntil: 'networkidle' });
    // Let any deferred boot XHR settle so an absent call is meaningful.
    await page.waitForTimeout(2000);

    if (PROBES_WHEN_ANONYMOUS[TARGET_ENV]) {
      // Pre-fix: the probe fires and 401s with the unauthorized envelope.
      const unauthorized = refreshResponses.find((res) => res.status() === 401);
      expect(unauthorized, 'expected the legacy boot-time refresh probe to 401').toBeTruthy();

      const body = await unauthorized.json();
      expect(body.event?.eventCode, 'refresh 401 should carry the unauthorized envelope').toBe(
        'unauthorized'
      );
    } else {
      // Post-fix: with no refresh token, the client must not probe at all.
      expect(
        refreshResponses.length,
        'no /api/login/refresh probe should fire on an anonymous load after the no-token fix'
      ).toBe(0);
    }
  });
});
