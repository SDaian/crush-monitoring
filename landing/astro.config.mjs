// @ts-check
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import sitemap from "@astrojs/sitemap";

// Static output (no server runtime) per the PRD; deployed on Vercel with
// this directory as the project root. Set `site` to the real domain before
// launch — the sitemap and canonical URLs derive from it.
export default defineConfig({
  output: "static",
  site: "https://capitolgains.example.com",
  integrations: [sitemap()],
  vite: { plugins: [tailwindcss()] },
});
