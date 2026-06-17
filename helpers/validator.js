import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { expect } from '@playwright/test';

const __dirname = dirname(fileURLToPath(import.meta.url));
const schemasDir = resolve(__dirname, '..', 'schemas');

// Strict by default so the validator catches drift in either direction:
//   - added fields      -> rejected by additionalProperties: false
//   - removed fields    -> rejected by the schema's "required" list
//   - renamed fields    -> seen as one removed + one added field
//   - retyped fields    -> rejected by the property's "type"
const ajv = new Ajv({
  allErrors: true,
  strict: false,
});
addFormats(ajv);

// Cache compiled validators by schema file name.
const validators = new Map();

/**
 * Load and compile a JSON Schema stored in schemas/<name>.schema.json.
 * @param {string} name - schema file name without the ".schema.json" suffix.
 */
function getValidator(name) {
  if (validators.has(name)) {
    return validators.get(name);
  }
  const schemaPath = resolve(schemasDir, `${name}.schema.json`);
  const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'));
  const validate = ajv.compile(schema);
  validators.set(name, validate);
  return validate;
}

/**
 * Validate a data object against a saved schema and fail the test with a
 * readable message if it does not match.
 *
 * @param {object} data - the parsed JSON payload to validate.
 * @param {string} schemaName - schema file name without ".schema.json".
 */
export function validateSchema(data, schemaName) {
  const validate = getValidator(schemaName);
  const valid = validate(data);
  if (!valid) {
    const details = (validate.errors || [])
      .map((e) => `  - ${e.instancePath || '(root)'} ${e.message}` +
        (e.params ? ` ${JSON.stringify(e.params)}` : ''))
      .join('\n');
    throw new Error(
      `Response did not match schema "${schemaName}":\n${details}`
    );
  }
}

/**
 * Fetch a JSON endpoint with Playwright's request context, assert a 2xx
 * status, and validate the body against a saved schema.
 *
 * @param {import('@playwright/test').APIRequestContext} request
 * @param {string} url - absolute or baseURL-relative endpoint path.
 * @param {string} schemaName - schema file name without ".schema.json".
 * @returns {Promise<object>} the parsed JSON body.
 */
export async function checkEndpoint(request, url, schemaName) {
  const response = await request.get(url);
  expect(
    response.ok(),
    `Expected 2xx from ${url}, got ${response.status()}`
  ).toBeTruthy();

  const body = await response.json();
  validateSchema(body, schemaName);
  return body;
}
