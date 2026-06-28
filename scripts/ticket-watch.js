#!/usr/bin/env node
// Logged-out availability watcher for a FIFA World Cup 2026 resale page.
//
// What it does
//   - Loads ONE public ticketing URL in a headless browser (logged out).
//   - Renders the SPA, reads the visible text, and best-effort classifies it as
//     AVAILABLE / SOLD_OUT / UNKNOWN using keyword heuristics.
//   - Stores a content signature in a local state file and notifies you only
//     when the meaningful page content CHANGES (e.g. sold-out -> available).
//   - Notifies via the console always, plus Telegram and/or a generic webhook
//     if configured through environment variables.
//
// What it deliberately does NOT do
//   - It does NOT log in, use your account, add to cart, or attempt a purchase.
//     It only reads a public page. That keeps it lower-risk and ToS-friendlier;
//     automating a logged-in checkout is exactly what gets accounts banned.
//   - It does NOT hammer the site. Polling is low-frequency with jitter, and a
//     minimum interval is enforced.
//
// Why a browser (not fetch): the FIFA resale page is a client-rendered SPA, so a
// plain HTTP GET returns an empty shell. Playwright + Chromium are already part
// of this repo, so we render the page for real.
//
// Usage
//   node scripts/ticket-watch.js            # check once, print result, exit
//   node scripts/ticket-watch.js --watch    # keep checking on an interval
//   npm run watch:tickets -- --watch        # same, via npm
//
// Configuration (all via env vars; copy .env.example -> .env and edit):
//   TICKET_URL              the resale page to watch (defaults to the FWC26 URL)
//   TICKET_WATCH_SELECTOR   optional CSS selector to narrow what is hashed
//   CHECK_INTERVAL_MIN      minutes between checks in --watch mode (default 5)
//   TELEGRAM_BOT_TOKEN      Telegram bot token (optional notifier)
//   TELEGRAM_CHAT_ID        Telegram chat id to message (optional notifier)
//   TICKET_WATCH_WEBHOOK    generic webhook URL; receives {text} JSON (Discord/Slack/etc.)
//   PLAYWRIGHT_IGNORE_HTTPS_ERRORS=1   only behind a TLS-intercepting proxy
//
// Exit codes (single-run mode): 0 = checked OK, 2 = page blocked/unreachable.
import { chromium } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STATE_FILE = path.join(__dirname, '..', '.ticket-watch-state.json');

const DEFAULT_URL =
  'https://fwc26-shop-usd.tickets.fifa.com/secure/selection/event/seat/performance/10229226725341/table/1/lang/es';

const TICKET_URL = process.env.TICKET_URL || DEFAULT_URL;
const SELECTOR = process.env.TICKET_WATCH_SELECTOR || '';
const MIN_INTERVAL_MIN = 2; // politeness floor; do not poll faster than this.
const INTERVAL_MIN = Math.max(
  MIN_INTERVAL_MIN,
  Number(process.env.CHECK_INTERVAL_MIN || 5)
);
const NAV_TIMEOUT_MS = 45_000;

// A descriptive, honest User-Agent so we are not pretending to be something we
// are not. Includes a contact-ish identifier for the site operator.
const USER_AGENT =
  'crush-monitoring-ticket-watch/1.0 (personal availability notifier; logged-out; +https://github.com/sdaian/crush-monitoring)';

// Heuristic keyword sets (multilingual: the URL is /lang/es). These are
// best-effort signals only — the primary trigger is "the page changed", not the
// classification. Override behaviour by narrowing TICKET_WATCH_SELECTOR.
const SOLD_OUT_HINTS = [
  'agotado',
  'agotadas',
  'sin disponibilidad',
  'no hay disponibilidad',
  'no disponible',
  'no hay entradas',
  'sold out',
  'no tickets available',
  'not available',
  'currently unavailable',
];
const AVAILABLE_HINTS = [
  'comprar',
  'seleccionar',
  'selecciona',
  'añadir',
  'agregar',
  'disponible',
  'disponibles',
  'add to cart',
  'buy',
  'select',
  'available',
  'continue',
  'continuar',
];

/** Classify rendered page text into a coarse availability state. */
function classify(text) {
  const t = text.toLowerCase();
  const soldOut = SOLD_OUT_HINTS.some((k) => t.includes(k));
  const available = AVAILABLE_HINTS.some((k) => t.includes(k));
  // "Sold out" wording is a stronger negative signal than generic action words.
  if (soldOut && !available) return 'SOLD_OUT';
  if (available && !soldOut) return 'AVAILABLE';
  if (available && soldOut) return 'MIXED';
  return 'UNKNOWN';
}

/** Stable signature of the meaningful page content. */
function signature(text) {
  // Collapse whitespace and digits-that-are-just-timers/ids would add noise, but
  // we keep digits because price/seat counts are meaningful. Whitespace only.
  const normalized = text.replace(/\s+/g, ' ').trim();
  return createHash('sha256').update(normalized).digest('hex');
}

async function loadState() {
  try {
    return JSON.parse(await readFile(STATE_FILE, 'utf8'));
  } catch {
    return null;
  }
}

async function saveState(state) {
  await writeFile(STATE_FILE, JSON.stringify(state, null, 2) + '\n', 'utf8');
}

/**
 * Render the page once and return a reading.
 * @returns {Promise<{ok: boolean, state?: string, sig?: string, excerpt?: string, detail?: string}>}
 */
