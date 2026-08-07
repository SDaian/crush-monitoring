// @ts-check
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import sitemap from "@astrojs/sitemap";
import tickerIndex from "./src/data/tickers/_index.json" with { type: "json" };
import { FontaineTransform } from "fontaine";

// @fontsource ships every @font-face with `font-display: swap`, which shows
// the fallback first and then visibly SWAPS to the webfont — a flash and a
// small reflow (the metric fallback can't match every weight's advance width
// exactly). Rewrite it to `optional`: with the preloads in FontPreloads.astro
// the real font is ready in the ~100ms block window on virtually every real
// connection (so it renders straight away, no swap); on a slow first load the
// metric-matched fallback simply stays for that page view — either way there
// is no swap flash and no layout shift.
const fontDisplayOptional = {
  name: "font-display-optional",
  // Rewrite in the final emitted CSS assets — Vite inlines @import-ed
  // @fontsource CSS outside per-file transform hooks, so patch the bundle.
  generateBundle(_options, bundle) {
    for (const file of Object.values(bundle)) {
      if (
        file.type === "asset" &&
        file.fileName.endsWith(".css") &&
        typeof file.source === "string" &&
        /font-display:\s*swap/i.test(file.source)
      ) {
        file.source = file.source.replace(
          /font-display:\s*swap/gi,
          "font-display:optional",
        );
      }
    }
  },
};

// Static output (no server runtime) per the PRD; deployed on Vercel with
// this directory as the project root. Set `site` to the real domain before
// launch — the sitemap and canonical URLs derive from it.
export default defineConfig({
  output: "static",
  site: "https://capitolledger.io",
  integrations: [
    // Strip the trailing slash so sitemap entries match the canonical URLs
    // Seo.astro emits (and the URLs used in the JSON-LD). A sitemap that
    // advertises /tickers/nvda/ while the page canonicalises to
    // /tickers/nvda still resolves, but it fills Search Console's Coverage
    // report with "alternate page with proper canonical tag" noise.
    sitemap({
      // Never advertise a page we tell robots to ignore — a sitemap entry
      // for a noindex URL is a contradictory signal in Search Console.
      // Two kinds are excluded: dated report permalinks (they canonicalise
      // to /report) and featured-watchlist ticker stubs below the
      // substance bar (they exist so an internal link resolves).
      filter: (page) => {
        const path = new URL(page).pathname.replace(/\/$/, "");
        if (/^\/report\/\d{4}-\d{2}-\d{2}$/.test(path)) return false;
        const slug = path.startsWith("/tickers/") ? path.slice(9) : null;
        if (slug) {
          const row = tickerIndex.tickers.find((t) => t.slug === slug);
          if (row && row.indexable === false) return false;
        }
        return true;
      },
      serialize: (item) => ({
        ...item,
        url: item.url.replace(/(?<!\/\/)\/$/, ""),
      }),
    }),
  ],
  vite: {
    plugins: [
      tailwindcss(),
      fontDisplayOptional,
      // Generates metric-compatible fallback @font-face rules (size-adjust,
      // ascent/descent overrides) so the swap from the fallback to the
      // webfont doesn't reflow the page. Paired with the font preloads in
      // FontPreloads.astro (see global.css --font-* stacks).
      FontaineTransform.vite({
        fallbacks: ["Arial", "Courier New"],
        resolvePath: (id) => new URL(`./node_modules/${id}`, import.meta.url),
      }),
    ],
  },
});
