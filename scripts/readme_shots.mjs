// Regenerate the README screenshots in .github/readme/ from real data.
//
//   cd landing && npm run build && cd ..
//   node scripts/readme_shots.mjs
//
// It serves landing/dist on a local port, renders the morning email from the
// committed data (congress.daily_report.build_report), and captures four
// JPEGs at quality 80: the home page, a member page's holdings, a ticker
// page's vote cards on a phone, and the email. Re-run it after a redesign —
// a README that shows last season's look misleads the reader.
//
// Set PW_CHROMIUM to a Chromium binary if Playwright's own is not installed.
import { chromium } from "@playwright/test";
import { spawn, execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const OUT = path.join(ROOT, ".github", "readme");
const PORT = 8799;
const SITE = `http://localhost:${PORT}`;
const JPEG = { type: "jpeg", quality: 80 };

// The email, rendered from the same payload the daily run sends. The
// "already reported" memory is seeded as on a first run, so the section
// shows the last week of disclosures rather than every one in 45 days.
function renderEmail() {
  const html = execFileSync("python3", ["-c", `
import json, sys
from congress import daily_report as dr
trades = json.load(open("docs/data/congress-trades.json"))["trades"]
ai = json.load(open("docs/data/ai-indicators.json"))
newest = max(t["filing_date"] for t in trades)
r = dr.build_report(trades, ai["tickers"], ai["meta"].get("new_signals", []), {},
                    newest, market_reading=ai.get("market"),
                    reported_ids=dr.seed_reported_ids(trades, newest))
sys.stdout.write(r["html"])
`], { cwd: ROOT, encoding: "utf8", maxBuffer: 1 << 26 });
  const file = path.join(mkdtempSync(path.join(tmpdir(), "readme-")), "email.html");
  writeFileSync(file, html);
  return file;
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const server = spawn("python3", ["-m", "http.server", String(PORT)], {
    cwd: path.join(ROOT, "landing", "dist"), stdio: "ignore",
  });
  await new Promise((r) => setTimeout(r, 800));
  const browser = await chromium.launch(
    process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {});
  try {
    const page = async (url, vp, dpr = 1) => {
      const p = await browser.newPage({ viewport: vp, deviceScaleFactor: dpr });
      await p.goto(url, { waitUntil: "networkidle" });
      // The read-triggered signup dialog never belongs in a screenshot.
      await p.addStyleTag({ content: "dialog { display: none !important; }" });
      return p;
    };

    let p = await page(`${SITE}/`, { width: 1280, height: 800 });
    await p.screenshot({ path: path.join(OUT, "home.jpg"), ...JPEG });
    await p.close();

    p = await page(`${SITE}/members/nancy-pelosi/`, { width: 1280, height: 800 });
    const top = await p.evaluate(() => {
      const h = [...document.querySelectorAll("h2")]
        .find((e) => /Estimated holdings/.test(e.textContent));
      return h.getBoundingClientRect().top + window.scrollY;
    });
    await p.screenshot({ path: path.join(OUT, "member.jpg"), fullPage: true,
      clip: { x: 0, y: top - 40, width: 1280, height: 760 }, ...JPEG });
    await p.close();

    p = await page(`${SITE}/tickers/nvda/#technical`, { width: 390, height: 844 }, 2);
    await p.evaluate(() => {
      const y = document.querySelector(".indcell").getBoundingClientRect().top;
      window.scrollTo(0, y + window.scrollY - 16);
    });
    await p.waitForTimeout(300);
    await p.screenshot({ path: path.join(OUT, "ticker-phone.jpg"), ...JPEG });
    await p.close();

    p = await page(`file://${renderEmail()}`, { width: 680, height: 1100 });
    await p.screenshot({ path: path.join(OUT, "email.jpg"), ...JPEG });
    await p.close();
  } finally {
    await browser.close();
    server.kill();
  }
  console.log(`wrote 4 screenshots to ${path.relative(ROOT, OUT)}/`);
}

main().catch((e) => { console.error(e); process.exit(1); });
