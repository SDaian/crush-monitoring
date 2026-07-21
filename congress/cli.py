"""Command-line interface for the congressional trade tracker.

Examples
--------
Incremental fetch of both chambers (what the daily Action runs):

    python3 -m congress fetch

Cautious first live run, saving raw payloads for debugging:

    python3 -m congress fetch --limit 25 --debug-dump /tmp/congress-debug

Parse a local fixture / downloaded filing without any network:

    python3 -m congress parse-ptr tests/congress/fixtures/senate_ptr_sample.html

Regenerate the full member roster (downloads congress-legislators):

    python3 -m congress roster
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from . import house, oge, pipeline, senate
from .normalize import MEMBERS_PATH, prune_cutoff

LEGISLATORS_URL = (
    "https://unitedstates.github.io/congress-legislators/legislators-current.json"
)


# ---------------------------------------------------------------------------
# Chamber sources (network wiring; the pipeline itself is network-free)
# ---------------------------------------------------------------------------

def _dump(debug_dir: Path | None, name: str, payload: str | bytes) -> None:
    if debug_dir is None:
        return
    debug_dir.mkdir(parents=True, exist_ok=True)
    path = debug_dir / name
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(payload, encoding="utf-8")


def _us_date(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%m/%d/%Y")


def make_senate_source(
    session, cutoff_iso: str, debug_dir: Path | None
) -> pipeline.ChamberSource:
    def list_filings():
        senate.accept_disclaimer(session)
        return senate.search_ptrs(session, date_from=_us_date(cutoff_iso))

    def fetch_trades(ref):
        if ref.is_paper:
            raise pipeline.PaperFiling(ref.url)
        html = senate.fetch_ptr_html(session, ref)
        _dump(debug_dir, f"senate-{ref.filing_id}.html", html)
        return senate.parse_ptr_html(html, ref)

    return pipeline.ChamberSource(
        chamber="senate",
        list_filings=list_filings,
        fetch_trades=fetch_trades,
        ref_id=lambda r: r.filing_id,
        ref_member=lambda r: r.name,
        ref_filing_date=lambda r: r.filed_date,
        ref_url=lambda r: r.url,
    )


def make_house_source(
    session, cutoff_iso: str, today: date, debug_dir: Path | None
) -> pipeline.ChamberSource:
    def list_filings():
        cutoff_year = int(cutoff_iso[:4])
        refs = []
        for year in range(cutoff_year, today.year + 1):
            tsv = house.fetch_index(session, year)
            _dump(debug_dir, f"house-index-{year}.txt", tsv)
            refs.extend(house.parse_index(tsv, year))
        return refs

    def fetch_trades(ref):
        pdf = house.fetch_ptr_pdf(session, ref)
        text = house.extract_pdf_text(pdf)
        if not text:
            raise pipeline.PaperFiling(ref.url)
        _dump(debug_dir, f"house-{ref.doc_id}.txt", text)
        return house.parse_ptr_text(text, ref)

    return pipeline.ChamberSource(
        chamber="house",
        list_filings=list_filings,
        fetch_trades=fetch_trades,
        ref_id=lambda r: r.doc_id,
        ref_member=lambda r: r.name,
        ref_filing_date=lambda r: r.filing_date,
        ref_url=lambda r: r.url,
    )


def make_executive_source(
    session, debug_dir: Path | None
) -> pipeline.ChamberSource:
    def list_filings():
        return oge.list_filings()

    def fetch_trades(ref):
        resp = oge.polite_get(
            session, ref.url, headers={"User-Agent": oge.BROWSER_UA}
        )
        text = oge.extract_pdf_text(resp.content)
        if not text.strip():
            raise pipeline.PaperFiling(ref.url)
        _dump(debug_dir, f"executive-{ref.unid}.txt", text)
        return oge.parse_transactions(
            text, unid=ref.unid, source_url=ref.url, filing_date=ref.filing_date
        )

    return pipeline.ChamberSource(
        chamber="executive",
        list_filings=list_filings,
        fetch_trades=fetch_trades,
        ref_id=lambda r: r.unid,
        ref_member=lambda r: oge.FILER_NAME,
        ref_filing_date=lambda r: r.filing_date,
        ref_url=lambda r: r.url,
    )


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def _cmd_fetch(args: argparse.Namespace) -> int:
    from .http import make_session

    today = datetime.now(timezone.utc).date()
    cutoff = prune_cutoff(today)
    debug_dir = Path(args.debug_dump) if args.debug_dump else None
    session = make_session()
    sources = []
    if args.chamber in ("both", "senate"):
        sources.append(make_senate_source(session, cutoff, debug_dir))
    if args.chamber in ("both", "house"):
        sources.append(make_house_source(session, cutoff, today, debug_dir))
    if args.chamber in ("both", "executive"):
        sources.append(make_executive_source(session, debug_dir))
    result = pipeline.run(
        sources,
        today=today,
        output_path=Path(args.output),
        state_path=Path(args.state),
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print(
        f"fetched={result.fetched} new_trades={result.new_trades} "
        f"paper={result.paper_skips} parse_errors={result.parse_errors} "
        f"recovered={result.recovered_errors} pruned={result.pruned_trades} "
        f"changed={result.changed}"
    )
    return 0


def _cmd_parse_ptr(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if path.suffix == ".html":
        ref = senate.SenateFilingRef(
            filing_id="local", name=args.member, filed_date="1970-01-01",
            url=f"file://{path}", is_paper=False, title="local file",
        )
        trades = senate.parse_ptr_html(path.read_text(encoding="utf-8"), ref)
    elif path.suffix in (".txt", ".pdf"):
        ref = house.HouseFilingRef(
            doc_id="local", name=args.member, state=None, district=None,
            filing_date="1970-01-01", year=1970, url=f"file://{path}",
        )
        if path.suffix == ".pdf":
            text = house.extract_pdf_text(path.read_bytes())
            if not text:
                print("no text layer (scanned/paper filing)", file=sys.stderr)
                return 1
        else:
            text = path.read_text(encoding="utf-8")
        trades = house.parse_ptr_text(text, ref)
    else:
        print(f"unsupported file type: {path.suffix}", file=sys.stderr)
        return 2
    print(json.dumps([t.to_dict() for t in trades], indent=2, ensure_ascii=False))
    return 0


def _cmd_roster(args: argparse.Namespace) -> int:
    from .http import make_session, polite_get

    data = polite_get(make_session(), LEGISLATORS_URL).json()
    existing = json.loads(MEMBERS_PATH.read_text(encoding="utf-8"))
    by_name = {m["name"]: m for m in existing["members"]}
    party_map = {"Democrat": "D", "Republican": "R", "Independent": "I"}
    members = []
    seen_names = set()
    for leg in data:
        term = leg["terms"][-1]
        name_parts = leg["name"]
        first = name_parts.get("first", "")
        last = name_parts.get("last", "")
        middle = name_parts.get("middle")
        nickname = name_parts.get("nickname")
        name = name_parts.get("official_full", f"{first} {last}")
        chamber = "senate" if term["type"] == "sen" else "house"
        state = term.get("state")
        entry = {
            "name": name,
            "chamber": chamber,
            "party": party_map.get(term.get("party"), term.get("party")),
            "state": state,
        }
        if chamber == "house" and term.get("district") is not None:
            entry["district"] = f"{state}-{term['district']}"
        # Filers mix legal names, nicknames and middle names across eFD and
        # the Clerk index, so alias every combination the source data gives.
        aliases = {
            f"{last}, {first}",
            f"{first} {last}",
        }
        if middle:
            aliases.update({f"{first} {middle} {last}", f"{middle} {last}"})
        if nickname:
            aliases.update({f"{nickname} {last}", f"{last}, {nickname}"})
            if middle:
                aliases.add(f"{nickname} {middle} {last}")
        aliases.update(by_name.get(name, {}).get("aliases", []))
        aliases.discard(name)
        entry["aliases"] = sorted(aliases)
        members.append(entry)
        seen_names.add(name)
    # Preserve hand-curated entries that the download does not include
    # (e.g. seed aliases for members missing from legislators-current).
    for name, entry in by_name.items():
        if name not in seen_names:
            members.append(entry)
    members.sort(key=lambda m: m["name"])
    MEMBERS_PATH.write_text(
        json.dumps(
            {"_comment": existing["_comment"], "members": members},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(members)} members to {MEMBERS_PATH}")
    return 0


DEFAULT_RETURNS = pipeline.REPO_ROOT / "docs" / "data" / "returns.json"
DEFAULT_HOLDINGS = pipeline.REPO_ROOT / "docs" / "data" / "holdings.json"
DEFAULT_AI = pipeline.REPO_ROOT / "docs" / "data" / "ai-indicators.json"

# Keep the dedup memory bounded — signals older than this are pruned from the
# emitted set (a golden cross from a year ago will never re-fire anyway).
AI_EMITTED_KEEP = 400


def _cmd_holdings(args: argparse.Namespace) -> int:
    """Build real stock-holdings composition for featured members from their
    latest annual financial-disclosure report (House Schedule A / Senate
    annual). Individual stocks only; scanned/paper reports are marked
    unavailable-with-link."""
    from . import holdings, senate
    from .http import make_session
    from .normalize import Roster, load_featured

    session = make_session()
    roster = Roster.load()
    featured = load_featured()
    today = datetime.now(timezone.utc).date()
    years = [today.year, today.year - 1, today.year - 2]
    senate_ready = False
    out: dict = {}

    for name in featured:
        entry = roster.find(name) or {}
        # Key by the roster-resolved display name so it matches the page's
        # DATA.meta.featured (which is also roster-resolved), e.g.
        # "Dave McCormick" → "David McCormick".
        display = entry.get("name", name)
        chamber = entry.get("chamber")
        last = display.split()[-1]
        state = entry.get("state")
        rec: dict = {"chamber": chamber, "available": False, "stocks": []}
        try:
            if chamber == "house":
                ref = holdings.house_latest_annual(session, last, state, years)
            elif chamber == "senate":
                if not senate_ready:
                    senate.accept_disclaimer(session)
                    senate_ready = True
                ref = holdings.senate_latest_annual(session, last)
            else:
                ref = None  # executive (scanned OGE 278) / unknown
            if ref:
                rec["source_url"] = ref.url
                rec["filing_date"] = ref.filing_date
                rec["report_year"] = ref.report_year
                stocks = holdings.fetch_holdings(session, ref, member=display)
                rec["stocks"] = [h.to_dict() for h in stocks]
                rec["available"] = bool(stocks)
        except Exception as exc:  # one member must not abort the whole run
            rec["error"] = str(exc)
        out[display] = rec
        print(
            f"{display}: {chamber or '?'} "
            f"{'available' if rec['available'] else 'unavailable'} "
            f"({len(rec['stocks'])} stocks)"
        )

    if not any(r["available"] for r in out.values()):
        print(
            "::warning::no member holdings parsed — keeping existing holdings.json"
        )
        return 0
    payload = {
        "meta": {
            "_comment": (
                "Real stock holdings (individual equities only) from each "
                "featured member's latest ANNUAL financial-disclosure report "
                "(House Schedule A / Senate annual). Value is the year-end "
                "STOCK Act bracket, not exact. An annual snapshot, not "
                "real-time; scanned/paper reports are marked unavailable. "
                "Generated by congress/holdings.py; do not edit by hand."
            ),
            "generated_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        },
        "holdings": out,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    n_avail = sum(1 for r in out.values() if r["available"])
    print(f"wrote holdings for {n_avail}/{len(out)} featured members → {path}")
    return 0


DEFAULT_LANDING_DATA = pipeline.REPO_ROOT / "landing" / "src" / "data"


def _cmd_landing(args: argparse.Namespace) -> int:
    """Regenerate the Capitol Ledger landing page's data files (feed + stats)
    from the committed trades JSON. Pure local transform — no network."""
    from . import landing_data

    trades = json.loads(Path(args.trades).read_text(encoding="utf-8"))["trades"]
    # Holdings feed the /members pages' estimated-portfolio section; absent or
    # unreadable holdings just skip that section (member pages still render).
    holdings: dict = {}
    holdings_path = Path(args.holdings)
    if holdings_path.exists():
        try:
            holdings = json.loads(holdings_path.read_text(encoding="utf-8")).get(
                "holdings", {}
            )
        except (ValueError, OSError):
            holdings = {}
    today = datetime.now(timezone.utc).date()
    rows, stats = landing_data.write_files(trades, Path(args.output), today)
    members = landing_data.write_member_files(trades, holdings, Path(args.output))
    print(
        f"landing data: {rows} feed rows; {stats['tradesThisYear']} trades "
        f"in {stats['year']}, est ${stats['estVolumeThisYearUsd']:,} vol, "
        f"{stats['pctFiledLate']}% late; {len(members)} member pages → {args.output}"
    )
    return 0


def _cmd_analytics(args: argparse.Namespace) -> int:
    """Print the site's Vercel Web Analytics traffic summary (the same block
    the morning report embeds). No-op message if VERCEL_TOKEN isn't set."""
    from . import analytics

    token, project_id, _ = analytics.config()
    if not token or not project_id:
        print(
            f"::warning::{analytics.ENV_TOKEN}/{analytics.ENV_PROJECT} not set "
            "— skipping analytics (report omits the traffic block)"
        )
        return 0
    today = datetime.now(timezone.utc).date().isoformat()
    summary = analytics.daily_summary(today, window_days=args.days)
    if not summary:
        print("analytics: no data returned (check token/project or API access)")
        return 0
    md, _ = analytics.format_block(summary)
    print(md)
    return 0


