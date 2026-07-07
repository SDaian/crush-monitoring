"""Offline tests for congress.daily_report.build_report (pure composition)."""

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from congress import daily_report
from congress.daily_report import build_report

AI = {
    "NVDA": {"price": 100, "chg_1d": 0.7, "rsi14": 55, "sma20": 90,
             "sma50": 80, "sma200": 70, "chg_1m": 5, "chg_1w": 2},   # Strong Buy
    "MSFT": {"price": 50, "chg_1d": -1.9, "rsi14": 45, "sma20": 55,
             "sma50": 60, "sma200": 70, "chg_1m": -3, "chg_1w": -1},  # Strong Sell
}
NEW_SIGNALS = [{"ticker": "NVDA", "type": "golden_cross",
                "label": "Golden cross (50-day above 200-day)", "asof": "2026-07-07"}]
TRADES = [
    {"member": "Nancy Pelosi", "party": "D", "ticker": "NVDA", "type": "buy",
     "amount_label": "$1,000,001 - $5,000,000", "tx_date": "2026-07-05",
     "filing_date": "2026-07-07"},
    {"member": "Old Filer", "party": "R", "ticker": "AAPL", "type": "sell",
     "amount_label": "$1,001 - $15,000", "tx_date": "2026-05-01",
     "filing_date": "2026-05-02"},  # outside the window
]


class TestBuildReport(unittest.TestCase):
    def setUp(self):
        self.r = build_report(TRADES, AI, NEW_SIGNALS,
                              prev_ratings={"MSFT": "Hold"}, today_iso="2026-07-07")

    def test_sections_present(self):
        md = self.r["markdown"]
        self.assertIn("🤖 AI stocks", md)
        self.assertIn("🔔 Signals overnight", md)
        self.assertIn("🏛 New congressional disclosures", md)
        self.assertIn("Not investment advice", md)

    def test_scorecard_ratings(self):
        self.assertEqual(self.r["ratings"]["NVDA"], "Strong Buy")
        self.assertEqual(self.r["ratings"]["MSFT"], "Strong Sell")
        self.assertIn("| NVDA |", self.r["markdown"])

    def test_new_signal_listed(self):
        self.assertIn("Golden cross", self.r["markdown"])

    def test_rating_flip_detected(self):
        # MSFT was "Hold" yesterday, now "Strong Sell" → flip reported.
        self.assertIn("MSFT** rating: Hold → Strong Sell", self.r["markdown"])

    def test_disclosure_window(self):
        md = self.r["markdown"]
        self.assertIn("Nancy Pelosi", md)      # filed 2026-07-07, in window
        self.assertNotIn("Old Filer", md)      # filed 2026-05-02, out of window
        self.assertEqual(self.r["counts"]["disclosures"], 1)

    def test_no_activity_messaging(self):
        r = build_report([], AI, [], prev_ratings=dict(self.r["ratings"]),
                         today_iso="2026-07-07")
        self.assertIn("No new signals or rating changes", r["markdown"])
        self.assertIn("No new disclosures", r["markdown"])


class TestMainDelivery(unittest.TestCase):
    """Exercise main() with the GitHub API + files stubbed."""

    def setUp(self):
        self._d = TemporaryDirectory()
        base = Path(self._d.name)
        (base / "trades.json").write_text(json.dumps({"trades": []}))
        (base / "ai.json").write_text(json.dumps(
            {"tickers": {}, "meta": {"new_signals": []}}))
        self.state = base / "state.json"
        self._orig = (daily_report.TRADES_JSON, daily_report.AI_JSON,
                      daily_report.STATE_JSON, daily_report._gh)
        daily_report.TRADES_JSON = base / "trades.json"
        daily_report.AI_JSON = base / "ai.json"
        daily_report.STATE_JSON = self.state
        self.calls = []

        def fake_gh(method, url, token, payload=None):
            self.calls.append((method, url, payload))
            return 201, {"number": 99}
        daily_report._gh = fake_gh
        os.environ["REPO"] = "SDaian/crush-monitoring"
        os.environ["GH_TOKEN"] = "x"

    def tearDown(self):
        (daily_report.TRADES_JSON, daily_report.AI_JSON,
         daily_report.STATE_JSON, daily_report._gh) = self._orig
        os.environ.pop("REPO", None)
        os.environ.pop("GH_TOKEN", None)
        os.environ.pop("REPORT_ASSIGNEE", None)
        self._d.cleanup()

    def test_posts_and_assigns_to_owner(self):
        self.assertEqual(daily_report.main(), 0)
        post = [c for c in self.calls if c[0] == "POST"][0]
        self.assertEqual(post[2]["assignees"], ["SDaian"])  # defaults to owner
        saved = json.loads(self.state.read_text())
        self.assertEqual(saved["issue_number"], 99)

    def test_assignee_override(self):
        os.environ["REPORT_ASSIGNEE"] = "someone-else"
        daily_report.main()
        post = [c for c in self.calls if c[0] == "POST"][0]
        self.assertEqual(post[2]["assignees"], ["someone-else"])

    def test_idempotent_same_day(self):
        # A report already recorded for today → main() must not POST again.
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        self.state.write_text(json.dumps(
            {"date": today, "issue_number": 42, "ratings": {}}))
        self.assertEqual(daily_report.main(), 0)
        self.assertEqual([c for c in self.calls if c[0] == "POST"], [])


if __name__ == "__main__":
    unittest.main()
