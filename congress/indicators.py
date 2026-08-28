"""Mechanical technical indicators for the "Featured stocks" tab.

This module computes a small, **descriptive** set of daily technical readings
for a fixed featured universe (chips, hyperscalers, data-center build-out, plus
a few off-theme names): the latest close, short/medium/long moving averages, Wilder's RSI,
period returns, volume vs. its 20-day average, and the 52-week range.

It is deliberately *indicators only* — the module never emits a buy / sell /
hold recommendation. The tracker's standing rule is "not investment advice";
any verdict is left to the reader (or to whatever assistant they paste the
page's pre-filled prompt into). Every number here is a mechanical function of
past daily closes, is a **daily snapshot** (not real-time), and is labelled as
such on the page.

Only the caller touches the network — it reuses ``congress.prices`` for the
Twelve Data fetch/session/key. Parsing and the indicator math are pure stdlib,
so the tests run offline against a JSON fixture.
"""

from __future__ import annotations

import json
import re
from datetime import date

# The featured stock universe (ticker → display name). Order drives the card
# strip on the page: chip / foundry names first, then hyperscalers & big-tech,
# then the data-center / power / server build-out. Any of these can be traded
# by members of Congress, which is why they live in this repo rather than a
# generic screener.
AI_TICKERS: list[dict[str, str]] = [
    {"ticker": "NVDA", "name": "NVIDIA"},
    {"ticker": "AMD", "name": "Advanced Micro Devices"},
    {"ticker": "INTC", "name": "Intel"},
    {"ticker": "AVGO", "name": "Broadcom"},
    {"ticker": "MU", "name": "Micron Technology"},
    {"ticker": "TSM", "name": "Taiwan Semiconductor (TSMC)"},
    {"ticker": "ASML", "name": "ASML Holding"},
    {"ticker": "AMAT", "name": "Applied Materials"},
    {"ticker": "LRCX", "name": "Lam Research"},
    {"ticker": "KLAC", "name": "KLA Corporation"},
    {"ticker": "SNDK", "name": "Sandisk"},
    {"ticker": "MSFT", "name": "Microsoft"},
    {"ticker": "GOOGL", "name": "Alphabet (Class A)"},
    {"ticker": "AMZN", "name": "Amazon"},
    {"ticker": "META", "name": "Meta Platforms"},
    {"ticker": "TSLA", "name": "Tesla"},
    {"ticker": "VRT", "name": "Vertiv Holdings"},
    {"ticker": "VST", "name": "Vistra"},
    {"ticker": "BE", "name": "Bloom Energy"},
    {"ticker": "SMCI", "name": "Super Micro Computer"},
    {"ticker": "DELL", "name": "Dell Technologies"},
    # Off-theme (not AI) but featured by request — tracked for their own sake.
    {"ticker": "YPF", "name": "YPF S.A. (ADR)"},
    {"ticker": "MELI", "name": "MercadoLibre"},
    {"ticker": "NU", "name": "Nu Holdings"},
    {"ticker": "SPCX", "name": "SpaceX"},
    {"ticker": "MP", "name": "MP Materials"},
    {"ticker": "UUUU", "name": "Energy Fuels"},
    {"ticker": "REMX", "name": "VanEck Rare Earth & Strategic Metals ETF"},
    {"ticker": "CC", "name": "Chemours"},
    {"ticker": "ROK", "name": "Rockwell Automation"},
    {"ticker": "EMR", "name": "Emerson Electric"},
    {"ticker": "V", "name": "Visa"},
    {"ticker": "PYPL", "name": "PayPal"},
    {"ticker": "SNOW", "name": "Snowflake"},
    {"ticker": "NOW", "name": "ServiceNow"},
]


def featured_set() -> set[str]:
    """The featured watchlist as a set — the universe the morning email scores
    and the tracker's "Featured stocks" tab shows."""
    return {t["ticker"] for t in AI_TICKERS}


