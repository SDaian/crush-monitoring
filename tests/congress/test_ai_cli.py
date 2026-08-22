"""Offline test for the `congress ai` subcommand (network stubbed).

Verifies the command writes a well-formed ai-indicators.json, that the
universe is every ticker page (not the hand-written watchlist), that only
featured symbols reach meta.new_signals, and that the dedup memory suppresses
re-notification of an already-emitted signal on a second run.
"""

import json
import os
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from congress import cli, indicators, prices


def _ascending_body(base):
    # 260 monotonically rising sessions → a guaranteed "new_52w_high" signal.
    closes = [base + i * 0.4 for i in range(260)]
    values = [{
        "datetime": f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}",
        "close": f"{closes[i]:.4f}", "volume": str(1_000_000 + i),
    } for i in range(259, -1, -1)]
    return json.dumps({"status": "ok", "values": values})


class TestAiCommand(unittest.TestCase):
    def setUp(self):
        self._real_fetch = prices.fetch_raw
        self._real_session = prices.make_session
        self._real_key = os.environ.get(prices.ENV_KEY)
        self._real_index = prices.fetch_index_raw
        prices.make_session = lambda: None
        prices.fetch_raw = lambda session, tk, key: _ascending_body(hash(tk) % 30)
        # The market reading rides along on every run; keep it offline too.
        prices.fetch_index_raw = lambda session, sym, key: _ascending_body(17)
        os.environ[prices.ENV_KEY] = "TESTKEY"

    def tearDown(self):
        prices.fetch_raw = self._real_fetch
        prices.fetch_index_raw = self._real_index
        prices.make_session = self._real_session
        if self._real_key is None:
            os.environ.pop(prices.ENV_KEY, None)
        else:
            os.environ[prices.ENV_KEY] = self._real_key

    @staticmethod
    def _index(dirpath, tickers):
        """A generated ticker index, as the `landing` step writes it."""
        path = Path(dirpath) / "_index.json"
        path.write_text(json.dumps({"tickers": [
            {"ticker": tk, "company": f"{tk} Inc.", "slug": tk.lower()}
            for tk in tickers]}), encoding="utf-8")
        return path

    def test_writes_and_dedupes(self):
        with TemporaryDirectory() as d:
            out = Path(d) / "ai-indicators.json"
            # AAPL has a page but is NOT on the featured watchlist — the case
            # that used to leave the third most-traded stock without a read.
            index = self._index(d, ["AAPL", "NVDA", "UNH"])
            args = types.SimpleNamespace(output=str(out), index=str(index))

            self.assertEqual(cli._cmd_ai(args), 0)
            data = json.loads(out.read_text())
            self.assertEqual(len(data["tickers"]),
                             len(indicators.AI_TICKERS) + 2)  # + AAPL, UNH
            nvda = data["tickers"]["NVDA"]
            for k in ("price", "rsi14", "sma200", "signals", "name"):
                self.assertIn(k, nvda)
            self.assertTrue(nvda["featured"])
            # Every page symbol gets the same reading; only the flag differs.
            aapl = data["tickers"]["AAPL"]
            self.assertFalse(aapl["featured"])
            self.assertEqual(aapl["name"], "AAPL Inc.")
            self.assertIsNotNone(aapl["rsi14"])
            # Every ticker made a new 52-week high, but only the featured ones
            # may notify — an email per page symbol would be noise.
            self.assertEqual(len(data["meta"]["new_signals"]),
                             len(indicators.AI_TICKERS))
            self.assertNotIn("AAPL", [s["ticker"]
                                      for s in data["meta"]["new_signals"]])
            self.assertTrue(aapl["signals"])  # still shown on its own page
            self.assertTrue(data["meta"]["emitted_signal_keys"])

            # Second run over identical data: nothing new to notify.
            self.assertEqual(cli._cmd_ai(args), 0)
            data2 = json.loads(out.read_text())
            self.assertEqual(data2["meta"]["new_signals"], [])

    def test_a_missing_index_falls_back_to_the_watchlist(self):
        # A stale or failed `landing` step costs a few readings, never the run.
        with TemporaryDirectory() as d:
            out = Path(d) / "ai-indicators.json"
            args = types.SimpleNamespace(output=str(out),
                                         index=str(Path(d) / "absent.json"))
            self.assertEqual(cli._cmd_ai(args), 0)
            data = json.loads(out.read_text())
            self.assertEqual(len(data["tickers"]), len(indicators.AI_TICKERS))

    def test_missing_key_keeps_existing(self):
        os.environ.pop(prices.ENV_KEY, None)
        with TemporaryDirectory() as d:
            out = Path(d) / "ai-indicators.json"
            args = types.SimpleNamespace(output=str(out),
                                         index=str(Path(d) / "absent.json"))
            self.assertEqual(cli._cmd_ai(args), 0)
            self.assertFalse(out.exists())  # no key → wrote nothing


