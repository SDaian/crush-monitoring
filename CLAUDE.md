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
