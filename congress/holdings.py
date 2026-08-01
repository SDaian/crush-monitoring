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

from .normalize import AMOUNT_BRACKETS, parse_amount, parse_option_detail
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
    option: dict | None = None   # {type, strike, expiration, contracts} for options

    def to_dict(self) -> dict:
        d = {
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
        if self.option:
            d["option"] = self.option
        return d


def is_stock(h: Holding) -> bool:
    return h.asset_type == "Stock"


def is_stock_or_option(h: Holding) -> bool:
    return h.asset_type in ("Stock", "Option")


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
    if "option" in r:
        return "Option"
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
        atype = normalize_asset_type(raw_type)
        out.append(
            Holding(
                member=member,
                chamber="senate",
                ticker=ticker,
                asset=name,
                asset_type=atype,
                raw_type=re.sub(r"\s+", " ", raw_type).strip(),
                value_lo=lo,
                value_hi=hi,
                value_label=label,
                owner=_owner(owner),
                source_url=source_url,
                filing_date=filing_date,
                report_year=report_year,
                option=parse_option_detail(asset) if atype == "Option" else None,
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
    r"^(?P<name>.+?)\s*\((?P<ticker>[A-Z][A-Z.]{0,6})\)\s*"
    r"(?P<code>\[[A-Z]{2}\])?\s*"
    r"(?:(?P<owner>SP|JT|DC|JC)\s+)?"
    r"\$(?P<lo>[\d,]+)\b"
)
_HOUSE_LEADING_CODE = re.compile(r"^\[(?P<code>[A-Z]{2})\]")
_HOUSE_CLASS_SUFFIX = re.compile(
    r"\s*[-,]?\s*(?:Class\s+[A-Z]\s*)?(?:Common Stock|Ordinary Shares|Units)\s*,?\s*$",
    re.I,
)
# Codes we surface as holdings: common stock and options. Everything else
# ([EF]/[MF] funds, [BA] bank, [OL] partnership, [GS]/[CS] debt, real estate…)
# is excluded.
_HOUSE_CODE_TYPE = {"ST": "Stock", "OP": "Option"}


def _clean_house_name(name: str) -> str:
    name = _HOUSE_CLASS_SUFFIX.sub("", name.strip())
    return re.sub(r"\s+", " ", name).strip(" ,-")


def _house_option_detail(lines: list[str], idx: int) -> dict | None:
    """Find the 'D: … call/put options …' description after an [OP] row."""
    for j in range(idx + 1, min(idx + 4, len(lines))):
        s = lines[j].strip()
        if "option" in s.lower() and ":" in s:
            det = parse_option_detail(s.split(":", 1)[1])
            if det:
                return det
    return None


def parse_house_annual_assets(
    text: str,
    *,
    member: str,
    source_url: str = "",
    filing_date: str = "",
    report_year: int | None = None,
) -> list[Holding]:
    """Parse individual **stock and option** holdings from a House Schedule A.

    A Schedule A line looks like ``<name> (<TICKER>) [<CODE>] <owner> $lo - …``,
    but the ``[<CODE>]`` sometimes wraps onto the next line (common for
    ``[OP]``), so the code is read from the row line or the line below it. The
    value's upper bound also wraps, so the bracket is resolved from its (unique)
    lower bound.
    """
    lines = text.splitlines()
    out: list[Holding] = []
    for i, raw in enumerate(lines):
        m = _HOUSE_STOCK.match(raw.strip())
        if not m:
            continue
        lo = int(m.group("lo").replace(",", ""))
        bracket = _BRACKET_BY_LO.get(lo)
        if bracket is None:
            continue  # not a recognized value bracket (e.g. an income figure)
        code = (m.group("code") or "").strip("[]")
        if not code:  # code wrapped onto the next line?
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            cm = _HOUSE_LEADING_CODE.match(nxt)
            code = cm.group("code") if cm else ""
        atype = _HOUSE_CODE_TYPE.get(code)
        if atype is None:
            continue  # not a stock or option
        name = _clean_house_name(m.group("name"))
        if not name:
            continue
        blo, bhi, label = bracket
        out.append(
            Holding(
                member=member,
                chamber="house",
                ticker=m.group("ticker"),
                asset=name,
                asset_type=atype,
                raw_type=f"[{code}]",
                value_lo=blo,
                value_hi=bhi,
                value_label=label,
                owner=m.group("owner") or None,
                source_url=source_url,
                filing_date=filing_date,
                report_year=report_year,
                option=_house_option_detail(lines, i) if atype == "Option" else None,
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


#: Why a member ended up with no holdings. Only ``ok`` and
#: ``no_individual_equities`` are *successes* — the rest mean we failed to read
#: a document that exists, which is worth a human looking at.
REASON_OK = "ok"
REASON_SCANNED = "scanned_no_text"
REASON_NO_ASSETS = "no_assets_parsed"
REASON_NO_EQUITIES = "no_individual_equities"
REASON_NO_FILING = "no_annual_filing"
REASON_UNSUPPORTED = "unsupported_chamber"
REASON_ERROR = "error"

#: Reasons that represent a genuine gap in coverage rather than a true zero.
NEEDS_REVIEW = frozenset(
    {REASON_SCANNED, REASON_NO_ASSETS, REASON_NO_FILING, REASON_ERROR}
)

REASON_TEXT = {
    REASON_OK: "parsed",
    REASON_SCANNED: "scanned report — no text layer to read",
    REASON_NO_ASSETS: "text extracted but no assets parsed — parser may need work",
    REASON_NO_EQUITIES: "parsed fine; holds no individual stocks (funds only)",
    REASON_NO_FILING: "no annual report found for the years searched",
    REASON_UNSUPPORTED: "chamber not supported (executive files a scanned OGE 278)",
    REASON_ERROR: "fetch or parse raised",
}


def classify(*, has_text: bool, parsed: int, kept: int) -> str:
    """Why did this member end up with `kept` stocks? Pure, so it is tested.

    The distinction that matters: a member holding **only funds** parses
    perfectly and legitimately has zero individual equities. Collapsing that
    into the same "unavailable" flag as an unreadable scan hides real coverage
    gaps behind data that is actually correct.
    """
    if not has_text:
        return REASON_SCANNED
    if parsed == 0:
        return REASON_NO_ASSETS
    if kept == 0:
        return REASON_NO_EQUITIES
    return REASON_OK


def fetch_holdings(
    session, ref: AnnualRef, *, member: str
) -> tuple[list[Holding], str]:
    """Fetch + parse a member's latest annual report into stock holdings.

    Returns ``(stocks, reason)`` — see ``classify``. The reason is carried all
    the way into holdings.json so an empty result can be triaged without
    re-running the fetch.
    """
    from . import house, senate
    from .http import polite_get

    if ref.chamber == "senate":
        html = polite_get(
            session, ref.url, headers={"Referer": senate.SEARCH_REFERER}
        ).text
        has_text = bool(html.strip())
        holds = parse_senate_annual_assets(
            html, member=member, source_url=ref.url,
            filing_date=ref.filing_date, report_year=ref.report_year,
        )
    else:
        text = house.extract_pdf_text(polite_get(session, ref.url).content)
        has_text = bool(text.strip())
        holds = (
            parse_house_annual_assets(
                text, member=member, source_url=ref.url,
                filing_date=ref.filing_date, report_year=ref.report_year,
            )
            if has_text
            else []
        )
    kept = [h for h in holds if is_stock_or_option(h)]
    return kept, classify(has_text=has_text, parsed=len(holds), kept=len(kept))
