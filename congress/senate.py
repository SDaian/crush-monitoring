"""Senate eFD (efdsearch.senate.gov) listing and PTR parsing.

Network functions take a requests session (built by ``congress.http``); all
parsing functions are pure stdlib functions of strings so they are fixture-
testable offline.

Flow (electronic filing search):
1. GET  /search/home/  → disclaimer form with a csrfmiddlewaretoken.
2. POST /search/home/  with the token + prohibition_agreement=1 → session
   cookies now allow searching.
3. POST /search/report/data/ (DataTables protocol) → JSON rows
   ``[first, last, <a href=…>report title</a>, date_received]``.
4. GET each electronic PTR page (/search/view/ptr/<uuid>/) → HTML table of
   transactions. Paper filings (/search/view/paper/…) are scanned images:
   skipped, linked, counted.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from .normalize import Trade, parse_amount, parse_date, parse_tx_type

BASE = "https://efdsearch.senate.gov"
HOME_URL = f"{BASE}/search/home/"
SEARCH_URL = f"{BASE}/search/report/data/"
SEARCH_REFERER = f"{BASE}/search/"
PTR_REPORT_TYPE = "[11]"  # eFD code for Periodic Transaction Reports
PAGE_SIZE = 100
MAX_PAGES = 200  # hard cap so a protocol change cannot loop forever

_CSRF_INPUT = re.compile(
    r"name=['\"]csrfmiddlewaretoken['\"]\s+value=['\"]([^'\"]+)['\"]"
)
_LINK = re.compile(r"href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", re.S)

_OWNER_MAP = {
    "self": None,
    "spouse": "SP",
    "joint": "JT",
    "child": "DC",
    "dependent child": "DC",
}


@dataclass
class SenateFilingRef:
    filing_id: str    # eFD report UUID
    name: str         # "First Last" as filed
    filed_date: str   # ISO
    url: str          # absolute report URL
    is_paper: bool
    title: str        # report link text (may say "(Amendment)")


class EfdError(RuntimeError):
    """eFD responded in an unexpected shape; message carries a body snippet."""


def _snippet(text: str, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", text)[:limit]


# ---------------------------------------------------------------------------
# Session dance + search (network)
# ---------------------------------------------------------------------------

def accept_disclaimer(session) -> None:
    """Accept the eFD prohibition-of-use agreement so searches work."""
    from .http import polite_get, polite_post

    resp = polite_get(session, HOME_URL)
    match = _CSRF_INPUT.search(resp.text)
    if not match:
        raise EfdError(
            "eFD disclaimer page had no csrfmiddlewaretoken; body: "
            + _snippet(resp.text)
        )
    resp = polite_post(
        session,
        HOME_URL,
        data={
            "csrfmiddlewaretoken": match.group(1),
            "prohibition_agreement": "1",
        },
        headers={"Referer": HOME_URL},
    )
    if "csrftoken" not in session.cookies:
        raise EfdError(
            "eFD disclaimer POST did not set a csrftoken cookie; body: "
            + _snippet(resp.text)
        )


def search_ptrs(session, date_from: str, date_to: str = "") -> list[SenateFilingRef]:
    """List PTR filings submitted in the date range (``MM/DD/YYYY`` bounds)."""
    from .http import polite_post

    refs: list[SenateFilingRef] = []
    for page in range(MAX_PAGES):
        start = page * PAGE_SIZE
        data = {
            "draw": str(page + 1),
            "start": str(start),
            "length": str(PAGE_SIZE),
            "report_types": PTR_REPORT_TYPE,
            "filer_types": "[]",
            "submitted_start_date": f"{date_from} 00:00:00" if date_from else "",
            "submitted_end_date": f"{date_to} 00:00:00" if date_to else "",
            "candidate_state": "",
            "senator_state": "",
            "office_id": "",
            "first_name": "",
            "last_name": "",
        }
        resp = polite_post(
            session,
            SEARCH_URL,
            data=data,
            headers={
                "Referer": SEARCH_REFERER,
                "X-CSRFToken": session.cookies.get("csrftoken", ""),
            },
        )
        try:
            payload = resp.json()
        except ValueError:
            raise EfdError(
                "eFD search returned non-JSON; body: " + _snippet(resp.text)
            ) from None
        rows = parse_search_rows(payload)
        refs.extend(rows)
        if len(rows) < PAGE_SIZE:
            return refs
    raise EfdError(f"eFD search exceeded {MAX_PAGES} pages; aborting")


_DATE_CELL = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def parse_search_rows(payload: dict) -> list[SenateFilingRef]:
    """Pure parser for one DataTables response page.

    Column layout has drifted before (an office/full-name text column sits
    between the name and the report link), so the link and date cells are
    located by content rather than by position; only first/last name are
    trusted to be columns 0 and 1.
    """
    if not isinstance(payload, dict) or "data" not in payload:
        raise EfdError(
            "eFD search payload missing 'data': " + _snippet(json.dumps(payload)[:500])
        )
    refs = []
    for row in payload["data"]:
        if len(row) < 4:
            raise EfdError(f"eFD search row too short: {row!r}")
        cells = [str(c) for c in row]
        first, last = cells[0], cells[1]
        link = next((m for m in map(_LINK.search, cells) if m), None)
        if not link:
            raise EfdError(f"eFD search row has no report link: {cells!r}")
        filed = next(
            (c.strip() for c in cells if _DATE_CELL.match(c.strip())), None
        )
        if not filed:
            raise EfdError(f"eFD search row has no filed date: {cells!r}")
        href, title = link.group(1), re.sub(r"\s+", " ", link.group(2)).strip()
        url = href if href.startswith("http") else BASE + href
        filing_id = url.rstrip("/").rsplit("/", 1)[-1]
        refs.append(
            SenateFilingRef(
                filing_id=filing_id,
                name=f"{first.strip()} {last.strip()}".strip(),
                filed_date=parse_date(filed),
                url=url,
                is_paper="/search/view/paper/" in url,
                title=title,
            )
        )
    return refs


def fetch_ptr_html(session, ref: SenateFilingRef) -> str:
    from .http import polite_get

    return polite_get(session, ref.url, headers={"Referer": SEARCH_REFERER}).text


# ---------------------------------------------------------------------------
# PTR page parsing (pure stdlib)
# ---------------------------------------------------------------------------

class _TableParser(HTMLParser):
    """Collect every <table> as a list of rows of stripped cell texts."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            text = re.sub(r"\s+", " ", "".join(self._cell)).strip()
            self._row.append(text)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.tables[-1].append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_ptr_html(html: str, ref: SenateFilingRef) -> list[Trade]:
    """Parse an electronic eFD PTR page into normalized trades.

    Expected transaction-table columns:
    # | Transaction Date | Owner | Ticker | Asset Name | Asset Type | Type |
    Amount | Comment. Raises ``ValueError``/``EfdError`` on shape surprises so
    the caller can record the filing as a parse error.
    """
    parser = _TableParser()
    parser.feed(html)
    table = _pick_transaction_table(parser.tables)
    if table is None:
        raise EfdError(f"eFD PTR {ref.filing_id}: no transaction table found")
    trades = []
    for cells in table:
        if not cells or not cells[0].rstrip(".").isdigit():
            continue  # header or footer row
        if len(cells) < 8:
            raise EfdError(
                f"eFD PTR {ref.filing_id}: row has {len(cells)} cells: {cells!r}"
            )
        (_, tx_date, owner, ticker, asset, asset_type, tx_type, amount) = cells[:8]
        kind, partial = parse_tx_type(tx_type)
        lo, hi, label = parse_amount(amount)
        ticker_clean = ticker.strip().strip("-").strip() or None
        trades.append(
            Trade(
                id=f"senate:{ref.filing_id}:{len(trades)}",
                chamber="senate",
                member=ref.name,
                ticker=ticker_clean,
                asset=asset,
                asset_type=asset_type or None,
                type=kind,
                partial=partial,
                owner=_OWNER_MAP.get(owner.strip().lower(), owner.strip() or None),
                tx_date=parse_date(tx_date),
                filing_date=ref.filed_date,
                amount_lo=lo,
                amount_hi=hi,
                amount_label=label,
                filing_id=ref.filing_id,
                source_url=ref.url,
            )
        )
    if not trades:
        raise EfdError(f"eFD PTR {ref.filing_id}: transaction table had no rows")
    return trades


def _pick_transaction_table(tables: list[list[list[str]]]):
    """Choose the table whose header mentions both Transaction Date and Amount."""
    for table in tables:
        for row in table[:2]:
            joined = " ".join(row).lower()
            if "transaction date" in joined and "amount" in joined:
                return table
    # fall back to the single table if the page has exactly one
    return tables[0] if len(tables) == 1 else None
