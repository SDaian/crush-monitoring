// Lab performance check for the landing site: what a reader on a phone waits
// for. Run it by hand before and after a change that touches a page's markup,
// CSS or scripts:
//
//   cd landing && npm run build && cd ..
//   node scripts/perf_lab.mjs                      # every scenario, 3 runs
//   node scripts/perf_lab.mjs --only tracker       # pages and scenarios naming "tracker"
//   node scripts/perf_lab.mjs --save before.json   # keep the numbers...
//   node scripts/perf_lab.mjs --baseline before.json  # ...and compare later
//
// It serves landing/dist the way the CDN does (HTTP/2, brotli) and drives
// Chromium with Playwright on two profiles:
//
//   phone    412x823, CPU 4x slower than this machine. Loads on slow 4G
//            (Chrome's preset: 562.5 ms per request, 1.44 Mbps); interactions
//            on good 4G (150 ms, 9 Mbps), after the page has loaded.
//   desktop  1350x940, full-speed CPU, 40 ms and 10 Mbps.
//
// and reports the median of each measure against its budget:
//
//   LCP  phone, slow 4G, first visit   2,000 ms
//   CLS  phone and desktop             0.05
//   INP  typing, filters, sorts, tabs  200 ms
//        bulk actions ("Show all")     300 ms
//
// INP here is the slowest interaction in a scenario, from the browser's Event
// Timing entries (input to the next paint). The CPU slowdown is relative to
// the machine that runs the script, so compare runs made on one machine; the
// header prints a fixed loop's time to make a change of machine visible.
//
// check-performance.mjs (npm postbuild) guards sizes on every build. This
// script measures what a file check cannot see: rows a script builds, layout
// shift and interaction time. It is not in CI: shared runners vary too much
// for timing budgets, and a check that fails at random gets ignored.
//
// Three choices matter for honest numbers:
// - The server uses a throwaway certificate that Chromium trusts by its key.
//   With the certificate error merely ignored, Chromium keeps nothing in its
//   HTTP cache, which once made every repeat visit look like a first one.
// - HTTP/2, as production serves it: over HTTP/1.1 the six-connection limit
//   queues the font preloads behind the stylesheet.
// - The signup dialog is marked as already answered, so it can never cover
//   the button a scenario clicks.
//
// It exits 1 when any measure is over its budget, 2 when it cannot start.
// Set PW_CHROMIUM to a Chromium binary if Playwright's own is not installed.
import { chromium } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { X509Certificate, createHash } from "node:crypto";
import { existsSync, mkdtempSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import http2 from "node:http2";
import { tmpdir } from "node:os";
import path from "node:path";
import zlib from "node:zlib";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const DIST = path.join(ROOT, "landing", "dist");

const BUDGET = { lcp: 2000, cls: 0.05, input: 200, bulk: 300 };
const KBPS = 1024 / 8; // kbit/s to bytes/s, as Chrome's presets count
const NET = {
  slow4g: { latency: 562.5, downloadThroughput: 1474.56 * KBPS, uploadThroughput: 675 * KBPS },
  good4g: { latency: 150, downloadThroughput: 9000 * KBPS, uploadThroughput: 1500 * KBPS },
  desktop: { latency: 40, downloadThroughput: 10240 * KBPS, uploadThroughput: 10240 * KBPS },
};
const PHONE = {
  viewport: { width: 412, height: 823 }, deviceScaleFactor: 1.75, isMobile: true, hasTouch: true,
  userAgent: "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
};
const DESKTOP = { viewport: { width: 1350, height: 940 }, deviceScaleFactor: 1 };
const TYPE_DELAY = 150; // ms between keystrokes: a quick typist on a phone

// ── Options ───────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const opt = (name) => { const i = args.indexOf(name); return i === -1 ? null : args[i + 1]; };
const RUNS = Number(opt("--runs") ?? 3);
const ONLY = opt("--only");
const SAVE = opt("--save");
const BASELINE = opt("--baseline");
// A setup problem is the reader's to fix, so it gets one line, not a stack.
const fail = (message) => { console.error(`perf_lab: ${message}`); process.exit(2); };
if (!(RUNS >= 1)) fail("--runs takes a number of runs, 1 or more");
if (!existsSync(path.join(DIST, "index.html")))
  fail("no landing/dist: run `npm run build` in landing/ first");
if (BASELINE && !existsSync(BASELINE)) fail(`no baseline file at ${BASELINE}`);

// ── The pages ─────────────────────────────────────────────────────────────
// The longest member and ticker pages are the worst case for their template,
// and picking them from the build keeps the script right when the featured
// set changes.
function largest(section) {
  const dir = path.join(DIST, section);
  const sizes = readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isDirectory() && existsSync(path.join(dir, e.name, "index.html")))
    .map((e) => [statSync(path.join(dir, e.name, "index.html")).size, e.name])
    .sort((a, b) => b[0] - a[0]);
  return `/${section}/${sizes[0][1]}`;
}
const MEMBER = largest("members");
const TICKER = largest("tickers");
// Every stock page links to /tickers?industry=<key>, and a deep link can
// shift on its own: the other stocks must be hidden before the first paint,
// or the cards jump (up to 0.31 on a phone, Nov 2026). The industry with the
// fewest stocks hides the most of them.
function smallestIndustry() {
  const html = readFileSync(path.join(DIST, "tickers", "index.html"), "utf8");
  const sizes = [...html.matchAll(/<option value="([a-z][a-z0-9-]*)"[^>]*>([^<]*)<\/option>/g)]
    .map((m) => [Number(m[2].match(/\((\d+)\)\s*$/)?.[1]), m[1]])
    .filter(([n]) => n > 0)
    .sort((a, b) => a[0] - b[0] || a[1].localeCompare(b[1]));
  return sizes.length ? `/tickers?industry=${sizes[0][1]}` : null;
}
const LOAD_PAGES = ["/", "/tracker", "/tickers", smallestIndustry(), TICKER, MEMBER,
  "/what-congress-is-buying", "/report", "/late", "/how-it-works"].filter(Boolean);

