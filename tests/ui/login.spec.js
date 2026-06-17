import { test, expect } from '@playwright/test';

// Login journey TEMPLATE — intentionally skipped.
//
// Synthetic logins need real (test) credentials and a known-good account.
// Supply them via environment variables / CI secrets, then remove `.skip`
// and adapt the selectors below to the real login form.
//
//   TEST_USER_EMAIL=...  TEST_USER_PASSWORD=...  npx playwright test --project=ui
//
// Keep this to ONE high-value flow: can a known user authenticate and land
// on an authenticated surface? Don't turn it into a full UI regression suite.
test.describe('Login journey', () => {
  test.skip('a known user can log in and reach the dashboard', async ({ page }) => {
    const email = process.env.TEST_USER_EMAIL;
    const password = process.env.TEST_USER_PASSWORD;

    expect(email, 'TEST_USER_EMAIL is required').toBeTruthy();
    expect(password, 'TEST_USER_PASSWORD is required').toBeTruthy();

    await page.goto('/login');

    // Adapt these selectors to the real form.
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill(password);
    await page.getByRole('button', { name: /sign in|log in/i }).click();

    // Adapt this assertion to a real authenticated landing surface.
    await expect(page).toHaveURL(/dashboard/);
    await expect(page.getByRole('navigation')).toBeVisible();
  });
});
