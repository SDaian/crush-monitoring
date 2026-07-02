"""House Clerk (disclosures-clerk.house.gov) listing and PTR parsing.

Flow:
1. GET the yearly index ZIP (``public_disc/financial-pdfs/<YEAR>FD.zip``),
   whose ``<YEAR>FD.txt`` member is a TSV of all filings; FilingType ``P``
   marks Periodic Transaction Reports.
2. GET each PTR PDF (``public_disc/ptr-pdfs/<YEAR>/<DocID>.pdf``).
   Electronically filed PTRs are text PDFs with a consistent transaction
   table; paper filings are image scans (no text layer) — skipped, linked,
   counted.

Only ``extract_pdf_text`` touches pdfplumber (lazy import); every parser is a
pure stdlib function of ``str`` so tests run offline on text fixtures.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass

from .normalize import Trade, parse_amount, parse_date, parse_tx_type

INDEX_URL = (
    "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
)
PTR_URL = (
    "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
)
MIN_TEXT_CHARS = 50  # under this, the PDF is a scan with no text layer

ASSET_CODES = {
    "ST": "Stock",
    "OP": "Option",
    "EF": "ETF",
    "MF": "Mutual Fund",
    "GS": "Government Security",
    "CS": "Corporate Security",
    "CT": "Cryptocurrency",
    "OT": "Other",
}


@dataclass
class HouseFilingRef:
    doc_id: str
    name: str          # "First Last" from the index
    state: str | None  # from StateDst, e.g. "TX"
    district: str | None  # e.g. "TX-10"
    filing_date: str   # ISO
    year: int
    url: str


class HouseError(RuntimeError):
    """Clerk data did not match the expected shape."""


# ---------------------------------------------------------------------------
# Index (network fetch + pure parse)
# ---------------------------------------------------------------------------

def fetch_index(session, year: int) -> str:
    """Download the yearly filing index ZIP and return the TSV text."""
    from .http import polite_get

    resp = polite_get(session, INDEX_URL.format(year=year))
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if not names:
            raise HouseError(
                f"{year}FD.zip contains no .txt index (members: {zf.namelist()!r})"
            )
        return zf.read(names[0]).decode("utf-8", errors="replace")


def parse_index(tsv_text: str, year: int) -> list[HouseFilingRef]:
    """Extract PTR filings (FilingType == 'P') from the yearly index TSV."""
    refs = []
    header: list[str] | None = None
    for line in tsv_text.splitlines():
        if not line.strip():
            continue
        cells = line.split("\t")
        if header is None:
            header = [c.strip() for c in cells]
            required = {"Last", "First", "FilingType", "StateDst", "FilingDate", "DocID"}
            missing = required - set(header)
            if missing:
                raise HouseError(
                    f"{year}FD.txt index header missing {sorted(missing)}: {header!r}"
                )
            continue
        row = dict(zip(header, (c.strip() for c in cells)))
        if row.get("FilingType") != "P" or not row.get("DocID"):
            continue
        state, district = _split_state_dst(row.get("StateDst", ""))
        refs.append(
            HouseFilingRef(
                doc_id=row["DocID"],
                name=f"{row.get('First', '')} {row.get('Last', '')}".strip(),
                state=state,
                district=district,
                filing_date=parse_date(row["FilingDate"]),
                year=year,
                url=PTR_URL.format(year=year, doc_id=row["DocID"]),
            )
        )
    if header is None:
        raise HouseError(f"{year}FD.txt index was empty")
    return refs


def _split_state_dst(state_dst: str) -> tuple[str | None, str | None]:
    match = re.fullmatch(r"([A-Z]{2})(\d{2})", state_dst.strip())
    if not match:
        return None, None
    state, num = match.group(1), int(match.group(2))
    return state, f"{state}-{num}"


# ---------------------------------------------------------------------------
# PDF text extraction (the only pdfplumber call site)
# ---------------------------------------------------------------------------

def fetch_ptr_pdf(session, ref: HouseFilingRef) -> bytes:
    from .http import polite_get

    return polite_get(session, ref.url).content


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from a PTR PDF; empty string means scanned/paper filing."""
    import pdfplumber

    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    text = "\n".join(pages)
    return text if len(text.strip()) >= MIN_TEXT_CHARS else ""


# ---------------------------------------------------------------------------
# PTR text parsing (pure stdlib)
# ---------------------------------------------------------------------------