// Each scenario returns after its last action; the slowest interaction in it
// is its value. `kind` picks the budget.
const SCENARIOS = [
  { name: "tracker: type in search", url: "/tracker", kind: "input", rows: true,
    run: async (p) => { await p.click("#q"); await p.keyboard.type("pelosi", { delay: TYPE_DELAY }); } },
  { name: "tracker: chamber filter", url: "/tracker", kind: "input", rows: true,
    run: async (p) => { await p.focus("#fChamber"); await p.keyboard.press("ArrowDown"); } },
  { name: "tracker: sort a column", url: "/tracker", kind: "input", rows: true,
    run: async (p) => { await p.click('th[data-k="amount_lo"]'); } },
  { name: "tracker: Show 200 more, three times", url: "/tracker", kind: "bulk", rows: true,
    run: async (p) => { for (let i = 0; i < 3; i++) { await p.click("#moreBtn"); await p.waitForTimeout(500); } } },
  { name: "tracker: Featured stocks tab", url: "/tracker", kind: "input", rows: true,
    run: async (p) => { await p.click("#tab-ai"); } },
  { name: "tracker: type while the data loads", url: "/tracker", kind: "input", early: true,
    run: async (p) => { await p.click("#q"); await p.keyboard.type("nvda", { delay: TYPE_DELAY }); } },
  { name: `${MEMBER}: type in the trade filter`, url: MEMBER, kind: "input",
    run: async (p) => { await p.click("#tfq"); await p.keyboard.type("nvda", { delay: TYPE_DELAY }); } },
  { name: `${MEMBER}: Buys/Sells filter`, url: MEMBER, kind: "input",
    run: async (p) => { await p.focus("#tfside"); await p.keyboard.press("ArrowDown"); } },
  { name: `${MEMBER}: Show all`, url: MEMBER, kind: "bulk",
    run: async (p) => { await p.click("#tfmore"); } },
  { name: "/tickers: type in the filter", url: "/tickers", kind: "input",
    run: async (p) => { await p.click("#tq"); await p.keyboard.type("nv", { delay: TYPE_DELAY }); } },
  { name: `${TICKER}: technicals tab`, url: TICKER, kind: "input",
    run: async (p) => { await p.click("#tab-tech"); } },
  { name: "/: open the menu", url: "/", kind: "input",
    run: async (p) => { await p.click(".menu-btn"); } },
];

// ── A local CDN ───────────────────────────────────────────────────────────
// A throwaway certificate, trusted by the hash of its public key.
function certificate() {
  const dir = mkdtempSync(path.join(tmpdir(), "perf-lab-"));
  const key = path.join(dir, "key.pem");
  const cert = path.join(dir, "cert.pem");
  try {
    execFileSync("openssl", ["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key,
      "-out", cert, "-days", "1", "-subj", "/CN=localhost"], { stdio: "ignore" });
  } catch {
    fail("needs `openssl` on the PATH to make its test certificate");
  }
  const pem = readFileSync(cert);
  const spki = new X509Certificate(pem).publicKey.export({ type: "spki", format: "der" });
  return { key: readFileSync(key), cert: pem, spki: createHash("sha256").update(spki).digest("base64") };
}

const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
  ".woff2": "font/woff2", ".woff": "font/woff", ".txt": "text/plain", ".xml": "application/xml",
};
const TEXT = new Set([".html", ".js", ".css", ".json", ".svg", ".txt", ".xml"]);

