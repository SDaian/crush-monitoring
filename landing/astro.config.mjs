// @ts-check
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import sitemap from "@astrojs/sitemap";
import { FontaineTransform } from "fontaine";

// Static output (no server runtime) per the PRD; deployed on Vercel with
// this directory as the project root. Set `site` to the real domain before
// launch — the sitemap and canonical URLs derive from it.
export default defineConfig({
  output: "static",
  site: "https://capitolledger.io",
  integrations: [sitemap()],
  vite: {
    plugins: [
      tailwindcss(),
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
