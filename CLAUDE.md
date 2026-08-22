# CLAUDE.md — Project conventions

## Chat style (MUST)

**Always talk to the user in ASD-STE100 Simplified Technical English.** This
rule applies to the chat replies only.

The rule does **not** change the product. It does not apply to the landing
page copy, the tracker, the email, the social posts, or any other text the
app shows to a reader. `landing/DESIGN.md` §7 governs that voice.

Write the chat replies to these rules:

- Use one word for one meaning. Do not use synonyms for the same thing.
- Keep sentences short: 20 words maximum for an instruction, 25 for a
  description.
- Write one instruction in one sentence.
- Use the active voice. Write "the parser reads the file", not "the file is
  read by the parser".
- Use simple tenses: present, past, or future. Do not use compound tenses.
- Start an instruction with the verb.
- Keep articles ("a", "the") in the sentence. Do not remove them.
- Use a maximum of three words in a noun cluster.
- Do not use "-ing" forms as nouns or adjectives when a simple verb works.
- Write one topic in one paragraph. Use a maximum of six sentences.
- Never restate a header in the sentence below it. A header names the topic;
  the paragraph must say something new, or the reader reads the thought twice
  (owner request, 2026-08-16).

**Follow Zinsser's four principles too**: clarity, simplicity, brevity,
humanity. STE gives the mechanics; Zinsser gives the reason for them. Two of
his principles are not mechanical, and no check measures them:

- **Clarity.** The reader must not read a sentence twice.
- **Humanity.** Write like a person, not like a form. Short does not mean cold.

**The rule stands on its own now** (owner decision, 2026-08-23). A Stop hook
(`.claude/hooks/chat_style.py`) used to measure every reply and block the
faulty ones; the owner removed it after a week of enforcement, keeping the
rule. Honor the rule without the referee — and when a reply drifts into long
sentences, passive voice or restated headers, that is the drift the hook
existed to catch. Never strip the warmth to satisfy the rules.

**Always read the `CONTEXT.md` files before you change related code, and use
their ubiquitous language.** The files are:

- `CONTEXT-MAP.md` (repo root) — the list of contexts and their relationships.
- `landing/CONTEXT.md` — the Capitol Ledger landing context.

Use each term exactly as its context defines it. The landing context defines
**Disclosure**, **Filing**, **Filing lag**, **Late**, **Days late**, **On
time**, **Amount bucket**, and **Recent disclosures**. Each term also lists
the words to avoid. Example: a **Filing** contains many **Disclosures**, so do
not use the two words for the same thing.

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

## Engineering principles (IMPORTANT)

How code gets written here. Each principle leads; the clause after it is how
it applies in *this* repo, and where a standing rule below overrides it, that
rule wins.

- **Do not preserve backward compatibility.** Remove obsolete paths instead of
  adding compatibility layers, fallbacks, or migrations. Three things here are
  **not** obsolete paths and survive this rule:
  - **Graceful degradation of the daily pipeline** — the non-fatal steps and
    gated integrations (unset key → skip, source outage → keep the prior file,
    media upload fails → manual-attach marker). That is resilience, not a
    compat shim: an optional step must never take the run down.
  - **The historical record** — `predictor/results_log.md`, prediction lambdas
    as filed, `congress/social_state.json`, and the git audit trail
    (`ROADMAP.md` §1). Annotate history; never rewrite it.
  - **Documented sunsets** — e.g. `docs/trades.html` serves until the apex
    domain resolves. Retire on the stated trigger, not on sight.
- **Choose the simplest implementation that fully meets the current
  requirements.** Avoid speculative abstractions, configuration, and
  indirection.
- **Grow the system in layers.** Start from the smallest version that works end
  to end, and add each new capability on top of a product that already works.
  Never trade a working product for unfinished complexity.
- **Keep components modular and concerns clearly separated.** The existing
  seams are the model: pure logic stays offline-testable, network is confined
  to `congress/http.py`, markup and CSS live in templates rather than in
  Python.
- **Prefer established, well-maintained libraries** when they reduce overall
  complexity or improve reliability. Do not reimplement common functionality
  without a clear reason. **The dependency policy overrides this bullet**:
  `predictor/` stays pure-stdlib and `congress/` parsers stay
  stdlib-importable, so a library that would break the offline tests is not an
  option however good it is.
