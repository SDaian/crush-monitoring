/**
 * Post-build performance budgets: what each built page costs a phone before
 * any script runs.
 *
 * Every check here reads the files in dist/, so it catches growth in what we
 * ship: HTML, JS, CSS, font preloads, the tracker's data, and the number of
 * elements a browser must lay out for the first paint. The last one is the
 * budget that found the real problem: the longest member page painted 19,837
 * elements, all 1,711 disclosure rows, before its script folded the list
 * (members/[slug].astro now folds it at build time).
 *
 * What it cannot see, because no browser runs here: rows a script builds (the
 * tracker's table), layout shift, and how long an interaction takes. Those
 * need the phone checks CLAUDE.md describes.
 *
 * WARN, NEVER FAIL, for the same reason as check-seo.mjs: an over-budget page
 * is slower, not broken, and must not take the deploy down. The worst value of
 * each measure prints on every build, so drift shows in the log early.
 */

import { readdir, readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { gzipSync } from "node:zlib";

const DIST = path.resolve(import.meta.dirname, "..", "dist");

// Sizes are gzip (level 6), a conservative stand-in for what the CDN sends:
// brotli comes out smaller, so a page within these budgets is within them on
// the wire too.
const BUDGET = {
  // Elements laid out for the first paint. Past a few thousand, a phone
  // spends hundreds of milliseconds in style and layout before anything is
  // usable.
  painted: 3_000,
  // Every element in the HTML, painted or not: they are all parsed.
  elements: 25_000,
  html: 100 * 1024,
  js: 20 * 1024, // per page: bundles plus inline scripts
  css: 15 * 1024, // per page: stylesheets plus inline <style>
  fontPreloads: 6,
  fontPreloadBytes: 100 * 1024, // woff2 is compressed already: raw bytes
  // A script in <head> blocks parsing; the few there set a class on <html>.
  headInlineScript: 1024,
  // The three JSON files the tracker downloads on every first visit.
  trackerData: 600 * 1024,
};

// Rows hidden from the first paint by the head script's class (see the
// frontmatter of src/pages/members/[slug].astro). Keep the two in sync.
const FOLD_CLASS = "tfold";

const VOID = new Set(
  "area base br col embed hr img input link meta source track wbr".split(" "),
);
const gz = (buf) => gzipSync(buf, { level: 6 }).length;
const kb = (n) => `${Math.round(n / 1024)} KB`;
const num = (n) => n.toLocaleString("en-US");

async function pages(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await pages(full)));
    else if (entry.name.endsWith(".html")) out.push(full);
  }
  return out;
}

