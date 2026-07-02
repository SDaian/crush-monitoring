"""Stock price lookup for the "return since disclosed buy" feature.

For each disclosed **buy** of a listed US equity, we estimate how the stock
has performed since the trade date:

    pct = (latest_close - close_on_buy_date) / close_on_buy_date * 100

This is deliberately a *stock-performance* number, **not** the member's
realized profit — holding period, later sells, dividends and position size
are all unknown, and the STOCK Act discloses a trade date, not a fill price
(so we use that day's close as a proxy). The page must label it accordingly.

Price data comes from Stooq (https://stooq.com), which serves free daily-close
CSVs with no API key. Only the network fetch lives in ``fetch_history`` (via
``congress.http``); parsing/return math is pure stdlib, so tests run offline.
"""

from __future__ import annotations

import bisect
import re
from datetime import date

STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"


def stooq_symbol(ticker: str) -> str:
    """Map a disclosed ticker to a Stooq US symbol.

    Stooq lowercases and suffixes ``.us``; share-class dots become hyphens
    (``BRK.B`` → ``brk-b.us``).
    """
    core = re.sub(r"[^a-z0-9]+", "-", ticker.strip().lower()).strip("-")
    return f"{core}.us"


def parse_history(csv_text: str) -> dict[str, float]:
    """Parse a Stooq daily CSV into ``{iso_date: close}``.

    Returns an empty dict for the "no data" / unlisted case (Stooq answers
    unknown symbols with a one-line body rather than a table).
    """
    hist: dict[str, float] = {}
    header_seen = False
    for line in csv_text.splitlines():
        parts = line.split(",")
        if not header_seen:
            header_seen = True
            # Header is "Date,Open,High,Low,Close,Volume"; anything else
            # (e.g. "No data") means there is no series.
            if parts[:1] != ["Date"]:
                return {}
            cols = {name: i for i, name in enumerate(parts)}
            continue
        if len(parts) < 5:
            continue
        d = parts[cols["Date"]].strip()
        raw = parts[cols["Close"]].strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) or not raw:
            continue
        try:
            hist[d] = float(raw)
        except ValueError:
            continue
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


def fetch_history(session, ticker: str) -> PriceSeries:
    """Download and parse a ticker's Stooq daily history (network)."""
    from .http import polite_get

    url = STOOQ_URL.format(symbol=stooq_symbol(ticker))
    text = polite_get(session, url).text
    return PriceSeries(parse_history(text))


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