- **Lean on the dependencies already in the project** before writing your own
  implementation or adding packages. Do not assume a library lacks a
  capability without checking its documentation and types. When the docs are
  unreachable from the sandbox (the egress proxy 403s some vendors), isolate
  the uncertain surface in one module, mark it UNVERIFIED, and probe read-only
  before any write — `congress/typefully.py` is the pattern.
- **Make architectural decisions for the long term.** Do not accept a stopgap
  that only works for now and is meant to be replaced later. A **trigger-gated
  `ROADMAP.md` stage is not a stopgap**: deferring SQLite until its trigger
  fires *is* the long-term decision — premature infrastructure is the failure
  mode the roadmap exists to prevent.

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

## Congress trades tracker (`congress/`, `/tracker` on the landing site)

A separate Pages section tracking STOCK Act trade disclosures, sourced only
from the official Senate eFD, House Clerk, and OGE (executive-branch 278-T)
sites. Full details in `congress/README.md`. Conventions:

- **Generated files are never hand-edited:** `docs/data/congress-trades.json`,
  `docs/data/returns.json`, `docs/data/performance.json`,
  `docs/data/holdings.json`,
  `docs/data/ai-indicators.json` and `congress/state.json` are written by
  `congress/pipeline.py` / `congress/prices.py` / `congress/holdings.py` /
  `congress/indicators.py` (daily via `.github/workflows/congress-trades.yml`).
  To change the data, fix the generator and re-run it.
- **A generator's output is only real if the workflow commits it.** The daily
  Action stages an explicit `FILES` list, so a path the generators write but
  `FILES` omits is regenerated every run and thrown away at the next checkout —
  with every step reporting success. That is how `landing/src/data/tickers`
  served two-month-old pages while the tracker was current. Two guards now hold
  the line, and **both must stay**: `tests/congress/test_workflow_paths.py`
  *runs* the landing generators into a temp dir and asserts the workflow stages
  every file they produce (so a new output fails the suite until it is listed),
  and a post-push workflow step fails the run if anything under `docs/data`,
  `landing/src/data` or `congress/` is left uncommitted. When you add a
  generator output, add its path to `FILES`.
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
  **An empty holdings list is not one thing.** `holdings.classify` records a
  `reason` per member, because the causes need different responses: a scanned
  PDF is a source limit, "no assets parsed" is a parser bug worth fixing, and
  **"funds only" is correct data, not a gap** — a member holding no individual
  equities genuinely has zero, and flagging it would be wrong. The `holdings`
  command prints the ones in `NEEDS_REVIEW` with their document URL and emits a
  `::warning::` per gap, so new coverage holes surface in the Action log instead
  of being absorbed silently.
- **Executive 278-T (President) is a curated seed, not a scrape:**
  `congress/oge_filings.json` lists the President's OGE Form 278-T Periodic
  Transaction Reports by stable document UNID (he is not in any browsable OGE
  view). `congress/oge.py` fetches + OCR-parses each on every run; the rows are
  managed-account purchases (chamber `executive`). Early filings held only
  **bonds**; the June-2026 filing added **stocks and ETFs**, so `oge.py` now
  classifies each row (`tickermatch.is_debt`) and resolves equity tickers via
  `congress/tickermatch.py` — the curated `OVERRIDES` map plus an index built
  from the published House/Senate rows (name + ticker pairs). **Resolution is
  exact or refused, never guessed**: the form has no ticker column and its OCR
  garbles names ("QUALM INC", "BOEING PANY"), so a miss prints a `::warning::`
  and a human adds the name to `OVERRIDES` — no re-download needed: the fetch
  command ends with a **retick pass** (`cli.retick_executive`) that re-resolves
  every published executive stock row lacking a ticker on every run, so an
  override lands the next morning by itself. A bond ETF is never debt — it trades as shares. To track a newly posted
  278-T, append its `unid` + `filename`.
  This file *is* hand-maintained (unlike the generated data files above).