function serve(tls) {
  const files = new Map();
  const load = (file) => {
    if (!files.has(file)) {
      const raw = readFileSync(file);
      const ext = path.extname(file);
      files.set(file, { ext, raw, br: TEXT.has(ext)
        ? zlib.brotliCompressSync(raw, { params: { [zlib.constants.BROTLI_PARAM_QUALITY]: 5 } }) : null });
    }
    return files.get(file);
  };
  // Clean URLs, as the site is deployed: /tracker is tracker/index.html.
  const resolve = (url) => {
    const p = decodeURIComponent(url.split(/[?#]/)[0]);
    for (const f of [path.join(DIST, p), path.join(DIST, p, "index.html"), path.join(DIST, `${p}.html`)])
      if (f.startsWith(DIST) && existsSync(f) && statSync(f).isFile()) return f;
    return null;
  };
  const server = http2.createSecureServer({ ...tls, allowHTTP1: true }, (req, res) => {
    // Vercel injects its analytics script; it is not in dist.
    if (req.url.startsWith("/_vercel/")) {
      res.writeHead(200, { "content-type": "text/javascript" });
      return res.end("");
    }
    const found = resolve(req.url);
    const file = found ?? path.join(DIST, "404.html");
    const f = load(file);
    const br = f.br && /\bbr\b/.test(req.headers["accept-encoding"] ?? "");
    const body = br ? f.br : f.raw;
    res.writeHead(found ? 200 : 404, {
      "content-type": TYPES[f.ext] ?? "application/octet-stream",
      "cache-control": "public, max-age=0, must-revalidate",
      ...(br ? { "content-encoding": "br" } : {}),
      "content-length": body.length,
    });
    res.end(body);
  });
  return new Promise((ok) => server.listen(0, "127.0.0.1", () => ok(server)));
}

// ── Measuring ─────────────────────────────────────────────────────────────
// Observers installed before any page script runs. Event Timing groups the
// events of one interaction under one interactionId; its duration runs from
// the input to the next paint, which is what INP reports.
const OBSERVE = () => {
  try { localStorage.setItem("cl.signup", JSON.stringify({ state: "subscribed", at: Date.now() })); } catch {}
  const m = (window.__lab = { lcp: null, shifts: [], events: [], inputs: 0, rowsAt: null });
  const watch = (type, fn, extra = {}) => {
    try { new PerformanceObserver((l) => l.getEntries().forEach(fn)).observe({ type, buffered: true, ...extra }); } catch {}
  };
  watch("largest-contentful-paint", (e) => { m.lcp = e.startTime; });
  watch("layout-shift", (e) => { if (!e.hadRecentInput) m.shifts.push([e.startTime, e.value]); });
  watch("event", (e) => { if (e.interactionId) m.events.push([e.interactionId, e.duration]); }, { durationThreshold: 16 });
  for (const type of ["pointerdown", "keydown"]) addEventListener(type, () => { m.inputs++; }, true);
  // The tracker builds its table after the data arrives; a load is not done
  // until the rows are there.
  document.addEventListener("DOMContentLoaded", () => {
    const rows = document.getElementById("rows");
    if (rows) new MutationObserver(() => { if (rows.children.length && m.rowsAt == null) m.rowsAt = performance.now(); })
      .observe(rows, { childList: true });
  });
};

// CLS: the largest burst of shifts, each burst ending after a 1 s gap or 5 s.
function cls(shifts) {
  let best = 0, sum = 0, start = -Infinity, last = -Infinity;
  for (const [t, v] of shifts) {
    if (t - last > 1000 || t - start > 5000) { start = t; sum = 0; }
    sum += v; last = t; best = Math.max(best, sum);
  }
  return best;
}

async function open(browser, profile, net, cpu) {
  const context = await browser.newContext(profile);
  await context.addInitScript(OBSERVE);
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", { offline: false, ...net });
  if (cpu > 1) await cdp.send("Emulation.setCPUThrottlingRate", { rate: cpu });
  return { context, page };
}

const lab = (page) => page.evaluate(() => window.__lab);
const hasRows = (page) => page.evaluate(() => !!document.getElementById("rows"));
async function settle(page, ms) {
  if (await hasRows(page))
    await page.waitForFunction(() => window.__lab.rowsAt != null, null, { timeout: 120_000, polling: 250 });
  await page.waitForLoadState("networkidle", { timeout: 120_000 }).catch(() => {});
  await page.waitForTimeout(ms);
}

async function measureLoad(browser, site, url, profile, net, cpu) {
  const { context, page } = await open(browser, profile, net, cpu);
  try {
    await page.goto(site + url, { waitUntil: "load", timeout: 120_000 });
    await settle(page, 1500);
    const m = await lab(page);
    return { lcp: m.lcp, cls: cls(m.shifts) };
  } finally {
    await context.close();
  }
}

async function measureScenario(browser, site, s) {
  const { context, page } = await open(browser, PHONE, NET.good4g, 4);
  try {
    if (s.early) {
      await page.goto(site + s.url, { waitUntil: "domcontentloaded", timeout: 120_000 });
      await s.run(page);
      await settle(page, 1000);
    } else {
      await page.goto(site + s.url, { waitUntil: "load", timeout: 120_000 });
      await settle(page, 2000);
      await s.run(page);
      await page.waitForTimeout(1500);
    }
    const m = await lab(page);
    // A scenario whose input never reached the page measured nothing.
    if (!m.inputs) throw new Error("no input reached the page");
    const worst = new Map();
    for (const [id, d] of m.events) worst.set(id, Math.max(worst.get(id) ?? 0, d));
    // Entries start at 16 ms; an interaction under that reports none.
    return Math.max(0, ...worst.values());
  } finally {
    await context.close();
  }
}

// ── Running ───────────────────────────────────────────────────────────────
const median = (v) => { const s = [...v].sort((a, b) => a - b); const h = s.length >> 1; return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2; };
const fmt = (unit, v) => (v == null ? "—" : unit === "ms" ? `${Math.round(v).toLocaleString("en-US")} ms` : v.toFixed(3));

function hostLoop() {
  const t = performance.now();
  let x = 0;
  for (let i = 0; i < 2e8; i++) x += i % 7;
  return Math.round(performance.now() - t + (x < 0 ? 1 : 0));
}

async function main() {
  const tls = certificate();
  const server = await serve(tls);
  const site = `https://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({
    args: [`--ignore-certificate-errors-spki-list=${tls.spki}`],
    ...(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {}),
  });
  const wanted = (name) => !ONLY || name.includes(ONLY);
  const results = [];
  const record = (name, unit, budget, values, error) => {
    const r = { name, unit, budget, values, median: values.length ? median(values) : null, error };
    results.push(r);
    process.stderr.write(`  measured ${name}: ${error ?? values.map((v) => fmt(unit, v)).join(", ")}\n`);
  };

  let built = "";
  try { built = execFileSync("git", ["log", "-1", "--format=%h"], { cwd: ROOT, encoding: "utf8" }).trim(); } catch {}
  const header = `perf lab · commit ${built || "?"} · ${RUNS} run(s) · host loop ${hostLoop()} ms (lower is faster)`;
  process.stderr.write(`${header}\n`);

  try {
    for (const url of LOAD_PAGES) {
      if (!wanted(url)) continue;
      const phone = [], desk = [];
      let error;
      try {
        for (let i = 0; i < RUNS; i++) phone.push(await measureLoad(browser, site, url, PHONE, NET.slow4g, 4));
        for (let i = 0; i < RUNS; i++) desk.push(await measureLoad(browser, site, url, DESKTOP, NET.desktop, 1));
      } catch (e) { error = String(e.message).split("\n")[0]; }
      record(`LCP ${url} (phone, slow 4G)`, "ms", BUDGET.lcp, phone.map((r) => r.lcp).filter((v) => v != null), error);
      record(`CLS ${url} (phone)`, "", BUDGET.cls, phone.map((r) => r.cls), error);
      record(`CLS ${url} (desktop)`, "", BUDGET.cls, desk.map((r) => r.cls), error);
    }
    for (const s of SCENARIOS) {
      const name = `INP ${s.name}`;
      if (!wanted(s.name)) continue;
      const values = [];
      let error;
      try { for (let i = 0; i < RUNS; i++) values.push(await measureScenario(browser, site, s)); }
      catch (e) { error = String(e.message).split("\n")[0]; }
      record(name, "ms", BUDGET[s.kind], values, error);
    }
  } finally {
    await browser.close();
    server.close();
  }

  const before = BASELINE ? new Map(JSON.parse(readFileSync(BASELINE, "utf8")).results.map((r) => [r.name, r])) : null;
  const width = Math.max(...results.map((r) => r.name.length));
  const lines = [header, ""];
  let over = 0, failed = 0;
  for (const r of results) {
    const status = r.error ? `ERROR: ${r.error}` : r.median > r.budget ? "OVER" : "ok";
    if (r.error) failed++; else if (r.median > r.budget) over++;
    const was = before?.get(r.name);
    lines.push(`${r.name.padEnd(width)}  ${fmt(r.unit, r.median).padStart(9)}  budget ${fmt(r.unit, r.budget).padStart(8)}  ` +
      `${(was ? `was ${fmt(r.unit, was.median)}` : "").padEnd(14)}  ${status}`);
  }
  lines.push("", `${results.length} ${results.length === 1 ? "measure" : "measures"}: ${over} over budget, ${failed} could not run.`);
  console.log(lines.join("\n"));
  if (SAVE) writeFileSync(SAVE, JSON.stringify({ header, runs: RUNS, results }, null, 1));
  if (over || failed) process.exitCode = 1;
}

await main();
