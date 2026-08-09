"""Market-wide volatility context — one number, the same on every surface.

The featured-stock readings say how one symbol is behaving. They say nothing
about the weather the whole market trades in. A 3% drop reads very differently
in a calm tape than in a stressed one, so the morning report and every ticker
page carry one line of market context.

**The number.** First choice is the **VIX** (CBOE Volatility Index — the
market's expected 30-day swing in the S&P 500). Twelve Data lists it as an
index symbol, but index coverage is plan-dependent and the key lives in a
GitHub secret, so this is UNVERIFIED from the dev sandbox in the sense of
CLAUDE.md: probe it, and degrade instead of failing.

**The fallback.** When the VIX comes back empty we compute our own reading
from the SPY closes — annualised 20-day realized volatility. It is a
different measurement (realized looks back, the VIX looks forward) and it
usually prints a few points lower, so it is labelled as *our* number and
never called "VIX". That honesty is the whole reason the fallback is
computed rather than proxied through a VIX ETF: VIXY holds futures and
decays, so its price is not the index level and no label can fix that.

**It never votes.** The market reading is deliberately absent from
``indicators.ai_score``. That score is a per-stock tally; a market-wide input
would move all 23 ratings at once and the morning report's rating-flip diff
would stop saying anything about the stock.

Pure stdlib, no I/O — the caller fetches, this module measures. The bands are
a convention we chose (and label as such), not an official classification.
"""

from __future__ import annotations

import math

# Annualisation factor for daily returns (trading days in a year).
YEAR = 252
REALIZED_WINDOW = 20

VIX_SYMBOL = "VIX"
BENCH_SYMBOL = "SPY"

SOURCE_VIX = "vix"
SOURCE_REALIZED = "realized"

LABELS = {
    SOURCE_VIX: "VIX",
    SOURCE_REALIZED: "S&P 500 volatility",
}
NOTES = {
    SOURCE_VIX: ("CBOE Volatility Index — the market's expected 30-day swing "
                 "in the S&P 500."),
    SOURCE_REALIZED: ("Annualised 20-day realized volatility of the S&P 500, "
                      "computed from daily closes. Our own reading, not the "
                      "VIX."),
}

# Level → band. Low bound is exclusive of the band above it; the last entry
# catches everything higher. A convention, stated as one on every surface.
BANDS = (
    (15.0, "calm", "Calm"),
    (25.0, "normal", "Normal"),
    (35.0, "elevated", "Elevated"),
    (None, "stressed", "Stressed"),
)
BAND_NOTE = "Bands are our own convention, not an official classification."


def band(level: float | None) -> tuple[str, str]:
    """(key, display label) for a volatility level. ("", "") when unknown."""
    if level is None:
        return ("", "")
    for ceiling, key, label in BANDS:
        if ceiling is None or level < ceiling:
            return (key, label)
    return BANDS[-1][1], BANDS[-1][2]


def realized_vol(closes: list[float], window: int = REALIZED_WINDOW):
    """Annualised realized volatility (%) over the last ``window`` sessions.

    The standard deviation of daily log returns, scaled by √252. Returns None
    when there is not enough history or a close is unusable."""
    if window < 2 or len(closes) < window + 1:
        return None
    tail = closes[-(window + 1):]
    rets = []
    for prev, cur in zip(tail, tail[1:]):
        if not prev or not cur or prev <= 0 or cur <= 0:
            return None
        rets.append(math.log(cur / prev))
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(YEAR) * 100


def _reading(source: str, level: float | None, prev: float | None,
             asof: str) -> dict | None:
    if level is None:
        return None
    key, label = band(level)
    reading = {
        "source": source,
        "label": LABELS[source],
        "note": NOTES[source],
        "level": round(level, 2),
        "asofDate": asof,
        "band": key,
        "bandLabel": label,
        "bandNote": BAND_NOTE,
    }
    # The VIX is quoted in points, so its move is a point difference — a
    # percentage of a volatility index reads as a second-order number nobody
    # uses. Absent when there is no prior session to compare with.
    if prev is not None:
        reading["chg_1d"] = round(level - prev, 2)
    return reading


def from_vix(rows: list[dict]) -> dict | None:
    """The reading from a VIX daily series (``indicators.parse_series`` rows).

    None when the series is empty — which is exactly what the parser returns
    for an unknown symbol or a plan that does not serve indices."""
    closes = [r["close"] for r in rows if r.get("close") is not None]
    if not closes:
        return None
    prev = closes[-2] if len(closes) > 1 else None
    return _reading(SOURCE_VIX, closes[-1], prev, rows[-1]["date"])


def from_benchmark(rows: list[dict], window: int = REALIZED_WINDOW):
    """The fallback reading, computed from the S&P 500 (SPY) daily closes."""
    closes = [r["close"] for r in rows if r.get("close") is not None]
    level = realized_vol(closes, window)
    if level is None:
        return None
    # Yesterday's reading, so the line can show which way volatility moved.
    prev = realized_vol(closes[:-1], window)
    return _reading(SOURCE_REALIZED, level, prev, rows[-1]["date"])


def build(vix_rows: list[dict] | None = None,
          bench_rows: list[dict] | None = None) -> dict | None:
    """The market reading: the VIX when it is available, else our own.

    Returns None when neither source produced a number — every surface then
    simply omits the line, the same way an absent earnings date does."""
    return from_vix(vix_rows or []) or from_benchmark(bench_rows or [])


def summary(reading: dict | None) -> str:
    """One plain sentence for a text surface, "" when there is no reading."""
    if not reading:
        return ""
    move = ""
    if reading.get("chg_1d") is not None:
        chg = reading["chg_1d"]
        move = f" ({'+' if chg > 0 else ''}{chg} pts)"
    return (f"{reading['label']} {reading['level']}{move} — "
            f"{reading['bandLabel'].lower()}")
