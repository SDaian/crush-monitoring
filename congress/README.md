# congress/ — congressional stock-trade fetcher

Scrapes Periodic Transaction Reports (PTRs) from the two official sources,
normalizes them into one schema, and accumulates them into
`docs/data/congress-trades.json` for the Pages tracker (`docs/trades.html`).

## Sources (official only)

| Chamber | Listing | Filing documents |
|---|---|---|
| Senate | `efdsearch.senate.gov` — disclaimer POST (CSRF) then the DataTables-style JSON search (`/search/report/data/`, report type 11 = PTR) | Electronic PTRs are HTML tables; paper filings (`/search/view/paper/…`) are scans |
| House | `disclosures-clerk.house.gov` — yearly index ZIP `public_disc/financial-pdfs/<YEAR>FD.zip` (TSV; FilingType `P` = PTR) | `public_disc/ptr-pdfs/<YEAR>/<DocID>.pdf`; e-filed PTRs are text PDFs, paper ones are scans |
| Executive (President) | `extapps2.oge.gov/201/Presiden.nsf` — OGE Form 278-T Periodic Transaction Reports. The President is **not** in OGE's browsable PAS Index view (appointees only) and the app exposes no search, so his filings are curated by stable document UNID in `oge_filings.json` | `.../PAS+Index/<UNID>/$FILE/<name>.pdf` — **scanned** PDFs with an OCR text layer |

## Executive 278-T (`oge.py` → chamber `executive`)

The President discloses trades on OGE Form 278-T. Unlike the House e-filed PDFs,
these are **scanned images with a noisy OCR text layer** (digits misread as
letters: `5`→`S`, `0`→`D`/`O`, `1`→`l`), so `oge.parse_transactions` anchors on
the regular `<type> <date> No <amount>` tail of each row and **snaps the amount
to the fixed STOCK Act brackets**, which corrects residual OCR errors. The
President's disclosed transactions are managed-account **purchases of corporate
& municipal bonds** (plus the odd bond ETF), so these rows carry **no equity
ticker** and therefore no "return since buy".

Because he is not listed in any browsable OGE view, the filings to ingest are
curated in **`congress/oge_filings.json`** (one entry per 278-T PDF: its stable
`unid` + attachment `filename`; the report date is parsed from the filename).
The daily job re-fetches and re-parses each seeded UNID. **To add a newly posted
278-T**, append its `unid` and `filename` to that file. Only `oge.fetch_trades`
(the PDF GET) and `oge.extract_pdf_text` (pdfplumber) touch the network/binary
deps; the parsing is pure and fixture-tested offline.

Paper/scanned filings are never parsed: they are recorded in
`skipped_filings` with a link and surfaced on the page. Parse-error filings
are also skipped-with-link but are **retried on every run** (they are not
marked processed), so they self-heal after a parser fix.

## Return since buy (`prices.py` → `docs/data/returns.json`)

