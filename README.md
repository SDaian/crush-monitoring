# crush-monitoring

Synthetic monitoring for Crush Software. Two layers run from a single
Playwright project:

- **API checks** (`tests/api/`) — hit REST endpoints and validate every JSON
  response against a saved JSON Schema in `schemas/`. Schemas use
  `additionalProperties: false` plus a `required` list, so they catch **added,
  renamed, removed, and retyped** fields, not just outright failures.
- **UI checks** (`tests/ui/`) — drive Chromium through critical journeys:
  landing-page render, a page-health check (no JS errors / no failed requests),
  the login surface (form render, auth-guard redirect, username-format
  validation, and an invalid-credentials rejection through the real auth
  backend), and the forgot-password page. An opt-in happy-path login runs when
  test credentials are supplied.

Stack: [Playwright](https://playwright.dev) + [Ajv](https://ajv.js.org),
ES modules, Node 20.

## Setup

```bash
npm install
npx playwright install --with-deps chromium
```

## Usage

Pick the target environment with `TARGET_ENV` (defaults to `dev`):

| `TARGET_ENV` | Base URL                       |
| ------------ | ------------------------------ |
| `dev`        | https://dev.crushsoftware.com  |
| `stg`        | https://stg.crushsoftware.com  |
| `prod`       | https://crush.crushsoftware.com |

```bash
# Everything against dev
npm test

# Just the API layer against staging
TARGET_ENV=stg npm run test:api

# Just the UI layer against prod
TARGET_ENV=prod npm run test:ui

# UI layer with a visible browser (debugging)
npm run test:headed

# Open the HTML report from the last run
npm run report
```

### Scripts

| Script              | Description                                  |
| ------------------- | -------------------------------------------- |
| `npm test`          | Run all checks (api + ui)                    |
| `npm run test:api`  | Run only the API project                     |
| `npm run test:ui`   | Run only the UI project                      |
| `npm run test:headed` | Run the UI project with a headed browser   |
| `npm run report`    | Open the last HTML report                    |

Reporters: `line` (console), `html` (`reports/html`), and `json`
(`results.json`). Traces, screenshots, and video are retained on failure.

## Adding an API endpoint check

1. Save the expected response shape as `schemas/<name>.schema.json`. Use
   `additionalProperties: false` and a `required` list covering every expected
   field so drift in any direction is caught.
2. Add a test in `tests/api/`:

   ```js
   import { test } from '@playwright/test';
   import { checkEndpoint } from '../../helpers/validator.js';

   test('GET /api/widgets matches the widgets schema', async ({ request }) => {
     await checkEndpoint(request, '/api/widgets', 'widgets');
   });
   ```

   `checkEndpoint` fetches the URL with Playwright's request context, asserts a
   2xx status, and validates the body against `schemas/widgets.schema.json`.
   For endpoints that contract on a non-2xx status (e.g. an endpoint that is
   supposed to `401`), pass `{ expectStatus: 401 }` — see
   `tests/api/login-refresh.api.spec.js`. `validateSchema(data, name)` is also
   exported for validating payloads you already have in hand.

## Adding a UI journey

1. Add a spec in `tests/ui/`. Keep journeys high-value — render checks,
   health checks, and authenticated flows that matter to users.
2. Prefer credential-free signals where possible — `tests/ui/login.spec.js`
   checks the login surface, the auth-guard redirect, client-side validation,
   and an invalid-credentials rejection through the real backend without any
   account. For an authenticated happy path, that same file has an opt-in test
   that runs only when credentials are supplied:

   ```bash
   # Crush login IDs are username@companycode, not email addresses.
   TEST_USER_USERNAME=...  TEST_USER_PASSWORD=...  TARGET_ENV=dev  npm run test:ui
   ```

## Network access (Claude Code on the web)

When running this suite from a Claude Code on the web cloud session, the
environment's **network egress allowlist** must permit the monitored hosts in
addition to the default trusted package registries (npm, etc. — needed for
`npm install` and the Playwright browser download).

Add the following to the environment's **Custom** allowed domains (configured
in the cloud environment UI under **Network access**, not in this repo):

| Domain                | Covers                                                        |
| --------------------- | ------------------------------------------------------------- |
| `*.crushsoftware.com` | `dev`, `stg`, and `prod` base URLs (see the `TARGET_ENV` table above) |

With **None** or default **Trusted** access the API and UI checks cannot reach
the target environments and will fail.

To verify the allowlist is in effect, probe all three base URLs:

```bash
npm run check:connectivity
```

It reports each host as reachable or blocked, and calls out an egress-proxy
denial (`host_not_allowed`) distinctly from the site being down. Exit code is
non-zero if any host is unreachable, so it doubles as a CI/setup gate.

The browser-based UI checks see the egress proxy's TLS-interception certificate
rather than the site's, so Chromium rejects it with `ERR_CERT_AUTHORITY_INVALID`
from a cloud session. To run the UI project locally from behind the proxy, set
`PLAYWRIGHT_IGNORE_HTTPS_ERRORS=1`:

```bash
PLAYWRIGHT_IGNORE_HTTPS_ERRORS=1 npm run test:ui
```

Leave it unset in CI — there is no intercepting proxy there, and certificate
validation is part of what monitoring should catch.

## Continuous monitoring (GitHub Actions)

Two workflows in `.github/workflows/` run on a schedule across all three
environments (`dev`, `stg`, `prod`) and can also be triggered manually via
**workflow_dispatch**:

- **`api-checks.yml`** — every 15 minutes. Slack alert on failure.
- **`ui-checks.yml`** — hourly. Uploads the Playwright HTML report as an
  artifact on failure, plus Slack alert on failure.

### Required secrets

| Secret                    | Used by         | Purpose                                         |
| ------------------------- | --------------- | ----------------------------------------------- |
| `SLACK_WEBHOOK_URL`       | both workflows  | Incoming webhook for failure alerts             |
| `TEST_USER_USERNAME_DEV`  | `ui-checks.yml` | Login ID (`username@companycode`) for **dev**   |
| `TEST_USER_PASSWORD_DEV`  | `ui-checks.yml` | Password for the **dev** login user             |
| `TEST_USER_USERNAME_STG`  | `ui-checks.yml` | Login ID for **stg**                            |
| `TEST_USER_PASSWORD_STG`  | `ui-checks.yml` | Password for the **stg** login user             |

The opt-in happy-path login test runs per environment: `ui-checks.yml` routes
the matching `*_DEV` / `*_STG` secret into `TEST_USER_USERNAME` /
`TEST_USER_PASSWORD` for that matrix leg, and the test skips wherever they are
empty. dev and stg are wired today; **prod** is intentionally not — add
`TEST_USER_USERNAME_PROD` / `TEST_USER_PASSWORD_PROD` and the corresponding
`matrix.env == 'prod'` branch in `ui-checks.yml` when a prod test account
exists. The credential-free login checks run on every environment regardless.

> Note: scheduled GitHub Actions only run from the repository's default
> branch.
