# congress/ — the Capitol Ledger pipeline

Fetches trade disclosures from the three official sources, normalizes them
into one schema, and writes every data file the site and the morning email
read. Run as `python3 -m congress <command>`; `--help` lists them all.

The rules behind each choice below, with the incident that set each one,
are in [`CLAUDE.md`](../CLAUDE.md). This file says what each part does and
how to run it.

## Sources (official only)

| Chamber | Listing | Filing documents |
|---|---|---|
| Senate | `efdsearch.senate.gov`: a disclaimer POST (CSRF), then the JSON search (`/search/report/data/`, report type 11 = PTR) | Electronic PTRs are HTML tables; paper filings (`/search/view/paper/…`) are scans |
| House | `disclosures-clerk.house.gov`: the yearly index ZIP `public_disc/financial-pdfs/<YEAR>FD.zip` (TSV; FilingType `P` = PTR) | `public_disc/ptr-pdfs/<YEAR>/<DocID>.pdf`; e-filed PTRs are text PDFs, paper ones are scans |
| Executive (President) | `extapps2.oge.gov/201/Presiden.nsf`, OGE Form 278-T. The President is in no browsable OGE view, so his filings are listed by document UNID in `oge_filings.json` | `.../PAS+Index/<UNID>/$FILE/<name>.pdf`, scanned PDFs with an OCR text layer |

A source that fails to list is skipped for the run and keeps its published
filings; the others carry on. `pipeline.track_sources` records the first day
of a failure in `state.json`, and a source failing on two different days is
named on the site and at the top of the morning email.

Scanned filings, and text layers made only of unmapped glyph codes
(`(cid:N)`), are recorded as paper in `skipped_filings` with a link and never
retried. A filing with readable text that yields no rows is a parse error: it
is listed as skipped and **retried on every run**, so a parser fix heals it.
A fix does not reach rows already published; `fetch --reparse-invalid`
re-downloads the filings whose rows break an invariant.

Known limit: an amended filing is treated as a new filing, so an amended
trade can appear twice, once per document, each linked to its own filing.

## Executive 278-T (`oge.py` → chamber `executive`)

The 278-T is a scanned form with a noisy OCR layer (`5`→`S`, `0`→`O`,
`1`→`l`). `oge.parse_transactions` anchors on the regular
`<type> <date> No <amount>` tail of each row and snaps the amount to the
STOCK Act brackets, which corrects most OCR damage.

The early filings held only bonds; since June 2026 they also list stocks and
ETFs. The form has no ticker column, so `tickermatch.py` resolves each equity
name **exactly or not at all**: from the curated `OVERRIDES` map, then from
the name–ticker pairs in the House and Senate rows. A miss prints a
`::warning::`; add the name to `OVERRIDES` and the next run's retick pass
fills the ticker in, with no re-download.

To track a newly posted 278-T, append its `unid` and `filename` to
`oge_filings.json`.

## Holdings (`holdings.py` → `docs/data/holdings.json`)

A PTR discloses trades; positions live in the **annual** report. `congress
holdings` parses the individual stocks and options from each featured
member's latest annual report:

- **House**: the Schedule A text PDF (`[ST]` stock, `[OP]` option).
- **Senate**: the eFD annual report's Assets table (HTML).
- **Executive**: the OGE 278 is a scanned image, so it is link-only.

Each member carries a `reason` (`holdings.classify`): parsed, scanned, no
assets parsed, funds only, no filing, or error. "Funds only" is correct data,
not a gap. A fetch that fails keeps the member's published holdings.

The member pages roll the snapshot forward with every later trade
(`landing_data.rolled_holdings`): buys add, sells subtract, options expire.
Values are bracket midpoints, never share counts.

## Prices and returns (`prices.py` → `returns.json`, `performance.json`)

For every disclosed **buy** of a listed US equity, `congress prices` records
the stock's change since the trade date, beside the S&P 500's change over the
same window (`bench_pct`). `performance.py` turns that into each featured
member's "$1 in every buy vs $1 in the S&P" series. This is the stock's
move, **not** the member's profit: holding period, sells and position size
are unknown, and the entry is the trade date's close, not the fill price.

Data comes from Twelve Data (`CONGRESS_PRICES_KEY`, 800 calls/day, 8/min).
Only `prices.fetch_raw` touches the network. A total miss keeps the previous
files.

## Technical readings (`indicators.py`, `market.py` → `ai-indicators.json`)

`congress ai` computes a reading for every symbol that has a ticker page:
RSI(14), the 8/21 EMA pair, the 20/50/200-day averages, period returns,
relative volume, the 52-week range, 1-year volatility, and (when the plan
serves it) the next earnings date. Records flagged `featured` feed the
morning scorecard and the tracker's "Featured stocks" tab.