For every disclosed **buy** of a listed US equity, `congress prices` estimates
how the stock has performed since the trade date, using Twelve Data (free tier, key via the CONGRESS_PRICES_KEY secret). Per buy it stores the
entry close (the trade date's close, or the prior session), and the % change to
the latest available close.

This is a **stock-performance follow-through, not the member's realized
profit** — holding period, later sells, dividends and position size are all
unknown, and the STOCK Act discloses a trade *date*, not a fill price. Only
listed US equities price; options, bonds, foreign and delisted names are left
out (the page shows "—"). The number is intentionally an estimate.

Only `prices.fetch_raw` touches the network; parsing and the return math are
pure stdlib, so `tests/congress/test_prices.py` runs offline against a JSON
fixture. Run standalone with `python3 -m congress prices` (add `--limit N` to
price only the first N tickers while testing).

**Live feed: Twelve Data.** The daily Action reads the `CONGRESS_PRICES_KEY` repo secret and prices the featured + ~100 most-traded tickers (free tier is 800 calls/day, 8/min), which covers where the buy volume is; the long tail shows “—”. The key is passed only as an env var and never written to any file, log or committed URL. On a total miss (missing key / outage) the writer keeps the existing `returns.json` rather than clobbering it.



**Option context.** For option trades we also capture the filer's free-text Description (House) / Comment (Senate) verbatim into `comment`, and parse out `option` = {type, strike, expiration, contracts} when disclosed (e.g. "Purchased 200 call options with a strike price of $50 and an expiration date of 3/19/27."). Disclosure is inconsistent — the page shows what the filer gave and "details not specified in filing" otherwise; quantity is only shown when the filer wrote it (it is not a required field).

## Real holdings (`holdings.py` → `docs/data/holdings.json`)

The PTRs above disclose *trades*, not positions. A member's actual **holdings**
live in their **annual** financial-disclosure report, which lists each asset
with a year-end value bracket. `congress holdings` parses the **individual
stocks and options** out of each featured member's latest annual report and
writes `docs/data/holdings.json` for the page's "Holdings" tab. The page then
shows an **estimated current** portfolio: it takes the annual report as a
baseline and **rolls it forward** with every PTR trade dated after the snapshot
(buys add, sells subtract, new tickers appear, fully-sold names drop off;
options past expiry are dropped). Parsing:

- **House**: annual FD (`FilingType == 'O'` in the same yearly index ZIP), a
  text PDF whose "Schedule A" lists `<name> (<TICKER>) [ST|OP] <owner> $lo - …`.
  The asset-type code (`[ST]` stock / `[OP]` option) can wrap to the next line;
  the value's upper bound wraps too, so the bracket is resolved from its
  (unique) lower bound. Option strike/expiry come from the row's `D:` note.
- **Senate**: the eFD "Annual Report" (`/search/view/annual/<uuid>/`), a
  structured HTML page whose Assets table has
  `# | Asset | Asset Type | Owner | Value | Income Type | Income`.
- **Executive (Trump)**: the annual OGE 278 is a ~250-page **scanned image** —
  not machine-readable — so it's shown "link only", and the page falls back to
  an inferred net-trading estimate.

Only individual company stocks (`[ST]` / "…Stock") are kept — ETFs, funds,
bonds, bank/retirement accounts, real estate and private business are excluded.
It is a **yearly snapshot**, values are **brackets**, and scanned/paper annual
reports can't be parsed (that member is marked `available: false`). Only the
listing/fetch helpers touch the network; the two parsers are pure and
fixture-tested offline (`tests/congress/test_holdings.py`).

## AI technical indicators (`indicators.py` → `docs/data/ai-indicators.json`)

The page's **"🤖 AI stocks"** tab shows *mechanical* daily technical readings
for a fixed AI-adjacent universe (chips, hyperscalers, data-center build-out —
see `AI_TICKERS`): latest close, RSI(14, Wilder), 20/50/200-day moving
averages, period returns, volume vs. its 20-day average, and the 52-week range.
`congress ai` fetches each ticker's daily history (reusing the Twelve Data
key/session from `prices.py`) and writes `docs/data/ai-indicators.json`.

