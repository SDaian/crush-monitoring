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

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import quote

from .http import polite_get
from .normalize import AMOUNT_BRACKETS, Trade, parse_date

# ---------------------------------------------------------------------------
# Endpoints and the target filer
# ---------------------------------------------------------------------------
OGE_HOST = "https://extapps2.oge.gov"
VIEW_PATH = "/201/Presiden.nsf/PAS+Index"
VIEW_URL = OGE_HOST + VIEW_PATH
PAGE_SIZE = 1000  # Domino caps a ReadViewEntries response at 1000 entries

# OGE's app is picky about non-browser agents; present a browser UA for its
# requests only (the shared bot UA stays the default for the .gov chambers).
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# We track the sitting President. Categories in the view read
# "Last, First[, MI], Agency, Position" — match on the name prefix so we do
# not depend on the exact agency/position wording.
FILER_NAME = "Donald J. Trump"
FILER_CATEGORY_KEY = "trump, donald"


# ---------------------------------------------------------------------------
# Listing: enumerate the filer's 278-T PDF documents from the Domino view
# ---------------------------------------------------------------------------
@dataclass
class OgeFiling:
    """One 278-T PDF attachment listed under the filer in the PAS Index view."""

    unid: str          # Domino universal id of the attachment's document
    filename: str      # e.g. "Donald J. Trump 10.20.2025 278-T (2).pdf"
    filing_date: str   # ISO, parsed from the filename date
    url: str           # absolute, URL-encoded download link
    label: str         # the view's link text, e.g. "Periodic (10/20/2025)"


_VIEWENTRY_RE = re.compile(r"<viewentry\b[^>]*>.*?</viewentry>", re.S)
_CATEGORY_RE = re.compile(r'category="true"\s*>\s*<text>(.*?)</text>', re.S)
_HREF_RE = re.compile(
    r"href='(/201/Presiden\.nsf/PAS\+Index/([0-9A-Fa-f]+)/\$FILE/([^']+?\.pdf))'"
    r"[^>]*>(?:<img[^>]*>)?([^<]*)</a>",
    re.I,
)
_FILENAME_DATE_RE = re.compile(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})")


def _entry_category(entry_xml: str) -> str | None:
    m = _CATEGORY_RE.search(entry_xml)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip()


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


def _documents_in_entry(entry_xml: str) -> list[OgeFiling]:
    """Extract every 278-T PDF link from one (child) view entry."""
    html = unescape(entry_xml)
    out: list[OgeFiling] = []
    for path, unid, filename, label in _HREF_RE.findall(html):
        low = f"{filename} {label}".lower()
        # Periodic Transaction Reports only — skip Annual/New-entrant 278s.
        if "278-t" not in low and "periodic" not in low:
            continue
        url = OGE_HOST + quote(path, safe="/$:+")
        out.append(
            OgeFiling(
                unid=unid,
                filename=filename.strip(),
                filing_date=_filename_date(filename) or "",
                url=url,
                label=re.sub(r"\s+", " ", label).strip(),
            )
        )
    return out


def parse_view_documents(pages: list[str], filer_key: str = FILER_CATEGORY_KEY) -> list[OgeFiling]:
    """Walk the categorized view XML (in order) and collect the filer's docs.

    ``pages`` is the list of ReadViewEntries XML responses in ``Start`` order.
    A category row sets the current filer; child rows under a matching filer
    contribute their 278-T attachments. Category state carries across the page
    boundary, so a filer split across two responses is still captured.
    """
    docs: list[OgeFiling] = []
    seen: set[str] = set()
    current_matches = False
    for xml in pages:
        for entry in _VIEWENTRY_RE.findall(xml):
            cat = _entry_category(entry)
            if cat is not None:
                current_matches = filer_key in cat.lower()
                continue
            if current_matches:
                for doc in _documents_in_entry(entry):
                    if doc.unid not in seen:
                        seen.add(doc.unid)
                        docs.append(doc)
    return docs


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
def fetch_view_page(session, start: int, count: int = PAGE_SIZE) -> str:
    url = (
        f"{VIEW_URL}?ReadViewEntries&OutputFormat=XML&ExpandView"
        f"&Start={start}&Count={count}"
    )
    return polite_get(session, url, headers={"User-Agent": BROWSER_UA}).text


def list_filings(session, max_pages: int = 6) -> list[OgeFiling]:
    """Page through the PAS Index view and return the filer's 278-T docs."""
    pages: list[str] = []
    start = 1
    for _ in range(max_pages):
        xml = fetch_view_page(session, start)
        pages.append(xml)
        n = len(_VIEWENTRY_RE.findall(xml))
        if n < PAGE_SIZE:
            break
        start += n
    return parse_view_documents(pages)


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
