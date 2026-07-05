"""Annual-report *holdings* (real portfolio composition) for featured members.

The Periodic Transaction Reports we ingest elsewhere disclose *trades*, not
positions. A member's actual holdings live in their **annual** financial
disclosure, which lists every asset with a year-end value bracket:

- **Senate**: the eFD "Annual Report" (``/search/view/annual/<uuid>/``) — a
  structured HTML page whose "Assets" table has columns
  ``# | Asset | Asset Type | Owner | Value | Income Type | Income``.
- **House**: the annual FD (index ``FilingType == 'O'``) — a text PDF whose
  "Schedule A: Assets" lists ``<name> (<TICKER>) [<CODE>]  $lo - $hi``.

This module parses those into :class:`Holding` records. Per the product
decision the page shows **individual stocks only** (not ETFs/funds/bank/…), so
``is_stock`` marks the equities and the pipeline filters to them.

Only the fetch helpers touch the network / pdfplumber; the parsers are pure
functions of ``str`` so tests run offline against fixtures.

Honesty caveats (kept visible on the page): an annual report is a **yearly
snapshot** (and lags), values are **brackets** not exact, and scanned/paper
annual reports (and the President's ~250-page scanned OGE 278) can't be parsed
— those members are shown "annual report not machine-readable — link only".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .normalize import AMOUNT_BRACKETS, parse_amount
from .senate import _OWNER_MAP, _TableParser

# STOCK Act value brackets keyed by their (unique) lower bound, so a House row
# — whose upper bound wraps onto the next line — can be resolved from its lo
# alone. {1001: (1001, 15000, "$1,001 - $15,000"), ...}
_BRACKET_BY_LO = {
    lo: (lo, hi, f"${lo:,} - ${hi:,}" if hi is not None else f"${lo:,} +")
    for lo, hi in AMOUNT_BRACKETS.values()
}

# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------

@dataclass
class Holding:
    member: str
    chamber: str
    ticker: str | None
    asset: str
    asset_type: str        # normalized: Stock | ETF | Fund | Bond | Other
    raw_type: str          # source asset-type text (audit trail)
    value_lo: int | None
    value_hi: int | None
    value_label: str
    owner: str | None      # SP | JT | DC | None(=self)
    source_url: str
    filing_date: str       # ISO
    report_year: int | None = None

    def to_dict(self) -> dict:
        return {
            "member": self.member,
            "chamber": self.chamber,
            "ticker": self.ticker,
            "asset": self.asset,
            "asset_type": self.asset_type,
            "value_lo": self.value_lo,
            "value_hi": self.value_hi,
            "value_label": self.value_label,
            "owner": self.owner,
        }


def is_stock(h: Holding) -> bool:
    return h.asset_type == "Stock"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
_TICKER_PREFIX = re.compile(r"^([A-Z][A-Z.]{0,5})\s*[-–—]\s*(.+)$")   # "AAPL - Apple Inc."
_TICKER_PAREN = re.compile(r"^(.*?)\s*\(([A-Z][A-Z.]{0,5})\)\s*$")     # "Apple Inc. (AAPL)"


def _split_ticker_prefix(asset: str) -> tuple[str | None, str]:
    m = _TICKER_PREFIX.match(asset.strip())
    if m:
        return m.group(1), m.group(2).strip()
    return None, asset.strip()


def _split_ticker_paren(asset: str) -> tuple[str | None, str]:
    m = _TICKER_PAREN.match(asset.strip())
    if m:
        return m.group(2), m.group(1).strip()
    return None, asset.strip()


def normalize_asset_type(raw: str) -> str:
    """Collapse the source asset-type text into a coarse class."""
    r = raw.lower()
    if "exchange traded" in r or "etf" in r:
        return "ETF"
    if "mutual fund" in r or "fund" in r:
        return "Fund"
    if "stock" in r:
        return "Stock"
    if "bond" in r or "note" in r or "corporate securities" in r and "stock" not in r:
        return "Bond"
    return "Other"


def _owner(raw: str) -> str | None:
    return _OWNER_MAP.get(raw.strip().lower(), raw.strip() or None)


# ---------------------------------------------------------------------------
# Senate annual report (structured HTML)
# ---------------------------------------------------------------------------

def _is_assets_header(header_row: list[str]) -> bool:
    j = " ".join(header_row).lower()
    return "asset" in j and "value" in j and "transaction" not in j


def parse_senate_annual_assets(
    html: str,
    *,
    member: str,
    source_url: str = "",
    filing_date: str = "",
    report_year: int | None = None,
) -> list[Holding]:
    """Parse the Assets table out of a Senate annual-report page."""
    parser = _TableParser()
    parser.feed(html)
    table = next((t for t in parser.tables if t and _is_assets_header(t[0])), None)
    if table is None:
        return []
    out: list[Holding] = []
    for row in table[1:]:
        if len(row) < 5:
            continue
        asset, raw_type, owner, value = row[1], row[2], row[3], row[4]
        if not asset.strip():
            continue
        try:
            lo, hi, label = parse_amount(value)
        except ValueError:
            continue  # account/wrapper rows have value "--" (not a holding)
        ticker, name = _split_ticker_prefix(asset)
        out.append(
            Holding(
                member=member,
                chamber="senate",
                ticker=ticker,
                asset=name,
                asset_type=normalize_asset_type(raw_type),
                raw_type=re.sub(r"\s+", " ", raw_type).strip(),
                value_lo=lo,
                value_hi=hi,
                value_label=label,
                owner=_owner(owner),
                source_url=source_url,
                filing_date=filing_date,
                report_year=report_year,
            )
        )
    return out


# ---------------------------------------------------------------------------
# House annual FD (Schedule A, text PDF)
# ---------------------------------------------------------------------------
# A House stock line looks like:
#   "Apple Inc. (AAPL) [ST] SP $5,000,001 - Capital Gains, Over $5,000,000"
# with the value's UPPER bound wrapped onto the next line. We take the asset
# name, ticker (parenthesised, right before the [ST] code), the owner code, and
# the value LOWER bound — then resolve the full bracket from the lo. Only [ST]
# (common stock) lines are kept; [OP] options, [OL] partnerships, [BA] bank
# accounts, [MF]/[EF] funds, real estate, etc. are skipped (stocks only).
_HOUSE_STOCK = re.compile(
    r"^(?P<name>.+?)\s*\((?P<ticker>[A-Z][A-Z.]{0,6})\)\s*\[ST\]\s+"
    r"(?:(?P<owner>SP|JT|DC|JC)\s+)?"
    r"\$(?P<lo>[\d,]+)\b"
)
_HOUSE_CLASS_SUFFIX = re.compile(
    r"\s*[-,]?\s*(?:Class\s+[A-Z]\s*)?(?:Common Stock|Ordinary Shares|Units)\s*,?\s*$",
    re.I,
)


def _clean_house_name(name: str) -> str:
    name = _HOUSE_CLASS_SUFFIX.sub("", name.strip())
    return re.sub(r"\s+", " ", name).strip(" ,-")


def parse_house_annual_assets(
    text: str,
    *,
    member: str,
    source_url: str = "",
    filing_date: str = "",
    report_year: int | None = None,
) -> list[Holding]:
    """Parse individual **stock** holdings from a House annual FD Schedule A."""
    out: list[Holding] = []
    for line in text.splitlines():
        m = _HOUSE_STOCK.match(line.strip())
        if not m:
            continue
        lo = int(m.group("lo").replace(",", ""))
        bracket = _BRACKET_BY_LO.get(lo)
        if bracket is None:
            continue  # not a recognized value bracket (e.g. an income figure)
        blo, bhi, label = bracket
        name = _clean_house_name(m.group("name"))
        if not name:
            continue
        out.append(
            Holding(
                member=member,
                chamber="house",
                ticker=m.group("ticker"),
                asset=name,
                asset_type="Stock",
                raw_type="[ST]",
                value_lo=blo,
                value_hi=bhi,
                value_label=label,
                owner=m.group("owner") or None,
                source_url=source_url,
                filing_date=filing_date,
                report_year=report_year,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Listing + fetch (network) — find each member's latest annual report
# ---------------------------------------------------------------------------
HOUSE_FIN_URL = (
    "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}/{doc}.pdf"
)


@dataclass
class AnnualRef:
    chamber: str
    url: str
    filing_date: str        # ISO
    report_year: int | None


def _index_rows(tsv_text: str):
    lines = [ln for ln in tsv_text.splitlines() if ln.strip()]
    if not lines:
        return
    header = [c.strip() for c in lines[0].split("\t")]
    for ln in lines[1:]:
        yield dict(zip(header, (c.strip() for c in ln.split("\t"))))


def house_latest_annual(session, last_name, state, years) -> AnnualRef | None:
    """Newest House annual FD (FilingType 'O') for a member, across ``years``."""
    from . import house
    from .normalize import parse_date

    best: AnnualRef | None = None
    for year in years:
        try:
            tsv = house.fetch_index(session, year)
        except Exception:
            continue
        for r in _index_rows(tsv):
            if r.get("FilingType") != "O" or not r.get("DocID"):
                continue
            if r.get("Last", "").strip().lower() != last_name.lower():
                continue
            if state and not r.get("StateDst", "").startswith(state):
                continue
            try:
                filed = parse_date(r["FilingDate"])
            except (KeyError, ValueError):
                continue
            if best is None or filed > best.filing_date:
                best = AnnualRef(
                    chamber="house",
                    url=HOUSE_FIN_URL.format(year=year, doc=r["DocID"]),
                    filing_date=filed,
                    report_year=year,
                )
    return best


def senate_latest_annual(session, last_name) -> AnnualRef | None:
    """Newest Senate annual report (``/view/annual/``) for a member."""
    import re as _re

    from . import senate
    from .http import polite_post
    from .normalize import parse_date

    data = {
        "draw": "1", "start": "0", "length": "100",
        "report_types": "[]", "filer_types": "[]",
        "submitted_start_date": "01/01/2022 00:00:00", "submitted_end_date": "",
        "candidate_state": "", "senator_state": "", "office_id": "",
        "first_name": "", "last_name": last_name,
    }
    resp = polite_post(
        session, senate.SEARCH_URL, data=data,
        headers={"Referer": senate.SEARCH_REFERER,
                 "X-CSRFToken": session.cookies.get("csrftoken", "")},
    )
    best: AnnualRef | None = None
    for row in resp.json().get("data", []):
        cells = [str(c) for c in row]
        m = next((mm for mm in map(senate._LINK.search, cells) if mm), None)
        if not m or "/view/annual/" not in m.group(1):
            continue
        title = _re.sub(r"<[^>]+>", "", m.group(2)).strip()
        filed_cell = next(
            (c.strip() for c in cells if _re.match(r"^\d{2}/\d{2}/\d{4}$", c.strip())),
            None,
        )
        try:
            filed = parse_date(filed_cell) if filed_cell else ""
        except ValueError:
            filed = ""
        ym = _re.search(r"(20\d{2})", title)
        href = m.group(1)
        url = href if href.startswith("http") else senate.BASE + href
        if best is None or filed > best.filing_date:
            best = AnnualRef(
                chamber="senate",
                url=url,
                filing_date=filed,
                report_year=int(ym.group(1)) if ym else None,
            )
    return best


def fetch_holdings(session, ref: AnnualRef, *, member: str) -> list[Holding]:
    """Fetch + parse a member's latest annual report into stock holdings."""
    from . import house, senate
    from .http import polite_get

    if ref.chamber == "senate":
        html = polite_get(
            session, ref.url, headers={"Referer": senate.SEARCH_REFERER}
        ).text
        holds = parse_senate_annual_assets(
            html, member=member, source_url=ref.url,
            filing_date=ref.filing_date, report_year=ref.report_year,
        )
    else:
        text = house.extract_pdf_text(polite_get(session, ref.url).content)
        if not text.strip():
            return []  # scanned annual report — no text layer
        holds = parse_house_annual_assets(
            text, member=member, source_url=ref.url,
            filing_date=ref.filing_date, report_year=ref.report_year,
        )
    return [h for h in holds if is_stock(h)]
