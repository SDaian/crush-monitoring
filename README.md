# crush-monitoring

Synthetic monitoring for Crush Software. Two layers run from a single
Playwright project:

- **API checks** (`tests/api/`) — hit REST endpoints and validate every JSON
  response against a saved JSON Schema in `schemas/`. Schemas use
  `additionalProperties: false` plus a `required` list, so they catch **added,
  renamed, removed, and retyped** fields, not just outright failures.
- **UI checks** (`tests/ui/`) — drive Chromium through critical journeys:
  home-page render, a no-console-errors / no-failed-requests health check, and
  a commented login-journey template.

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
   `validateSchema(data, name)` is also exported for validating payloads you
   already have in hand.

## Adding a UI journey

1. Add a spec in `tests/ui/`. Keep journeys high-value — render checks,
   health checks, and authenticated flows that matter to users.
2. For authenticated flows, see `tests/ui/login.spec.js`: it's a skipped
   template. Supply credentials via env vars / CI secrets, remove `.skip`, and
   adapt the selectors:

   ```bash
   TEST_USER_EMAIL=...  TEST_USER_PASSWORD=...  npm run test:ui
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

## Continuous monitoring (GitHub Actions)

> **Scheduled runs are currently PAUSED.** The `schedule` triggers in both
> workflows are commented out until `*.crushsoftware.com` is reachable from CI
> (see [Network access](#network-access-claude-code-on-the-web)). Re-enable by
> uncommenting the `schedule` block in each workflow. Manual
> **workflow_dispatch** runs still work in the meantime.

Two workflows in `.github/workflows/` run on a schedule across all three
environments (`dev`, `stg`, `prod`) and can also be triggered manually via
**workflow_dispatch**:

- **`api-checks.yml`** — every 15 minutes. Slack alert on failure.
- **`ui-checks.yml`** — hourly. Uploads the Playwright HTML report as an
  artifact on failure, plus Slack alert on failure.

### Required secrets

| Secret              | Used by              | Purpose                              |
| ------------------- | -------------------- | ------------------------------------ |
| `SLACK_WEBHOOK_URL` | both workflows       | Incoming webhook for failure alerts  |

For the login journey you'll also want `TEST_USER_EMAIL` and
`TEST_USER_PASSWORD` as secrets (and wired into the workflow `env`) once you
enable it.

> Note: scheduled GitHub Actions only run from the repository's default
> branch.
