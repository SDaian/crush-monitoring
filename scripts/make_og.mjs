// Render one Open Graph card per ticker and member page:
//   node scripts/make_og.mjs [--force]
//
// Reads the generated page indexes, substitutes congress/social/og_template.html
// and writes landing/public/og/<kind>-<slug>.png (1200x630). Seo.astro points
// each page at its own file and falls back to /og.png.
//
// SKIPS a card that already exists, unless --force. That is the whole design:
// the card carries STABLE content (symbol, company, seat), never trade counts
// or prices, so a card only needs rendering when a page first appears. Put a
// number on it and the daily Action would rewrite ~120 binaries every morning.
//
// Browser resolution matches scripts/render_card.mjs:
//   1. CARD_CHROMIUM env var (this sandbox: /opt/pw-browsers/chromium)
//   2. the "chrome" channel (GitHub Actions runners ship Google Chrome)
import { chromium } from "playwright";
import { pathToFileURL } from "node:url";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const TEMPLATE = path.join(ROOT, "congress/social/og_template.html");
const OUT_DIR = path.join(ROOT, "landing/public/og");
const force = process.argv.includes("--force");

const read = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8"));

const PARTY = { D: "Democrat", R: "Republican", I: "Independent" };

// Fit the headline to its column. Libre Franklin 900 runs ~0.62em per
// character at these sizes, and the card's text column is 1072px wide.
function titlePx(text) {
  const fit = Math.floor(1072 / (text.length * 0.62));
  return Math.max(58, Math.min(148, fit));
}

function cards() {
  const out = [];
  for (const t of read("landing/src/data/tickers/_index.json").tickers ?? []) {
    out.push({
      file: `ticker-${t.slug}.png`,
      kicker: "Congressional trades",
      title: t.ticker,
      subtitle: t.company || t.ticker,
    });
  }
  for (const m of read("landing/src/data/members/_index.json").members ?? []) {
    // The seat line reads as it does on the page: party, then district for a
    // House member and state for a senator. An executive filer has neither.
    const party = PARTY[m.party] ?? m.party ?? "";
    const seat = m.chamber === "Executive"
      ? "Executive branch"
      : m.district || m.state || "";
    out.push({
      file: `member-${m.slug}.png`,
      kicker: "Disclosed trades",
      title: m.name,
      subtitle: [party, seat].filter(Boolean).join(" · "),
    });
  }
  return out;
}

const esc = (s) =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const template = fs.readFileSync(TEMPLATE, "utf8");
fs.mkdirSync(OUT_DIR, { recursive: true });

const all = cards();
const todo = force
  ? all
  : all.filter((c) => !fs.existsSync(path.join(OUT_DIR, c.file)));

if (!todo.length) {
  console.log(`make-og: ${all.length} cards, all present — nothing to render`);
  process.exit(0);
}

const executablePath = process.env.CARD_CHROMIUM || undefined;
const browser = await chromium.launch(
  executablePath ? { executablePath } : { channel: "chrome" },
);
const page = await browser.newPage({
  viewport: { width: 1200, height: 630 },
  deviceScaleFactor: 1,
});

// One temp file next to the template, so the relative font URLs resolve.
const tmp = path.join(path.dirname(TEMPLATE), ".og-render.html");
try {
  for (const c of todo) {
    const html = template
      .replace(/\{\{KICKER\}\}/g, esc(c.kicker))
      .replace(/\{\{TITLE\}\}/g, esc(c.title))
      .replace(/\{\{TITLE_PX\}\}/g, String(titlePx(c.title)))
      .replace(/\{\{SUBTITLE\}\}/g, esc(c.subtitle));
    fs.writeFileSync(tmp, html);
    // goto(file://), not setContent(): about:blank blocks file:// subresources,
    // which silently drops the @font-face fonts.
    await page.goto(pathToFileURL(tmp).href, { waitUntil: "networkidle" });
    const card = await page.$("#card");
    if (!card) throw new Error("no #card element in og_template.html");
    await card.screenshot({ path: path.join(OUT_DIR, c.file) });
  }
} finally {
  fs.rmSync(tmp, { force: true });
  await browser.close();
}

console.log(
  `make-og: rendered ${todo.length} of ${all.length} cards → landing/public/og/`,
);
