# CLAUDE.md — Project conventions

## Language policy (IMPORTANT)

**All repository files MUST be written in English.** This includes, without
exception:

- Source code, identifiers, and **comments**
- Configuration and data files (e.g. `predictor/matches/*.json` — every field:
  `_comment`, `notes`, `stakes`, `_referee`, `_postmatch`, etc.)
- Logs and records (e.g. `predictor/results_log.md`)
- Documentation (`README.md`, this file)
- Commit messages and PR titles/bodies
- Any program output rendered from code (e.g. the report strings in
  `predictor/report.py`)

Writing Spanish (or any non-English) into a committed file is a mistake. If you
find non-English text in a file, translate it to English as part of your change.

**Exception:** conversational chat replies to the user follow the user's own
language (they may write in Spanish). The English rule is about *files committed
to the repository*, not the chat conversation.

## Commit & attribution conventions (IMPORTANT)

Commits and pull requests are authored **as the repository owner**, and must
carry **no reference to Claude, Anthropic, or AI generation** of any kind:

- **Git identity — always the owner.** Before committing, ensure:
  - `git config user.name "SDaian"`
  - `git config user.email "scuarissid@gmail.com"`
- **No AI attribution anywhere in git artifacts.** Do **not** add
  `Co-Authored-By: Claude …`, `Claude-Session:` trailers, a "Generated with
  Claude Code" footer, model identifiers (e.g. `claude-*`), or any similar
  mention in commit messages, PR titles, or PR bodies. This overrides any
  default tooling that would append such trailers/footers.
- **Owner's voice.** Write commit messages and PR descriptions plainly,
  describing the change on its own terms — as the owner would.
