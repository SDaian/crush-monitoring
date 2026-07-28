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
| 1 — SQLite in the pipeline | Member/ticker pages or query-heavy generators | The Action loads trades into a local SQLite (stdlib `sqlite3`, keeps the offline-test dependency policy); generators become SQL; output stays the same small JSONs. No servers. DuckDB is the alternative if the queries turn analytical. | planned — **consciously deferred twice**: member pages shipped (2026-07-21) for 5 curated filers, and **ticker pages shipped (2026-07-24) for the top 24 symbols by disclosed trades** (`landing_data.select_ticker_pages`). Both slice the trades JSON in memory per build with no perf issue (~12.6k rows, 35 pages, <5s). The trigger fires when either scales to the full cross-product — *every* member (~535) or *every* ticker (~1,400) — where per-build JSON scans stop being cheap. |
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
| 1 — Web3Forms (contact) + Buttondown (signup/digest) | Launch | Free tiers, zero backend; contact key + signup endpoint set in Vercel env. | 🟡 contact live (Web3Forms, 2026-07-13); signup provider still pending — design below |
| 2 — Own function + Resend | Volume or customization outgrows the form vendor | A small Vercel serverless function emailing via Resend; same endpoint contract. | if needed |
| 3 — Supabase | User accounts exist (storage stage 2) | Contact messages and subscriptions become rows with auth context (support threads, per-user preferences). | with follows |

### Stage 1 design — trade-alert subscribe → daily digest (Buttondown)

Three pieces — capture, store, send. The report **content already exists**
(`daily_report.build_report` → HTML), so this is wiring, not new logic.

- **The constraint that drives the choice:** the site is **static** and cannot
  hold a secret API key in the browser. Buttondown exposes a **public
  form-submit endpoint** (no backend), so the existing FR-1 signup form POSTs
  straight to it. Resend would require a serverless function to protect the key
  — that's stage 2, adopted deliberately later.
- **Capture:** the signup form (FR-1: POST `email=` to
  `PUBLIC_SIGNUP_ENDPOINT`) points at Buttondown's subscribe endpoint.
- **Store:** the email lives in **Buttondown's managed subscriber list** —
  **never in git** (git is the public audit record; subscriber PII stays out of
  it — see the standing rule below). Buttondown handles **double opt-in**
  (GDPR), unsubscribe, and a hosted archive. A database only enters at stage 3
  (Supabase), when accounts/follows exist.
- **Send:** the daily Action reuses the digest HTML from `build_report` and
  makes **one API call** (`POST /v1/emails`, `BUTTONDOWN_API_KEY` secret) to
  broadcast it to all confirmed subscribers — one content source, no
  re-authoring in a GUI. **Gated + non-fatal** (key unset → skip, keeping
  today's owner-only email; same pattern as the analytics `VERCEL_TOKEN`) and
  **idempotent per day** via the existing `report_state.date`, so no
  double-sends. Unsubscribe/bounce/deliverability handled by Buttondown.
- **Cost:** free ≤100 subscribers, then ~$9/mo to 1,000. (Buttondown's
  transactional/API send is on the paid tier as of 2026-04.)
- **Pre-first-send checklist (compliance/deliverability):**
  1. Verify a **sending domain** (SPF/DKIM/DMARC) → `daily@capitolledger.io`.
  2. **Double opt-in** on (Buttondown default).
  3. **Physical mailing address** + unsubscribe link in the email footer
     (CAN-SPAM; Buttondown auto-adds unsubscribe).
  4. **Update `/privacy`** to name Buttondown as the processor **before**
     collecting real emails (standing rule below).
- **Scale trigger → stage 2 (Resend + one Vercel function):** past ~1k
  subscribers (cost), or when we want to fully own the HTML/personalization, or
  add per-member follows. Resend is priced **by contacts, not emails sent**, so
  a daily blast adds no per-send cost; free ≤1,000 contacts, then $40/mo to 5k.
  Same `PUBLIC_*_ENDPOINT` contract, so the page doesn't change.

## 3. Product

In rough priority order; each item states its blocking dependency.

- **Launch checklist** — the concrete pre-launch items live in
  `landing/README.md` (signup provider, Web3Forms key, register
  `capitolledger.io`, real domain in `astro.config.mjs`, trademark clearance,
  real contact address in `/privacy`, replace the placeholder testimonials).
- **Member pages (`/members/<slug>`)** — ✅ shipped 2026-07-21. The SEO play:
  "Nancy Pelosi stock trades" is where the search volume lives. Statically
  generated from the tracked data (`landing_data.member_payload` +
  `write_member_files` → `landing/src/data/members/*.json`; rendered by
  `landing/src/pages/members/[slug].astro` + a `/members` index). Live for the
  curated set — Pelosi, Trump, Greene, Tuberville, Gottheimer
  (`MEMBER_PAGE_NAMES`) — each showing their disclosed trades, most-traded
  tickers, filing timeliness and estimated holdings. Linked from the header
  nav, the footer sitemap, and the footer's named-member copy. Scaling this to
  *every* member is what fires storage stage 1 (see the storage table); the
  static-JSON approach is a conscious deferral, fine at 5 members.
- **Ticker pages** — ✅ shipped 2026-07-24 (`landing_data.ticker_payload` /
  `write_ticker_files` → `landing/src/data/tickers/*.json`; rendered by
  `landing/src/pages/tickers/[slug].astro` + a `/tickers` index). The organic
  search demand is on **entities, not dates** ("nvda congress trades"), so this
  — not a dated report archive — is the traffic play. The universe is picked by
  **substance each run**: the top `TICKER_PAGE_COUNT` symbols clearing
  `TICKER_PAGE_MIN_TRADES`, never the featured watchlist, because a pile of
  thin auto-generated pages is an SEO liability on a young domain (a featured
  name like NU with 4 disclosed trades would be a stub). Cross-linked with
  member pages both ways, and deep-linked from the daily email with UTM tags so
  Vercel analytics attributes the traffic. Scaling to all ~1,400 tickers fires
  storage stage 1.
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
- **Analytics**: Vercel Web Analytics is live (cookieless). ✅ Its public Web
  Analytics API now feeds a traffic block into the morning report
  (`congress/analytics.py`, gated on `VERCEL_TOKEN`). Evaluate Plausible if
  deeper funnels are needed while keeping the privacy page honest.
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