FEATURED_TICKERS = ["MU", "INTC", "NVDA", "TSM", "AMD", "AVGO", "TSLA", "MSFT"]


def _cmd_prices(args: argparse.Namespace) -> int:
    """Estimate 'return since buy' for the priceable disclosed buys."""
    from . import prices

    key = prices.api_key()
    if not key:
        print(
            f"::warning::{prices.ENV_KEY} not set — skipping price refresh, "
            "keeping existing returns.json"
        )
        return 0

    def redact(text):  # never let the key reach logs (it rides in the URL)
        return str(text).replace(key, "***")

    trades = json.loads(Path(args.trades).read_text(encoding="utf-8"))["trades"]
    # Free tier is 800 calls/day, 8/min — price the featured + most-traded
    # names (where the volume is), not the whole long tail.
    tickers = prices.select_tickers(trades, FEATURED_TICKERS, args.top)
    if args.limit:
        tickers = tickers[: args.limit]
    print(f"pricing {len(tickers)} tickers via Twelve Data (8/min)…")
    session = prices.make_session()
    series_by_ticker = {}
    unlisted = 0
    for i, tk in enumerate(tickers, 1):
        try:
            raw = prices.fetch_raw(session, tk, key)
        except Exception as exc:  # a single bad ticker must not abort the run
            print(f"  {tk}: fetch error: {redact(exc)}")
            continue
        series = prices.PriceSeries(prices.parse_history(raw))
        if series:
            series_by_ticker[tk] = series
        else:
            unlisted += 1
            if unlisted <= 3:  # surface why a ticker prices as empty (ops aid)
                head = redact(" ".join(raw.split())[:160])
                print(f"  [debug] {tk} empty; body: {head!r}")
        if i % 20 == 0:
            print(f"  priced {i}/{len(tickers)} tickers…")

    returns, price_map, stats = prices.compute_returns(trades, series_by_ticker)
    stats["unlisted_tickers"] = unlisted
    stats["priced_tickers_of"] = len(tickers)
    if not returns:
        # A total miss means the source is unreachable/misconfigured, not that
        # the world has no returns. Never overwrite a good returns.json with an
        # empty one — leave the last committed file (or the sample) in place.
        print(
            f"::warning::priced 0/{stats['total_buys']} buys — price source "
            "unreachable or key invalid; keeping existing returns.json"
        )
        return 0
    payload = {
        "meta": {
            "_comment": (
                "Estimated stock performance since each disclosed BUY. NOT a "
                "member's realized profit — holding period, later sells, "
                "dividends and position size are unknown, and entry uses the "
                "trade date's close, not the fill price. Only the featured + "
                "most-traded tickers are priced. Generated by "
                "congress/prices.py; do not edit by hand."
            ),
            "generated_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "source": "twelvedata.com",
            **stats,
        },
        "prices": price_map,
        "returns": returns,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"priced {stats['priced_buys']}/{stats['total_buys']} buys across "
        f"{stats['tickers']} tickers ({unlisted} unlisted) → {out}"
    )
    return 0


