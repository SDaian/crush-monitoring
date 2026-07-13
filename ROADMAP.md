# Roadmap — Capitol Ledger

The staged evolution of the app, as agreed in design discussions. Stages are
gated by **triggers, not dates**: each move happens when its trigger is real,
never before — premature infrastructure is how small products die. Keep this
file current when a stage ships or a decision changes.

## 1. Data storage

Guiding principle: **git + JSON is the canonical, auditable record** — every
published number traceable to a commit is part of the brand. Databases get
added *around* that record, never instead of it.

| Stage | Trigger | Move | Status |
|---|---|---|---|
| 0 — JSON in git | — (current) | Pipeline writes JSON, the daily Action commits it, static pages read it. Free audit log, zero infra. | ✅ live |
| 1 — SQLite in the pipeline | Member/ticker pages or query-heavy generators | The Action loads trades into a local SQLite (stdlib `sqlite3`, keeps the offline-test dependency policy); generators become SQL; output stays the same small JSONs. No servers. DuckDB is the alternative if the queries turn analytical. | planned |
| 2 — Serverless Postgres | User accounts / follows / per-user alerts | Neon, Supabase or Vercel Postgres for **user data only** (multi-writer, private — wrong fit for git). Supabase preferred: bundles auth + row-level security. The public trade record keeps publishing to git/JSON. | planned |

Scale reality check: congressional trading is tens of thousands of rows per
year. A single Postgres handles this product at any success level; free tiers
run out long before Postgres does. Turso (edge SQLite) and parquet-on-object-
storage with DuckDB were considered and parked as over-engineering here.

## 2. Contact & email handling

Guiding principle: **pages commit to a contract, not a vendor** — forms POST
form-encoded fields to a `PUBLIC_*_ENDPOINT` env var, so providers swap
without touching a page.

| Stage | Trigger | Move | Status |
|---|---|---|---|
| 0 — Endpoint unset | — | Forms show the "opens soon" pre-launch state. | ✅ live |
| 1 — Web3Forms (contact) + Buttondown (signup/digest) | Launch | Free tiers, zero backend; contact key + signup endpoint set in Vercel env. | pending setup |
| 2 — Own function + Resend | Volume or customization outgrows the form vendor | A small Vercel serverless function emailing via Resend; same endpoint contract. | if needed |
| 3 — Supabase | User accounts exist (storage stage 2) | Contact messages and subscriptions become rows with auth context (support threads, per-user preferences). | with follows |

## 3. Product

In rough priority order; each item states its blocking dependency.

- **Launch checklist** — the concrete pre-launch items live in
  `landing/README.md` (signup provider, Web3Forms key, register
  `capitolledger.io`, real domain in `astro.config.mjs`, trademark clearance,
  real contact address in `/privacy`, replace the placeholder testimonials).
- **Member pages (`/members/<name>`)** — the SEO play: "Nancy Pelosi stock
  trades" is where the search volume lives; the footer blurb holds those
  keywords today. Statically generated from the tracked data (this is the
  trigger for storage stage 1). Start with the featured members (Pelosi,
  Trump, Tuberville, Greene, Gottheimer).
- **Member and ticker follows** — already promised on the site ("Member and
  ticker follows are next"): per-user watchlists and filtered alerts. Requires
  accounts → triggers storage stage 2 (Supabase) and contact stage 3.
- **Ticker pages** — same machinery as member pages, second wave.
- **Feed curation preference** — surface featured members in the landing feed
  when present (owner request, parked during the design review).
- **Digest evolution** — once follows exist, the one-daily-email promise
  stays; the email personalizes (your follows first, then everything new).

## 4. Technologies to evaluate / discover

Not commitments — things to test when their stage approaches.

- **Storage**: DuckDB (analytical SQL over the trade history), Turso/libSQL
  (edge reads if latency ever matters), parquet snapshots for research use.
- **Email**: Resend (transactional), Buttondown vs. Loops vs. Listmonk
  (self-hosted) for the digest as subscriber count grows.
- **Auth**: Supabase Auth first; Clerk if auth UX needs outgrow it.
- **Search**: Pagefind (static, no server — fits the site) for member/ticker
  search before any database-backed search.
- **Analytics**: Vercel Web Analytics is live (cookieless); evaluate Plausible
  if deeper funnels are needed while keeping the privacy page honest.
- **Monitoring**: GitHub Actions already alerts on pipeline failure via the
  daily report; add uptime checks (e.g. UptimeRobot free) at launch.

## Standing rules

- **Collision check on every ship:** before merging a non-trivial change,
  check it against this file — does it ship a stage, fire a trigger, or
  collide with a stage or rule below? (Full checklist in `CLAUDE.md` →
  "Roadmap collision check".) Roadmap updates ride in the same PR.
- Every number on a public page must trace to an official filing (see
  `landing/docs/adr/0001`); no stage may break that.
- The privacy page is updated **before** any change to what is collected —
  new tools that touch visitor data (analytics, forms, auth) update
  `/privacy` in the same PR.
- Honest labelling everywhere: estimates marked as estimates, placeholders
  replaced before launch, no feature promised on the site before it's on
  this roadmap.