- **The seat beside the trade is two facts, never three.** Member pages list
  the symbols a member disclosed in an industry one of their committees
  oversees. Both halves are public record; the line between them is not drawn,
  and no surface may draw it — not in copy, not by layout, not by colour. The
  banned words are in `landing/CONTEXT.md` under **Oversees**.
  `congress/sectors.json` holds the two curated maps (committee → industries,
  ticker → industry) and is **hand-maintained**, like `oge_filings.json`;
  `congress/sectors.py` is pure and offline-tested. Two rules hold it honest:
  **committees with jurisdiction over every industry stay unmapped** (the money
  committees, Judiciary, the tax committees — a flag that always fires says
  nothing), and **every page prints its own coverage** ("covers 65 of the 102
  symbols"), because an unlisted ticker is unclassified, not out of the
  industry. Add a missing ticker to the map rather than widening a committee.
- **The two sector maps have two jobs, so they cover different ground.** The
  `tickers` map also badges every `/tickers/<symbol>` page and drives the
  **industry filter** on `/tickers` (`?industry=<key>` deep-links from each
  stock page), so it aims to be **complete**: a stock with no badge reads as a
  broken dataset, not as a stock with no industry. That is why six of the
  fourteen industries (consumer, industrial, autos, materials, realestate,
  business) map to **no committee at all** — they exist to classify stocks, and
  adding one to a committee would silently widen the member-page flag. The
  `committees` map stays deliberately partial (above). Three guards:
  `tests/congress/test_sectors.py` fails if any generated ticker page lacks an
  industry, if a symbol is listed twice (`json.loads` keeps the last duplicate
  silently), or if a label exceeds **21 characters** — the industry `<select>`
  takes its width from its longest option and a longer label pushes the control
  off a 320px screen. `write_ticker_files` also emits a `::warning::` per
  unclassified page, because the page universe is re-picked every run.
- **Trading performance vs the S&P 500 (member pages):** the prices run also
  fetches one benchmark series (SPY) and (a) stamps each priced buy in
  `returns.json` with `bench_pct` — the index's move over the *same* window —
  and (b) writes `docs/data/performance.json` (`congress/performance.py`, pure
  math): a per-featured-member weekly "$1 in every priced buy vs the same $1,
  same dates, in the S&P" index series. This can only be built during the
  prices run (full histories exist only in memory), which is why the workflow
  re-runs `congress landing` after prices. The member-page section
  (`PerformanceChart.astro`) is **gated**: it renders only with ≥3 priced buys
  AND benchmark data, and its not-realized-profit caption is part of the
  component so the chart cannot ship without it. Equal-weighted everywhere —
  filings disclose brackets, so weighting by position size would be invented.
- **Bonds are kept but de-emphasized:** ticker-less debt rows (Trump's
  executive 278-T bonds, munis, treasuries) stay in the record, the tracker
  and the member pages. Until June 2026 they were his entire page (57/57
  rows); his newer filings add tickered stocks and ETFs beside them, and the
  executive coverage is a differentiator either way. But
  they are excluded from the HEADLINE surfaces (`landing_data.is_bond`): the
  home-page stats say "stock trades" and count exactly that, and the live
  feed already requires a ticker. Don't widen `is_bond` to tickered rows.
- **Return-since-buy is an estimate — label it as such:** `congress/prices.py`
  fetches Twelve Data daily closes (free tier, key via the CONGRESS_PRICES_KEY secret) and records, per disclosed
  **buy**, the stock's % change since the trade date. It is NOT the member's
  realized profit (holding/sells/dividends/position size unknown; entry uses
  the trade date's close, not the fill price). Keep that caveat visible on the
  page and only show it for equity-like assets (never options/crypto).
- **Two universes, one rule: every ticker page gets a reading.** `congress ai`
  computes readings for **every symbol in the generated ticker index**
  (`indicators.reading_universe`, fed by `landing/src/data/tickers/_index.json`
  — the `landing` step runs *before* it in the workflow, so "a page implies a
  reading" holds by construction). It used to compute only `AI_TICKERS`, and
  the two universes disagreed: pages are picked by substance (disclosed
  trades), readings were picked by theme — so **AAPL, the third most-traded
  stock in Congress, had a page with no reading**. Each record carries
  `featured: true|false`, and the surfaces that must stay short filter on it:
  the **morning email scorecard** (`build_report` iterates `AI_TICKERS`), the
  tracker's **"⭐ Featured stocks" tab** (`aiTickers()` returns `AI_ORDER` and
  nothing else), and **`meta.new_signals`** — a signal on a non-featured
  symbol still shows on that ticker's page but never opens an issue or emails.
  A missing/unreadable index falls back to the featured watchlist: a failed
  `landing` step costs a few readings, never the run. Cost is one API call per
  symbol per day (8/min, 800/day tier); ~93 readings + ~122 priced tickers sits
  well inside it.
- **Featured-stocks tab is indicators + a mechanical summary, never advice:**
  `congress/indicators.py` + `congress ai` compute *mechanical* daily technical
  readings (RSI, moving averages, volume, 52-week range) for the
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
  (same checks + thresholds) — the report reuses the Python one. The **ticker
  page** (`/tickers/<symbol>`) carries the same reading in a "Technical read"
  panel, for featured symbols only, built by `landing_data.technical_block` —
  which calls `indicators.ai_score` directly, so that surface cannot drift
  either. It ships with the vote breakdown and the "not a recommendation"
  caption, and the page's congressional trades stay its `<h1>`/description so
  it still reads as a disclosure record first. The sparkline is `series` (52
  weekly closes downsampled from the history the indicators run already
  fetched — **no extra API call**) drawn as build-time inline SVG; an empty
  series omits the chart. `nextEarnings` is opt-in via the `EARNINGS_DATES`
  variable, because it is an extra per-ticker call on an endpoint that is not
  on every Twelve Data plan — unset or failing, the line is simply absent.
- **A paced fetch that cannot return new numbers must not run.** The two
  Twelve Data steps sleep 8s between ~220 calls, so a run costs ~29 minutes of
  GitHub runner time — 88% of the daily Action bill, spent waiting. `congress
  prices` and `congress ai` take **`--skip-if-closed`**, which compares the
  newest `asof_date` the output already holds against
  `market.last_closed_session(now)`. **The test is the settled session, not
  the weekday**, and the run log says why: the crons fire at 04:30-08:20 UTC,
  hours *before* the US close, so each run captures the PREVIOUS session
  (Fri 05:00 → Thursday's close, Sat 05:00 → **Friday's** close). A naive
  "skip at the weekend" would drop the Saturday run that captures Friday and
  leave the site a day behind until Tuesday. Steady state skips **Sunday and
  the pre-close Monday run** — 2 days in 7, ~253 min/month. Holidays get **no
  hardcoded table**: a stale list would silently skip a real trading day,
  which is worse than one wasted fetch a few times a year (we fetch once, store
  the unchanged close, and the comparison skips the next run by itself). A
  missing, unreadable or garbled date always fetches.
- **Market context is one number, and it never votes:** `congress/market.py`
  turns a daily series into the market-wide volatility reading the morning
  report and **every** ticker page show. First choice is the **VIX**
  (`prices.fetch_index_raw`, one extra call a day, no `country` filter — that
  filter drops an index). Twelve Data's index coverage is plan-dependent and
  the key is a secret, so the surface is probed, not assumed: an empty series
  falls back to **our own annualised 20-day realized volatility of SPY**
  (a second call, only then), labelled "S&P 500 volatility" and **never**
  "VIX" — a different measurement needs a different name, which is also why a
  VIX ETF (VIXY holds futures and decays) is not an option. Neither source →
  no `market` key and every surface omits the line. The reading is
  **deliberately absent from `indicators.ai_score`**: that score is a
  per-stock tally, and a market-wide input would flip all 23 ratings at once
  and empty the morning report's rating-flip diff of meaning. The bands
  (<15 calm / <25 normal / <35 elevated / else stressed) are **our
  convention** and every surface says so. It reaches the site as ONE
  generated file, `landing/src/data/market.json` (written by
  `landing_data.write_files`, always written even when null because the pages
  import it at build time) — not copied into each ticker payload, which would
  rewrite all 98 of them every morning with the same number and bury the real
  trade changes. `MarketStrip.astro` renders it for `/report` and the ticker
  pages; `email_template.market_line` for the email.
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
  `congress/report_state.json` (generated; do not hand-edit).
  - **Quiet days do not send** (`daily_report.whats_new`). The market closes at
    the weekend and on holidays, so a Sunday email repeats Saturday's word for
    word. When the latest daily close has not advanced **and** no new filing
    has arrived since the last delivered report, the run skips *every* delivery
    — digest, Buttondown broadcast, traffic email, GitHub issue — and writes no
    dated permalink, but **still publishes `report.json` so `/report` stays
    current**, and records **nothing** in `report_state.json` (its fingerprint
    keeps describing the last report that went out, so a later cron re-asks the
    question). The test is a fingerprint — `market_date` (max `asof_date` across
    the featured tickers), `trades_total`, `last_filing_date` — not the weekday:
    a market holiday is just as quiet, and ~8% of filings carry a weekend date,
    so a blanket weekend skip would hold a real disclosure until Monday. Signals
    and rating flips get **no test of their own**: both derive from the
    indicators, so a new close already covers them, and testing them separately
    would re-send yesterday's signals off a stale file. A missing baseline and
    `REPORT_FORCE` both always send.
  UTC cron ignores
  DST so the Madrid clock time drifts ±1h; precise timing needs an external
  scheduler hitting the `workflow_dispatch` API.
  - **Subscribers = `congress/buttondown.py`** (gated + non-fatal). The same
    `build_report` HTML is broadcast to confirmed subscribers with one API call
    (`POST /v1/emails`, `BUTTONDOWN_API_KEY` secret); Buttondown owns the list,
    double opt-in, unsubscribe and deliverability. **Subscriber PII never
    enters this repo** — we only POST content, never read or store the list.
    Unset key or any API error → skipped, and the owner's SMTP copy plus the
    GitHub issue still go out. It sits inside the per-day idempotency gate, so
    subscribers can't be double-sent. Capture is the FR-1 form contract
    (`PUBLIC_SIGNUP_ENDPOINT`, set in Vercel, not in code).
  - **Web edition = `/report`** (`landing/src/pages/report.astro`), rendered
    from `landing/src/data/report.json`, which `daily_report.main()` writes from
    the **same payload** `build_report` builds the email from — so the page and
    the email can never drift. The one deliberate difference: the email caps
    disclosures at `MAX_DISCLOSURES` because clients clip long messages, while
    the page lists **every** one — that is what the email's "…and N more"
    links. **Disclosures lead the report** (first section — they are the
    product; the scorecard supports). **Bond/muni filings are a count in the
    email, full rows on the page** (owner's call — one senator's muni ladder
    was drowning the inbox): the email and issue list stock/option rows only
    (split with the same `landing_data.is_bond` predicate as the home-page
    stats, deliberately not widened) plus "…plus N bond & muni filings — see
    the full report" linking the dated permalink; the `/report` page shows
    the whole window undivided, bonds included. If you add a path that `main()` writes, **stub it in
    `TestMainDelivery`** — the suite calls `main()` for real and will
    otherwise overwrite the committed file.
  - **Report archive = `/report/<date>` + `/report/archive`.** `main()` also
    writes `landing/src/data/reports/<date>.json` (+ `_index.json`) — the SAME
    payload as `report.json`, so a permalink can never disagree with what went
    out — and the email's "view in browser" now links the dated permalink. The
    original one-indexable-URL decision (nobody searches "morning report July
    24"; 365 near-duplicate pages a year is an SEO liability) still stands,
    amended not reversed: **every dated page is `noindex` and canonicalizes to
    `/report`** (`check-seo.mjs` warns if one loses it); only `/report` and
    `/report/archive` are indexable. No backfill — the archive starts the day
    it shipped; earlier reports live in git history and the dated GitHub
    issues. Shared markup lives in `ReportBody.astro` so the two renderings
    cannot drift. The flat-file archive migrates when storage stage 1 fires.
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
- **Social drafts (X via Typefully) are approval-gated and seeded:**
  `python3 -m congress social` (daily Action step) turns notable NEW filings
  (featured member, ≥$1M bracket floor, or >90d late) into card PNGs
  (`congress/social/card_template.html` + `scripts/render_card.mjs`,
  repo-local fonts) and tweet copy (`congress/social/copy_template.txt`,
  280-char enforced with graceful degradation), then creates UNPUBLISHED
  Typefully drafts. Live is double-gated (`TYPEFULLY_API_KEY` secret AND
  `SOCIAL_LIVE=true` variable) because the Typefully **v2** endpoint shapes
  are well-sourced but not doc-verified (`congress/typefully.py` — the docs
  site 403s the dev sandbox; v1 was retired for API keys, which the
  probe-before-write caught on the very first live run); a read-only probe
  (GET /me) plus social-set resolution run before any write. The card PNG
  is attached automatically (`typefully.upload_media`: upload slot →
  presigned-S3 PUT → status poll); if that fails the draft still goes out
  with an "[attach card: …]" note and the owner drag-drops the PNG from the
  run's `social-cards` artifact during approval.
  Dedup state is `congress/social_state.json` (chamber:filing_id → draft),
  committed by the Action; a failed record stays out of the state so it
  retries. `--seed` marked the 163-filing backlog as seen at ship time —
  never drip-feed old disclosures as if they were news. The narrative hook
  ("Already holds ~$121K of AMZN — 4.2% of their estimated portfolio") comes
  from `social.holdings_context`: the member page's rolled-forward holdings
  estimate, so it is always "~"/"estimated" (bracket midpoints, never
  invented precision) and silently absent when the member has no page, no
  parsed holdings, or no position. Under the 280 limit it degrades context
  line first, late line second — accountability outlives the nice-to-have.
- **Search indexing is push + pull:** the sitemap (`robots.txt` →
  `sitemap-index.xml`) covers Google; `congress/indexnow.py`
  (`python3 -m congress indexnow`, non-fatal daily workflow step) pushes the
  refreshed URLs to IndexNow (Bing/Yandex family — also feeds DuckDuckGo and
  Yahoo). Ownership proof is `landing/public/<KEY>.txt`; the key is public by
  design, NOT a secret. Bing Webmaster Tools itself is a one-time manual
  setup (import from Google Search Console).
- **A parser fix does not reach data already published.** `congress/state.json`
  records every processed `filing_id`, so a document is never read twice —
  which means a bad row stays live forever unless the filing is forgotten.
  `python3 -m congress fetch --reparse-invalid` finds rows breaking an
  invariant (`pipeline.invalid_trades`), drops those *whole filings* from the
  state and the output, and lets the normal fetch re-download them. Drop the
  whole filing, never the single row: re-parsing is per document, so leaving a
  sibling row behind duplicates it.
- **Dependency policy:** `predictor/` stays pure-stdlib. `congress/` may use
  `requests` + `pdfplumber` (`congress/requirements.txt`, installed only by
  the Action) but **parsers must stay stdlib-importable** so
  `tests/congress` runs offline with no third-party deps — network code is
  confined to `congress/http.py`, pdfplumber to `house.extract_pdf_text` /
  `oge.extract_pdf_text`, and Twelve Data to `prices.fetch_raw`.
- **Committee seats are on the member pages.** `landing_data.committee_block`
  reads `docs/data/committees.json` (written by `congress committees`) and
  `[slug].astro` renders the seats with their subcommittees. It **states
  the seat only** — a committee beside a trade is a fact, a claim that one
  caused the other is not, and the page's fineprint says so. An empty list
  renders **nothing**, not an empty heading: a seatless sitting member, a
  former member and an executive filer are three different facts (the
  `holdings.classify` rule again), and only the reasons in
  `committees.NEEDS_REVIEW` are gaps worth chasing.
- **Adding a featured member:** append the canonical name to
  `congress/featured.json` and make sure `congress/members.json` has an entry
  (with the filer-name spellings as `aliases`).
- **Run both test suites before committing:**
  `python3 -m unittest discover -s tests/predictor -p 'test_*.py'` and
  `python3 -m unittest discover -s tests/congress -p 'test_*.py'`.
- **The tracker is now a native page** at `landing/src/pages/tracker.astro`
  (`/tracker`), rebuilt in the Capitol Ledger design system rather than the
  standalone `docs/trades.html`. It is deliberately **trimmed to two tabs** —
  *All trades* (filter 12k+ rows) and *Featured stocks* (indicator scorecard) —
  because `/tickers/<symbol>` and `/members/<slug>` now cover ticker focus and
  holdings better, as static indexable pages; the tab bar links out to them.
  Its data is fetched from `/data/*.json`, copied out of `docs/data` at build
  time by `landing/scripts/copy-tracker-data.mjs` (npm `prebuild`), so the
  6 MB trades JSON stays committed **once**, in `docs/data`; the copies are
  gitignored. Because the page injects markup at runtime, its CSS must stay
  `<style is:global>` scoped under `.tracker` — Astro's scoped styles only tag
  build-time elements, so scoping it would silently unstyle every row and card.
  `docs/trades.html` still serves the old standalone build on GitHub Pages and
  is retired only once the apex domain resolves.
- The `node --check` rule for inline scripts applies to the tracker's inline
  script (extract it from `tracker.astro`) and to `docs/index.html`.
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
  Pelosi, Trump, Greene, Tuberville, Gottheimer, Fields, Cisneros, Armstrong,
  McCormick, McClain Delaney, McGuire), each showing that member's
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
  every member is the storage-stage-1 trigger — see
  `ROADMAP.md` (deliberately deferred at 10 members). SEO helpers (canonical,
  OG image, JSON-LD) live in the shared `src/components/Seo.astro`.
- **Ticker pages** (`/tickers/<slug>` + a `/tickers` index) are the organic-
  search surface: search demand is on **entities, not dates** ("nvda congress
  trades"), so these — not a dated report archive — are the traffic play. Each
  shows who in Congress traded the symbol, the buy/sell split, and the recent
  trades with a link to every official filing. **The universe is picked by
  substance on every run**, never hand-listed: `landing_data.select_ticker_pages`
  takes **every** symbol clearing `TICKER_PAGE_MIN_TRADES` — there is
  deliberately **no top-N cap**, because one cut 66 symbols that met the bar
  (ORCL 47, IBM 45, LMT 25 …), which is a content gap, not SEO hygiene.
  Featured-watchlist names *below* the bar also get a page, because the
  tracker's Featured tab links per ticker and a link must resolve — but they
  are **`noindex`** (`ticker_is_indexable`), so a 4-trade stub (NU) never
  enters the index and the "no thin indexable pages" rule still holds. A
  ticker with **zero** disclosed trades gets no page at all (the tab says so
  inline, without linking). Anything `noindex` is also excluded from the
  sitemap (the `astro.config.mjs` filter, which likewise drops dated report
  permalinks): advertising a page you tell robots to ignore is a
  contradictory signal.
  Generated by `landing_data.ticker_payload` + `write_ticker_files`;
  rendered by `src/pages/tickers/[slug].astro`, which splits into **two tabs**
  — *Disclosed trades* (default) and *Market & technicals* — sitting directly
  under the headline so the readings are one click away, not one scroll down.
  Both panels ship in the HTML (the switch only hides one, so the page stays
  fully indexable), a synchronous head script sets the class that hides one
  (no flash), and **with JavaScript off both panels show** — the page the
  tabs replaced. `#technical` still deep-links from the tracker: it opens tab
  2, and a switch writes the hash back. Cross-linked with member pages
  in both directions (member chips carry `hasPage`/`slug`), and deep-linked from
  the morning email via `daily_report.ticker_links` with UTM tags so Vercel
  analytics attributes the email as a traffic source. Scaling to all ~1,400
  tickers fires storage stage 1.
- **Every content page ends in a real signup form.** Search traffic lands on
  `/tickers/<symbol>` and `/members/<slug>`, not the home page, so a CTA that
  merely *links* to the signup elsewhere converts at ~zero — it asks an arriving
  reader to navigate away and re-decide. Use `SignupForm.astro`
  (`hero`/`band`/`modal` variants); `/privacy` is the one deliberate exception,
  and the header CTA anchors to the on-page `#join` rather than bouncing home.
  `SignupModal.astro` is the read-triggered dialog — **never an on-arrival
  popup** (Google's intrusive-interstitial policy, and it's what makes people
  bounce): 60% scroll or desktop exit intent, behind a time floor, dismissal
  remembered in `localStorage`, retired for good on subscribe, and not rendered
  at all when `PUBLIC_SIGNUP_ENDPOINT` is unset. It runs on the home page too,
  held back by a **synchronous** geometry check — never open a dialog asking
  for an email over a form already on screen. That check must not be an
  `IntersectionObserver`: its callbacks land at end-of-frame, so a fast scroll
  or an `#anchor` jump onto the form fires the scroll handler first and opens
  the modal on top of it. **Copy constraint: these
  surfaces may not promise a per-ticker or per-member alert** — follows don't
  exist yet (`ROADMAP.md`). Promise the daily email, and lead with the page's own
  real number ("171 disclosed so far").
- **A missing `PUBLIC_SIGNUP_ENDPOINT` is silent and fatal.** Unset, every form
  answers "Signups open soon" and nobody can subscribe — which from the outside
  looks identical to nobody *wanting* to. `src/lib/signup.ts` warns loudly at
  build time; it warns and never throws, so a deploy is never taken down over it.
- **Charts must not out-claim the data.** The holdings ring/bars on member pages
  (`HoldingsChart.astro` + `src/lib/holdings.ts`) render bracket midpoints of a
  **truncated** list, so two things are mandatory: always draw the folded
  remainder (the 16 listed can be 40% of a real portfolio — Greene), and always
  caption ties (Pelosi's top eight are all exactly $15.0M because all eight are
  in the same $5M–$25M band; equal slices mean equal *brackets*). Bar widths are
  clamped — the untracked tail can exceed the largest listed holding and will
  otherwise render past 100% and off the page. Charts are inline SVG built at
  build time; no chart library, no client JS.
- **Meta descriptions are capped at 150 chars, structurally.** Google truncates
  what it shows at ~155 desktop / ~120 mobile, and most of our descriptions
  interpolate pipeline data (a company name, a member's name, a trade count) —
  so a page that fits today can overflow after tomorrow's refresh. Compose every
  description with `seoDescription()` from `src/lib/seo.ts`: the first argument
  is the sentence that must survive (front-load the page's own numbers there),
  the rest are tail clauses appended only while they still fit, so a long value
  drops a whole clause instead of being cut mid-word. Guard the data's edges —
  the President discloses ticker-less bonds, so "across N tickers" has to
  disappear rather than render "across 0 tickers". `scripts/check-seo.mjs` runs
  as npm `postbuild` and **warns** about overruns and missing titles; it
  deliberately does not fail the build (a cosmetic overflow must never take the
  deploy down).
- **Authoring notes must not ship. Comments in `.astro` use `{/* … */}`.**
  Astro strips those and **keeps** `<!-- … -->`, so 25 rationale comments in
  the components became **686 comments and 132 KB across 124 published pages**
  — every reader who opened View Source read the design notes. Explain code in
  the frontmatter (`// …`) or in a JSX comment.
  `tests/congress/test_landing_source.py` **fails the offline suite** on any
  HTML comment in a `.astro` file (the Action runs that suite first), and
  `landing/scripts/check-copy.mjs` (npm `postbuild`, next to `check-seo.mjs`)
  **warns** on the other machine-written tells: comments that reached the
  output, emoji in visible copy, three-plus em dashes in one block, and a short
  list of generated-sounding phrases. It warns and never fails, for
  `check-seo`'s reason — a cosmetic count must not take the deploy down. The
  rules themselves live in `landing/DESIGN.md` §7; note that em-dash *density*
  is deliberately not a rule (the prototype runs ~20 per 1,000 words — the tell
  is stacking, not the dash), typographic marks (→ ★ ✕) are not emoji, and the
  AI disclosure on `/how-it-works` stays: removing it would hide something
  true.
- **The icon set is generated, not hand-made.** `landing/scripts/make-icons.py`
  (stdlib only, run it manually) writes `favicon.svg`, a real multi-size
  `favicon.ico` (16/32/48, the file Google's separate favicon crawler wants at
  the site root), `favicon-96.png` and `apple-touch-icon.png` from one set of
  rectangles. Change the mark there and re-run; don't hand-edit the outputs.
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
- **Check every UI change on a phone BEFORE you ship it — a desktop
  screenshot proves nothing.** The filter on `/tickers` looked correct at
  1200px and clipped its placeholder mid-sentence at 375px. Build the site,
  serve `landing/dist` over `python3 -m http.server`, and drive the page with
  Playwright at **320, 375 and 414 px**. Assert three things, because the eye
  misses all of them in a screenshot:
  1. **The document never scrolls sideways**:
     `documentElement.scrollWidth <= clientWidth`.
  2. **No element overflows its own box**: compare `scrollWidth` with
     `clientWidth` per element. Deliberate exceptions exist and must stay —
     the trades table (`.tscroll`) and the mobile menu scroll on purpose.
  3. **Text fits its control**: measure the string against the box width
     (a canvas/probe span), because a clipped placeholder or a truncated
     label still reports zero overflow.
  Prefer a shorter string over a smaller font: 375px is the real floor.
