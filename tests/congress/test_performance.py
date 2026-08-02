"""Offline tests for congress.performance (member-vs-S&P math, no network)."""

import unittest

from congress import performance
from congress.prices import NON_EQUITY, PriceSeries, compute_returns


def series(points: dict[str, float]) -> PriceSeries:
    return PriceSeries(points)


# A benchmark that goes 100 → 110 over January (+10%).
BENCH = series({"2026-01-02": 100.0, "2026-01-09": 102.0,
                "2026-01-16": 105.0, "2026-01-23": 108.0,
                "2026-01-30": 110.0})


def buy(member="Nancy Pelosi", ticker="AAA", tx="2026-01-02", id="b1",
        type="buy", asset_type="Stock"):
    return {"member": member, "ticker": ticker, "tx_date": tx, "id": id,
            "type": type, "asset_type": asset_type,
            "amount_lo": 1001, "amount_hi": 15000,
            "filing_date": "2026-02-01"}


class TestBenchPct(unittest.TestCase):
    def test_same_window_as_the_buy(self):
        # Entry snaps to the close on/before the trade date, like buy_return.
        self.assertEqual(performance.bench_pct(BENCH, "2026-01-02"), 10.0)
        self.assertEqual(performance.bench_pct(BENCH, "2026-01-17"),
                         round((110 - 105) / 105 * 100, 1))

    def test_before_first_close_is_unpriced(self):
        self.assertIsNone(performance.bench_pct(BENCH, "2025-12-01"))

    def test_no_bench(self):
        self.assertIsNone(performance.bench_pct(None, "2026-01-02"))
        self.assertIsNone(performance.bench_pct(series({}), "2026-01-02"))


class TestComputeReturnsBench(unittest.TestCase):
    def test_rows_carry_bench_pct(self):
        stock = series({"2026-01-02": 50.0, "2026-01-30": 60.0})
        returns, _, _ = compute_returns([buy()], {"AAA": stock}, BENCH)
        self.assertEqual(returns["b1"]["pct"], 20.0)
        self.assertEqual(returns["b1"]["bench_pct"], 10.0)

    def test_without_bench_field_is_absent_not_null(self):
        stock = series({"2026-01-02": 50.0, "2026-01-30": 60.0})
        returns, _, _ = compute_returns([buy()], {"AAA": stock}, None)
        self.assertNotIn("bench_pct", returns["b1"])


class TestMemberSeries(unittest.TestCase):
    def test_single_stock_tracks_its_growth(self):
        stock = series({"2026-01-02": 50.0, "2026-01-09": 55.0,
                        "2026-01-16": 60.0, "2026-01-23": 65.0,
                        "2026-01-30": 70.0})
        buys = [buy(id=f"b{i}") for i in range(3)]  # 3 identical legs
        out = performance.member_series(buys, {"AAA": stock}, BENCH)
        self.assertEqual(out["buys"], 3)
        self.assertEqual(out["dates"][0], "2026-01-02")
        self.assertEqual(out["dates"][-1], "2026-01-30")
        self.assertEqual(out["member"][0], 100.0)
        self.assertEqual(out["member"][-1], 140.0)   # 50 → 70
        self.assertEqual(out["bench"][-1], 110.0)    # 100 → 110

    def test_staggered_entries_weight_both_sides_identically(self):
        # Leg 1 enters Jan 2 (stock flat, bench +10%); leg 2 enters Jan 16
        # (stock flat, bench 105→110). Member ends flat at 100; the bench line
        # must average the same two windows — never credit the earlier entry
        # only to one side.
        flat = series({"2026-01-02": 10.0, "2026-01-16": 10.0,
                       "2026-01-30": 10.0})
        buys = [buy(id="b1"), buy(id="b2", tx="2026-01-16"),
                buy(id="b3", tx="2026-01-16")]
        out = performance.member_series(buys, {"AAA": flat}, BENCH)
        self.assertEqual(out["member"][-1], 100.0)
        expected = round(100 * (110 / 100 + 110 / 105 + 110 / 105) / 3, 1)
        self.assertEqual(out["bench"][-1], expected)

    def test_below_min_buys_is_none(self):
        stock = series({"2026-01-02": 50.0, "2026-01-30": 60.0})
        out = performance.member_series([buy(), buy(id="b2")],
                                        {"AAA": stock}, BENCH)
        self.assertIsNone(out)

    def test_unpriceable_legs_do_not_count_toward_min(self):
        stock = series({"2026-01-02": 50.0, "2026-01-30": 60.0})
        buys = [buy(id=f"b{i}") for i in range(3)]
        buys += [buy(id="x", ticker="NOPE")]  # no series
        out = performance.member_series(buys[:2] + [buys[3]],
                                        {"AAA": stock}, BENCH)
        self.assertIsNone(out)


class TestBuildPerformance(unittest.TestCase):
    def test_only_qualifying_members_present(self):
        stock = series({"2026-01-02": 50.0, "2026-01-30": 60.0})
        trades = [buy(id=f"p{i}") for i in range(3)]
        trades += [buy(member="Tommy Tuberville", id="t1")]  # 1 buy < min
        trades += [buy(member="Nancy Pelosi", id="opt",
                       asset_type="Option")]  # never priced
        out = performance.build_performance(
            trades, {"AAA": stock}, BENCH,
            ["Nancy Pelosi", "Tommy Tuberville", "Donald J. Trump"],
            NON_EQUITY)
        self.assertEqual(sorted(out["members"]), ["Nancy Pelosi"])
        self.assertEqual(out["benchmark"]["ticker"], "SPY")
        self.assertEqual(out["benchmark"]["asof_date"], "2026-01-30")
        self.assertEqual(out["members"]["Nancy Pelosi"]["buys"], 3)
