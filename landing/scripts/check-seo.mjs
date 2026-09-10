/**
 * Post-build SEO audit: report every built page whose <meta name="description">
 * would be truncated in search results, plus missing titles/descriptions.
 *
 * Most descriptions interpolate data (a company name, a member's name, a trade
 * count), so a page that fit yesterday can overflow tomorrow when the pipeline
 * refreshes. src/lib/seo.ts clamps at compose time; this is the check that the
 * clamp is actually being used everywhere.
 *
 * WARN, NEVER FAIL. A cosmetic overflow must not take the deploy down — the
 * lesson from the build-resilience fix: a hard failure over something that
 * affects nobody's ability to read the site is a worse outcome than the
 * overflow itself.
 */

import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const DIST = path.resolve(import.meta.dirname, "..", "dist");
const MAX = 150; // keep in sync with DESC_MAX in src/lib/seo.ts

async function pages(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await pages(full)));
    else if (entry.name.endsWith(".html")) out.push(full);
  }
  return out;
}

const attr = (html, re) => html.match(re)?.[1]?.trim() ?? "";
const decode = (s) =>
  s
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");

let files;
try {
  files = await pages(DIST);
} catch {
  console.warn("check-seo: no dist/ to audit — skipped.");
  process.exit(0);
}

const problems = [];
for (const file of files.sort()) {
  const html = await readFile(file, "utf8");
  const url = "/" + path.relative(DIST, file).replace(/(index)?\.html$/, "");
  const description = decode(
    attr(html, /<meta name="description" content="([^"]*)"/),
  );
  const title = decode(attr(html, /<title>([^<]*)<\/title>/));

  if (!title) problems.push(`${url} — missing <title>`);
  if (!description) problems.push(`${url} — missing meta description`);
  // Dated report permalinks must stay OUT of search indexes — /report is the
  // one indexable report URL (a year of near-duplicate dated pages is an SEO
  // liability). A dated page that loses its noindex is a real regression.
  if (/^\/report\/\d{4}-\d{2}-\d{2}\/$/.test(url) &&
      !/<meta name="robots" content="noindex/.test(html))
    problems.push(`${url} — dated report page is MISSING noindex`);
  else if (description.length > MAX)
    problems.push(
      `${url} — description is ${description.length} chars (max ${MAX}): ` +
        `"${description.slice(0, 60)}…"`,
    );

  // Structure, not metadata — but it regresses the same silent way. A page
  // without a skip link makes a keyboard visitor tab the whole nav before
  // the record they came for, and both defects below were found by audit,
  // not by anyone reading the page.
  if (!/class="skip-link/.test(html))
    problems.push(`${url} — missing skip link`);

  const levels = [...html.matchAll(/<h([1-6])[\s>]/g)].map((m) => +m[1]);
  const h1s = levels.filter((n) => n === 1).length;
  if (h1s !== 1) problems.push(`${url} — has ${h1s} <h1> (want exactly 1)`);
  for (let i = 1; i < levels.length; i++) {
    if (levels[i] > levels[i - 1] + 1) {
      problems.push(
        `${url} — heading jumps h${levels[i - 1]} to h${levels[i]}`,
      );
      break;
    }
  }
}

if (problems.length) {
  console.warn(
    `\ncheck-seo: ${problems.length} issue(s) across ${files.length} pages:`,
  );
  for (const p of problems) console.warn(`  ! ${p}`);
  console.warn("");
} else {
  console.log(
    `check-seo: ${files.length} pages — titled, within ${MAX} chars, ` +
      `one <h1>, ordered headings, skip link present.`,
  );
}
