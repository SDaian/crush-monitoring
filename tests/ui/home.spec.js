import { test, expect } from '@playwright/test';

// Home-page render check: the highest-value, lowest-cost UI signal.
// If this fails, the app is effectively down for users.
test.describe('Home page', () => {
  test('renders the landing page', async ({ page }) => {
    const response = await page.goto('/');

    expect(response, 'no response from home page').not.toBeNull();
    expect(
      response.status(),
      `home page returned ${response?.status()}`
    ).toBeLessThan(400);

    // The document should have a non-empty title and a rendered body.
    await expect(page).toHaveTitle(/.+/);
    await expect(page.locator('body')).toBeVisible();
  });
});
