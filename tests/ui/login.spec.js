import { test, expect } from '@playwright/test';

// Login is the front door to Crush Cloud — every unauthenticated user lands
// here — so these checks treat it as a critical user journey. They run WITHOUT
// real credentials. The high-value, credential-free signals are:
//   1. the login surface renders,
//   2. the auth guard redirects protected routes here,
//   3. client-side username-format validation works, and
//   4. the auth backend is alive and correctly rejecting bad credentials.
//
// A real happy-path login is included but opt-in: it only runs when
// TEST_USER_USERNAME / TEST_USER_PASSWORD are supplied (e.g. via CI secrets).
// In CI those are wired per-environment, so it exercises only the environments
// that have credentials configured.

const USERNAME = 'input#username';
const PASSWORD = 'input#password';
const SUBMIT = 'button[type="submit"]';

test.describe('Login page', () => {
  test('renders the login form', async ({ page }) => {
    await page.goto('/login');

    await expect(page).toHaveTitle(/login/i);
    await expect(
      page.getByRole('heading', { name: /welcome to crush software/i })
    ).toBeVisible();
    await expect(page.locator(USERNAME)).toBeVisible();
    await expect(page.locator(PASSWORD)).toBeVisible();
    await expect(page.locator(SUBMIT)).toBeVisible();
    await expect(page.locator('a[href="/forgot-password"]')).toBeVisible();
  });

  test('redirects an unauthenticated user from a protected route to login', async ({ page }) => {
    await page.goto('/');

    await expect(page).toHaveURL(/\/login/);
    await expect(page.locator(USERNAME)).toBeVisible();
  });

  test('flags an email-format username client-side without calling the auth API', async ({ page }) => {
    // Crush login IDs are username@companycode, not email addresses. The form
    // should surface the format hint on the client and NOT hit /api/login.
    let loginPosted = false;
    page.on('request', (req) => {
      if (req.method() === 'POST' && req.url().includes('/api/login')) {
        loginPosted = true;
      }
    });

    await page.goto('/login');
    await page.fill(USERNAME, 'someone@example.com');
    await page.fill(PASSWORD, 'whatever');
    await page.click(SUBMIT);

    await expect(page.getByText(/username@companycode/i)).toBeVisible();
    expect(loginPosted, 'login API should not be called for a malformed username').toBe(false);
    await expect(page).toHaveURL(/\/login/);
  });

  test('rejects well-formed but invalid credentials via the auth backend', async ({ page }) => {
    // Well-formed but bogus credentials exercise the real auth path
    // (form -> POST /api/login -> error handling) and prove the login service
    // is alive and rejecting. No valid account required.
    await page.goto('/login');
    await page.fill(USERNAME, 'synthetic-monitor@crush');
    await page.fill(PASSWORD, 'definitely-not-the-password');

    const [loginResponse] = await Promise.all([
      page.waitForResponse(
        (res) => res.request().method() === 'POST' && res.url().includes('/api/login')
      ),
      page.click(SUBMIT),
    ]);

    const body = await loginResponse.text();
    expect(
      body,
      'auth backend should report an invalid-credentials event'
    ).toContain('invalid-user-or-password');

    // Still on the login page — not authenticated.
    await expect(page).toHaveURL(/\/login/);
  });

  test('a known user can log in and reach an authenticated surface', async ({ page, context }) => {
    const username = process.env.TEST_USER_USERNAME;
    const password = process.env.TEST_USER_PASSWORD;
    test.skip(!username || !password, 'TEST_USER_USERNAME / TEST_USER_PASSWORD not set');

    await page.goto('/login');
    await page.fill(USERNAME, username);
    await page.fill(PASSWORD, password);

    const [loginResponse] = await Promise.all([
      page.waitForResponse(
        (res) => res.request().method() === 'POST' && res.url().endsWith('/api/login')
      ),
      page.click(SUBMIT),
    ]);
    expect(loginResponse.status(), 'login should be accepted').toBe(200);

    // A successful login leaves the login route for the authenticated app and
    // surfaces the signed-in chrome.
    await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 15_000 });
    await expect(page.getByRole('button', { name: /user menu/i })).toBeVisible();

    // The session is established via a refresh-token cookie.
    const cookieNames = (await context.cookies()).map((c) => c.name);
    expect(cookieNames, 'a session cookie should be set').toContain('refresh_token');
  });
});