def reading_universe(page_tickers: list[str],
                     names: dict[str, str] | None = None) -> list[dict]:
    """Every symbol we compute a daily reading for.

    A reading costs one API call, so the universe used to be the hand-written
    featured list above. That made the two universes disagree: ticker pages
    pick themselves by substance (disclosed trades), readings were picked by
    theme — so AAPL, the third most-traded stock in Congress, had a page with
    no reading. The rule now is one rule: **every symbol with a page gets a
    reading.** Pass the page universe (``landing_data.select_ticker_pages``,
    or the generated ticker index) and this orders it featured-first, because
    that order still drives the email scorecard and the tracker tab.

    Each entry is ``{ticker, name, featured}``. ``featured`` is what the
    surfaces that must stay short filter on.
    """
    names = names or {}
    featured = featured_set()
    out = [{"ticker": t["ticker"], "name": t["name"], "featured": True}
           for t in AI_TICKERS]
    seen = {t["ticker"] for t in out}
    for tk in page_tickers:
        if not tk or tk in seen:
            continue
        seen.add(tk)
        out.append({"ticker": tk, "name": names.get(tk) or tk,
                    "featured": tk in featured})
    return out


# Trading-day windows (approximate calendar spans in sessions).
RSI_PERIOD = 14
SMA_WINDOWS = (20, 50, 200)
WEEK = 5
MONTH = 21
YEAR = 252


def parse_series(body: str) -> list[dict]:
    """Parse a Twelve Data ``time_series`` body into ascending OHLCV-ish rows.

    Returns ``[{"date": iso, "close": float, "volume": float}]`` sorted oldest
    → newest. The API answers newest-first and wraps errors / unknown symbols
    in ``{"status": "error", ...}``; those yield an empty list.
    """
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, dict) or data.get("status") != "ok":
        return []
    rows: list[dict] = []
    for row in data.get("values") or []:
        d = str(row.get("datetime", "")).strip()[:10]
        raw_close = str(row.get("close", "")).strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) or not raw_close:
            continue
        try:
            close = float(raw_close)
        except ValueError:
            continue
        try:
            volume = float(str(row.get("volume", "")).strip() or "nan")
        except ValueError:
            volume = float("nan")
        rows.append({"date": d, "close": close, "volume": volume})
    rows.sort(key=lambda r: r["date"])
    return rows


def sma(values: list[float], n: int) -> float | None:
    """Simple moving average of the last ``n`` values, or None if too few."""
    if len(values) < n or n <= 0:
        return None
    return sum(values[-n:]) / n


def pct_change(closes: list[float], periods: int) -> float | None:
    """Percent change of the latest close vs. the close ``periods`` sessions
    ago, or None if the history is too short or the prior close is non-positive."""
    if len(closes) <= periods or periods <= 0:
        return None
    prev = closes[-periods - 1]
    if prev <= 0:
        return None
    return (closes[-1] - prev) / prev * 100.0


def wilder_rsi(closes: list[float], n: int = RSI_PERIOD) -> float | None:
    """Wilder's Relative Strength Index over ``n`` periods (needs n+1 closes).

    Seeds the average gain/loss with the simple mean of the first ``n`` deltas,
    then applies Wilder smoothing to the rest. Returns 100.0 when there is no
    average loss (pure up-run), 0.0 for a pure down-run, or None if there are
    not enough closes.
    """
    if len(closes) < n + 1 or n <= 0:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]
    avg_gain = sum(gains[:n]) / n
    avg_loss = sum(losses[:n]) / n
    for i in range(n, len(deltas)):
        avg_gain = (avg_gain * (n - 1) + gains[i]) / n
        avg_loss = (avg_loss * (n - 1) + losses[i]) / n
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _round(x: float | None, places: int) -> float | None:
    return None if x is None else round(x, places)


# Named mechanical signals. ``dir`` is only a *visual* hint of the event's
# conventional technical connotation (bull = commonly read constructive,
# bear = cautionary, neutral = a momentum-stretch flag) — it is NOT a
# recommendation. The label states the event; the reader draws the conclusion.
SIGNAL_DEFS: dict[str, dict[str, str]] = {
    "golden_cross": {"label": "Golden cross (50-day above 200-day)", "dir": "bull"},
    "death_cross": {"label": "Death cross (50-day below 200-day)", "dir": "bear"},
    "reclaim_sma50": {"label": "Reclaimed the 50-day average", "dir": "bull"},
    "lose_sma50": {"label": "Lost the 50-day average", "dir": "bear"},
    "new_52w_high": {"label": "New 52-week high", "dir": "bull"},
    "new_52w_low": {"label": "New 52-week low", "dir": "bear"},
    "rsi_oversold": {"label": "RSI crossed below 30 (oversold)", "dir": "neutral"},
    "rsi_overbought": {"label": "RSI crossed above 70 (overbought)", "dir": "neutral"},
}