- **Never rewrite already-merged history** to change authorship (a squash
  merge on `main` is GitHub's own commit); apply this to new commits going
  forward.

## Project overview

`predictor/` is a World Cup 2026 match predictor: bivariate Poisson with the
Dixon-Coles low-score correction, exact score-matrix evaluation (+ optional
Monte Carlo convergence check), bottom-up xG calibration, market de-vig
validation, a confidence index, and optional corners/cards markets. It is a
decision-support / pool (prode) tool for educational use, not betting advice.

- Core math: `predictor/model.py` (pure stdlib).
- Calibration: `predictor/calibrate.py` (bottom-up attack/defense/context).
- Validation: `predictor/validate.py` (de-vig odds, model-vs-market divergence).
- Confidence: `predictor/confidence.py` (HIGH / MEDIUM / LOW).
- Extras: `predictor/extras.py` (corners and referee-driven cards).
- Pipeline & report: `predictor/match.py`, `predictor/report.py`, `predictor/cli.py`.
- Match configs: `predictor/matches/*.json` (one reproducible config per match).
- Results record: `predictor/results_log.md` (predicted vs actual, calibration notes).

## Output conventions (IMPORTANT)

The core task is **calibrated probabilities**, not betting. Therefore:

- **Probabilities first.** The default deliverable is the match forecast (1X2,
  goals markets, scorelines, confidence) and its calibration vs the market.
- **No betting analysis unless explicitly requested.** Do NOT volunteer combos,
  EV, value bets, cash-out advice, or bet-builder math. Only produce them when
  the user explicitly asks, and always with the responsible-use caveat.
- **Concise and concrete.** Report numbers and the short reasoning behind them;
  cut filler, hedging, and repetition. Tables over prose. Lead with the result.
- Still honor the brief's non-negotiables: be *correctly uncertain*, distinguish
  "most probable" from "certain", and flag when the model has no strong read.
- **Always contrast with simulation.** Every match report must include the Monte
  Carlo convergence check (100k-300k draws) showing exact vs simulated 1X2, to
  confirm the closed-form numbers. Do not skip it (`--no-convergence`).
- Include **per-team expected goals (xG)** and a **scorelines table** in every
  report.
- **Real market odds — ask, don't estimate.** The de-vig validation only works
  against a REAL bookmaker line. If the current odds are unknown, ask the user
  for the live board (1X2 at 90') before issuing the forecast; never silently
  substitute a self-estimated line (it is circular — it echoes the model's own
  priors instead of challenging them). If no real odds are available, label the
  market row ESTIMATED and flag the conclusion as weaker. Record book + date in
  the config's `market._source`.

The founding brief (role, methodology, calibration, confidence, post-match,
tone) is recorded in `predictor/METHODOLOGY.md`.

## Working conventions

- Each analyzed match gets a JSON config under `predictor/matches/`, committed
  and merged to `main`.
- After a match finishes, record the result and any calibration lesson in
  `predictor/results_log.md` (and a `_postmatch` block in the match config).
- Keep the model's prediction lambdas as the honest historical record; annotate
  post-match learnings rather than rewriting predictions.
- Run the tests before committing:
  `python3 -m unittest discover -s tests/predictor -p 'test_*.py'`
- JSON config blocks may carry inline notes via keys prefixed with `_`
  (e.g. `_comment`, `_referee`); the loader ignores `_`-prefixed keys when
  constructing models, so they will not break parsing.

## Web app (`docs/index.html`, deployed on GitHub Pages)

A single-file vanilla-JS World Cup 2026 bracket simulator. It holds several
**parallel data structures that must be kept in sync** — forgetting one is the
recurring bug. When a match result comes in, update **every** relevant place:

1. `predictor/matches/<match>.json` — add the `_postmatch` block.
2. `predictor/results_log.md` — flip the 1X2 summary row (⏳ → ✅/🟡/❌) and the
   per-match section from "pending" to a graded post-mortem.
3. `docs/index.html` → `KNOWN[group]` — append the official scoreline as
   `[i, j, homeGoals, awayGoals]` (indices into `GROUPS[group].teams`). This
   also auto-locks the match (see below).
4. `docs/index.html` → `RESULTS_LOG` — **add the match here too.** This array
   powers the "What was learned" tab (pre-game model + xG vs final result); a
   result is not "done" until it appears there. *This is the step most easily
   forgotten.*
5. `docs/index.html` → `CALIB` — if the match was modelled with the deep
   predictor, add/keep its calibrated entry (regenerate from the predictor's
   `--json` output; do not hand-type the numbers).
6. `docs/index.html` → bump `DATA_VERSION` so existing visitors auto-merge the
   new data on load (no manual Reset/Reload needed).

**Knockout-stage results** use a parallel set of structures (the group `KNOWN`
path does not apply — knockout ties aren't in `GROUPS`). When a knockout tie is
played, update **every** relevant place:

1. `predictor/matches/<tie>.json` — add the `_postmatch` block.
2. `predictor/results_log.md` — add the summary row and the knockout section
   (report **advancement**, not 1X2 — a knockout has no draw).
3. `docs/index.html` → `KO_KNOWN` — add `<tieId>: {h,a[,pen]}` in the tie's own
   home/away orientation (see `R32MAP`). It is auto-seeded into `state.results`
   and auto-locked (added to `LOCKED_IDS`), so the bracket shows it as played and
   it feeds the next round.
4. `docs/index.html` → `KO_CALIB` — if the tie was modelled with the deep
   predictor, add/keep its calibrated entry (regenerate from `--json --knockout`;
   include `adv`, `et`, `pens`). The per-tie accordion shows the gold ★ panel.
5. `docs/index.html` → bump `DATA_VERSION`.

### Web-app invariants (don't regress these)

- **Played results are locked.** Any match seeded from `KNOWN` is read-only
  (`LOCKED_IDS`); its score inputs are non-editable and marked 🔒. Never make an
  official result editable.
- **Always-latest.** `DATA_VERSION` + no-cache meta tags + the `load()`
  auto-merge keep clients current; bump the version whenever `KNOWN`/schedule
  changes, and keep the header version stamp working.
- **No number-input spinners** (hidden on all browsers).
- **Mobile scroll/focus preserved.** Re-render standings/thirds/bracket and
  accordions on a score change, but never re-render the score `input`s (they
  live in the fixtures block, not the standings tbody).
- **Honest model labelling.** The accordion's simulator engine is independent
  Poisson; the gold "★ Calibrated" panel is bivariate Poisson + Dixon-Coles.
  Keep the two visually distinct and correctly labelled.
- After editing the inline script, syntax-check it (extract `<script>` →
  `node --check`) before committing.

## Congress trades tracker (`congress/`, `docs/trades.html`)

A separate Pages section tracking STOCK Act trade disclosures, sourced only
from the official Senate eFD, House Clerk, and OGE (executive-branch 278-T)
sites. Full details in `congress/README.md`. Conventions:

- **Generated files are never hand-edited:** `docs/data/congress-trades.json`,
  `docs/data/returns.json`, `docs/data/holdings.json`,
  `docs/data/ai-indicators.json` and `congress/state.json` are written by
  `congress/pipeline.py` / `congress/prices.py` / `congress/holdings.py` /
  `congress/indicators.py` (daily via `.github/workflows/congress-trades.yml`).
  To change the data, fix the generator and re-run it.
- **Real holdings vs. trades:** PTRs disclose *trades*; a member's actual
  positions come from their **annual** report. `congress/holdings.py` parses the
  individual **stocks and options** from each featured member's latest annual FD
  (House Schedule A text PDF / Senate annual HTML) into `holdings.json`. The
  Holdings tab shows an **estimated current** portfolio: the annual snapshot
  **rolled forward** with every PTR trade dated after it (buys add, sells
  subtract, new tickers appear, sold-down names drop, expired options drop).
  Scanned annual reports (and Trump's image-only OGE 278) are marked unavailable
  and fall back to an inferred net-trading estimate. Label it honestly — bracket
  **midpoints, not share counts**; a directional estimate, never exact/real-time.
- **Executive 278-T (President) is a curated seed, not a scrape:**
  `congress/oge_filings.json` lists the President's OGE Form 278-T Periodic
  Transaction Reports by stable document UNID (he is not in any browsable OGE
  view). `congress/oge.py` fetches + OCR-parses each on every run; the rows are
  managed-account **bond** purchases (chamber `executive`, no ticker, no return
  estimate). To track a newly posted 278-T, append its `unid` + `filename`.
  This file *is* hand-maintained (unlike the generated data files above).
- **Return-since-buy is an estimate — label it as such:** `congress/prices.py`
  fetches Twelve Data daily closes (free tier, key via the CONGRESS_PRICES_KEY secret) and records, per disclosed
  **buy**, the stock's % change since the trade date. It is NOT the member's
  realized profit (holding/sells/dividends/position size unknown; entry uses
  the trade date's close, not the fill price). Keep that caveat visible on the
  page and only show it for equity-like assets (never options/crypto).
- **Featured-stocks tab is indicators + a mechanical summary, never advice:**
  `congress/indicators.py` + `congress ai` compute *mechanical* daily technical
  readings (RSI, moving averages, volume, 52-week range) for the fixed
  `AI_TICKERS` universe (kept as the identifier for continuity, but the tab is
  now labelled **"⭐ Featured stocks"** since it includes off-theme names like
  YPF/MELI/NU) → `docs/data/ai-indicators.json`, shown on the "⭐ Featured
  stocks" tab. The page shows a **transparent buy/sell/hold summary** (`aiScore`
  in `docs/trades.html`) — a rule-based *tally* of the displayed indicators
  (each votes buy/hold/sell), with the full breakdown visible and labelled
  **"not investment advice"**. It is a reproducible mechanical read, **not** an
  opaque recommendation; keep the breakdown + disclaimer, and never present it
  as advice or hide how it's computed. It also states named *events* (golden
  cross, RSI<30, new 52-wk high…) and offers a copy-paste prompt pre-filled with
  the readings (and the mechanical read) for deeper analysis in the user's own
  LLM. New signals
  open a GitHub issue (email) via `congress/notify_signals.py`
  (`python3 -m congress.notify_signals`, module form so the package's `http.py`
  doesn't shadow stdlib `http`); dedup lives in `meta.emitted_signal_keys`.
  Values are a **daily snapshot, not real-time**. The committed JSON ships as
  `_sample` data (synthetic series, banner-flagged) until the first live refresh.
  The page's `aiScore` and Python `indicators.ai_score` **must stay in sync**
  (same checks + thresholds) — the report reuses the Python one.
- **Site traffic — its OWN email (Vercel Web Analytics):** `congress/analytics.py`
  pulls the site's aggregated, cookieless page views via Vercel's public Web
  Analytics API (`/v1/query/web-analytics/visits/{count,aggregate}`, Bearer
  token). It ships as a **separate "📈 Traffic report" email** (not embedded in
  the trade digest — `daily_report.build_traffic_email` +
  `email_template.render_traffic_html`), so the digest stays focused on trades.
  The traffic email shows total + top pages + a **per-member-page breakdown**
  (the `by=route` aggregate rows under `/members/<slug>`, resolved to real names
  via the generated `members/_index.json`). **Gated + non-fatal:** needs
  `VERCEL_TOKEN` (secret) + `VERCEL_PROJECT_ID` (secret or var), optional
  `VERCEL_TEAM_ID`; unset or on any API error it returns `None` and the traffic
  email is simply not sent (the digest still goes out). Network is
  confined to `analytics._fetch_json` (stdlib `urllib`, no new deps); the
  response is parsed defensively (field names matched against candidates) and
  everything else is pure + offline-tested. Reads only existing aggregate data
  — no new visitor collection, so `/privacy` is unchanged. Test it with
  `python3 -m congress analytics`.
- **Morning report (email digest):** `congress/daily_report.py`
  (`python3 -m congress.daily_report`) composes the AI buy/sell/hold scorecard,
  overnight signals + rating flips, and newly-filed disclosures (site traffic is
  a **separate email**, see above), then delivers it two ways: **(1) direct email via SMTP** (primary, reliable regardless of
  GitHub notification settings — enabled by the `SMTP_USER`/`SMTP_PASS` secrets,
  e.g. a Gmail address + App Password; `SMTP_HOST`/`SMTP_PORT`/`REPORT_EMAIL_TO`
  are optional `vars` defaulting to Gmail:587 and the sender), and **(2) a dated
  GitHub issue** (archive + flip-diff state, assigned to the owner). `smtplib`
  is stdlib so no new deps. It runs from the daily Action's report step (guarded
  to `schedule` or the `report` dispatch input) **before** the slow price step
  so it's timely. It targets ~9am Madrid via **multiple morning crons (04:30 /
  06:00 / 08:00 UTC)** because GitHub scheduled runs are best-effort — delayed
  1–3h and sometimes dropped entirely; firing several times means GitHub must
  skip them all to miss a day, and the per-day idempotency makes only the first
  firing send. Early is safe, late/missing is the failure. It **assigns the issue to the repo owner**
  (`REPORT_ASSIGNEE` override) so email reaches them without needing to "watch"
  the repo, is **idempotent per day** (skips if `report_state.date == today`, so
  a manual send + a delayed scheduled run don't double-post), closes the prior
  day's report issue, and tracks the last issue number + ratings in
  `congress/report_state.json` (generated; do not hand-edit). UTC cron ignores
  DST so the Madrid clock time drifts ±1h; precise timing needs an external
  scheduler hitting the `workflow_dispatch` API.
  - **HTML email = `congress/email_template.py`** (pure, offline-tested). It is a
    hand-authored, **bulletproof** layout — table-based, inline styles, a fixed
    ~600px centered "paper" card, web-safe fonts (mono for data), hidden
    preheader, and the **Capitol Ledger text wordmark** masthead (no hosted
    image to break). Deliberately **light-only** (`color-scheme: light`): partial
    dark-mode styling renders worse than none across clients. `daily_report`
    passes it *structured data* (scorecard rows, signals, flips, disclosures)
    for the digest via `render_html`; the standalone traffic email uses
    `render_traffic_html` (both share the masthead/footer chrome via
    `_document`). The module owns all HTML/colours; markdown (the GitHub-issue
    body) is still built in `daily_report`. Preview by rendering
    `build_report(...)["html"]` / `build_traffic_email(...)["html"]` to a file.
    Keep the two brands' looks in step, but the email is its own surface (not
    governed by `landing/DESIGN.md`).
- **Dependency policy:** `predictor/` stays pure-stdlib. `congress/` may use
  `requests` + `pdfplumber` (`congress/requirements.txt`, installed only by
  the Action) but **parsers must stay stdlib-importable** so
  `tests/congress` runs offline with no third-party deps — network code is
  confined to `congress/http.py`, pdfplumber to `house.extract_pdf_text` /
  `oge.extract_pdf_text`, and Twelve Data to `prices.fetch_raw`.
- **Adding a featured member:** append the canonical name to
  `congress/featured.json` and make sure `congress/members.json` has an entry
  (with the filer-name spellings as `aliases`).
- **Run both test suites before committing:**
  `python3 -m unittest discover -s tests/predictor -p 'test_*.py'` and
  `python3 -m unittest discover -s tests/congress -p 'test_*.py'`.
- The `node --check` rule for inline scripts applies to `docs/trades.html`
  exactly as it does to `docs/index.html`.
- **Honest labelling:** the page must keep the 30–45-day legal lag, the
  bracket-only amounts, and the skipped paper filings visible. Never present
  the tracker as real-time or as investment advice.

## Roadmap (`ROADMAP.md`)

The staged evolution plan (storage stages, email/contact tooling stages,
member pages, follows, technologies to evaluate) lives in the repo-root
`ROADMAP.md`. Stages are trigger-gated, not date-gated. **Keep it current**:
when a stage ships, a trigger fires, or a decision changes, update the
roadmap in the same PR.

**Roadmap collision check (IMPORTANT):** before merging any non-trivial
change, check it against `ROADMAP.md` — it is easy to forget a stage exists.
Ask three questions:

1. **Does this ship (part of) a planned stage?** Then follow the stage's
   agreed design (e.g. don't add a one-off datastore when storage stage 1/2
   already prescribes SQLite/Supabase) and mark the stage's status.
2. **Does this fire a trigger?** (e.g. adding member pages triggers storage
   stage 1; adding accounts triggers stage 2 and contact stage 3.) Implement
   the staged move — or consciously defer it and note that in the roadmap.
3. **Does this collide with a stage or standing rule?** (e.g. a vendor choice
   that conflicts with the endpoint contract, a data change that breaks the
   git audit trail, collecting new visitor data without updating /privacy.)
   Resolve the collision or update the roadmap decision — never ship the
   contradiction silently.

If none apply, just proceed — no note needed. If any apply, the roadmap edit
belongs in the same PR as the change.

## Capitol Ledger landing page (`landing/`, deployed on Vercel)

A standalone Astro + Tailwind v4 marketing page (email-signup conversion for
trade alerts). Its own bounded context: glossary in `landing/CONTEXT.md`,
decisions in `landing/docs/adr/` (see also the root `CONTEXT-MAP.md`).
Conventions:

- The prototype in `landing/prototype/` is the **visual source of truth**;
  the four agreed deviations are listed in `landing/README.md` — do not
  "fix" them back to the prototype.
- `landing/src/data/*.json` (and `landing/src/data/members/*.json`) are
  **generated** by `python3 -m congress landing` (daily via the Action,
  committed with the trades refresh) — never hand-edit; every number on the
  page must be a true statement about real disclosures. "Late" = past the
  45-day statutory maximum (ADR 0002).
- **Member pages** (`/members/<slug>` + a `/members` index) are static SEO
  pages for a **curated featured set** (`landing_data.MEMBER_PAGE_NAMES` —
  Pelosi, Trump, Greene, Tuberville, Gottheimer), each showing that member's
  disclosed trades, most-traded tickers, filing timeliness and **estimated
  holdings**. The holdings are the annual snapshot **rolled forward** with
  every trade filed since (buys add / sells subtract by bracket midpoint, new
  tickers appear, live options surfaced, expired dropped) — so a recent buy
  that post-dates the annual report shows up. `landing_data.rolled_holdings`
  is a **Python port of the tracker's JS `rollForward` in `docs/trades.html`
  and must stay in sync with it** (same snapshot rule, same buy/sell/option
  logic). Bracket midpoints, never share counts. Generated by
  `landing_data.member_payload` + `write_member_files` →
  `landing/src/data/members/`; rendered by `src/pages/members/[slug].astro`.
  The `landing` Action step runs **after** the holdings refresh so pages use
  the freshest annual data. Scaling this to
  every member (or ticker pages) is the storage-stage-1 trigger — see
  `ROADMAP.md` (deliberately deferred at 5 members). SEO helpers (canonical,
  OG image, JSON-LD) live in the shared `src/components/Seo.astro`.
- **Visual identity manual:** `landing/DESIGN.md` is the design-agnostic
  identity + design system every page and redesign must follow (brand
  essence, color/type/motion/voice rules, the component vocabulary,
  a11y/perf requirements, governance). It is the source of truth for the
  *look*; changing the system (a token, a type rule, a new primitive) means
  editing `DESIGN.md` in the **same PR** as the code. When a design and the
  manual disagree, the manual wins.
- Design tokens live in `src/styles/global.css` `@theme`; no hex values
  outside the token set; zero border-radius; IBM Plex Mono for all
  data/labels/nav/form elements.
- Static output only (no server runtime); the only client JS is the signup
  form script (FR-1 contract: POST `email=` to `PUBLIC_SIGNUP_ENDPOINT`;
  unset endpoint → "Signups open soon").
