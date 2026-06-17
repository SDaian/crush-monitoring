// Environment configuration for crush-monitoring.
// Select the target environment with the TARGET_ENV env var (defaults to "dev").
//
//   TARGET_ENV=stg npx playwright test
//
const ENVIRONMENTS = {
  dev: {
    name: 'dev',
    baseURL: 'https://dev.crushsoftware.com',
  },
  stg: {
    name: 'stg',
    baseURL: 'https://stg.crushsoftware.com',
  },
  prod: {
    name: 'prod',
    baseURL: 'https://crush.crushsoftware.com',
  },
};

const TARGET_ENV = process.env.TARGET_ENV || 'dev';

const config = ENVIRONMENTS[TARGET_ENV];

if (!config) {
  throw new Error(
    `Unknown TARGET_ENV "${TARGET_ENV}". Valid values: ${Object.keys(ENVIRONMENTS).join(', ')}`
  );
}

export { ENVIRONMENTS, TARGET_ENV };
export default config;