def compute_signals(rows: list[dict]) -> list[dict]:
    """Detect the mechanical signals that *fire on the latest bar*.

    A signal is an event — a crossing between the latest close/indicator and
    the prior one — so it triggers once, on the day it happens, and is empty on
    every other day. Returns ``[{type, label, dir, asof}]`` (usually empty).
    Signals whose underlying average lacks enough history are simply skipped.
    """
    closes = [r["close"] for r in rows]
    if len(closes) < 2:
        return []
    out: list[dict] = []
    asof = rows[-1]["date"]
    c, cp = closes[-1], closes[-2]

    def emit(t: str) -> None:
        out.append({"type": t, "asof": asof, **SIGNAL_DEFS[t]})

    # Moving-average crosses (need the 200-day today AND yesterday → 201 bars).
    s50, s50p = sma(closes, 50), sma(closes[:-1], 50)
    s200, s200p = sma(closes, 200), sma(closes[:-1], 200)
    if None not in (s50, s50p, s200, s200p):
        if s50p <= s200p and s50 > s200:
            emit("golden_cross")
        elif s50p >= s200p and s50 < s200:
            emit("death_cross")
    # Price reclaiming / losing its 50-day average.
    if s50 is not None and s50p is not None:
        if cp <= s50p and c > s50:
            emit("reclaim_sma50")
        elif cp >= s50p and c < s50:
            emit("lose_sma50")
    # RSI crossing into an extreme zone.
    r, rp = wilder_rsi(closes), wilder_rsi(closes[:-1])
    if r is not None and rp is not None:
        if rp >= 30 and r < 30:
            emit("rsi_oversold")
        elif rp <= 70 and r > 70:
            emit("rsi_overbought")
    # New 52-week extreme vs. the prior (up to) 252-session window.
    prior = closes[-(YEAR + 1):-1]
    if prior:
        if c > max(prior):
            emit("new_52w_high")
        elif c < min(prior):
            emit("new_52w_low")
    return out


def signal_key(ticker: str, sig: dict) -> str:
    """Stable dedup key for one fired signal (ticker + type + bar date)."""
    return f"{ticker}|{sig['type']}|{sig['asof']}"


def ai_score(t: dict) -> dict:
    """Mechanical buy/hold/sell tally from one ticker's indicators.

    This MUST mirror ``aiScore`` in docs/trades.html exactly (same checks,
    same thresholds) so the page and the morning report agree. Each check
    votes buy(+1)/hold(0)/sell(-1); the net ratio maps to a label. It is a
    transparent rule-based read, NOT investment advice.
    """
    def cmp(x, y):
        return 1 if x > y else -1 if x < y else 0

    votes: list[int] = []
    p = t.get("price")
    if p is not None and t.get("sma20") is not None:
        votes.append(cmp(p, t["sma20"]))
    if p is not None and t.get("sma50") is not None:
        votes.append(cmp(p, t["sma50"]))
    if p is not None and t.get("sma200") is not None:
        votes.append(cmp(p, t["sma200"]))
    if t.get("sma50") is not None and t.get("sma200") is not None:
        votes.append(cmp(t["sma50"], t["sma200"]))
    r = t.get("rsi14")
    if r is not None:
        votes.append(1 if r < 30 else -1 if r > 70 else 0)
    if t.get("chg_1m") is not None:
        votes.append(cmp(t["chg_1m"], 0))
    if t.get("chg_1w") is not None:
        votes.append(cmp(t["chg_1w"], 0))

    buys = sum(1 for v in votes if v > 0)
    sells = sum(1 for v in votes if v < 0)
    holds = sum(1 for v in votes if v == 0)
    total = len(votes) or 1
    ratio = (buys - sells) / total
    if ratio >= 0.5:
        label = "Strong Buy"
    elif ratio >= 0.15:
        label = "Buy"
    elif ratio <= -0.5:
        label = "Strong Sell"
    elif ratio <= -0.15:
        label = "Sell"
    else:
        label = "Hold"
    return {"label": label, "buys": buys, "sells": sells, "holds": holds,
            "ratio": round(ratio, 3)}


