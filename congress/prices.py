"""Stock price lookup for the "return since disclosed buy" feature.

For each disclosed **buy** of a listed US equity, we estimate how the stock
has performed since the trade date:

    pct = (latest_close - close_on_buy_date) / close_on_buy_date * 100

This is deliberately a *stock-performance* number, **not** the member's
realized profit — holding period, later sells, dividends and position size
are all unknown, and the STOCK Act discloses a trade date, not a fill price
(so we use that day's close as a proxy). The page must label it accordingly.

Prices come from the free Yahoo Finance chart API (JSON, no API key). We use
the **adjusted** close so stock splits and dividends don't distort the
estimate. Stooq — the obvious free CSV source — now gates automated requests
behind a JavaScript anti-bot challenge, so it cannot be used headless.

Only the network fetch lives in ``fetch_raw`` (via ``congress.http``);
parsing and the return math are pure stdlib, so tests run offline.
"""

from __future__ import annotations

import bisect
import json
import re
from datetime import datetime, timezone

# 3 years of daily candles comfortably covers the current + previous calendar
# year window the tracker keeps.
YAHOO_HOST = "https://query1.finance.yahoo.com"
CHART_PATH = "/v8/finance/chart/{symbol}?range=3y&interval=1d"
# Yahoo 429s anonymous/datacenter requests; a browser UA plus a cookie+crumb
# session (below) is what lets CI reach the chart API — the same handshake
# yfinance uses.
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def make_price_session():
    """A requests.Session primed with Yahoo cookies + crumb.

    Anonymous requests from shared CI IPs get 429'd; establishing the cookie
    Yahoo sets on its consent host and fetching a crumb makes the session look
    like a real browser and lifts the block. Network-only, so imported lazily
    and never touched by the offline tests.
    """
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    session.headers["User-Agent"] = BROWSER_UA
    retry = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=None,
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    crumb = ""
    try:  # cookie handshake, then a crumb tied to that cookie
        session.get("https://fc.yahoo.com/", timeout=10)
        resp = session.get(f"{YAHOO_HOST}/v1/test/getcrumb", timeout=10)
        text = resp.text.strip()
        if resp.ok and text and "<" not in text:
            crumb = text
    except Exception:
        pass
    session.crumb = crumb
    return session


def yahoo_symbol(ticker: str) -> str:
    """Map a disclosed ticker to a Yahoo symbol.

    Yahoo uppercases and writes share classes with a hyphen (``BRK.B`` →
    ``BRK-B``); ADRs like ``TSM`` are unchanged.
    """
    return re.sub(r"[^A-Z0-9]+", "-", ticker.strip().upper()).strip("-")


def parse_history(body: str) -> dict[str, float]:
    """Parse a Yahoo chart JSON body into ``{iso_date: adjusted_close}``.

    Returns an empty dict for the unknown-symbol / no-data case.
    """
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return {}
    chart = (data or {}).get("chart") or {}
    results = chart.get("result") or []
    if chart.get("error") or not results:
        return {}
    res = results[0]
    stamps = res.get("timestamp") or []
    indicators = res.get("indicators") or {}
    adj = (indicators.get("adjclose") or [{}])[0].get("adjclose")
    quote = (indicators.get("quote") or [{}])[0].get("close")
    closes = adj if adj is not None else quote
    if not stamps or not closes:
        return {}
    hist: dict[str, float] = {}
    for ts, close in zip(stamps, closes):
        if close is None:
            continue
        iso = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        hist[iso] = float(close)
    return hist


class PriceSeries:
    """A ticker's daily closes with nearest-trading-day lookup."""

    def __init__(self, hist: dict[str, float]):
        self.dates = sorted(hist)
        self.hist = hist

    def __bool__(self) -> bool:
        return bool(self.dates)

    def close_on_or_before(self, iso: str) -> tuple[str, float] | None:
        """Close on ``iso`` or the most recent trading day before it.

        Markets are shut on weekends/holidays, so a buy dated on a closed day
        resolves to the prior session. Returns None if the series starts
        after ``iso`` (no entry price available).
        """
        i = bisect.bisect_right(self.dates, iso) - 1
        if i < 0:
            return None
        d = self.dates[i]
        return d, self.hist[d]

    def latest(self) -> tuple[str, float] | None:
        if not self.dates:
            return None
        d = self.dates[-1]
        return d, self.hist[d]


def fetch_raw(session, ticker: str) -> str:
    """Download a ticker's raw Yahoo chart JSON body (network)."""
    import urllib.parse

    from .http import polite_get

    url = YAHOO_HOST + CHART_PATH.format(symbol=yahoo_symbol(ticker))
    crumb = getattr(session, "crumb", "")
    if crumb:
        url += "&crumb=" + urllib.parse.quote(crumb, safe="")
    return polite_get(session, url).text


def fetch_history(session, ticker: str) -> PriceSeries:
    """Download and parse a ticker's Yahoo daily history (network)."""
    return PriceSeries(parse_history(fetch_raw(session, ticker)))


def buy_return(series: PriceSeries, tx_date: str) -> dict | None:
    """Compute the since-buy return record for one buy, or None if unpriced."""
    if not series:
        return None
    entry = series.close_on_or_before(tx_date)
    latest = series.latest()
    if not entry or not latest or entry[1] <= 0:
        return None
    entry_date, entry_close = entry
    latest_date, latest_close = latest
    pct = (latest_close - entry_close) / entry_close * 100
    return {
        "entry_date": entry_date,
        "entry_close": round(entry_close, 4),
        "latest_date": latest_date,
        "latest_close": round(latest_close, 4),
        "pct": round(pct, 1),
    }


def compute_returns(trades: list[dict], series_by_ticker: dict[str, PriceSeries]):
    """Build the returns map for every priceable buy.

    Returns ``(returns_by_id, prices_by_ticker, stats)`` where
    ``returns_by_id`` maps trade id → {entry_date, entry_close, pct, …}, and
    ``prices_by_ticker`` maps ticker → {asof_date, asof_close} for tooltips.
    """
    returns: dict[str, dict] = {}
    prices: dict[str, dict] = {}
    total_buys = 0
    for t in trades:
        if t.get("type") != "buy" or not t.get("ticker"):
            continue
        total_buys += 1
        series = series_by_ticker.get(t["ticker"])
        if not series:
            continue
        rec = buy_return(series, t["tx_date"])
        if rec is None:
            continue
        returns[t["id"]] = {
            "entry_date": rec["entry_date"],
            "entry_close": rec["entry_close"],
            "pct": rec["pct"],
        }
        prices[t["ticker"]] = {
            "asof_date": rec["latest_date"],
            "asof_close": rec["latest_close"],
        }
    stats = {
        "total_buys": total_buys,
        "priced_buys": len(returns),
        "tickers": len(prices),
    }
    return returns, prices, stats


def distinct_buy_tickers(trades: list[dict]) -> list[str]:
    """Every ticker that appears on at least one buy, sorted."""
    return sorted({t["ticker"] for t in trades
                   if t.get("type") == "buy" and t.get("ticker")})
