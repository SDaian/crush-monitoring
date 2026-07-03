"""OGE executive-branch 278-T ingester (Periodic Transaction Reports).

The President and other PAS (Presidentially Appointed, Senate-confirmed)
filers post OGE Form 278-T "Periodic Transaction Reports" to the U.S. Office
of Government Ethics public-disclosure app — a Lotus Domino database at
``extapps2.oge.gov/201/Presiden.nsf``. This module:

1. Enumerates a filer's 278-T documents from the categorized "PAS Index"
   view (``?ReadViewEntries&OutputFormat=XML``), paginating past Domino's
   1000-entry-per-response cap.
2. Parses the transaction table out of each PDF.

Unlike the House e-filed PTRs, the OGE 278-T PDFs are **scanned images with an
OCR text layer**, so the extracted text is noisy: digits are mangled
(``5``→``S``, ``0``→``D``/``O``, ``1``→``l``/``I``), the leading row number
drifts onto its own line, and asset descriptions are truncated mid-name. The
parser is deliberately tolerant — it anchors on the regular
``<type> <date> No <amount-bracket>`` tail of each row and snaps the amount to
the fixed set of STOCK Act disclosure brackets, which corrects residual OCR
digit errors. The President's disclosed transactions are managed-account
purchases of corporate and municipal **bonds** (plus the odd bond ETF), so
these rows carry no equity ticker.

Only the two functions that hit the network (``fetch_view_page``,
``fetch_pdf_bytes``) import ``requests``/``pdfplumber``; everything else is a
pure function of ``str``/``bytes`` so the offline test suite runs without the
scraper dependencies.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from .http import polite_get
from .normalize import AMOUNT_BRACKETS, Trade, parse_date

# ---------------------------------------------------------------------------
# Endpoints and the target filer
# ---------------------------------------------------------------------------
OGE_HOST = "https://extapps2.oge.gov"
VIEW_PATH = "/201/Presiden.nsf/PAS+Index"

# OGE's app is picky about non-browser agents; present a browser UA for its
# requests only (the shared bot UA stays the default for the .gov chambers).
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

FILER_NAME = "Donald J. Trump"

# The President is NOT listed in OGE's browsable "PAS Index" view (that view
# covers Senate-confirmed appointees only), and the Domino app exposes no
# full-text search or President-specific view. His 278-T PDFs are reachable
# only by their stable document UNID. So the set of filings to ingest is
# curated in this seed file; the daily job re-fetches and re-parses each one.
PACKAGE_DIR = Path(__file__).resolve().parent
SEED_PATH = PACKAGE_DIR / "oge_filings.json"


@dataclass
class OgeFiling:
    """One 278-T PDF attachment (a Periodic Transaction Report)."""

    unid: str          # Domino universal id of the attachment's document
    filename: str      # e.g. "Donald J. Trump 10.20.2025 278-T (2).pdf"
    filing_date: str   # ISO, parsed from the filename date
    url: str           # absolute, URL-encoded download link
    label: str         # short human label, e.g. "Periodic (2025-10-20)"


_FILENAME_DATE_RE = re.compile(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})")


def _filename_date(filename: str) -> str | None:
    """Parse the report date embedded in the attachment filename to ISO."""
    m = _FILENAME_DATE_RE.search(filename)
    if not m:
        return None
    mm, dd, yy = m.group(1), m.group(2), m.group(3)
    if len(yy) == 2:
        yy = "20" + yy
    try:
        return parse_date(f"{int(mm):02d}/{int(dd):02d}/{yy}")
    except ValueError:
        return None


def filing_url(unid: str, filename: str) -> str:
    """Build the absolute, URL-encoded $FILE download link for an attachment."""
    path = f"{VIEW_PATH}/{unid}/$FILE/{filename}"
    return OGE_HOST + quote(path, safe="/$:+")


def parse_seed(data: dict) -> list[OgeFiling]:
    """Turn the curated seed JSON into :class:`OgeFiling` refs."""
    out: list[OgeFiling] = []
    for f in data.get("filings", []):
        unid, filename = f["unid"], f["filename"]
        out.append(
            OgeFiling(
                unid=unid,
                filename=filename,
                filing_date=f.get("date") or _filename_date(filename) or "",
                url=filing_url(unid, filename),
                label=f.get("label")
                or f"Periodic ({_filename_date(filename) or filename})",
            )
        )
    return out


def load_seed(path: Path = SEED_PATH) -> list[OgeFiling]:
    if not path.exists():
        return []
    return parse_seed(json.loads(path.read_text(encoding="utf-8")))


def list_filings(session=None, seed_path: Path = SEED_PATH) -> list[OgeFiling]:
    """Return the President's 278-T filings to ingest (from the seed file).

    Listing needs no network — the seed *is* the list; ``session`` is accepted
    only so the call site matches the other chambers' source wiring.
    """
    return load_seed(seed_path)


# ---------------------------------------------------------------------------
# Parsing: the OCR'd 278-T transaction table
# ---------------------------------------------------------------------------
# OCR confuses a handful of digits with letters; fix these only inside the
# numeric date/amount fields, never in the free-text description.
_OCR_DIGITS = str.maketrans({
    "S": "5", "s": "5", "O": "0", "o": "0", "D": "0",
    "l": "1", "I": "1", "B": "8", "Z": "2", "G": "6",
})

# A transaction row's regular tail: <type> <date> <notification> <amount>.
# Everything before the type token is the (truncated) asset description.
_TX_RE = re.compile(
    r"^(?P<desc>.+?)\s+"
    r"(?P<type>\w*urchase|sale(?:\s*\(partial\))?|exchange)\s+"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4}[A-Za-z]?)\s+"
    r"(?P<notif>N[o0]|Yes)\s+"
    r"(?P<amt>\$[\s\S]+?)\s*$",
    re.IGNORECASE,
)
_MONEY_TOKEN = re.compile(r"\$\s*([0-9OoDIlSBZG.,]+)")
_LEADING_JUNK = re.compile(r"^[\s.·•…\"'`*—–-]+")


def _classify_type(token: str) -> tuple[str, bool]:
    t = token.strip().lower()
    if "urchase" in t:
        return "buy", False
    if "exchange" in t:
        return "exchange", False
    if "sale" in t or t.startswith("s"):
        return "sell", "partial" in t
    raise ValueError(f"unrecognized transaction type: {token!r}")


def _ocr_int(raw: str) -> int:
    """Turn an OCR'd money figure (``50D,001``, ``50.001``) into an int."""
    digits = raw.translate(_OCR_DIGITS)
    digits = re.sub(r"[.,\s]", "", digits)
    return int(digits)