// Attribute names and values of one start tag. A plain substring test would
// read Tailwind's `hidden` class as the `hidden` attribute.
function attributes(source) {
  const out = new Map();
  for (const m of source.matchAll(
    /([^\s"'=<>/]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g,
  ))
    out.set(m[1].toLowerCase(), m[2] ?? m[3] ?? m[4] ?? "");
  return out;
}

// Counts the elements in the HTML, and the ones painted before any script
// runs: everything outside a `hidden` subtree and outside the folded rows.
// Elements hidden by a CSS breakpoint still count, so this errs high.
function elements(html) {
  const markup = html
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<(script|style|template)\b[^>]*>[\s\S]*?<\/\1>/gi, "");
  let total = 0;
  let painted = 0;
  let hiddenDepth = 0;
  const open = [];
  for (const m of markup.matchAll(/<(\/?)([a-zA-Z][\w:-]*)([^>]*)>/g)) {
    const [, closing, name, rest] = m;
    const tag = name.toLowerCase();
    if (closing) {
      const at = open.findLastIndex((e) => e.tag === tag);
      if (at === -1) continue; // a stray close tag closes nothing
      for (const e of open.splice(at)) if (e.hidden) hiddenDepth--;
      continue;
    }
    total++;
    const attrs = attributes(rest);
    const classes = (attrs.get("class") ?? "").split(/\s+/);
    const hidden = attrs.has("hidden") || classes.includes(FOLD_CLASS);
    if (!hiddenDepth && !hidden) painted++;
    if (VOID.has(tag) || rest.trimEnd().endsWith("/")) continue;
    if (hidden) hiddenDepth++;
    open.push({ tag, hidden });
  }
  return { total, painted };
}

const assetSizes = new Map();
async function assetGz(href) {
  if (!assetSizes.has(href)) {
    const file = path.join(DIST, href.split(/[?#]/)[0]);
    assetSizes.set(href, existsSync(file) ? gz(await readFile(file)) : 0);
  }
  return assetSizes.get(href);
}

const isRemote = (url) => /^(https?:)?\/\//.test(url);
const isData = (attrs) => /json/.test(attrs.get("type") ?? "");

let files;
try {
  files = (await pages(DIST)).sort();
} catch {
  console.warn("check-performance: no dist/ to audit — skipped.");
  process.exit(0);
}

const problems = [];
const worst = {};
const note = (measure, value, url) => {
  if (!worst[measure] || value > worst[measure].value)
    worst[measure] = { value, url };
};

for (const file of files) {
  const html = await readFile(file, "utf8");
  const url = "/" + path.relative(DIST, file).replace(/(index)?\.html$/, "");
  const headEnd = html.indexOf("</head>");
  const over = [];

  const htmlGz = gz(Buffer.from(html));
  const { total, painted } = elements(html);

  let js = 0;
  for (const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
    const attrs = attributes(m[1]);
    if (isData(attrs)) continue;
    const src = attrs.get("src");
    const inHead = headEnd !== -1 && m.index < headEnd;
    if (src && isRemote(src)) problems.push(`${url} — third-party script ${src}`);
    else if (src) js += await assetGz(src);
    else js += gz(Buffer.from(m[2]));
    if (inHead && src && !attrs.has("defer") && !attrs.has("async") && attrs.get("type") !== "module")
      problems.push(`${url} — render-blocking script in <head>: ${src}`);
    if (inHead && !src && m[2].length > BUDGET.headInlineScript)
      problems.push(
        `${url} — ${num(m[2].length)} B inline script in <head> (parsing waits for it; budget ${num(BUDGET.headInlineScript)} B)`,
      );
  }

  let css = 0;
  let preloads = 0;
  let preloadBytes = 0;
  for (const m of html.matchAll(/<link\b([^>]*)>/gi)) {
    const attrs = attributes(m[1]);
    const href = attrs.get("href") ?? "";
    const rel = attrs.get("rel") ?? "";
    if (rel === "stylesheet") {
      if (isRemote(href)) problems.push(`${url} — third-party stylesheet ${href}`);
      else css += await assetGz(href);
    }
    if (rel === "preload" && attrs.get("as") === "font") {
      preloads++;
      const font = path.join(DIST, href);
      if (existsSync(font)) preloadBytes += (await readFile(font)).length;
      else problems.push(`${url} — preloads ${href}, which does not exist`);
    }
  }
  for (const m of html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi))
    css += gz(Buffer.from(m[1]));

  // Media without both dimensions moves the text around it when it loads.
  for (const m of html.matchAll(/<(img|iframe|video)\b([^>]*)>/gi)) {
    const attrs = attributes(m[2]);
    if (!attrs.has("width") || !attrs.has("height"))
      problems.push(`${url} — <${m[1].toLowerCase()}> without width and height`);
  }

  if (painted > BUDGET.painted)
    over.push(`${num(painted)} elements painted before any script runs (budget ${num(BUDGET.painted)})`);
  if (total > BUDGET.elements)
    over.push(`${num(total)} elements in the HTML (budget ${num(BUDGET.elements)})`);
  if (htmlGz > BUDGET.html) over.push(`HTML ${kb(htmlGz)} (budget ${kb(BUDGET.html)})`);
  if (js > BUDGET.js) over.push(`JS ${kb(js)} (budget ${kb(BUDGET.js)})`);
  if (css > BUDGET.css) over.push(`CSS ${kb(css)} (budget ${kb(BUDGET.css)})`);
  if (preloads > BUDGET.fontPreloads || preloadBytes > BUDGET.fontPreloadBytes)
    over.push(
      `${preloads} font preloads, ${kb(preloadBytes)} (budget ${BUDGET.fontPreloads}, ${kb(BUDGET.fontPreloadBytes)})`,
    );
  if (over.length) problems.push(`${url} — ${over.join("; ")}`);

  note("painted", painted, url);
  note("html", htmlGz, url);
  note("js", js, url);
  note("css", css, url);
  note("fonts", preloadBytes, url);
}

let trackerData = 0;
const DATA = path.join(DIST, "data");
if (existsSync(DATA))
  for (const name of await readdir(DATA))
    if (name.endsWith(".json")) trackerData += gz(await readFile(path.join(DATA, name)));
if (trackerData > BUDGET.trackerData)
  problems.push(`/data — tracker data ${kb(trackerData)} (budget ${kb(BUDGET.trackerData)})`);

// vercel.json tells browsers to keep every /_astro file for a year without
// asking again. That is right only while each name carries a hash of its
// content, so a changed file gets a new name; a file without one would be
// stale for a year after its first change.
const ASSETS = path.join(DIST, "_astro");
if (existsSync(ASSETS))
  for (const name of await readdir(ASSETS))
    if (!/\.[\w-]{8,}\.\w+$/.test(name))
      problems.push(`/_astro/${name} — no content hash in the name, but vercel.json caches /_astro for a year`);

const summary =
  `worst: ${num(worst.painted.value)} elements painted (${worst.painted.url}), ` +
  `HTML ${kb(worst.html.value)} (${worst.html.url}), JS ${kb(worst.js.value)} (${worst.js.url}), ` +
  `CSS ${kb(worst.css.value)} (${worst.css.url}), font preloads ${kb(worst.fonts.value)}; ` +
  `tracker data ${kb(trackerData)}. Sizes are gzip.`;

if (problems.length) {
  console.warn(
    `\ncheck-performance: ${problems.length} issue(s) across ${files.length} pages:`,
  );
  for (const p of problems) console.warn(`  ! ${p}`);
  console.warn(`  ${summary}\n`);
} else {
  console.log(`check-performance: ${files.length} pages within budget — ${summary}`);
}
