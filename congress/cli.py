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

from . import house, pipeline, senate
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


def _cmd_prices(args: argparse.Namespace) -> int:
    """Estimate 'return since buy' for every priceable disclosed buy."""
    from . import prices

    trades = json.loads(Path(args.trades).read_text(encoding="utf-8"))["trades"]
    tickers = prices.distinct_buy_tickers(trades)
    if args.limit:
        tickers = tickers[: args.limit]
    session = prices.make_price_session()
    series_by_ticker = {}
    unlisted = 0
    for i, tk in enumerate(tickers, 1):
        try:
            raw = prices.fetch_raw(session, tk)
        except Exception as exc:  # a single bad ticker must not abort the run
            print(f"  {tk}: fetch error: {exc}")
            continue
        series = prices.PriceSeries(prices.parse_history(raw))
        if series:
            series_by_ticker[tk] = series
        else:
            unlisted += 1
            if unlisted <= 3:  # surface why a ticker prices as empty (ops aid)
                head = " ".join(raw.split())[:160]
                print(f"  [debug] {tk} ({prices.yahoo_symbol(tk)}) empty; body: {head!r}")
        if i % 25 == 0:
            print(f"  priced {i}/{len(tickers)} tickers…")

    returns, price_map, stats = prices.compute_returns(trades, series_by_ticker)
    stats["unlisted_tickers"] = unlisted
    if not returns:
        # A total miss means the price source is unreachable/blocked, not that
        # the world has no returns. Never overwrite a good returns.json with an
        # empty one — leave the last committed file (or the sample) in place.
        print(
            f"::warning::priced 0/{stats['total_buys']} buys — price source "
            "unreachable; keeping existing returns.json"
        )
        return 0
    payload = {
        "meta": {
            "_comment": (
                "Estimated stock performance since each disclosed BUY. NOT a "
                "member's realized profit — holding period, later sells, "
                "dividends and position size are unknown, and entry uses the "
                "trade date's close, not the fill price. Generated by "
                "congress/prices.py; do not edit by hand."
            ),
            "generated_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "source": "finance.yahoo.com",
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
    fetch.add_argument("--chamber", choices=("both", "senate", "house"),
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

    for chamber in ("senate", "house"):
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
    prices_p.add_argument("--limit", type=int, default=None,
                          help="Max distinct buy tickers to price (testing).")
    prices_p.set_defaults(func=_cmd_prices)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
