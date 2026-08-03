// Screenshot a social card: node scripts/render_card.mjs <card.html> <out.png>
// The HTML is produced by `python3 -m congress social` from
// congress/social/card_template.html; this script only renders it.
//
// Browser resolution, in order:
//   1. CARD_CHROMIUM env var (this sandbox: /opt/pw-browsers/chromium)
//   2. the "chrome" channel (GitHub Actions runners ship Google Chrome,
//      so CI needs no `playwright install` download)
// Renders the #card element at deviceScaleFactor 2 → 3200x1800 PNG
// (2x of 1600x900, the 16:9 X-timeline-safe ratio).
import { chromium } from "playwright";
import { pathToFileURL } from "node:url";

const [htmlPath, outPath] = process.argv.slice(2);
if (!htmlPath || !outPath) {
  console.error("usage: node scripts/render_card.mjs <card.html> <out.png>");
  process.exit(2);
}

const executablePath = process.env.CARD_CHROMIUM || undefined;
const browser = await chromium.launch(
  executablePath ? { executablePath } : { channel: "chrome" },
);
const page = await browser.newPage({
  viewport: { width: 1600, height: 900 },
  deviceScaleFactor: 2,
});
// goto(file://), not setContent(): about:blank blocks file:// subresources,
// which silently drops the @font-face fonts.
await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "networkidle" });
const card = await page.$("#card");
if (!card) {
  console.error(`no #card element in ${htmlPath}`);
  process.exit(1);
}
await card.screenshot({ path: outPath });
await browser.close();
console.log(`rendered ${outPath}`);
