import { test, expect } from '@playwright/test';

// Password recovery is part of the auth surface users depend on when locked
// out. Credential-free checks: the page renders its form and is reachable from
// the login page.
test.describe('Forgot password page', () => {
  test('renders the recovery form', async ({ page }) => {
    await page.goto('/forgot-password');

    await expect(page).toHaveTitle(/forgot password/i);
    await expect(page.getByRole('heading', { name: /forgot password/i })).toBeVisible();
    await expect(page.locator('input#email')).toBeVisible();
    await expect(page.getByRole('button', { name: /send code/i })).toBeVisible();
  });

  test('is reachable from the login page', async ({ page }) => {
    await page.goto('/login');
    await page.click('a[href="/forgot-password"]');

    await expect(page).toHaveURL(/\/forgot-password/);
    await expect(page.getByRole('heading', { name: /forgot password/i })).toBeVisible();
  });
});
