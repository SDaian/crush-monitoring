"""Member trading performance vs the S&P 500 (pure math, no network).

Built during the daily price run, while every fetched ticker's full daily
history is still in memory (only entry/latest closes are persisted to
``returns.json``, so this cannot be recomputed later from committed data).

Two honest constructions, both equal-weighted because filings disclose
bracket amounts, never position sizes:

- **Per-buy benchmark window**: for each priced buy, the S&P's % change over
  the *same* window (trade date's close → latest close). Stored per trade in
  ``returns.json`` as ``bench_pct`` so a buy's return is always shown next to
  what the index did over the identical period.
- **The $1 race**: $1 spread equally across every priced buy at its trade
  date and held, sampled weekly — against the same $1, same dates, same
  weights, put into the S&P instead. Both sides stagger entries identically,
  so a member is never credited or penalized for *when* the comparison
  starts. Written to ``docs/data/performance.json`` for the featured member
  pages.

Neither is the member's realized profit — holding period, later sells,
dividends and fill prices are all unknown. Every rendering of these numbers
must keep that caveat visible.
"""

from __future__ import annotations

from datetime import date, timedelta

# One extra Twelve Data call per run buys the whole benchmark. SPY tracks the
# S&P 500 with negligible error at the 0.1% rounding this feature uses.
BENCH_TICKER = "SPY"
BENCH_LABEL = "S&P 500"

# A performance section needs enough buys that its numbers aren't one lucky
# pick wearing a median's clothes.
MIN_PRICED_BUYS = 3

WEEK_STEP_DAYS = 7


def bench_pct(bench, tx_date: str) -> float | None:
    """The benchmark's % change from ``tx_date``'s close to its latest close."""
    if not bench:
        return None
    entry = bench.close_on_or_before(tx_date)
    latest = bench.latest()
    if not entry or not latest or entry[1] <= 0:
        return None
    return round((latest[1] - entry[1]) / entry[1] * 100, 1)


def _grid(first_iso: str, last_iso: str, step_days: int = WEEK_STEP_DAYS) -> list[str]:
    """Weekly sample dates from first buy to the latest close, endpoints kept."""
    d = date.fromisoformat(first_iso)
    last = date.fromisoformat(last_iso)
    out = []
    while d < last:
        out.append(d.isoformat())
        d += timedelta(days=step_days)
    out.append(last.isoformat())
    return out


def member_series(buys: list[dict], series_by_ticker: dict, bench) -> dict | None:
    """The $1-race series for one member's priced buys.

    ``buys`` are trade dicts (``ticker``, ``tx_date``). A buy participates
    only if both its own series and the benchmark can price its entry, and on
    every sampled date a buy that cannot be priced is dropped from BOTH means
    for that date — the two lines must always average the same trades.
    """
    if not bench:
        return None
    latest = bench.latest()
    if not latest:
        return None

    legs = []
    for t in buys:
        series = series_by_ticker.get(t.get("ticker"))
        if not series:
            continue
        entry = series.close_on_or_before(t["tx_date"])
        bench_entry = bench.close_on_or_before(t["tx_date"])
        if not entry or not bench_entry or entry[1] <= 0 or bench_entry[1] <= 0:
            continue
        legs.append({
            "series": series,
            "entry_date": entry[0],
            "entry_close": entry[1],
            "bench_entry_close": bench_entry[1],
        })
    if len(legs) < MIN_PRICED_BUYS:
        return None

    first = min(leg["entry_date"] for leg in legs)
    dates = _grid(first, latest[0])
    member_vals: list[float] = []
    bench_vals: list[float] = []
    for d in dates:
        growths: list[tuple[float, float]] = []
        for leg in legs:
            if leg["entry_date"] > d:
                continue
            close = leg["series"].close_on_or_before(d)
            bench_close = bench.close_on_or_before(d)
            if not close or not bench_close:
                continue
            growths.append((
                close[1] / leg["entry_close"],
                bench_close[1] / leg["bench_entry_close"],
            ))
        if not growths:
            member_vals.append(100.0)
            bench_vals.append(100.0)
            continue
        member_vals.append(round(100 * sum(g for g, _ in growths) / len(growths), 1))
        bench_vals.append(round(100 * sum(b for _, b in growths) / len(growths), 1))

    return {
        "dates": dates,
        "member": member_vals,
        "bench": bench_vals,
        "buys": len(legs),
    }


def is_priceable_buy(t: dict, non_equity: frozenset | set) -> bool:
    return (
        t.get("type") == "buy" and bool(t.get("ticker"))
        and t.get("asset_type") not in non_equity
    )


def build_performance(trades: list[dict], series_by_ticker: dict, bench,
                      member_names: list[str], non_equity) -> dict:
    """The ``performance.json`` payload: one $1-race series per featured member
    that has enough priced buys. Members that don't qualify are simply absent —
    the page treats absence as "not enough priceable buys"."""
    members = {}
    for name in member_names:
        buys = [t for t in trades
                if t.get("member") == name and is_priceable_buy(t, non_equity)]
        series = member_series(buys, series_by_ticker, bench)
        if series:
            members[name] = series
    asof = bench.latest() if bench else None
    return {
        "benchmark": {"ticker": BENCH_TICKER, "label": BENCH_LABEL,
                      "asof_date": asof[0] if asof else None},
        "members": members,
    }