def _load_prev_emitted(path: Path) -> set[str]:
    """The set of signal keys we've already notified on, from the last run's
    committed output file (empty if the file is missing/unreadable/sample)."""
    try:
        prev = json.loads(path.read_text(encoding="utf-8"))
        return set(prev.get("meta", {}).get("emitted_signal_keys") or [])
    except (OSError, ValueError):
        return set()


def _cmd_ai(args: argparse.Namespace) -> int:
    """Compute daily technical indicators + mechanical signals for the AI
    universe, writing docs/data/ai-indicators.json. Indicators only — never a
    buy/sell/hold verdict. New signals (not previously emitted) are surfaced in
    meta.new_signals for the workflow's notification step."""
    from . import indicators, prices

    key = prices.api_key()
    if not key:
        print(
            f"::warning::{prices.ENV_KEY} not set — skipping AI indicators, "
            "keeping existing ai-indicators.json"
        )
        return 0

    def redact(text):  # the key rides in the request URL; never let it log
        return str(text).replace(key, "***")

    out_path = Path(args.output)
    prev_emitted = _load_prev_emitted(out_path)
    session = prices.make_session()
    tickers: dict[str, dict] = {}
    new_signals: list[dict] = []
    emitted = set(prev_emitted)
    universe = indicators.AI_TICKERS
    print(f"computing indicators for {len(universe)} AI tickers via Twelve Data (8/min)…")
    for spec in universe:
        tk, name = spec["ticker"], spec["name"]
        try:
            rows = indicators.parse_series(prices.fetch_raw(session, tk, key))
        except Exception as exc:  # one bad ticker must not abort the run
            print(f"  {tk}: fetch error: {redact(exc)}")
            continue
        ind = indicators.compute_indicators(rows)
        if not ind:
            print(f"  {tk}: no price history (unlisted?) — skipped")
            continue
        sigs = indicators.compute_signals(rows)
        rec = {"name": name, **ind, "signals": sigs}
        tickers[tk] = rec
        for s in sigs:
            k = indicators.signal_key(tk, s)
            if k not in prev_emitted:
                new_signals.append({"ticker": tk, "name": name, **s})
            emitted.add(k)
        tag = f" · {len(sigs)} signal(s)" if sigs else ""
        print(f"  {tk}: {ind['price']} RSI {ind['rsi14']}{tag}")

    if not tickers:
        print(
            "::warning::computed 0 AI tickers — price source unreachable or "
            "key invalid; keeping existing ai-indicators.json"
        )
        return 0

    # Bound the dedup memory: keep the most recent keys by their bar date.
    emitted = set(sorted(emitted, key=lambda k: k.rsplit("|", 1)[-1])[-AI_EMITTED_KEEP:])
    payload = {
        "meta": {
            "_comment": (
                "Daily mechanical technical indicators (RSI, moving averages, "
                "volume, 52-week range) + named signals for an AI-adjacent "
                "ticker universe. INDICATORS ONLY — never a buy/sell/hold "
                "recommendation; a daily snapshot, not real-time; not "
                "investment advice. Generated by congress/indicators.py via "
                "the `ai` CLI; do not edit by hand."
            ),
            "generated_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "source": "twelvedata.com",
            "new_signals": new_signals,
            "emitted_signal_keys": sorted(emitted),
        },
        "tickers": tickers,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote indicators for {len(tickers)}/{len(universe)} AI tickers, "
        f"{len(new_signals)} new signal(s) → {out_path}"
    )
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="congress",
        description=(
            "Congressional stock-trade tracker (official Senate eFD + House "
            "Clerk disclosures)."
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Incremental fetch of new PTR filings.")
    fetch.add_argument("--chamber",
                       choices=("both", "senate", "house", "executive"),
                       default="both")
    fetch.add_argument("--limit", type=int, default=None,
                       help="Max new filings per chamber this run.")
    fetch.add_argument("--dry-run", action="store_true",
                       help="List what would be fetched; write nothing.")
    fetch.add_argument("--debug-dump", default=None, metavar="DIR",
                       help="Save raw payloads (search pages, PTR HTML/text).")
    fetch.add_argument("--output", default=str(pipeline.DEFAULT_OUTPUT))
    fetch.add_argument("--state", default=str(pipeline.DEFAULT_STATE))
    fetch.set_defaults(func=_cmd_fetch)

    for chamber in ("senate", "house", "executive"):
        alias = sub.add_parser(chamber, help=f"Fetch only the {chamber}.")
        alias.add_argument("--limit", type=int, default=None)
        alias.add_argument("--dry-run", action="store_true")
        alias.add_argument("--debug-dump", default=None, metavar="DIR")
        alias.add_argument("--output", default=str(pipeline.DEFAULT_OUTPUT))
        alias.add_argument("--state", default=str(pipeline.DEFAULT_STATE))
        alias.set_defaults(func=_cmd_fetch, chamber=chamber)

    parse = sub.add_parser(
        "parse-ptr",
        help="Parse a local PTR file (.html senate, .txt/.pdf house) to JSON.",
    )
    parse.add_argument("file")
    parse.add_argument("--member", default="Local Fixture",
                       help="Member name to stamp on the parsed trades.")
    parse.set_defaults(func=_cmd_parse_ptr)

    roster = sub.add_parser(
        "roster",
        help="Regenerate members.json from unitedstates/congress-legislators.",
    )
    roster.set_defaults(func=_cmd_roster)

    prices_p = sub.add_parser(
        "prices",
        help="Estimate return-since-buy from Stooq daily closes.",
    )
    prices_p.add_argument("--trades", default=str(pipeline.DEFAULT_OUTPUT))
    prices_p.add_argument("--output", default=str(DEFAULT_RETURNS))
    prices_p.add_argument("--top", type=int, default=100,
                          help="Price featured + this many most-traded tickers.")
    prices_p.add_argument("--limit", type=int, default=None,
                          help="Hard cap on tickers priced this run (testing).")
    prices_p.set_defaults(func=_cmd_prices)

    holdings_p = sub.add_parser(
        "holdings",
        help="Build real stock holdings for featured members from annual reports.",
    )
    holdings_p.add_argument("--output", default=str(DEFAULT_HOLDINGS))
    holdings_p.set_defaults(func=_cmd_holdings)

    ai_p = sub.add_parser(
        "ai",
        help="Compute AI-universe technical indicators + signals (Twelve Data).",
    )
    ai_p.add_argument("--output", default=str(DEFAULT_AI))
    ai_p.set_defaults(func=_cmd_ai)

    landing_p = sub.add_parser(
        "landing",
        help="Regenerate the landing page's feed + stats data files.",
    )
    landing_p.add_argument("--trades", default=str(pipeline.DEFAULT_OUTPUT))
    landing_p.add_argument("--holdings", default=str(DEFAULT_HOLDINGS))
    landing_p.add_argument("--output", default=str(DEFAULT_LANDING_DATA))
    landing_p.set_defaults(func=_cmd_landing)

    analytics_p = sub.add_parser(
        "analytics",
        help="Print the site's Vercel Web Analytics traffic summary.",
    )
    analytics_p.add_argument("--days", type=int, default=7,
                             help="Trailing window in days (default 7).")
    analytics_p.set_defaults(func=_cmd_analytics)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
