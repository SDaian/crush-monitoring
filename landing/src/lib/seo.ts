/**
 * Meta-description composition.
 *
 * Google truncates the description it shows at roughly 155-160 characters on
 * desktop and ~120 on mobile. Anything past that is written for nobody. Several
 * of our descriptions interpolate data we do not control the length of (a
 * company name like "Taiwan Semiconductor Manufacturing Company Ltd.", a
 * member's full name), so "count it once and eyeball it" is not a guarantee —
 * a new data value can silently push a page over the line.
 *
 * `seoDescription` makes the limit structural: pass the sentence that must
 * survive first, then optional tail clauses. Each tail clause is appended only
 * if the whole string still fits, so the description degrades by dropping a
 * whole clause instead of being cut mid-word. The final clamp is a backstop for
 * the case where the required part alone is too long.
 *
 * Note this is about *presentation*, not ranking — meta descriptions are not a
 * ranking signal. A description that reads as a complete thought earns the
 * click; a truncated one loses it.
 */

/** Characters we allow. Under Google's desktop cut, comfortably over mobile's. */
export const DESC_MAX = 150;

const squash = (s: string) => s.replace(/\s+/g, " ").trim();

/** Hard cut at the last word boundary that leaves room for the ellipsis. */
function clamp(text: string, max: number): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max - 1);
  const space = cut.lastIndexOf(" ");
  return `${(space > max * 0.6 ? cut.slice(0, space) : cut).replace(/[\s,;:—-]+$/, "")}…`;
}

/**
 * Compose a description that is guaranteed to fit.
 *
 * @param required The core sentence — front-load the page's own numbers here.
 * @param optional Tail clauses, appended in order while they still fit.
 */
export function seoDescription(required: string, ...optional: string[]): string {
  let out = clamp(squash(required), DESC_MAX);
  for (const raw of optional) {
    const clause = squash(raw);
    if (!clause) continue;
    const next = `${out} ${clause}`;
    if (next.length <= DESC_MAX) out = next;
  }
  return out;
}

/**
 * Page titles.
 *
 * Google shows roughly 580px of a title — about 55-60 characters — and Bing
 * cuts sooner. 114 of 119 indexable titles once ran past that, the ticker ones
 * to 82, so the words that were cut were the ones that said what the page is.
 *
 * `seoTitle` takes candidates in order of preference and returns the first
 * that fits. Callers list the full form first and the brand-free, shorter
 * forms after it, so the brand suffix is the first thing given up and the
 * search term is the last. Google prints the site name separately above the
 * result, which is why the suffix is the cheapest thing to lose.
 */
export const TITLE_MAX = 60;
export const BRAND = "Capitol Ledger";

/** "…  · Capitol Ledger" — the suffix every page title uses. */
export const branded = (core: string) => `${squash(core)} · ${BRAND}`;

export function seoTitle(...candidates: string[]): string {
  const clean = candidates.map(squash).filter(Boolean);
  const fit = clean.find((c) => c.length <= TITLE_MAX);
  return fit ?? clamp(clean[clean.length - 1] ?? BRAND, TITLE_MAX);
}

/**
 * A company name short enough for a title: "Apple Inc." → "Apple",
 * "ASML Holding N.V. - New York Registry Shares" → "ASML". The filings carry
 * the legal name with share-class notes attached; a title wants the name a
 * person would search for. Anything still too long simply fails to fit, and
 * `seoTitle` falls through to the ticker-only candidate.
 */
export function shortCompany(name: string): string {
  let s = squash(name)
    .split(/ - | American Depositary| Common Stock| Class [A-Z]\b/i)[0]
    .trim();
  const tail =
    /[,\s]+(inc\.?|incorporated|corp\.?|corporation|company|co\.?|ltd\.?|limited|n\.v\.?|plc|s\.a\.?|holdings?|l\.p\.?)$/i;
  for (let prev = ""; prev !== s; ) {
    prev = s;
    s = s.replace(tail, "").trim();
  }
  return s.replace(/[,.]$/, "");
}

/** "1 trade" / "31 trades", with the count thousands-separated. */
export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
}

/**
 * Structured data: one entity graph.
 *
 * Every page used to describe the publisher as a bare {name: "Capitol
 * Ledger"}, and the WebSite node carried each page's own description — 119
 * different accounts of what "the site" is. Answer engines match entities by
 * name, and a namesake publication covers the same subject, so the graph now
 * gives the publisher one stable @id and every Dataset, page and breadcrumb
 * points at it. Keep in step with `site` in astro.config.mjs.
 */
export const SITE = "https://capitolledger.io";
export const ORG_ID = `${SITE}/#organization`;
export const WEBSITE_ID = `${SITE}/#website`;
/** The whole record — every disclosed trade — declared once, on /tracker. */
export const RECORD_ID = `${SITE}/tracker#dataset`;

/** An absolute URL for a site path. Schema consumers do not resolve relative ones. */
export const abs = (path: string) => new URL(path, SITE).href;

/** What every Dataset here shares: the publisher, the licence, and the
 *  record each one is a slice of. Page-specific fields spread on top. */
export function dataset(path: string, fields: Record<string, unknown>) {
  return {
    "@context": "https://schema.org",
    "@type": "Dataset",
    url: abs(path),
    creator: { "@id": ORG_ID },
    publisher: { "@id": ORG_ID },
    isAccessibleForFree: true,
    license: "https://www.usa.gov/government-works",
    inLanguage: "en",
    ...(path === "/tracker" ? {} : { isPartOf: { "@id": RECORD_ID } }),
    ...fields,
  };
}

/** A BreadcrumbList from [name, path] pairs, with absolute URLs. */
export function breadcrumbs(...trail: [string, string][]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: trail.map(([name, path], i) => ({
      "@type": "ListItem",
      position: i + 1,
      name,
      item: abs(path),
    })),
  };
}

/** FAQPage markup from the same list `Faq.astro` renders. */
export function faqSchema(items: { q: string; a: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: { "@type": "Answer", text: item.a },
    })),
  };
}
