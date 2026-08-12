"""Which industry a symbol belongs to, and which industries a committee
oversees — so a member page can put the two side by side.

Pure stdlib, no network. The maps live in ``sectors.json`` and are OURS: no
official body publishes a committee-to-industry table, and the vendor sector
field is not available offline. So the module states its own coverage instead
of hiding it, and every surface that uses it must print two things: that the
grouping is ours, and how much of the member's trading it classifies.

The output is a coincidence of two public facts — a seat and a disclosed
trade. It is not a conflict of interest, and this module never says it is.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

SECTORS_PATH = Path(__file__).resolve().parent / "sectors.json"


def load(path: Path = SECTORS_PATH) -> dict:
    """The curated maps. A missing or broken file returns empty maps, and
    every surface then shows no sector line at all — a lost feature, never a
    failed build."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, AttributeError):
        return {"sectors": {}, "committees": {}, "tickers": {}}
    return {
        "sectors": data.get("sectors") or {},
        "committees": data.get("committees") or {},
        "tickers": data.get("tickers") or {},
    }


def normalize(ticker: str | None) -> str:
    """The symbol as the maps key it: upper case, no surrounding space."""
    return (ticker or "").strip().upper()


def ticker_sector(ticker: str | None, data: dict) -> str | None:
    """The sector key for a symbol, or None when we do not classify it."""
    return (data.get("tickers") or {}).get(normalize(ticker))


def committee_sectors(committee_id: str | None, data: dict) -> list[str]:
    """The sector keys a committee has direct jurisdiction over.

    An empty list is the normal answer for most committees. Appropriations,
    Judiciary and the tax committees touch every industry, so mapping them
    would fire the flag on almost every trade and mean nothing.
    """
    return list((data.get("committees") or {}).get(committee_id or "") or [])


def label(sector_key: str, data: dict) -> str:
    """The reader-facing name of a sector key."""
    return (data.get("sectors") or {}).get(sector_key) or sector_key


def classify(trades: list[dict], data: dict) -> dict:
    """Group a member's trades by sector, and count what we could classify.

    Returns ``{"by_sector": {key: Counter(ticker -> trades)}, "classified":
    n, "total": n}``, where the two counts are DISTINCT symbols. The caller
    publishes them, because "no overlap" and "we did not classify the symbol"
    are different answers and a reader must be able to tell them apart.
    """
    by_sector: dict[str, Counter] = {}
    seen: set[str] = set()
    classified: set[str] = set()
    for t in trades:
        tk = normalize(t.get("ticker"))
        if not tk:
            continue
        seen.add(tk)
        key = ticker_sector(tk, data)
        if not key:
            continue
        classified.add(tk)
        by_sector.setdefault(key, Counter())[tk] += 1
    return {
        "by_sector": by_sector,
        "classified": len(classified),
        "total": len(seen),
    }


def overlap(seats: list[dict], grouped: dict, data: dict,
            cap: int = 10) -> list[dict]:
    """One row per sector the member's seats oversee AND traded in.

    Grouped by sector, not by seat, because seats overlap: a senator on
    Health, on Veterans' Affairs and on Aging oversees health three times,
    and printing the same 26 symbols three times reads as three findings
    instead of one fact. Each row names every seat that covers the sector.

    An empty result covers two different cases on purpose: we map no sector
    to any of the seats, or the member traded nothing we classify into them.
    Neither is a finding, so neither gets a line on the page. ``cap`` limits
    the symbols listed; ``more`` carries the remainder.
    """
    rows = []
    for key in sorted(data.get("sectors") or {}):
        counts = grouped.get("by_sector", {}).get(key)
        if not counts:
            continue
        covering = [s.get("name") for s in seats
                    if key in committee_sectors(s.get("id"), data)
                    and s.get("name")]
        if not covering:
            continue
        ranked = counts.most_common()
        rows.append({
            "sector": key,
            "label": label(key, data),
            "committees": covering,
            "tickers": [{"ticker": tk, "count": n} for tk, n in ranked[:cap]],
            "more": max(0, len(ranked) - cap),
            "symbols": len(ranked),
            "trades": sum(counts.values()),
        })
    rows.sort(key=lambda r: (-r["trades"], r["label"]))
    return rows
