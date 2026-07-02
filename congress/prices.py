"""Stock price lookup for the "return since disclosed buy" feature.

For each disclosed **buy** of a listed US equity, we estimate how the stock
has performed since the trade date:

    pct = (latest_close - close_on_buy_date) / close_on_buy_date * 100

This is deliberately a *stock-performance* number, **not** the member's
realized profit — holding period, later sells, dividends and position size
are all unknown, and the STOCK Act discloses a trade date, not a fill price
(so we use that day's close as a proxy). The page must label it accordingly.

Prices come from Twelve Data (https://twelvedata.com), a keyed provider whose
free tier (800 calls/day, 8/min) is reachable from CI — unlike Stooq (which
now JS-walls automated requests) and Yahoo (which 429s shared runner IPs).
The API key is read from the ``CONGRESS_PRICES_KEY`` environment variable and
never written to any file, log or URL that gets printed.

Only ``fetch_raw`` / ``make_session`` touch the network; parsing and the
return math are pure stdlib, so tests run offline against a JSON fixture.
"""

from __future__ import annotations

import bisect
import json
import os
import re
import time

TD_HOST = "https://api.twelvedata.com"
# Cover the current + previous calendar year window (plus a margin so a buy
# early in the window still has a prior close). 1500 daily bars ≈ 6 years.
TD_OUTPUTSIZE = 1500
TD_INTERVAL = "1day"
# Free tier: 8 requests/minute. Pace at 8s to stay comfortably under.
TD_MIN_INTERVAL = 8.0
BROWSER_UA = "crush-monitoring congress-trades bot (+https://github.com/SDaian/crush-monitoring)"

ENV_KEY = "CONGRESS_PRICES_KEY"

_last_request = 0.0


def api_key() -> str:
    return os.environ.get(ENV_KEY, "").strip()


def td_symbol(ticker: str) -> str:
    """Map a disclosed ticker to a Twelve Data symbol (uppercase, trimmed)."""
    return ticker.strip().upper()


def make_session():
    """A plain requests.Session with a UA and retry/backoff on 429/5xx."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    session.headers["User-Agent"] = BROWSER_UA
    retry = Retry(
        total=2,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=None,
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _pace() -> None:
    global _last_request
    wait = TD_MIN_INTERVAL - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def fetch_raw(session, ticker: str, key: str) -> str:
    """Download a ticker's raw Twelve Data time_series JSON (network).

    The key is sent as a query param; callers must never print the request
    URL (it would leak the key). Errors are surfaced by the caller with the
    key redacted.
    """
    _pace()
    params = {
        "symbol": td_symbol(ticker),
        "interval": TD_INTERVAL,
        "outputsize": TD_OUTPUTSIZE,
        "apikey": key,
    }
    resp = session.get(f"{TD_HOST}/time_series", params=params, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_history(body: str) -> dict[str, float]:
    """Parse a Twelve Data time_series JSON body into ``{iso_date: close}``.

    Returns an empty dict for the error / unknown-symbol / rate-limited case
    (Twelve Data answers those with ``{"status": "error", ...}``).
    """
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict) or data.get("status") != "ok":
        return {}
    hist: dict[str, float] = {}
    for row in data.get("values") or []:
        d = str(row.get("datetime", "")).strip()[:10]
        raw = str(row.get("close", "")).strip()
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


def fetch_history(session, ticker: str, key: str) -> PriceSeries:
    """Download and parse a ticker's Twelve Data daily history (network)."""
    return PriceSeries(parse_history(fetch_raw(session, ticker, key)))


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


# Assets whose "return" isn't the underlying equity's move, so we never price
# them even though they carry a ticker (mirrors the page's guard).
NON_EQUITY = {"Option", "Cryptocurrency"}


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
        if t.get("asset_type") in NON_EQUITY:
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
    """Every ticker on at least one equity buy, sorted (options/crypto excl.)."""
    return sorted({
        t["ticker"] for t in trades
        if t.get("type") == "buy" and t.get("ticker")
        and t.get("asset_type") not in NON_EQUITY
    })


def select_tickers(trades: list[dict], featured: list[str], top_n: int) -> list[str]:
    """Featured tickers plus the ``top_n`` most-traded — the set worth the
    free-tier quota. Buys of the long tail keep showing “—”."""
    from collections import Counter
    counts = Counter(
        t["ticker"] for t in trades
        if t.get("type") == "buy" and t.get("ticker")
        and t.get("asset_type") not in NON_EQUITY
    )
    top = [tk for tk, _ in counts.most_common(top_n)]
    return sorted(set(featured) | set(top))