- **Seven votes.** `indicators.votes` decides one buy/hold/sell vote per
  check; `ai_score` counts them into a label; every surface shows the
  breakdown and "not investment advice". Volatility and the market reading
  never vote. Changing the vote set bumps `SCORE_VERSION`.
- **Named signals** (golden/death cross, RSI crossing 30/70, new 52-week
  high/low) on featured symbols go to `meta.new_signals`;
  `python3 -m congress.notify_signals` opens a GitHub issue for each (more
  than eight at once become one summary issue).
- **Market context** (`market.py`): the VIX when the plan serves it,
  otherwise our own 20-day realized volatility of SPY, labelled as such.
- `--skip-if-closed` skips the paced fetch when no new session has closed.

## Site data (`landing_data.py` → `landing/src/data/`)

`congress landing` writes everything the Astro site builds from: the feed
and stats, `/late`, `/what-congress-is-buying`, one JSON per member page and
ticker page (with their FAQ answers, holdings, committee seats and technical
read), `market.json`, and the indexes. A page file the run did not write is
deleted. `sectors.py` + `sectors.json` badge each stock with an industry and
list a member's trades in industries their committees oversee
(`committees.py`).

## Morning report (`daily_report.py`, `email_template.py`)

`python3 -m congress.daily_report` builds one payload and delivers it as:

- an email to the owner over SMTP (`SMTP_USER`, `SMTP_PASS`),
- the same email to subscribers through Buttondown (`buttondown.py`),
- a dated GitHub issue, assigned to the owner,
- `landing/src/data/report.json` and a dated copy, for `/report`.

Disclosures lead, then the featured scorecard, then overnight signals and
rating flips. "New" means not yet reported, inside a 45-day lookback. The
report sends once a day, and skips quiet days (no new close and no new
filing). Two separate traffic emails, daily and on Mondays weekly, come from
Vercel Web Analytics (`analytics.py`).

## Social drafts (`social.py`, `typefully.py`)

`congress social` turns notable new filings (a featured member, a bracket
floor of $1M or more, or more than 90 days late) into a card image and post
copy, and creates **unpublished** Typefully drafts for the owner to approve.
Live needs both `TYPEFULLY_API_KEY` and the variable `SOCIAL_LIVE=true`;
otherwise the run renders the cards as the `social-cards` artifact and writes
nothing. The card is attached automatically; if the upload fails the draft
carries an `[attach card: …]` note instead.

- Design: `social/card_template.html`; wording: `social/copy_template.txt`.
- State: `social_state.json` maps `chamber:filing_id` to its draft. Delete an
  entry to re-draft that filing.

## Search push (`indexnow.py`)

`congress indexnow` sends the day's changed, indexable pages to IndexNow
(Bing, Yandex and the engines they feed). The key in `landing/public/` is
public by design.

## Files in this folder

| File | Kind |
|---|---|
| `members.json` | Roster with filer-name aliases. `congress roster` rebuilds it and keeps the aliases. |
| `featured.json` | The featured members. Hand-maintained. |
| `oge_filings.json` | The President's 278-T documents. Hand-maintained. |
| `sectors.json` | Committee → industries and ticker → industry. Hand-maintained. |
| `state.json` | Processed filing ids and failing sources. Generated. |
| `report_state.json` | The last report: date, ratings, reported ids. Generated. |
| `social_state.json` | Drafted filings. Generated. |

Only `http.py` imports `requests`, and only the two `extract_pdf_text`
functions import `pdfplumber`. Every parser is stdlib-only, so the tests run
offline.

## Usage

```bash
# offline tests: no network, no third-party packages
python3 -m unittest discover -s tests/congress -p 'test_*.py'

# live commands (pip install -r congress/requirements.txt first)
python3 -m congress fetch --dry-run          # list what would be fetched
python3 -m congress fetch --limit 25         # a capped run
python3 -m congress senate --debug-dump d    # one source, save raw payloads
python3 -m congress parse-ptr file.html      # parse a local filing, no network
python3 -m congress landing                  # rebuild the site's data files
```

The development sandbox cannot reach the government sites, so parsers are
written against `tests/congress/fixtures/`. When a live run surprises us,
dispatch the workflow with a `limit`: that saves the extracted text of each
fetched filing to the run's `congress-fetch-debug` artifact. Fix the parser,
add the text as a fixture, and push.

## Data limits (by law, not by us)

- A filing may arrive 30 to 45 days after the trade.
- Amounts are brackets ($1,001–$15,000 … $50,000,001+), never exact.
- A trade may belong to a spouse (SP), a joint account (JT) or a dependent
  child (DC).
