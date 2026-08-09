/**
 * Post-build copy audit: the tells that mark a page as machine-written.
 *
 * Three of them, in the order they matter:
 *
 *   1. HTML comments in the output. Authoring notes belong in the repo, not in
 *      View Source. `tests/congress/test_landing_source.py` already fails the
 *      suite on the cause (an `<!-- -->` in a .astro file); this catches any
 *      other route into the built HTML.
 *   2. Emoji in the visible copy. A ⭐ in a heading and a 🔎 on a tab read as
 *      filler; the type system already carries the emphasis.
 *   3. Em dashes stacked inside one paragraph. The dash itself is house voice
 *      (the prototype runs ~20 per 1,000 words), so page-level density is NOT
 *      the signal — a matched pair around a phrase is correct English. Three
 *      or more in one block is the tic.
 *
 * WARN, NEVER FAIL, for the same reason as check-seo.mjs: a cosmetic count
 * must not take the deploy down. The numbers print every build, so a drift
 * shows up in the log while it is still one page.
 */

import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const DIST = path.resolve(import.meta.dirname, "..", "dist");
// Pictographs only: the emoji planes, plus the handful of dingbats that read
// as emoji (⭐ ⚠ ✅ ❌ ‼). Everything else in those blocks is typography the
// design system uses on purpose — arrows (→ ↗), rating stars (★ ☆), the clear
// glyph (✕) — and a check that cries wolf on them gets ignored. Regional
// -indicator flags are excluded too: they name a person's country in the
// reviews block, which is content rather than interface chrome.
const EMOJI =
  /(?![\u{1F1E6}-\u{1F1FF}])[\u{1F300}-\u{1FAFF}]|[\u{2B50}\u{26A0}\u{2705}\u{274C}\u{2757}\u{203C}\u{2049}\u{2728}]/gu;
// A dash joining two words, i.e. prose — not the "—" we print for an empty cell.
const PROSE_DASH = /\w[,)"']?\s+—\s+\w/g;
const DASH_PER_BLOCK = 3;
// Phrases that read as generated. Keep this list short and specific: a lint
// nobody trusts gets ignored, and voice is DESIGN.md's job, not this file's.
const PHRASES = [
  "so you don't have to",
  "in today's fast-paced",
  "unlock the power",
  "dive in",
  "delve into",
  "seamless",
  "cutting-edge",
  "game-changer",
  "it's important to note",
  "when it comes to",
];

async function pages(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await pages(full)));
    else if (entry.name.endsWith(".html")) out.push(full);
  }
  return out;
}

const strip = (html) =>
  html
    .replace(/<(script|style)\b[\s\S]*?<\/\1>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ");

const files = await pages(DIST);
const comments = [];
const emoji = [];
const stacked = [];
const phrases = [];

for (const file of files) {
  const html = await readFile(file, "utf8");
  const rel = path.relative(DIST, file);

  const found = html.match(/<!--[\s\S]*?-->/g) ?? [];
  if (found.length) comments.push(`${rel} (${found.length})`);

  const text = strip(html.replace(/<!--[\s\S]*?-->/g, " "));
  const marks = text.match(EMOJI) ?? [];
  if (marks.length) emoji.push(`${rel}: ${[...new Set(marks)].join("")}`);

  for (const block of html.matchAll(/<(p|li|figcaption)\b[^>]*>([\s\S]*?)<\/\1>/g)) {
    const body = strip(block[2]);
    const n = (body.match(PROSE_DASH) ?? []).length;
    if (n >= DASH_PER_BLOCK) stacked.push(`${rel}: ${body.trim().slice(0, 70)}…`);
  }

  const lower = text.toLowerCase();
  for (const phrase of PHRASES) {
    if (lower.includes(phrase)) phrases.push(`${rel}: "${phrase}"`);
  }
}

const report = (label, rows) => {
  if (!rows.length) return 0;
  const shown = [...new Set(rows)].slice(0, 8);
  console.warn(`check-copy: ${label} (${rows.length})`);
  for (const row of shown) console.warn(`  ${row}`);
  if (rows.length > shown.length) {
    console.warn(`  …and ${rows.length - shown.length} more`);
  }
  return rows.length;
};

const total =
  report("HTML comments in the output", comments) +
  report("emoji in the visible copy", emoji) +
  report(`em dashes stacked ${DASH_PER_BLOCK}+ in one block`, stacked) +
  report("phrases that read as generated", phrases);

console.log(
  total === 0
    ? `check-copy: ${files.length} pages, no comments, emoji or stacked dashes.`
    : `check-copy: ${files.length} pages, ${total} issue(s) above (warning only).`,
);
