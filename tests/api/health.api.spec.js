import { test } from '@playwright/test';
import { checkEndpoint } from '../../helpers/validator.js';

// Example API check.
//
// Each test hits a REST endpoint and validates the JSON response against a
// saved schema in schemas/. The schema uses additionalProperties: false plus
// a "required" list, so this catches added, renamed, removed, and retyped
// fields — not just outright failures.
//
// To add a new endpoint check:
//   1. Save the expected shape as schemas/<name>.schema.json
//      (additionalProperties: false + required list).
//   2. Add a test below that calls checkEndpoint(request, '<path>', '<name>').
test.describe('API contract checks', () => {
  test('GET /api/health matches the health schema', async ({ request }) => {
    await checkEndpoint(request, '/api/health', 'health');
  });
});