async function check() {
  // Normally Playwright finds its own Chromium (after `npx playwright install
  // chromium`). CHROMIUM_EXECUTABLE lets you point at a pre-installed browser
  // when the bundled build version does not match (e.g. some managed CI/cloud
  // images ship a fixed Chromium under a different build number).
  const executablePath = process.env.CHROMIUM_EXECUTABLE || undefined;
  const browser = await chromium.launch(executablePath ? { executablePath } : {});
  try {
    const context = await browser.newContext({
      userAgent: USER_AGENT,
      locale: 'es-ES',
      ignoreHTTPSErrors: process.env.PLAYWRIGHT_IGNORE_HTTPS_ERRORS === '1',
    });
    const page = await context.newPage();

    let response;
    try {
      response = await page.goto(TICKET_URL, {
        waitUntil: 'domcontentloaded',
        timeout: NAV_TIMEOUT_MS,
      });
    } catch (err) {
      // A tunnel/proxy connection failure usually means the host is not on the
      // network egress allowlist (e.g. a Claude Code on the web session), not
      // that FIFA is down. Call that out distinctly.
      const blocked = /ERR_TUNNEL_CONNECTION_FAILED|ERR_PROXY_CONNECTION_FAILED|ERR_SOCKS/.test(
        err.message
      );
      const hint = blocked
        ? ' — host likely not on the network egress allowlist; run the watcher from a machine that can reach FIFA directly'
        : '';
      return { ok: false, detail: `navigation failed (${err.message})${hint}` };
    }

    // Surface an egress-proxy denial as a config problem, not a site problem
    // (mirrors scripts/check-connectivity.js).
    const denyReason = response?.headers()?.['x-deny-reason'];
    if (denyReason) {
      return {
        ok: false,
        detail: `BLOCKED by egress proxy (${denyReason}) — this host must be on the network allowlist; run the watcher from a machine that can reach FIFA's site`,
      };
    }

    // Give the SPA a moment to hydrate, then read the (optionally scoped) text.
    await page.waitForLoadState('networkidle', { timeout: NAV_TIMEOUT_MS }).catch(() => {});
    let text;
    if (SELECTOR) {
      text = (await page.locator(SELECTOR).first().innerText().catch(() => '')) || '';
    }
    if (!text) {
      text = await page.evaluate(() => document.body?.innerText || '');
    }

    const status = response?.status() ?? 0;
    if (!text.trim()) {
      return { ok: false, detail: `empty render (HTTP ${status})` };
    }

    const excerpt = text.replace(/\s+/g, ' ').trim().slice(0, 400);
    return { ok: true, state: classify(text), sig: signature(text), excerpt, status };
  } finally {
    await browser.close();
  }
}

/** Send a notification to every configured channel. Console is always used. */
async function notify(title, body) {
  const line = `\n=== ${title} ===\n${body}\n`;
  console.log(line);

  const tasks = [];
  const { TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TICKET_WATCH_WEBHOOK } = process.env;
  if (TELEGRAM_BOT_TOKEN && TELEGRAM_CHAT_ID) {
    tasks.push(
      fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          chat_id: TELEGRAM_CHAT_ID,
          text: `${title}\n${body}`,
          disable_web_page_preview: false,
        }),
      }).catch((e) => console.error(`Telegram notify failed: ${e.message}`))
    );
  }
  if (TICKET_WATCH_WEBHOOK) {
    tasks.push(
      fetch(TICKET_WATCH_WEBHOOK, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        // `content` for Discord, `text` for Slack — send both keys.
        body: JSON.stringify({ text: `${title}\n${body}`, content: `${title}\n${body}` }),
      }).catch((e) => console.error(`Webhook notify failed: ${e.message}`))
    );
  }
  await Promise.all(tasks);
}

/** One full cycle: read page, compare to stored state, notify on change. */
async function runOnce() {
  const reading = await check();
  const stamp = new Date().toISOString();

  if (!reading.ok) {
    console.error(`[${stamp}] check failed: ${reading.detail}`);
    return { ok: false };
  }

  const prev = await loadState();
  const changed = !prev || prev.sig !== reading.sig;
  const becameAvailable =
    prev && prev.state !== 'AVAILABLE' && reading.state === 'AVAILABLE';

  console.log(
    `[${stamp}] state=${reading.state} changed=${changed} (HTTP ${reading.status})`
  );

  if (changed) {
    const title = becameAvailable
      ? '🎟️  Tickets may be AVAILABLE — check now'
      : `🔔 Ticket page changed (state: ${reading.state})`;
    const body =
      `URL: ${TICKET_URL}\n` +
      `When: ${stamp}\n` +
      `Detected state: ${reading.state}\n` +
      `Previous state: ${prev ? prev.state : '(first run)'}\n\n` +
      `Snippet: ${reading.excerpt}\n\n` +
      `Note: heuristic detection — open the page and confirm manually.`;
    await notify(title, body);
  }

  await saveState({
    sig: reading.sig,
    state: reading.state,
    checkedAt: stamp,
    url: TICKET_URL,
  });
  return { ok: true, state: reading.state };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const watch = process.argv.includes('--watch');
  console.log(`Ticket watcher — logged out, read-only.`);
  console.log(`URL: ${TICKET_URL}`);
  if (SELECTOR) console.log(`Scoped to selector: ${SELECTOR}`);

  if (!watch) {
    const res = await runOnce();
    process.exit(res.ok ? 0 : 2);
  }

  console.log(`Watch mode: every ~${INTERVAL_MIN} min (with jitter). Ctrl+C to stop.`);
  // eslint-disable-next-line no-constant-condition
  while (true) {
    try {
      await runOnce();
    } catch (err) {
      console.error(`cycle error: ${err.message}`);
    }
    // ±20% jitter so requests are not perfectly periodic.
    const base = INTERVAL_MIN * 60_000;
    const jitter = base * 0.2 * (Math.random() * 2 - 1);
    await sleep(Math.round(base + jitter));
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