def _snap_bracket(lo: int, hi: int | None) -> tuple[int | None, int | None, str]:
    """Snap an OCR-derived (lo, hi) to the nearest STOCK Act bracket.

    Bracket floors are distinctive (1,001 / 15,001 / 50,001 / …), so nearest
    floor recovers the intended bracket even when a digit was misread.
    """
    if hi is None:  # open-ended top bracket
        label = "$50,000,001 +"
        blo, bhi = AMOUNT_BRACKETS[label]
        return blo, bhi, label
    best = min(
        AMOUNT_BRACKETS.items(),
        key=lambda kv: (
            abs(kv[1][0] - lo) if kv[1][0] is not None else 10**18,
            abs((kv[1][1] or 0) - hi),
        ),
    )
    label, (blo, bhi) = best
    return blo, bhi, label


def _parse_amount(amt: str) -> tuple[int | None, int | None, str]:
    tokens = _MONEY_TOKEN.findall(amt)
    if not tokens:
        raise ValueError(f"no amount in {amt!r}")
    if len(tokens) >= 2:
        return _snap_bracket(_ocr_int(tokens[0]), _ocr_int(tokens[1]))
    if "+" in amt or "over" in amt.lower() or "more" in amt.lower():
        return _snap_bracket(_ocr_int(tokens[0]), None)
    raise ValueError(f"single-sided amount {amt!r}")


def _parse_tx_date(raw: str) -> str:
    return parse_date(raw.translate(_OCR_DIGITS).strip())


def _clean_description(desc: str) -> str:
    desc = _LEADING_JUNK.sub("", desc)
    # A stray leading row number that landed on the description line.
    desc = re.sub(r"^\d{1,3}\s+(?=[A-Za-z])", "", desc)
    return re.sub(r"\s+", " ", desc).strip()


def parse_transactions(
    text: str,
    *,
    unid: str,
    source_url: str,
    filing_date: str,
    member: str = FILER_NAME,
    chamber: str = "executive",
) -> list[Trade]:
    """Parse an OGE 278-T's OCR text into normalized :class:`Trade` rows.

    Lines that do not match the transaction tail (headers, footers, the
    certification block, the Privacy Act notice) are simply skipped.
    """
    trades: list[Trade] = []
    row = 0
    for line in text.splitlines():
        line = line.strip()
        if not line or "$" not in line:
            continue
        m = _TX_RE.match(line)
        if not m:
            continue
        try:
            tx_type, partial = _classify_type(m.group("type"))
            tx_date = _parse_tx_date(m.group("date"))
            lo, hi, label = _parse_amount(m.group("amt"))
        except ValueError:
            continue
        asset = _clean_description(m.group("desc"))
        if not asset:
            continue
        row += 1
        trades.append(
            Trade(
                id=f"{chamber}:{unid}:{row}",
                chamber=chamber,
                member=member,
                ticker=None,          # 278-T assets are bonds — no equity ticker
                asset=asset,
                type=tx_type,
                tx_date=tx_date,
                filing_date=filing_date,
                amount_lo=lo,
                amount_hi=hi,
                amount_label=label,
                filing_id=unid,
                source_url=source_url,
                partial=partial,
                asset_type="bond",
            )
        )
    return trades


# ---------------------------------------------------------------------------
# Network glue (the only functions that import requests / pdfplumber)
# ---------------------------------------------------------------------------
def extract_pdf_text(content: bytes) -> str:
    """Extract text from a 278-T PDF (all pages). Imports pdfplumber lazily."""
    import io

    import pdfplumber

    with pdfplumber.open(io.BytesIO(content)) as doc:
        return "\n".join((p.extract_text() or "") for p in doc.pages)


def fetch_trades(session, filing: OgeFiling) -> list[Trade]:
    resp = polite_get(session, filing.url, headers={"User-Agent": BROWSER_UA})
    text = extract_pdf_text(resp.content)
    return parse_transactions(
        text,
        unid=filing.unid,
        source_url=filing.url,
        filing_date=filing.filing_date,
    )
