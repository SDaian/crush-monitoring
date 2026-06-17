import { test } from '@playwright/test';
import { checkEndpoint } from '../../helpers/validator.js';

// API contract check.
//
// Crush Cloud has no public health endpoint, so we contract-check the one
// JSON API that answers without authentication: the token-refresh endpoint.
// The SPA itself calls GET /api/login/refresh on every unauthenticated load;
// it is *supposed* to return 401 with a structured error envelope. Validating
// that envelope confirms the login service is up and its error contract is
// intact, across dev/stg/prod, without sending any credentials.
//
// To add another endpoint check:
//   1. Save the expected shape as schemas/<name>.schema.json
//      (additionalProperties: false + required list).
//   2. Add a test below that calls checkEndpoint(request, '<path>', '<name>',
//      { expectStatus } if the contract is a non-2xx response).
test.describe('API contract checks', () => {
  test('GET /api/login/refresh returns the unauthorized error envelope', async ({ request }) => {
    await checkEndpoint(request, '/api/login/refresh', 'login-refresh', { expectStatus: 401 });
  });
});
