// Copies the tracker's data files into the Astro static output.
//
// Single source of truth stays `docs/data/*.json` — the daily Action commits
// it there once. Copying at BUILD time (instead of committing a second copy
// under landing/public) keeps a 6 MB JSON out of git history twice a day.
// The copies are gitignored build artifacts.
//
// Fails loudly: a missing source file must break the build rather than ship a
// tracker that silently renders an empty table.
import { copyFile, mkdir, stat } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "..", "docs", "data");
const dest = join(here, "..", "public", "data");

// Only what the trimmed tracker actually reads. holdings.json is deliberately
// absent — the Holdings tab now lives on the member pages.
const FILES = [
  "congress-trades.json",
  "returns.json",
  "ai-indicators.json",
];

await mkdir(dest, { recursive: true });
let total = 0;
for (const name of FILES) {
  const from = join(src, name);
  const info = await stat(from).catch(() => null);
  if (!info) {
    console.error(
      `\n[copy-tracker-data] MISSING ${from}\n` +
        `The tracker cannot be built without it. Run \`python3 -m congress fetch\`\n` +
        `or restore docs/data from git.\n`,
    );
    process.exit(1);
  }
  await copyFile(from, join(dest, name));
  total += info.size;
  console.log(
    `[copy-tracker-data] ${name} (${(info.size / 1048576).toFixed(2)} MB)`,
  );
}
console.log(
  `[copy-tracker-data] ${FILES.length} files, ${(total / 1048576).toFixed(2)} MB → public/data`,
);
