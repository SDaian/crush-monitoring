"""Offline tests for congress.indicators (pure technical-analysis math)."""

import json
import unittest

from congress import indicators as ind


def td_body(closes, volumes=None, status="ok"):
    """Build a Twelve Data time_series body (newest-first) from ascending
    ``closes`` so the parser has to sort it back into order."""
    n = len(closes)
    vols = volumes if volumes is not None else [1_000_000] * n
    values = []
    for i in range(n - 1, -1, -1):  # API returns newest first
        values.append({
            "datetime": f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}",
            "close": f"{closes[i]:.4f}",
            "volume": str(int(vols[i])),
        })
    return json.dumps({"status": status, "values": values})


class TestParseSeries(unittest.TestCase):
    def test_sorted_ascending_with_volume(self):
        rows = ind.parse_series(td_body([10, 11, 12], [5, 6, 7]))
        self.assertEqual([r["date"] for r in rows], sorted(r["date"] for r in rows))
        self.assertEqual([r["close"] for r in rows], [10.0, 11.0, 12.0])
        self.assertEqual([r["volume"] for r in rows], [5.0, 6.0, 7.0])

    def test_error_status_is_empty(self):
        self.assertEqual(ind.parse_series(td_body([1, 2], status="error")), [])
        self.assertEqual(ind.parse_series("not json"), [])

    def test_bad_rows_skipped(self):
        body = json.dumps({"status": "ok", "values": [
            {"datetime": "2025-01-02", "close": "10", "volume": "100"},
            {"datetime": "bad", "close": "9", "volume": "50"},
            {"datetime": "2025-01-01", "close": "", "volume": "50"},
        ]})
        rows = ind.parse_series(body)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["close"], 10.0)


class TestSMAandPctChange(unittest.TestCase):
    def test_sma_known(self):
        self.assertEqual(ind.sma(list(range(1, 21)), 20), 10.5)  # mean 1..20
        self.assertIsNone(ind.sma([1, 2, 3], 20))  # too few

    def test_pct_change(self):
        closes = [100, 110]  # +10% over 1 period
        self.assertAlmostEqual(ind.pct_change(closes, 1), 10.0)
        self.assertIsNone(ind.pct_change([100], 1))  # too short
        self.assertIsNone(ind.pct_change([0, 5], 1))  # prior close 0


class TestWilderRSI(unittest.TestCase):
    def test_pure_uptrend_is_100(self):
        self.assertEqual(ind.wilder_rsi(list(range(1, 40)), 14), 100.0)

    def test_pure_downtrend_is_0(self):
        self.assertEqual(ind.wilder_rsi(list(range(40, 1, -1)), 14), 0.0)

    def test_too_few_is_none(self):
        self.assertIsNone(ind.wilder_rsi([1, 2, 3], 14))  # need 15 closes

    def test_known_first_step(self):
        # 15 closes → exactly 14 deltas: ten +1 gains then four -1 losses.
        # The first RSI is the simple average step: avg_gain=10/14,
        # avg_loss=4/14, RS=2.5, RSI = 100 - 100/3.5 = 71.4286.
        closes = [100 + i for i in range(11)]          # 100..110 (ten +1)
        closes += [closes[-1] - (i + 1) for i in range(4)]  # 109..106 (four -1)
        self.assertEqual(len(closes), 15)
        self.assertAlmostEqual(ind.wilder_rsi(closes, 14), 71.4286, places=3)


class TestComputeIndicators(unittest.TestCase):
    def test_empty_history_none(self):
        self.assertIsNone(ind.compute_indicators([]))

    def test_full_bundle(self):
        # 260 ascending sessions so every SMA + the 52w range are defined.
        closes = [100 + i * 0.5 for i in range(260)]
        vols = [1_000_000 + i for i in range(260)]
        rows = ind.parse_series(td_body(closes, vols))
        out = ind.compute_indicators(rows)
        self.assertEqual(out["price"], round(closes[-1], 2))
        self.assertEqual(out["rsi14"], 100.0)          # monotonic up
        self.assertIsNotNone(out["sma200"])
        self.assertEqual(out["high_52w"], round(max(closes), 2))
        self.assertEqual(out["low_52w"], round(closes[-260 + 8], 2)
                         if len(closes) < ind.YEAR else round(closes[-ind.YEAR], 2))
        self.assertGreater(out["vs_sma50"], 0)         # price above rising MA
        self.assertEqual(out["range_pos"], 100.0)      # at the 52w high
        self.assertIsNotNone(out["avg_vol_20"])

    def test_partial_history_sma_none(self):
        closes = [10 + i for i in range(30)]  # only 30 bars
        out = ind.compute_indicators(ind.parse_series(td_body(closes)))
        self.assertIsNotNone(out["sma20"])
        self.assertIsNone(out["sma50"])
        self.assertIsNone(out["sma200"])
        self.assertIsNone(out["vs_sma200"])


class TestSignals(unittest.TestCase):
    def types(self, rows):
        return {s["type"] for s in ind.compute_signals(rows)}

    def test_flat_series_no_signals(self):
        rows = ind.parse_series(td_body([100] * 300))
        self.assertEqual(ind.compute_signals(rows), [])

    def test_new_52w_high_on_ascending(self):
        rows = ind.parse_series(td_body([100 + i for i in range(60)]))
        self.assertIn("new_52w_high", self.types(rows))
        self.assertNotIn("new_52w_low", self.types(rows))

    def test_new_52w_low_on_descending(self):
        rows = ind.parse_series(td_body([200 - i for i in range(60)]))
        self.assertIn("new_52w_low", self.types(rows))

    def test_reclaim_sma50(self):
        # Below the 50-day for a stretch, then a final close back above it.
        closes = [100] * 60 + [80] * 5 + [101]
        self.assertIn("reclaim_sma50", self.types(ind.parse_series(td_body(closes))))

    def test_golden_cross_on_last_bar(self):
        # 200 flat bars, then 49 more flat + one huge up-bar drives the 50-day
        # decisively above the 200-day exactly on the final session.
        closes = [100] * 249 + [100000]
        t = self.types(ind.parse_series(td_body(closes)))
        self.assertIn("golden_cross", t)
        self.assertNotIn("death_cross", t)

    def test_death_cross_on_last_bar(self):
        closes = [100] * 249 + [0.01]
        t = self.types(ind.parse_series(td_body(closes)))
        self.assertIn("death_cross", t)

    def test_signal_key_stable(self):
        sig = {"type": "golden_cross", "asof": "2026-07-06",
               "label": "x", "dir": "bull"}
        self.assertEqual(ind.signal_key("NVDA", sig),
                         "NVDA|golden_cross|2026-07-06")


if __name__ == "__main__":
    unittest.main()
