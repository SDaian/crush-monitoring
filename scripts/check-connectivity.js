#!/usr/bin/env node
// Probe every monitored base URL and report whether it is reachable from the
// current network. Primarily a fast check that the egress allowlist permits
// *.crushsoftware.com — e.g. from a Claude Code on the web cloud session.
//
//   npm run check:connectivity          # probe all environments
//   node scripts/check-connectivity.js  # same
//
// Exit code 0 if every host is reachable (any HTTP response from the origin
// counts as reachable), non-zero if any host is blocked or unreachable.
import { ENVIRONMENTS } from '../config.js';

const TIMEOUT_MS = 15_000;

/**
 * Probe a single base URL.
 * @param {string} baseURL
 * @returns {Promise<{ok: boolean, detail: string}>}
 */
async function probe(baseURL) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(baseURL, {
      method: 'GET',
      redirect: 'manual',
      signal: controller.signal,
    });

    // The Claude Code on the web egress proxy denies disallowed hosts with a
    // 403 and an x-deny-reason header. Surface that as a config problem, not a
    // site problem.
    const denyReason = res.headers.get('x-deny-reason');
    if (denyReason) {
      return {
        ok: false,
        detail: `BLOCKED by egress proxy (${denyReason}) — add *.crushsoftware.com to the environment's network allowlist`,
      };
    }

    // Any genuine response from the origin means the host is reachable, even a
    // 4xx/5xx — that's the site answering, not the network blocking us.
    return { ok: true, detail: `reachable (HTTP ${res.status})` };
  } catch (err) {
    const reason = err.name === 'AbortError' ? `timed out after ${TIMEOUT_MS}ms` : err.message;
    return { ok: false, detail: `unreachable (${reason})` };
  } finally {
    clearTimeout(timer);
  }
}

const entries = Object.values(ENVIRONMENTS);
const results = await Promise.all(
  entries.map(async (env) => ({ env, ...(await probe(env.baseURL)) }))
);

let failed = 0;
for (const { env, ok, detail } of results) {
  const mark = ok ? '✓' : '✗';
  if (!ok) failed++;
  console.log(`${mark} ${env.name.padEnd(4)} ${env.baseURL.padEnd(34)} ${detail}`);
}

if (failed > 0) {
  console.error(`\n${failed} of ${results.length} host(s) not reachable.`);
  process.exit(1);
}
console.log(`\nAll ${results.length} hosts reachable.`);