# A transaction row as pdfplumber lays it out: optional owner code, asset
# name, type code, transaction date, notification date, amount bracket (which
# may wrap onto the next line, leaving a trailing "-").
_ROW = re.compile(
    r"^(?:(?P<owner>SP|JT|DC)\s+)?"
    r"(?P<asset>.+?)\s+"
    r"(?P<type>S \(partial\)|P|S|E)\s+"
    r"(?P<d1>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<d2>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<amount>\$[\d,]+(?:\s*[-–]\s*\$?[\d,]*)?|None)\s*$"
)
# Per-row metadata continuations from the e-filing system (ignored). The
# PDF layout pads the markers with wide runs of spaces ("F      S     : New",
# "S          O : ..."), so whitespace between the letters is flexible.
_META = re.compile(r"^\(?(F\s+S|S\s+O|D|C|L)\s*:\s*")
# Boilerplate/header/footer lines (ignored, never appended to asset names),
# including the IPO question and the certification block at the end of the
# form.
_SKIP = re.compile(
    r"(clerk of the house|house of representatives|financial disclosure"
    r"|periodic transaction|filing id|state/district|transactions?$"
    r"|^id\s+owner\s+asset|^type\s+date|^asset\s+|notification|amount"
    r"|cap\.?\s*gains|^\*|initial public offering|^name:|^status:"
    r"|^page \d|^https?://"
    r"|i\s+p\s+o|^yes\b|^no\b|certify|digitally signed|knowledge and belief"
    r"|electronically filed|^signature)",
    re.I,
)
_TICKER = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,9})\)")
_CODE = re.compile(r"\[([A-Z]{2})\]")
_MONEY_TOKEN = re.compile(r"\$[\d,]+")


def parse_ptr_text(text: str, ref: HouseFilingRef) -> list[Trade]:
    """Parse extracted House PTR text into normalized trades.

    Raises ``HouseError``/``ValueError`` when nothing parses (the caller
    records the filing as a parse error and links the PDF instead).
    """
    # pdfplumber renders some glyph gaps as NUL bytes ("F\x00\x00 S\x00: New"),
    # which \s does not match — normalize them to spaces before any regex.
    text = text.replace("\x00", " ")
    pending: dict | None = None
    rows: list[dict] = []

    def finalize():
        nonlocal pending
        if pending is not None:
            rows.append(pending)
            pending = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _ROW.match(line)
        if match:
            finalize()
            pending = match.groupdict()
            pending["extra"] = []
            continue
        if pending is None or _SKIP.search(line):
            continue
        if _META.match(line):
            pending["closed"] = True  # metadata ends the asset-name block
            continue
        if pending["amount"].rstrip().endswith(("-", "–")):
            # A wrapped amount lands at the end of the continuation line
            # ("Market ETF (ITOT) [EF] $15,000") — the rest is asset name.
            money = _MONEY_TOKEN.findall(line)
            if money:
                pending["amount"] = (
                    pending["amount"].rstrip(" -–") + " - " + money[-1]
                )
                remainder = line[: line.rfind(money[-1])].strip()
                if remainder and not pending.get("closed"):
                    pending["extra"].append(remainder)
                continue
        if not pending.get("closed"):
            pending["extra"].append(line)
    finalize()

    trades = []
    for row in rows:
        asset_full = " ".join([row["asset"], *row["extra"]]).strip()
        kind, partial = parse_tx_type(row["type"])
        lo, hi, label = parse_amount(row["amount"])
        ticker_match = _TICKER.search(asset_full)
        code_match = _CODE.search(asset_full)
        asset_clean = _CODE.sub("", _TICKER.sub("", asset_full))
        # Some PDFs wrap the "F S: New" filing-status marker so that a bare
        # "F S" trails the asset name; strip it.
        asset_clean = re.sub(r"\bF\s+S\s*$", "", asset_clean)
        asset_clean = re.sub(r"\s+", " ", asset_clean).strip(" -")
        trades.append(
            Trade(
                id=f"house:{ref.doc_id}:{len(trades)}",
                chamber="house",
                member=ref.name,
                ticker=ticker_match.group(1) if ticker_match else None,
                asset=asset_clean,
                asset_type=(
                    ASSET_CODES.get(code_match.group(1), code_match.group(1))
                    if code_match
                    else None
                ),
                type=kind,
                partial=partial,
                owner=row["owner"],
                tx_date=parse_date(row["d1"]),
                filing_date=ref.filing_date,
                amount_lo=lo,
                amount_hi=hi,
                amount_label=label,
                filing_id=ref.doc_id,
                source_url=ref.url,
                state=ref.state,
                district=ref.district,
            )
        )
    if not trades:
        raise HouseError(f"house PTR {ref.doc_id}: no transaction rows parsed")
    return trades
