# Capitol Ledger — landing page

Standalone marketing site for the politician-trades tracker: it converts
visitors into email subscribers for trade alerts. Astro (static, zero client
JS except the signup form and stats count-up scripts), Tailwind CSS v4 with
the design tokens in `src/styles/global.css` (`@theme`), self-hosted fonts.

Four pages, sharing `src/components/Header.astro` / `Footer.astro`:

- `/` — the conversion page (hero, live feed, stats, teaser, CTA).
- `/how-it-works` — the trust page: the full pipeline, the parsing tech and
  the AI role (honestly bounded: AI builds the parsers, deterministic code
  produces every published number), what the numbers mean, a sample email
  built from the same real `disclosures.json` the feed uses, and an FAQ.
- `/late` — the late-filers leaderboard: the year's worst filing delays
  from the generated `late.json` (one row per member — their worst filing —
  ranked by days past the 45-day maximum, plus their late-filing count).
- `/privacy` — privacy policy + terms in plain English (no cookies, no
  trackers, email only, GDPR rights); linked from the footer and the
  signup form's beta note.

**The visual identity and design system is `DESIGN.md`** — the design-agnostic
manual (brand essence, color/type/motion/voice rules, the component vocabulary,
accessibility/performance requirements) every page and future redesign must
follow. Read it before changing anything visual; update it in the same PR when
the system itself changes.

The approved prototype in `prototype/capitol-trades-landing.html` is the
visual source of truth, with four deliberate deviations agreed in the design
review (see `docs/adr/` and `CONTEXT.md`):

1. Feed header reads **"Recent disclosures"** — the rows are a curated
   window of real disclosures, not the literal five latest.
2. The **02 · Structure** and **03 · Signal** copy claims only what the
   product does (no committee assignments, no follows yet).
3. On mobile the **filed-late column stays visible**; only the amount hides
   (mobile-first audience must see the signature accusation).
4. Every rendered number is **real** — feed and stats come from
   `src/data/*.json`, generated daily from official filings.

## Data

`src/data/disclosures.json`, `src/data/stats.json` and `src/data/late.json`
are **generated — do not edit by hand**:

```bash
# from the repo root
python3 -m congress landing
```

The daily GitHub Action regenerates them after each trades refresh and
commits them with the trades; the push to `main` triggers Vercel's rebuild,
so the page tracks the data automatically. "Late" means past the STOCK
Act's **45-day statutory maximum** (`docs/adr/0002`).

## Develop

```bash
npm install
npm run dev        # local dev server
npm run build      # static build to dist/
npm run preview    # serve the build
```

## Environment

| Variable | Purpose |
|---|---|
| `PUBLIC_SIGNUP_ENDPOINT` | Signup provider endpoint the form POSTs `email=` to (form-encoded). **Unset** → submitting shows "Signups open soon" (pre-launch state). |
| `PUBLIC_CONTACT_ENDPOINT` | Contact-form endpoint (POSTs form-encoded `email`, `message`, `subject`). Web3Forms chosen at launch: `https://api.web3forms.com/submit`. **Unset** → "Contact opens soon". |
| `PUBLIC_CONTACT_KEY` | Sent as `access_key` with the contact POST when set (Web3Forms' auth shape). Public by design — it only routes submissions. |

## Deploy (Vercel)

1. Import the GitHub repo in Vercel; set the project's **Root Directory**
   to `landing/`. Framework preset: Astro (auto-detected).
2. Set `PUBLIC_SIGNUP_ENDPOINT` in the project's environment variables once
   a signup provider is chosen.
3. Update `site` in `astro.config.mjs` to the real domain (sitemap and
   canonical URLs derive from it).

Where the app goes after launch — storage stages, email tooling, member
pages, follows — is recorded in the repo-root [`ROADMAP.md`](../ROADMAP.md).

## Pre-launch checklist (open items from the design review)

- [ ] Choose the signup provider and set `PUBLIC_SIGNUP_ENDPOINT`
      (Buttondown suggested — it also sends the daily digest).
- [x] ~~Create a Web3Forms access key (free) and set
      `PUBLIC_CONTACT_ENDPOINT` + `PUBLIC_CONTACT_KEY` in Vercel~~ — done;
      contact form live and owner-tested (2026-07-13).
- [ ] Analytics decision (the ≥3% conversion goal is unmeasurable without).
- [ ] "Capitol Ledger" trademark/domain clearance vs. the "Capitol Trades"
      competitor.
- [ ] Set the real domain in `astro.config.mjs`.
- [ ] **Finish `/privacy` for launch:** name the chosen email provider in
      section 03 and add a real contact address (today the page says "reply
      to any email", which only works once emails exist).
- [ ] **Replace the placeholder testimonials.** The "What readers say"
      section ships with fictional reviews (marked in `src/pages/index.astro`)
      as a design stand-in. Swap them for real, permissioned user quotes —
      or remove the section — before launch; fabricated reviews presented as
      genuine on a live page would be deceptive (and illegal in several
      markets).
