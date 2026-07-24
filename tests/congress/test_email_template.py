"""Offline tests for congress.email_template (pure HTML rendering, no I/O)."""

import unittest

from congress import email_template as et

SCORECARD = [
    {"ticker": "NVDA", "price": 124.9, "chg": "+0.7%", "chg_dir": 1,
     "rsi": 55, "trend": "50d›200d", "label": "Strong Buy"},
    {"ticker": "TSLA", "price": 251.7, "chg": "-3.2%", "chg_dir": -1,
     "rsi": 33, "trend": "50d‹200d", "label": "Strong Sell"},
]
SIGNALS = [{"ticker": "SPCX", "label": "New 52-week high", "asof": "2026-07-24"}]
FLIPS = [{"ticker": "TSLA", "prev": "Sell", "label": "Strong Sell"}]
DISCLOSURES = [{"filing_date": "2026-07-24", "who": "Nancy Pelosi (D)",
                "name": "NVDA", "type": "buy", "amount": "$1,000,001 - $5,000,000"}]
TRAFFIC = {"total": 1284, "windowDays": 7,
           "pages": [("/", 640), ("/members/nancy-pelosi", 180)],
           "memberPages": [("nancy-pelosi", 180)]}


def _render(**over):
    kw = dict(date_label="Friday, July 24, 2026", disclaimer="Not **advice.**",
              scorecard=SCORECARD, signals=SIGNALS, flips=FLIPS,
              disclosures=DISCLOSURES, extra_disclosures=0, cutoff="2026-07-21",
              tracker_url="https://example.test/trades.html",
              preheader="preview line")
    kw.update(over)
    return et.render_html(**kw)


class TestRenderHtml(unittest.TestCase):
    def test_masthead_and_structure(self):
        html = _render()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Capitol&nbsp;Ledger", html)
        self.assertIn("Friday, July 24, 2026", html)
        self.assertIn("preview line", html)          # preheader present
        self.assertIn("<table", html)

    def test_scorecard_rows_and_colors(self):
        html = _render()
        self.assertIn("<b>NVDA</b>", html)
        self.assertIn("Strong Buy", html)
        self.assertIn("Strong Sell", html)
        self.assertIn(et.BUY, html)                  # green somewhere
        self.assertIn(et.SELL, html)                 # red somewhere

    def test_sections(self):
        html = _render()
        self.assertIn("Nancy Pelosi", html)          # disclosure in window
        self.assertIn("New 52-week high", html)      # signal
        self.assertIn("Sell → ", html)               # flip arrow

    def test_digest_has_no_traffic(self):
        # Traffic moved to its own email — the digest must not carry it.
        html = _render()
        self.assertNotIn("Site traffic", html)
        self.assertNotIn("page views", html)

    def test_empty_states(self):
        html = _render(scorecard=[], signals=[], flips=[], disclosures=[])
        self.assertIn("No indicator data.", html)
        self.assertIn("No new signals or rating changes", html)
        self.assertIn("No new disclosures", html)

    def test_extra_disclosures_note(self):
        self.assertIn("and 5 more", _render(extra_disclosures=5))

    def test_escapes_no_injection(self):
        bad = [{"ticker": "<script>x</script>", "price": 1, "chg": "0%",
                "chg_dir": 0, "rsi": 1, "trend": "—", "label": "Hold"}]
        html = _render(scorecard=bad)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class TestTrafficEmail(unittest.TestCase):
    def test_traffic_email_renders(self):
        html = et.render_traffic_html(
            date_label="Friday, July 24, 2026", traffic=TRAFFIC,
            member_names={"nancy-pelosi": "Nancy Pelosi"},
            tracker_url="https://example.test/trades.html",
            preheader="1,284 page views")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Capitol&nbsp;Ledger", html)
        self.assertIn("Traffic", html)               # masthead label
        self.assertIn("Site traffic", html)
        self.assertIn("1,284 page views", html)
        self.assertIn("Nancy Pelosi", html)          # member breakdown
        # It is a trade-focused digest's sibling, not the digest itself.
        self.assertNotIn("Strong Buy", html)


if __name__ == "__main__":
    unittest.main()
