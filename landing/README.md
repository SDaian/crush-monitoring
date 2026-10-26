# landing/ — the Capitol Ledger site

The public site at [capitolledger.io](https://capitolledger.io): Astro,
static output, Tailwind CSS v4 with the design tokens in
`src/styles/global.css` (`@theme`), self-hosted fonts. Every number on it
comes from files the pipeline generates; none is typed by hand.

## Pages

| Path | What it shows |
|---|---|
| `/` | The signup page: the headline, recent disclosures, the year's stats. |
| `/tracker` | The whole record, searchable, plus the "Featured stocks" scorecard. Loads its data from `/data/*.json` at run time. |
| `/members`, `/members/<slug>` | One page per featured filer: trades grouped by month, estimated holdings, committee seats, performance against the S&P 500, timeliness. |
| `/tickers`, `/tickers/<symbol>` | One page per traded stock: who traded it, the trades, and a "Market & technicals" tab. |
| `/what-congress-is-buying` | The last 45 days of congressional buys, ranked by how many members bought. |
| `/late` | The year's worst filing delays. |
| `/report`, `/report/<date>`, `/report/archive` | The morning email on the web. Dated copies are `noindex`. |
| `/how-it-works`, `/roadmap`, `/privacy` | How the data is made, what comes next, and the privacy terms. |

Shared parts live in `src/components/`: `Header`, `Footer`, `Seo` (canonical,
Open Graph, JSON-LD), `SignupForm` and `SignupModal`, `Faq`,
`NewestFiling`, `MarketStrip`, `HoldingsChart`, `PerformanceChart`.

## Design

**[`DESIGN.md`](DESIGN.md) is the source of truth for the look**: color, type,
motion, voice, components, accessibility. Read it before a visual change, and
change it in the same PR when the system itself changes. The words the site
uses are defined in [`CONTEXT.md`](CONTEXT.md); decisions are recorded in
`docs/adr/`.

The prototype in `prototype/capitol-trades-landing.html` is the original
visual reference, with four agreed deviations. Do not "fix" them back:

1. The feed header reads **"Recent disclosures"**: the rows are a curated
   window of real disclosures, not the literal five latest.
2. The **02 · Structure** and **03 · Signal** copy claims only what the
   product does (no follows yet).
3. On mobile the **filed-late column stays visible**; only the amount hides.
4. Every rendered number is **real**, from `src/data/*.json`.

## Data

Everything in `src/data/` is **generated; do not edit it by hand**:

```bash
# from the repo root
python3 -m congress landing
```

That writes `disclosures.json`, `stats.json`, `late.json`, `buying.json`,
`market.json`, one file per member in `members/` and per ticker in
`tickers/` (each folder with an `_index.json`). `report.json` and `reports/`
come from the morning report. The daily Action commits them with the trades,
and the push to `main` makes Vercel rebuild.

The tracker's large data files stay in `docs/data/` and are copied into
`public/data/` at build time (`scripts/copy-tracker-data.mjs`, npm
`prebuild`); the copies are not committed.

## Develop

```bash
npm install
npm run dev        # local dev server
npm run build      # static build to dist/, then the post-build checks
npm run preview    # serve the build
```

`npm run build` ends with two checks that warn and never fail the build:
`scripts/check-seo.mjs` (title and description length, headings, canonical
tags, Open Graph cards) and `scripts/check-copy.mjs` (comments, emoji or
stacked dashes in the published HTML).

Before you ship a UI change, check it on a phone. Serve `dist/` with
`python3 -m http.server` and drive the page with Playwright at 320, 375 and
414 px: no sideways scroll, no element wider than its box, no clipped text.
`CLAUDE.md` explains why each of the three checks exists.

## Environment (Vercel project variables)

| Variable | Purpose |
|---|---|
| `PUBLIC_SIGNUP_ENDPOINT` | Where the forms POST `email=` (Buttondown's embed-subscribe URL). **Unset** → every form says "Signups open soon", the signup dialog is not rendered, and the build prints a warning. |
| `PUBLIC_CONTACT_ENDPOINT` | The contact form's endpoint (Web3Forms, `https://api.web3forms.com/submit`). **Unset** → "Contact opens soon". |
| `PUBLIC_CONTACT_KEY` | Sent as `access_key` with the contact POST. Public by design: it only routes messages. |

## Deploy (Vercel)

The Vercel project builds from `landing/` (Astro preset) on every push to
`main`. `capitolledger.io` is the primary domain; `www.capitolledger.io` and
the project's `vercel.app` domain redirect to it with a 308. `site` in
`astro.config.mjs` is the same host, so canonical tags, the sitemap and the
Open Graph URLs agree. Page traffic comes from Vercel Web Analytics, which is
cookieless.

`vercel.json` holds the ticker redirects (`/tickers/goog` → `/tickers/googl`,
`/tickers/fb` → `/tickers/meta`).

## Open items

- [ ] **Remove or replace the placeholder testimonials.** "What readers say"
      on the home page uses fictional reviews (marked in
      `src/pages/index.astro`). Fake reviews on a live page are deceptive,
      and illegal in several markets.
- [ ] "Capitol Ledger" trademark clearance against the "Capitol Trades"
      competitor.
- [ ] Check that replies to the morning email reach a monitored inbox:
      `/privacy` tells readers to reply to any email for data requests.

Where the product goes next (storage, email tooling, follows) is in the
repo-root [`ROADMAP.md`](../ROADMAP.md).