- **Mechanical summary, never advice.** The Python module emits only numbers;
  the page's `aiScore` derives a **transparent buy/sell/hold tally** from those
  indicators (each votes buy/hold/sell, full breakdown shown, labelled "not
  investment advice"). It is a reproducible rule-based read, not an opaque
  recommendation. Each ticker also carries two **copy-paste prompts** pre-filled
  with the readings (and that mechanical read) for a deeper, fundamentals-aware
  analysis in the user's *own* AI assistant.
- **Named signals + notification.** `compute_signals` detects events that fire
  on the latest bar — golden/death cross, RSI crossing 30/70, reclaiming/losing
  the 50-day, new 52-week high/low. New signals (deduped via
  `meta.emitted_signal_keys`) are surfaced in `meta.new_signals`;
  `notify_signals.py` opens a GitHub **issue** per new signal (which emails repo
  watchers). Runs as `python3 -m congress.notify_signals` — module form, so the
  package's `http.py` doesn't shadow stdlib `http`. A burst (> 8) collapses into
  one summary issue.
- **Snapshot, not real-time; not advice.** Values are the previous session's
  daily close. The indicator math and signal detection are pure stdlib and
  fixture-tested offline (`tests/congress/test_indicators.py`,
  `test_ai_cli.py`). The committed `ai-indicators.json` ships as clearly-labelled
  `_sample` data until the first live refresh overwrites it.

## Morning report (`daily_report.py` → GitHub issue email)

`congress daily_report` (run as `python3 -m congress.daily_report`) composes a
short morning digest and delivers it **(1) by direct email via SMTP** (primary
— set `SMTP_USER`/`SMTP_PASS` secrets, e.g. a Gmail address + App Password;
optional `SMTP_HOST`/`SMTP_PORT`/`REPORT_EMAIL_TO` default to Gmail:587 and the
sender) and **(2) as a dated GitHub issue** (archive + flip state, assigned to
the owner). The digest has three sections: the AI **buy/sell/hold scorecard**
(`indicators.ai_score`, mirroring the page's `aiScore`), **signals overnight**
(new mechanical signals + tickers whose rating flipped vs. yesterday), and
**new congressional disclosures** (filed in the last few days). It closes the
previous day's report issue and records the issue number + ratings in
`congress/report_state.json` for the next run's diff. The daily Action runs it
before the slow price step (guarded to the schedule or the `report` dispatch
input), timed via the `06:50 UTC` cron to land near **9am Madrid** (UTC cron
ignores DST, so the local time drifts ±1h). Pure stdlib except the GitHub API
call; `build_report` is fixture-tested offline. It is **not investment advice** —
the disclaimer rides at the top of every issue.

## Data-honesty constraints (by law, not by us)

- Filings may lag the trade by **30–45 days**.
- Amounts are **brackets** ($1,001–$15,000 … $50,000,001+), never exact.
- Trades may belong to a spouse (SP), joint account (JT) or dependent child (DC).

## Layout

- `normalize.py` — `Trade` schema, bracket/type/date parsing, name
  canonicalization, roster join. Pure stdlib.
- `senate.py` / `house.py` / `oge.py` — listing + parsing per chamber
  (`oge.py` covers the executive-branch 278-T). Parsers are pure functions of
  `str`/`bytes` (fixture-testable offline).
- `holdings.py` — annual-report **holdings** (real portfolio) parser for the
  featured members: House Schedule A (text PDF) + Senate annual report (HTML).
- `oge_filings.json` — curated list of the President's 278-T PDFs by UNID
  (he is not in any browsable OGE view). Append new filings here.
- `http.py` — the only module importing `requests`: shared UA, retries,
  ≥1 s spacing between requests.
- `pipeline.py` — incremental orchestration: diff filings against
  `state.json`, fetch only new ones, dedupe by trade id, prune to the
  current + previous calendar year, write diff-friendly JSON (one trade per
  line).
- `cli.py` — `python3 -m congress …` entry point.
- `members.json` — roster (party/state/district + filer-name aliases).
  Regenerate the full chamber roster with `python3 -m congress roster`
  (downloads `unitedstates/congress-legislators`); hand-curated aliases are
  preserved.
- `featured.json` — the watchlist strip on the page.
- `state.json` — processed filing IDs (generated; do not hand-edit).

## Usage

```bash
# offline tests — no network, no third-party deps
python3 -m unittest discover -s tests/congress -p 'test_*.py'

# live fetch (pip install -r congress/requirements.txt first)
python3 -m congress fetch                 # full incremental run
python3 -m congress fetch --limit 25      # cautious capped run
python3 -m congress fetch --dry-run       # list what would be fetched
python3 -m congress senate --debug-dump d # one chamber, save raw payloads
python3 -m congress parse-ptr file.html   # parse a local filing, no network
```

## The daily Action & live iteration

`.github/workflows/congress-trades.yml` runs the offline tests, then
`python3 -m congress fetch`, and commits `docs/data/congress-trades.json` +
`state.json` only when they changed. `workflow_dispatch` accepts a `limit`
input for cautious runs; failed runs upload `fetch.log` and the
`--debug-dump` payloads as artifacts.

The dev sandbox used to build this cannot reach the government domains, so
the parsers were written against `tests/congress/fixtures/`. When a live run
surprises us (eFD CSRF details, House PDF layout variance), the loop is:
grab the run's debug artifacts → fix the parser → update the fixtures so the
tests encode reality → push. For that loop, temporarily add a `push` trigger
for the development branch to the workflow (capped with `--limit 25`) and
remove it again before merging to `main`.

Known simplification: amendment filings are treated as separate filings
(deduped by filing id only), so an amended trade can appear twice — once per
filing — each linked to its own official document.
