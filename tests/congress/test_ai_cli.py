"""Offline test for the `congress ai` subcommand (network stubbed).

Verifies the command writes a well-formed ai-indicators.json and that the
signal dedup memory suppresses re-notification of an already-emitted signal on
a second run against the same data.
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
        prices.make_session = lambda: None
        prices.fetch_raw = lambda session, tk, key: _ascending_body(hash(tk) % 30)
        os.environ[prices.ENV_KEY] = "TESTKEY"

    def tearDown(self):
        prices.fetch_raw = self._real_fetch
        prices.make_session = self._real_session
        if self._real_key is None:
            os.environ.pop(prices.ENV_KEY, None)
        else:
            os.environ[prices.ENV_KEY] = self._real_key

    def test_writes_and_dedupes(self):
        with TemporaryDirectory() as d:
            out = Path(d) / "ai-indicators.json"
            args = types.SimpleNamespace(output=str(out))

            self.assertEqual(cli._cmd_ai(args), 0)
            data = json.loads(out.read_text())
            self.assertEqual(len(data["tickers"]), len(indicators.AI_TICKERS))
            nvda = data["tickers"]["NVDA"]
            for k in ("price", "rsi14", "sma200", "signals", "name"):
                self.assertIn(k, nvda)
            # Every ticker made a new 52-week high → one new signal each.
            self.assertEqual(len(data["meta"]["new_signals"]),
                             len(indicators.AI_TICKERS))
            self.assertTrue(data["meta"]["emitted_signal_keys"])

            # Second run over identical data: nothing new to notify.
            self.assertEqual(cli._cmd_ai(args), 0)
            data2 = json.loads(out.read_text())
            self.assertEqual(data2["meta"]["new_signals"], [])

    def test_missing_key_keeps_existing(self):
        os.environ.pop(prices.ENV_KEY, None)
        with TemporaryDirectory() as d:
            out = Path(d) / "ai-indicators.json"
            args = types.SimpleNamespace(output=str(out))
            self.assertEqual(cli._cmd_ai(args), 0)
            self.assertFalse(out.exists())  # no key → wrote nothing


if __name__ == "__main__":
    unittest.main()
