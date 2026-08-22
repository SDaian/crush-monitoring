"""Resolve an OGE 278-T asset description to an equity ticker — or refuse.

The President's newer 278-Ts (June 2026 onward) disclose stocks and ETFs, not
only bonds, but the form has **no ticker column** and its OCR text layer
mangles names ("QUALM INC", "BOEING PANY"). Guessing a ticker from a garbled
name would put a false row on a real stock page, so this module's contract is
strict: **resolve exactly, or return None and say so**. The pipeline reports
every miss; a human adds it to the override map.

Two sources of truth, in order:

1. ``OVERRIDES`` — a curated map for names the OCR garbles or the index
   cannot know. Hand-maintained, like ``oge_filings.json``.
2. An index built from the trades we already publish: House and Senate rows
   carry both the asset name and its ticker, so ~13,000 rows vote on what
   each normalized name means. A name that maps to two different tickers is
   dropped as ambiguous rather than resolved by majority.

Pure stdlib; no I/O outside :func:`load_index`.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Bond / debt detection — these rows keep ticker=None on purpose
# ---------------------------------------------------------------------------
# A coupon percentage is the strongest tell (munis and corporates both carry
# one); the keywords catch the rest. Checked BEFORE any ticker resolution.
_COUPON = re.compile(r"\d(?:\.\d+)?\s*%")
_DEBT_WORDS = re.compile(
    r"\b(BOND|BONDS|NOTE|NOTES|DUE|PERP|MUNI|TREAS|TSY|T-?BILL|DEBENTURE|"
    r"REV|BD|OBLIG|CTF|B/E|B/Q|GO REF)\b",
    re.IGNORECASE,
)


_ETF = re.compile(
    r"\bETFS?\b|\bFUND\b|\bISHARES\b|\bSPDR\b|\bVANGUARD\b|"
    r"\bBULLETSHARES\b|\bPREFERRED\b|\bPFD\b", re.IGNORECASE)


def is_debt(asset: str) -> bool:
    """True for a bond/note/muni row. An ETF is never debt — a bond ETF
    trades as shares under a ticker, and the President's June 2026 filing
    holds several (iShares Treasury Bond ETF among them)."""
    if _ETF.search(asset):
        return False
    return bool(_COUPON.search(asset) or _DEBT_WORDS.search(asset))


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------
# OCR garbles seen in the real filings. Applied as whole-word fixes before
# suffix stripping, and only ones unambiguous enough to be safe.
_OCR_FIXES = {
    "PANY": "COMPANY",
    "PANIES": "COMPANIES",
    "QUALM": "QUALCOMM",
    "INCORPORA": "INCORPORATED",
}
# Corporate furniture that varies between filings of the same company.
_SUFFIXES = re.compile(
    r"\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|COMPANIES|PLC|LTD|LLC|"
    r"GROUP|HOLDINGS|HLDGS|THE|NEW)\b\.?",
)
_CLASS_TAIL = re.compile(
    r"\b(CLASS\s+[A-C]|CL\s+[A-C]|COMMON|ORDINARY|SHARES|SHS|STOCK|ADR|ADS|"
    r"SPONSORED|AMERICAN\s+DEPOSITARY(?:\s+SHARES?)?|USD?\s*[\d.]+(?:\s+\d+)*)\b\.?",
)
_NON_ALNUM = re.compile(r"[^A-Z0-9 ]+")


def normalize_name(asset: str) -> str:
    """A canonical key for an asset name: OCR-fixed, de-suffixed, squashed."""
    up = asset.upper()
    words = [_OCR_FIXES.get(w, w) for w in up.split()]
    up = " ".join(words)
    up = _NON_ALNUM.sub(" ", up)
    up = _CLASS_TAIL.sub(" ", up)
    up = _SUFFIXES.sub(" ", up)
    return re.sub(r"\s+", " ", up).strip()


# ---------------------------------------------------------------------------
# The curated override map — garbled or index-invisible names
# ---------------------------------------------------------------------------
# Keys are normalize_name() outputs. Add a line per reported miss; never let
# code guess. ETFs the congressional record rarely trades are listed here too.
OVERRIDES: dict[str, str] = {
    "QUALCOMM": "QCOM",
    "REPUBLIC SVCS": "RSG",
    "MOODYS": "MCO",
    "LENNOX INTL": "LII",
    "FACTSET RESH SYS": "FDS",
    "ROYAL CARIBBEAN": "RCL",
    "AXON ENTERPRISE": "AXON",
    "INTUIT": "INTU",
    "WALT DISNEY": "DIS",
    "MOTOROLA SOLUTIONS": "MSI",
    "BERKSHIRE HATHAWAY": "BRK.B",
    "T MOBILE US": "TMUS",
    "BROADRIDGE FINL SOLUTIONS": "BR",
}


def build_index(trades: list[dict]) -> dict[str, str]:
    """name → ticker from rows that carry both. Ambiguous names are dropped."""
    votes: dict[str, set[str]] = defaultdict(set)
    for t in trades:
        tk = (t.get("ticker") or "").strip().upper()
        asset = t.get("asset") or ""
        if not tk or not asset or is_debt(asset):
            continue
        key = normalize_name(asset)
        if key:
            votes[key].add(tk)
    return {k: next(iter(v)) for k, v in votes.items() if len(v) == 1}


def load_index(path: str | Path) -> dict[str, str]:
    """The index from a published congress-trades.json; {} when unreadable."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return build_index(doc.get("trades") or [])


def resolve(asset: str, index: dict[str, str]) -> str | None:
    """The ticker for an asset name, or None. Never a guess."""
    key = normalize_name(asset)
    if not key:
        return None
    if key in OVERRIDES:
        return OVERRIDES[key]
    return index.get(key)
