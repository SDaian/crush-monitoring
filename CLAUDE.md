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
