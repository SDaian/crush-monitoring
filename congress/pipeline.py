"""Incremental orchestration: list filings, fetch new ones, merge, prune, write.

The pipeline is chamber-agnostic: each chamber is wired in as a
``ChamberSource`` (see ``congress.cli``), so tests can drive the whole
incremental flow with stub sources and no network.

Output file layout (``docs/data/congress-trades.json``): ``meta`` is
pretty-printed and each trade is one line, so daily auto-commits produce
readable per-trade diffs while staying valid JSON.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from .normalize import (
    Roster,
    Trade,
    enrich,
    enrich_dict,
    load_featured,
    prune_cutoff,
    trade_sort_key,
)

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "data" / "congress-trades.json"
DEFAULT_STATE = PACKAGE_DIR / "state.json"


# A source whose listing has failed on two different days is paused, not a
# blip: the site says so and the morning report flags it. One bad morning
# stays in the Action log only.
PAUSE_DAYS = 1
SOURCE_LABELS = {"senate": "Senate", "house": "House",
                 "executive": "Executive branch"}


def track_sources(state: dict, attempted: list[str], failed: list[str],
                  today: date) -> None:
    """Record in ``state["sources"]`` the first day each source's listing
    failed; a success clears it. Pure on ``state``.

    A failure is otherwise a warning in one run's log, and a source can stay
    dark for weeks without anyone reading it (the Senate eFD began refusing
    the runner on 23 Oct 2026). The key is absent while every source works,
    so a healthy run leaves state.json unchanged.
    """
    status = state.setdefault("sources", {})
    for chamber in attempted:
        if chamber in failed:
            status.setdefault(chamber, {"failing_since": today.isoformat()})
        else:
            status.pop(chamber, None)
    if not status:
        del state["sources"]


def paused_sources(state: dict, trades: list[dict], today: date,
                   min_days: int = PAUSE_DAYS) -> list[dict]:
    """The sources failing for at least ``min_days`` days, with the newest
    filing we still show for each. Pure, so every surface states the same
    two facts: when the fetch began failing, and how current the data is."""
    out = []
    for chamber, s in sorted((state.get("sources") or {}).items()):
        since = s.get("failing_since")
        if not since or (today - date.fromisoformat(since)).days < min_days:
            continue
        newest = max((t["filing_date"] for t in trades
                      if t.get("chamber") == chamber and t.get("filing_date")),
                     default=None)
        out.append({"chamber": chamber,
                    "label": SOURCE_LABELS.get(chamber, chamber.title()),
                    "since": since, "newest": newest})
    return out


def pause_line(p: dict) -> str:
    """One sentence for the report: the outage and what it leaves showing."""
    line = (f"{p['label']}: our daily fetch from the official site has failed "
            f"since {p['since']}.")
    if p.get("newest"):
        line += f" The newest {p['label']} filing shown is {p['newest']}."
    return line


class PaperFiling(Exception):
    """Raised by a fetcher when the filing is a scan with no parseable text."""


_CID = re.compile(r"\(cid:\d+\)")


def unreadable(text: str) -> bool:
    """A text layer made of unmapped glyph codes is a scan for our purposes.

    pdfplumber writes "(cid:50)" for a glyph whose font carries no Unicode
    map. A page of them has text, so the scan test let it through as a parse
    error, retried every run for ever (Trump's 12-Aug-2026 278-T: a signature
    line and ~200 chars of codes). A real report with a stray code or two has
    hundreds of words, so the codes must at least match the words to count.
    """
    codes = len(_CID.findall(text))
    words = len(_CID.sub(" ", text).split())
    return codes > 0 and codes >= words


@dataclass
class ChamberSource:
    """One chamber's listing + fetching, injected by the CLI (or tests)."""

    chamber: str                                  # "senate" | "house"
    list_filings: Callable[[], list]              # → chamber-specific refs
    fetch_trades: Callable[[object], list[Trade]]  # ref → trades; raises
    #   PaperFiling for scans (permanent skip) or any other exception for a
    #   parse error (skipped now, retried on the next run).
    ref_id: Callable[[object], str]
    ref_member: Callable[[object], str]
    ref_filing_date: Callable[[object], str]      # ISO
    ref_url: Callable[[object], str]
    # ref → (report date ISO | None, version); version 0 is the original and
    # N is "Amendment N". Only for a source whose LISTING names the report an
    # amendment corrects (the Senate eFD). None: filings are taken as listed.
    ref_version: Callable[[object], tuple] | None = None