def next_earnings(body: str, today: str) -> dict | None:
    """The next scheduled earnings date from a Twelve Data ``earnings`` body,
    or None. Pure, so it is tested offline.

    "Next" means the earliest dated entry strictly after ``today``: the feed
    mixes reported history with upcoming dates, and a past date is not a
    schedule. Anything unparseable yields None — the page then shows nothing
    rather than a guess.
    """
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None
    rows = data.get("earnings") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return None
    upcoming = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        d = str(r.get("date", "")).strip()[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) or d <= today:
            continue
        upcoming.append({"date": d, "time": str(r.get("time") or "").strip()})
    if not upcoming:
        return None
    upcoming.sort(key=lambda r: r["date"])
    return upcoming[0]


def weekly_closes(rows: list[dict], weeks: int = 52) -> list[dict]:
    """One close per ISO week for the last ``weeks`` weeks — the sparkline on
    the ticker page. Derived from the series already fetched for the
    indicators, so it costs no extra API call. Each point is the LAST close
    of its week, which is what a weekly chart plots."""
    by_week: dict[tuple[int, int], dict] = {}
    for r in rows:
        if r.get("close") is None or not r.get("date"):
            continue
        try:
            y, w, _ = date.fromisoformat(r["date"]).isocalendar()
        except ValueError:
            continue
        by_week[(y, w)] = {"d": r["date"], "c": round(r["close"], 2)}
    points = [by_week[k] for k in sorted(by_week)]
    return points[-weeks:]


def compute_indicators(rows: list[dict]) -> dict | None:
    """Compute the descriptive indicator bundle for one ticker, or None.

    ``rows`` is the ascending output of :func:`parse_series`. Returns None when
    there is no usable price history at all; individual indicators that lack
    enough history are simply ``None`` (the page renders those as "—").
    """
    closes = [r["close"] for r in rows if r["close"] is not None]
    if not closes:
        return None
    vols = [r["volume"] for r in rows if r["volume"] == r["volume"]]  # drop NaN
    last = closes[-1]
    window52 = closes[-YEAR:] if len(closes) >= YEAR else closes
    high52 = max(window52)
    low52 = min(window52)

    smas = {n: sma(closes, n) for n in SMA_WINDOWS}
    vol = vols[-1] if vols else None
    avg_vol = sma(vols, 20) if len(vols) >= 20 else None

    return {
        "asof_date": rows[-1]["date"],
        "price": round(last, 2),
        "chg_1d": _round(pct_change(closes, 1), 2),
        "chg_1w": _round(pct_change(closes, WEEK), 2),
        "chg_1m": _round(pct_change(closes, MONTH), 2),
        "rsi14": _round(wilder_rsi(closes, RSI_PERIOD), 1),
        "sma20": _round(smas[20], 2),
        "sma50": _round(smas[50], 2),
        "sma200": _round(smas[200], 2),
        # Price relative to each MA, in percent (positive = price above the MA).
        "vs_sma50": _round(
            (last / smas[50] - 1) * 100 if smas[50] else None, 1),
        "vs_sma200": _round(
            (last / smas[200] - 1) * 100 if smas[200] else None, 1),
        "volume": int(vol) if vol is not None else None,
        "avg_vol_20": int(avg_vol) if avg_vol is not None else None,
        "rel_vol": _round(vol / avg_vol if avg_vol else None, 2),
        "high_52w": round(high52, 2),
        "low_52w": round(low52, 2),
        # Where the price sits in its 52-week range, 0 (low) → 100 (high).
        "range_pos": _round(
            (last - low52) / (high52 - low52) * 100 if high52 > low52 else None,
            0),
        "bars": len(closes),
        # Weekly closes for the ticker page's sparkline (no extra fetch).
        "series": weekly_closes(rows),
    }
