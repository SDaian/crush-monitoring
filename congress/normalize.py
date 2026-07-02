"""Unified trade schema and normalization helpers.

Pure stdlib and side-effect free: every function here takes plain values and
returns plain values, so the offline test suite runs without the scraper
dependencies (requests / pdfplumber).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
MEMBERS_PATH = PACKAGE_DIR / "members.json"
FEATURED_PATH = PACKAGE_DIR / "featured.json"

# ---------------------------------------------------------------------------
# Amount brackets
# ---------------------------------------------------------------------------
# The STOCK Act only requires filers to disclose a bracket, never an exact
# amount. `hi` is None for the open-ended top bracket.
AMOUNT_BRACKETS: dict[str, tuple[int | None, int | None]] = {
    "$1,001 - $15,000": (1_001, 15_000),
    "$15,001 - $50,000": (15_001, 50_000),
    "$50,001 - $100,000": (50_001, 100_000),
    "$100,001 - $250,000": (100_001, 250_000),
    "$250,001 - $500,000": (250_001, 500_000),
    "$500,001 - $1,000,000": (500_001, 1_000_000),
    "$1,000,001 - $5,000,000": (1_000_001, 5_000_000),
    "$5,000,001 - $25,000,000": (5_000_001, 25_000_000),
    "$25,000,001 - $50,000,000": (25_000_001, 50_000_000),
    "$50,000,001 +": (50_000_001, None),
}

_DASHES = re.compile(r"[‐-―−]")  # unicode hyphens/dashes → "-"
_MONEY = re.compile(r"\$\s*([\d,]+)")


def parse_amount(label: str) -> tuple[int | None, int | None, str]:
    """Parse a disclosure amount bracket into ``(lo, hi, clean_label)``.

    Tolerates whitespace and dash variants, ``Over $X`` / ``$X +`` for the
    open top bracket and ``$X or less`` for a bottom bracket. Raises
    ``ValueError`` on anything that does not look like a bracket.
    """
    clean = _DASHES.sub("-", label).strip()
    clean = re.sub(r"\s+", " ", clean)
    amounts = [int(m.group(1).replace(",", "")) for m in _MONEY.finditer(clean)]
    lowered = clean.lower()
    if len(amounts) == 2:
        lo, hi = amounts
        canonical = f"${lo:,} - ${hi:,}"
        return lo, hi, canonical
    if len(amounts) == 1:
        amt = amounts[0]
        if "less" in lowered:  # "$15,000 or less"
            return 0, amt, f"${amt:,} or less"
        if "over" in lowered or "+" in clean or "more" in lowered:
            return amt, None, f"${amt:,} +"
    raise ValueError(f"unrecognized amount bracket: {label!r}")


# ---------------------------------------------------------------------------
# Transaction types
# ---------------------------------------------------------------------------
# Senate eFD spells types out ("Purchase", "Sale (Full)"); House PTR PDFs use
# codes ("P", "S", "S (partial)", "E"). Map both to buy/sell/exchange.
_TX_TYPES: dict[str, tuple[str, bool]] = {
    "p": ("buy", False),
    "purchase": ("buy", False),
    "s": ("sell", False),
    "sale": ("sell", False),
    "sale (full)": ("sell", False),
    "s (full)": ("sell", False),
    "s (partial)": ("sell", True),
    "sale (partial)": ("sell", True),
    "e": ("exchange", False),
    "exchange": ("exchange", False),
}


def parse_tx_type(raw: str) -> tuple[str, bool]:
    """Map a raw transaction-type token to ``(type, partial)``.

    Raises ``ValueError`` for unknown tokens so callers can record the filing
    as a parse error instead of guessing.
    """
    key = re.sub(r"\s+", " ", raw.strip().lower().rstrip("."))
    try:
        return _TX_TYPES[key]
    except KeyError:
        raise ValueError(f"unrecognized transaction type: {raw!r}") from None


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

def parse_date(raw: str) -> str:
    """Normalize ``MM/DD/YYYY`` (or already-ISO) to ISO ``YYYY-MM-DD``."""
    clean = raw.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(clean, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date: {raw!r}")


# ---------------------------------------------------------------------------
# Names and roster
# ---------------------------------------------------------------------------
_HONORIFICS = ("hon.", "hon", "mr.", "mr", "mrs.", "mrs", "ms.", "ms", "dr.",
               "dr", "senator", "sen.", "sen", "rep.", "rep",
               "representative")
_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v", "md", "m.d."}
_TRAILING_SUFFIX = re.compile(r",?\s+(jr|sr|ii|iii|iv|v)\.?\s*$", re.I)


def canonical_name(raw: str) -> str:
    """Lowercase lookup key: honorifics/suffixes stripped, 'Last, First'
    reordered to 'first last', whitespace collapsed."""
    # Strip a trailing ", Jr."-style suffix BEFORE the comma reorder, or
    # "A. Mitchell McConnell, Jr." would be read as last="…", first="Jr.".
    clean = _TRAILING_SUFFIX.sub("", raw.strip())
    if "," in clean:
        last, _, first = clean.partition(",")
        clean = f"{first.strip()} {last.strip()}"
    tokens = [t for t in re.split(r"\s+", clean.lower()) if t]
    while tokens and tokens[0] in _HONORIFICS:
        tokens.pop(0)
    while tokens and tokens[-1] in _SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _first_last_key(canonical: str) -> str:
    """Fallback key dropping middle tokens ('michael t. mccaul' → 'michael mccaul')."""
    tokens = canonical.split()
    if len(tokens) <= 2:
        return canonical
    return f"{tokens[0]} {tokens[-1]}"


class Roster:
    """Member roster (party/state/chamber) joined onto scraped trades by name."""

    def __init__(self, members: list[dict]):
        self.members = members
        self._exact: dict[str, dict] = {}
        self._loose: dict[str, dict] = {}
        for m in members:
            for name in [m["name"], *m.get("aliases", [])]:
                key = canonical_name(name)
                self._exact.setdefault(key, m)
                self._loose.setdefault(_first_last_key(key), m)

    @classmethod
    def load(cls, path: Path = MEMBERS_PATH) -> "Roster":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls([m for m in data["members"] if not isinstance(m, str)])

    def find(self, raw_name: str, chamber: str | None = None) -> dict | None:
        key = canonical_name(raw_name)
        hit = self._exact.get(key) or self._loose.get(_first_last_key(key))
        if hit and chamber and hit.get("chamber") not in (None, chamber):
            return None
        return hit


def load_featured(path: Path = FEATURED_PATH) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["featured"]


# ---------------------------------------------------------------------------
# Trade record
# ---------------------------------------------------------------------------

@dataclass
class Trade:
    """One disclosed transaction, normalized across both chambers."""

    id: str            # "<chamber>:<filing_id>:<row>" — global dedupe key
    chamber: str       # "house" | "senate"
    member: str        # display name (roster name when matched)
    ticker: str | None
    asset: str
    type: str          # "buy" | "sell" | "exchange"
    tx_date: str       # ISO
    filing_date: str   # ISO
    amount_lo: int | None
    amount_hi: int | None
    amount_label: str
    filing_id: str
    source_url: str
    party: str | None = None
    state: str | None = None
    district: str | None = None
    asset_type: str | None = None
    partial: bool = False
    owner: str | None = None  # "SP" spouse | "JT" joint | "DC" dependent child | None = self

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "chamber": self.chamber,
            "member": self.member,
            "party": self.party,
            "state": self.state,
            "district": self.district,
            "ticker": self.ticker,
            "asset": self.asset,
            "asset_type": self.asset_type,
            "type": self.type,
            "partial": self.partial,
            "owner": self.owner,
            "tx_date": self.tx_date,
            "filing_date": self.filing_date,
            "amount_lo": self.amount_lo,
            "amount_hi": self.amount_hi,
            "amount_label": self.amount_label,
            "filing_id": self.filing_id,
            "source_url": self.source_url,
        }


def enrich(trade: Trade, roster: Roster) -> Trade:
    """Fill party/state/district (and the display name) from the roster.

    Scraped fields already on the trade (e.g. House state/district from the
    Clerk index) are kept when the roster has no entry.
    """
    entry = roster.find(trade.member, chamber=trade.chamber)
    if entry:
        trade.member = entry["name"]
        trade.party = entry.get("party") or trade.party
        trade.state = entry.get("state") or trade.state
        trade.district = entry.get("district") or trade.district
    return trade


def enrich_dict(t: dict, roster: Roster) -> dict:
    """Same as ``enrich`` for an already-serialized trade dict.

    Applied to every stored trade on every pipeline run, so trades ingested
    before a roster refresh pick up party/state retroactively.
    """
    entry = roster.find(t["member"], chamber=t["chamber"])
    if entry:
        t["member"] = entry["name"]
        t["party"] = entry.get("party") or t["party"]
        t["state"] = entry.get("state") or t["state"]
        t["district"] = entry.get("district") or t["district"]
    return t


def trade_sort_key(t: dict) -> tuple:
    """Stable output order: filing_date desc, member, tx_date desc, id."""
    return (
        _desc_date(t["filing_date"]),
        t["member"],
        _desc_date(t["tx_date"]),
        t["id"],
    )


def _desc_date(iso: str) -> int:
    return -int(iso.replace("-", ""))


def prune_cutoff(today: date) -> str:
    """Keep current + previous calendar year: cutoff is Jan 1 of last year."""
    return date(today.year - 1, 1, 1).isoformat()
