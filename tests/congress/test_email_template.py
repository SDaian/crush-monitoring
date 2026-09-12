"""Offline tests for congress.email_template (pure HTML rendering, no I/O)."""

import unittest

from congress import email_template as et

SCORECARD = [
    {"ticker": "NVDA", "price": 124.9, "chg": "+0.7%", "chg_dir": 1,
     "rsi": 55, "trend": "50d›200d", "label": "Strong Buy",
     "agree": 7, "votes": 7, "unanimous": True},
    {"ticker": "TSLA", "price": 251.7, "chg": "-3.2%", "chg_dir": -1,
     "rsi": 33, "trend": "50d‹200d", "label": "Strong Sell",
     "agree": 4, "votes": 6, "unanimous": False},
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

    def test_vote_count_rides_under_the_label(self):
        html = _render()
        self.assertIn("7 of 7 votes", html)
        self.assertIn("4 of 6 votes", html)
        # The key, so a bare fraction never leaves the reader guessing.
        self.assertIn("how many checks agreed with the read", html)

    def test_clean_sweep_is_starred_and_a_split_is_not(self):
        html = et.scorecard_table(SCORECARD)
        self.assertEqual(html.count("&#9733;"), 2)  # NVDA's row + the key
        rows = html.split("TSLA")
        self.assertNotIn("&#9733;", rows[1].split("</tr>")[0])

    def test_a_row_with_no_votes_shows_only_the_label(self):
        # An indicator file that predates the field must still render.
        html = et.scorecard_table([
            {"ticker": "BE", "price": 92.4, "chg": "+0.1%", "chg_dir": 1,
             "rsi": 48, "trend": "50d‹200d", "label": "Hold"}])
        self.assertIn("Hold", html)
        self.assertNotIn("votes</span>", html)

    def test_the_read_stays_in_six_columns(self):
        # The count is a second LINE in the Read cell, never a seventh column:
        # six already do not fit a 390px phone at this padding.
        html = et.scorecard_table(SCORECARD)
        self.assertEqual(html.count("<th"), 6)

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
        self.assertIn("No new stock/option disclosures", html)

    def test_extra_disclosures_note(self):
        self.assertIn("and 5 more", _render(extra_disclosures=5))

    def test_escapes_no_injection(self):
        bad = [{"ticker": "<script>x</script>", "price": 1, "chg": "0%",
                "chg_dir": 0, "rsi": 1, "trend": "—", "label": "Hold"}]
        html = _render(scorecard=bad)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class TestEmbedVariant(unittest.TestCase):
    """What a newsletter provider receives differs deliberately."""

    def test_keeps_our_masthead(self):
        # Our wordmark is the identity — it stays in the broadcast. The
        # provider's own header is what gets turned off, in its template.
        embed = _render(standalone=False)
        self.assertIn("Capitol&nbsp;Ledger", embed)
        self.assertIn("Friday, July 24, 2026", embed)

    def test_drops_the_redundant_right_label(self):
        # The provider's subject already says "Morning report", and that cell
        # is what wrapped the wordmark onto two lines on a phone — an embed has
        # no <head> for the mobile media query to live in.
        self.assertIn("Morning report", _render())
        self.assertNotIn("Morning report", _render(standalone=False))

    def test_keeps_the_intro_and_content(self):
        # The disclaimer, the view-in-browser link and every section stay.
        embed = _render(standalone=False, report_url="https://x/report")
        self.assertIn("in your browser", embed)
        self.assertIn("Not advice.", embed)       # intro disclaimer
        self.assertIn("Strong Buy", embed)        # scorecard survives
        self.assertIn("Nancy Pelosi", embed)

    def test_no_page_chrome(self):
        embed = _render(standalone=False)
        for chrome in ("<!DOCTYPE", "</html>", 'width="600"', "display:none;max-height"):
            self.assertNotIn(chrome, embed)


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
