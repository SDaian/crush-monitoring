"""Offline tests for congress.daily_report.build_report (pure composition)."""

import unittest

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


if __name__ == "__main__":
    unittest.main()