@dataclass
class RunResult:
    changed: bool
    fetched: int = 0
    new_trades: int = 0
    paper_skips: int = 0
    parse_errors: int = 0
    recovered_errors: int = 0
    pruned_trades: int = 0
    # Rows of an earlier version of a report, removed because a later
    # amendment restates the whole report (see apply_amendments).
    superseded_trades: int = 0
    # Chambers whose LISTING failed this run (a site outage or a refused
    # session). Their published filings stay as they are and the next run
    # retries; the other chambers still update.
    failed_sources: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_output(path: Path) -> dict:
    if not path.exists():
        return {"meta": {}, "trades": [], "skipped_filings": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("meta", {}).get("_sample"):
        # Fixture-derived placeholder committed before the first live run:
        # start fresh so no fake IDs linger in the real dataset.
        return {"meta": {}, "trades": [], "skipped_filings": []}
    return data


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"processed": {"senate": {}, "house": {}}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("processed", {})
    for chamber in ("senate", "house"):
        data["processed"].setdefault(chamber, {})
    return data


def dump_output(output: dict) -> str:
    """Valid JSON with pretty meta and one trade/skip per line (diff-friendly)."""
    compact = dict(separators=(",", ":"), ensure_ascii=False)

    def lines(items):
        return ",\n".join("  " + json.dumps(i, **compact) for i in items)

    parts = ['{\n"meta": ']
    parts.append(json.dumps(output["meta"], indent=1, ensure_ascii=False))
    parts.append(',\n"trades": [\n')
    parts.append(lines(output["trades"]))
    parts.append('\n],\n"skipped_filings": [\n')
    parts.append(lines(output["skipped_filings"]))
    parts.append("\n]\n}\n")
    return "".join(parts)


def save_state(state: dict, path: Path) -> None:
    state["_comment"] = (
        "Processed filing IDs (id -> filing date) so daily runs only fetch "
        "new filings. Generated by congress/pipeline.py; do not edit by hand."
    )
    path.write_text(
        json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Amendments
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Version:
    """One listed filing, seen as a version of a report."""

    filed: str               # ISO date the source received THIS document
    report_date: str | None  # ISO date of the report it is a version of
    number: int              # 0 = the original, N = "Amendment N"


# What a filer states about one trade. Two rows equal in all of these are the
# same statement, whichever document carries them.
_STATED = ("ticker", "asset", "asset_type", "type", "partial", "owner",
           "tx_date", "amount_lo", "amount_hi", "comment")
# The listing's title date can sit one day from the date on the document
# itself (a time-zone effect: McCormick's amendment is listed "for
# 03/06/2025" and its own page says 03/05/2025).
_TITLE_SLACK_DAYS = 1


def _stated(t: dict) -> tuple:
    return tuple(t.get(k) for k in _STATED)


def apply_amendments(trades: dict[str, dict], listed: dict[str, Version],
                     chamber: str,
                     log: Callable[[str], None] = print) -> tuple[int, int]:
    """Make each amended report count once, dated when it was first filed.

    An amendment is a full restatement of a report with corrections (a trade
    date, "Sale (Full)" to "Sale (Partial)", a missing ticker). Treated as a
    new filing it did two wrong things: every trade the correction left alone
    counted twice, and every row of the amendment carried the day the
    AMENDMENT arrived, so a report filed on time in May 2025 and corrected in
    August 2026 showed all its trades as filed 400 days late.

    For every amendment whose rows we hold, in ``trades`` (id → row, edited
    in place):

    * The rows of each earlier version of the same report are removed. An
      earlier version is a filing by the same member, with a lower version
      number, not filed later, whose title names the same report date (give
      or take ``_TITLE_SLACK_DAYS``), AND that shares at least half of the
      smaller document's rows with the amendment. The title alone is not
      enough: a member can file two reports on one day (Boozman does, every
      time), and only the content says which one an amendment corrects.
      Exact or refused: when a candidate exists and none shares enough, the
      rows all stay and a warning names the filing.
    * The amendment's rows take ``filing_date`` from the earliest version we
      held, or from the title's report date when we held none, and record the
      day the amendment arrived as ``amended``.

    The pass is idempotent: a second run finds nothing to remove and the
    dates already in place. Returns (rows removed, rows re-dated).
    """
    by_filing: dict[str, list[dict]] = defaultdict(list)
    for t in trades.values():
        if t.get("chamber") == chamber and t.get("filing_id") in listed:
            by_filing[t["filing_id"]].append(t)

    def gap(a: str, b: str) -> int:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)

    removed = redated = 0
    amendments = sorted(
        (fid for fid in by_filing if listed[fid].number > 0),
        key=lambda fid: (listed[fid].report_date or "", listed[fid].number,
                         listed[fid].filed, fid))
    for fid in amendments:
        v, rows = listed[fid], by_filing.get(fid)
        if not rows:
            continue  # removed earlier in this pass by a later amendment
        if not v.report_date:
            log(f"::warning::{chamber}:{fid} is an amendment whose title "
                "names no report date; left as listed")
            continue
        member = rows[0]["member"]
        mine = Counter(map(_stated, rows))
        candidates = [
            c for c, crows in by_filing.items()
            if c != fid and crows and crows[0]["member"] == member
            and listed[c].number < v.number and listed[c].filed <= v.filed
            and listed[c].report_date
            and gap(listed[c].report_date, v.report_date) <= _TITLE_SLACK_DAYS
        ]
        replaced = []
        for c in candidates:
            shared = sum((mine & Counter(map(_stated, by_filing[c]))).values())
            if 2 * shared >= min(len(rows), len(by_filing[c])):
                replaced.append(c)
        seen_before = "amended" in rows[0]  # dated by an earlier run
        if candidates and not replaced and not seen_before:
            # Said once, on the run that first reads the amendment. On every
            # later run the member's OTHER report of that day is still a
            # candidate that shares nothing, and that is the normal state.
            log(f"::warning::{chamber}:{fid} amends a report of "
                f"{v.report_date}, but no earlier filing by {member} for that "
                f"date shares its rows ({', '.join(sorted(candidates))}); "
                "nothing was removed")
        first_dates = [t["filing_date"] for c in replaced for t in by_filing[c]]
        if seen_before:
            first_dates.append(rows[0]["filing_date"])
        first = min(first_dates) if first_dates else v.report_date
        for c in replaced:
            for t in by_filing.pop(c):
                del trades[t["id"]]
                removed += 1
        for t in rows:
            if t["filing_date"] != first or t.get("amended") != v.filed:
                t["filing_date"] = first
                t["amended"] = v.filed
                redated += 1
    return removed, redated


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def invalid_trades(trades: list[dict]) -> list[dict]:
    """Rows that violate an invariant a disclosure bracket cannot break.

    Today that is an inverted amount range (`amount_hi < amount_lo`), which a
    House PTR produced when the form's "$200 late filing fee" boilerplate was
    mistaken for the bracket's upper bound. Pure and list-based so it is tested
    offline and can be reused as filings are re-parsed.
    """
    bad = []
    for t in trades:
        lo, hi = t.get("amount_lo"), t.get("amount_hi")
        if lo is not None and hi is not None and hi < lo:
            bad.append(t)
            continue
        # An executive 278-T discloses past trades, so a trade date after
        # the filing date is an OCR year misread, not a fact. Executive
        # ONLY: a House e-filed form with a future date says what the
        # filer typed, and re-parsing it would reproduce the same date
        # forever (an infinite re-download loop, not a repair).
        if (t.get("chamber") == "executive" and t.get("tx_date")
                and t.get("filing_date")
                and t["tx_date"] > t["filing_date"]):
            bad.append(t)
    return bad


def forget_filings(state: dict, output: dict, filing_ids: set[str]) -> int:
    """Drop `filing_ids` from the processed state and their trades from the
    output, so the next fetch re-downloads and re-parses them.

    Fixing a parser only helps future filings — `state["processed"]` means an
    already-seen document is never read again, so a bad row would otherwise
    stay published forever.
    """
    for chamber in state.get("processed", {}):
        state["processed"][chamber] = {
            i: d for i, d in state["processed"][chamber].items()
            if i not in filing_ids
        }
    before = len(output["trades"])
    output["trades"] = [
        t for t in output["trades"] if t.get("filing_id") not in filing_ids
    ]
    return before - len(output["trades"])


def run(
    sources: list[ChamberSource],
    *,
    today: date | None = None,
    output_path: Path = DEFAULT_OUTPUT,
    state_path: Path = DEFAULT_STATE,
    limit: int | None = None,
    log: Callable[[str], None] = print,
    dry_run: bool = False,
    generated_at: str | None = None,
    reparse_invalid: bool = False,
) -> RunResult:
    today = today or datetime.now(timezone.utc).date()
    cutoff = prune_cutoff(today)
    output = load_output(output_path)
    state = load_state(state_path)
    roster = Roster.load()
    result = RunResult(changed=False)

    if reparse_invalid:
        bad = invalid_trades(output["trades"])
        ids = {t["filing_id"] for t in bad if t.get("filing_id")}
        if ids:
            dropped = forget_filings(state, output, ids)
            log(
                f"reparse: {len(bad)} invalid rows across {len(ids)} filings — "
                f"dropped {dropped} trades, re-fetching those documents"
            )
        else:
            log("reparse: no invalid rows found")

    trades = {t["id"]: t for t in output["trades"]}
    skipped = {s["filing_id"]: s for s in output["skipped_filings"]}
    before = _content_key(output)
    state_before = json.dumps(state, sort_keys=True)
    # chamber → {filing id → Version}, for each source that listed this run
    # and names its amendments. Applied below, once the names are canonical.
    versions: dict[str, dict[str, Version]] = {}

    for source in sources:
        processed = state["processed"].setdefault(source.chamber, {})
        # One government site failing must not take the others down: a
        # refused Senate session once stopped the House and OGE fetches too,
        # and nothing was published for two runs. Keep this chamber's data,
        # say so in the Action log, and retry on the next run.
        try:
            listed = source.list_filings()
        except Exception as exc:  # network or protocol failure, not a parse error
            result.failed_sources.append(source.chamber)
            log(f"::warning::{source.chamber}: listing failed, keeping its "
                f"published filings and retrying next run — {exc}")
            continue
        refs = [
            r
            for r in listed
            if source.ref_filing_date(r) >= cutoff
            and source.ref_id(r) not in processed
        ]
        if limit is not None and len(refs) > limit:
            log(
                f"{source.chamber}: {len(refs)} new filings, "
                f"limiting to {limit} this run"
            )
            refs = refs[:limit]
        log(f"{source.chamber}: fetching {len(refs)} new filings")
        if dry_run:
            for ref in refs:
                log(
                    f"  would fetch {source.ref_id(ref)} "
                    f"({source.ref_member(ref)}, {source.ref_filing_date(ref)})"
                )
            continue
        for ref in refs:
            fid = source.ref_id(ref)
            result.fetched += 1
            try:
                new = source.fetch_trades(ref)
            except PaperFiling:
                skipped[fid] = _skip_entry(source, ref, "paper")
                processed[fid] = source.ref_filing_date(ref)
                result.paper_skips += 1
                continue
            except Exception as exc:  # parse error: skip now, retry next run
                skipped[fid] = _skip_entry(source, ref, "parse_error")
                result.parse_errors += 1
                log(f"  {source.chamber}:{fid} parse error: {exc}")
                continue
            if fid in skipped:  # a previously failed filing now parses
                del skipped[fid]
                result.recovered_errors += 1
            for trade in new:
                trades[trade.id] = enrich(trade, roster).to_dict()
                result.new_trades += 1
            processed[fid] = source.ref_filing_date(ref)
        if source.ref_version is not None:
            versions[source.chamber] = {
                source.ref_id(r): Version(source.ref_filing_date(r),
                                          *source.ref_version(r))
                for r in listed
            }

    # Re-enrich every stored trade so a roster refresh fills party/state on
    # trades ingested before the member existed in members.json. Skipped
    # filings get the same name normalization ("Rohit Khanna" → "Ro Khanna")
    # so the page can attribute them to featured members.
    for t in trades.values():
        enrich_dict(t, roster)
    for s in skipped.values():
        entry = roster.find(s["member"], chamber=s["chamber"])
        if entry:
            s["member"] = entry["name"]

    # An amended report counts once, dated when it was first filed. After the
    # re-enrich above, so "the same member" compares canonical names; before
    # the prune below, so a report first filed before the window leaves with
    # the rest of that year however late its amendment arrived.
    for chamber, listed_versions in versions.items():
        removed, redated = apply_amendments(trades, listed_versions, chamber, log)
        result.superseded_trades += removed
        if removed or redated:
            log(f"{chamber}: amended reports — removed {removed} rows of "
                f"superseded versions, re-dated {redated} rows to the first "
                "filing")

    # Prune everything (trades, skips, state) outside the two-year window.
    kept = {i: t for i, t in trades.items() if t["filing_date"] >= cutoff}
    result.pruned_trades = len(trades) - len(kept)
    trades = kept
    skipped = {i: s for i, s in skipped.items() if s["filing_date"] >= cutoff}
    for chamber in state["processed"]:
        state["processed"][chamber] = {
            i: d for i, d in state["processed"][chamber].items() if d >= cutoff
        }

    if not dry_run:
        track_sources(state, [s.chamber for s in sources],
                      result.failed_sources, today)
    output["trades"] = sorted(trades.values(), key=trade_sort_key)
    output["skipped_filings"] = sorted(
        skipped.values(), key=lambda s: (s["filing_date"], s["filing_id"]), reverse=True
    )
    result.changed = _content_key(output) != before
    if dry_run or not result.changed:
        log("no changes" if not result.changed else "dry run: not writing")
        # The output is unchanged, but `processed` may still have advanced
        # (a filing fetched fine and yielded rows identical to what is
        # already published). Without this save the filing is re-fetched
        # on every run forever, with each run reporting success.
        if not dry_run and json.dumps(state, sort_keys=True) != state_before:
            save_state(state, state_path)
            log("state updated (filings processed with no output changes)")
        return result

    output["meta"] = _build_meta(
        output, state, today, cutoff, generated_at, roster
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dump_output(output), encoding="utf-8")
    save_state(state, state_path)
    log(
        f"wrote {len(output['trades'])} trades "
        f"({result.new_trades} new, {result.pruned_trades} pruned, "
        f"{len(output['skipped_filings'])} skipped filings) to {output_path}"
    )
    return result


def _skip_entry(source: ChamberSource, ref, reason: str) -> dict:
    return {
        "chamber": source.chamber,
        "member": source.ref_member(ref),
        "filing_date": source.ref_filing_date(ref),
        "reason": reason,
        "filing_id": source.ref_id(ref),
        "source_url": source.ref_url(ref),
    }


def _content_key(output: dict) -> str:
    return json.dumps(
        [output["trades"], output["skipped_filings"]], sort_keys=True
    )


def _build_meta(
    output: dict,
    state: dict,
    today: date,
    cutoff: str,
    generated_at: str | None,
    roster: Roster,
) -> dict:
    prev_version = output.get("meta", {}).get("data_version", "")
    stamp = today.isoformat()
    serial = 1
    if prev_version.startswith(stamp + "."):
        serial = int(prev_version.rsplit(".", 1)[1]) + 1
    return {
        "_comment": (
            "Generated by congress/pipeline.py from official Senate eFD and "
            "House Clerk disclosures. Do not edit by hand. Amounts are the "
            "legal disclosure brackets; filings lag trades by 30-45 days by "
            "law."
        ),
        "generated_at": generated_at
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_version": f"{stamp}.{serial}",
        "window": {"from": cutoff, "to": today.isoformat()},
        "counts": {
            "trades": len(output["trades"]),
            "members": len({t["member"] for t in output["trades"]}),
            "filings_processed": sum(
                len(v) for v in state["processed"].values()
            ),
            "filings_skipped": len(output["skipped_filings"]),
        },
        # Resolve featured names to roster display names so the page's
        # exact-match member filter lines up with the trade rows.
        "featured": [
            (roster.find(name) or {"name": name})["name"]
            for name in load_featured()
        ],
    }
