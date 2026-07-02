# congress/ — congressional stock-trade fetcher

Scrapes Periodic Transaction Reports (PTRs) from the two official sources,
normalizes them into one schema, and accumulates them into
`docs/data/congress-trades.json` for the Pages tracker (`docs/trades.html`).

## Sources (official only)

| Chamber | Listing | Filing documents |
|---|---|---|
| Senate | `efdsearch.senate.gov` — disclaimer POST (CSRF) then the DataTables-style JSON search (`/search/report/data/`, report type 11 = PTR) | Electronic PTRs are HTML tables; paper filings (`/search/view/paper/…`) are scans |
| House | `disclosures-clerk.house.gov` — yearly index ZIP `public_disc/financial-pdfs/<YEAR>FD.zip` (TSV; FilingType `P` = PTR) | `public_disc/ptr-pdfs/<YEAR>/<DocID>.pdf`; e-filed PTRs are text PDFs, paper ones are scans |

Paper/scanned filings are never parsed: they are recorded in
`skipped_filings` with a link and surfaced on the page. Parse-error filings
are also skipped-with-link but are **retried on every run** (they are not
marked processed), so they self-heal after a parser fix.

## Return since buy (`prices.py` → `docs/data/returns.json`)

For every disclosed **buy** of a listed US equity, `congress prices` estimates
how the stock has performed since the trade date, using the free Yahoo Finance chart API (JSON, no API key). Per buy it stores the
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

**Status — live feed not yet connected.** Both free keyless feeds block GitHub
Actions' shared IPs: Stooq serves a JavaScript anti-bot page, and Yahoo 429s
the runner even with a cookie+crumb session. So `prices` currently prices
nothing from CI; the writer detects a total miss and **keeps the existing
`returns.json`** rather than clobbering it, and `docs/data/returns.json` ships
a clearly-labelled **illustrative sample** (the page shows a placeholder
banner). Wiring a real feed means a keyed provider (e.g. Twelve Data / Tiingo)
via a repo secret, scoped to the most-traded tickers to fit the free quota —
tracked as follow-up.

## Data-honesty constraints (by law, not by us)

- Filings may lag the trade by **30–45 days**.
- Amounts are **brackets** ($1,001–$15,000 … $50,000,001+), never exact.
- Trades may belong to a spouse (SP), joint account (JT) or dependent child (DC).

## Layout

- `normalize.py` — `Trade` schema, bracket/type/date parsing, name
  canonicalization, roster join. Pure stdlib.
- `senate.py` / `house.py` — listing + parsing per chamber. Parsers are pure
  functions of `str`/`bytes` (fixture-testable offline).
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