if __name__ == "__main__":
    unittest.main()


class TestSkipWhenClosed(unittest.TestCase):
    """The guard reads what the output already holds, not the calendar."""

    def write(self, tmp, section, asof):
        path = Path(tmp) / "out.json"
        path.write_text(json.dumps(
            {"meta": {}, section: {"NVDA": {"asof_date": asof}}}), encoding="utf-8")
        return path

    def test_newest_close_reads_either_output_shape(self):
        with TemporaryDirectory() as tmp:
            # returns.json keys its rows under "prices", indicators under
            # "tickers"; one helper serves both steps.
            self.assertEqual(
                cli.newest_close(self.write(tmp, "prices", "2026-08-14")),
                "2026-08-14")
            self.assertEqual(
                cli.newest_close(self.write(tmp, "tickers", "2026-08-17")),
                "2026-08-17")

    def test_newest_close_takes_the_maximum(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.json"
            path.write_text(json.dumps({"tickers": {
                "A": {"asof_date": "2026-08-11"},
                "B": {"asof_date": "2026-08-14"},
            }}), encoding="utf-8")
            self.assertEqual(cli.newest_close(path), "2026-08-14")

    def test_a_missing_file_never_skips(self):
        with TemporaryDirectory() as tmp:
            self.assertIsNone(cli.newest_close(Path(tmp) / "absent.json"))
            self.assertFalse(cli.market_shut(Path(tmp) / "absent.json"))

    def test_unreadable_file_never_skips(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text("{ not json", encoding="utf-8")
            self.assertIsNone(cli.newest_close(path))


class TestRetickExecutive(unittest.TestCase):
    """The self-heal pass: OVERRIDES additions land without a re-download."""

    def write(self, tmp, trades):
        path = Path(tmp) / "trades.json"
        path.write_text(json.dumps({"trades": trades}), encoding="utf-8")
        return path

    def test_fills_tickers_and_strips_row_numbers(self):
        trades = [
            {"chamber": "executive", "asset_type": "Stock", "ticker": None,
             "asset": "1082 HOME DEPOT INC"},
            {"chamber": "executive", "asset_type": "Stock", "ticker": None,
             "asset": "QUALM INC"},
            {"chamber": "house", "asset_type": "Stock", "ticker": "HD",
             "asset": "Home Depot, Inc. (The) Common Stock"},
        ]
        with TemporaryDirectory() as tmp:
            path = self.write(tmp, trades)
            fixed, refused = cli.retick_executive(path)
            doc = json.loads(path.read_text())
        by = {t["asset"]: t for t in doc["trades"]}
        self.assertIn("HOME DEPOT INC", by)          # number stripped
        self.assertEqual(by["HOME DEPOT INC"]["ticker"], "HD")
        self.assertEqual(by["QUALM INC"]["ticker"], "QCOM")
        self.assertEqual(refused, [])

    def test_refusals_are_reported_and_rows_untouched(self):
        trades = [{"chamber": "executive", "asset_type": "Stock",
                   "ticker": None, "asset": "TOTAL OCR MUSH XYZQ"}]
        with TemporaryDirectory() as tmp:
            path = self.write(tmp, trades)
            fixed, refused = cli.retick_executive(path)
            doc = json.loads(path.read_text())
        self.assertEqual(refused, ["TOTAL OCR MUSH XYZQ"])
        self.assertIsNone(doc["trades"][0]["ticker"])

    def test_bond_rows_and_other_chambers_stay_alone(self):
        trades = [
            {"chamber": "executive", "asset_type": "bond", "ticker": None,
             "asset": "SOME MUNI 4.5% DUE 2031"},
            {"chamber": "house", "asset_type": "Stock", "ticker": None,
             "asset": "QUALM INC"},
        ]
        with TemporaryDirectory() as tmp:
            path = self.write(tmp, trades)
            fixed, refused = cli.retick_executive(path)
            doc = json.loads(path.read_text())
        self.assertEqual((fixed, refused), (0, []))
        self.assertTrue(all(t["ticker"] is None for t in doc["trades"]))

    def test_missing_file_is_quiet(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                cli.retick_executive(Path(tmp) / "gone.json"), (0, []))
