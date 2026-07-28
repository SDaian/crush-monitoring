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
        self.assertIn("⭐ Featured stocks", md)
        self.assertIn("🔔 Signals overnight", md)
        self.assertIn("🏛 New congressional disclosures", md)
        self.assertIn("Not investment advice", md)

    def test_html_body(self):
        html = self.r["html"]
        self.assertIn("<table", html)
        self.assertIn("<b>NVDA</b>", html)      # scorecard row
        self.assertIn("Strong Buy", html)        # colored read label
        self.assertIn("Nancy Pelosi", html)      # disclosure in window
        self.assertNotIn("<script", html)        # escaped, no raw injection

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

    def test_ticker_deep_links(self):
        # Tickers with a public page link back into the site, UTM-tagged so
        # Vercel analytics can attribute the email as a traffic source.
        urls = daily_report.ticker_links(
            {"tickers": [{"ticker": "NVDA", "slug": "nvda"}]})
        self.assertEqual(
            urls["NVDA"],
            "https://capitolledger.io/tickers/nvda?utm_source=email"
            "&utm_medium=report&utm_campaign=morning")
        r = build_report(TRADES, AI, NEW_SIGNALS, prev_ratings={},
                         today_iso="2026-07-07", ticker_urls=urls)
        self.assertIn("/tickers/nvda?utm_source=email", r["html"])
        # A ticker with no page stays plain text (no link to a 404).
        self.assertNotIn("/tickers/msft", r["html"])

    def test_digest_has_no_traffic(self):
        # Traffic is delivered in its own email now, not the digest.
        self.assertNotIn("Traffic", self.r["markdown"])
        self.assertNotIn("page views", self.r["html"])


class TestTrafficEmail(unittest.TestCase):
    TRAFFIC = {"total": 1284, "windowDays": 7,
               "pages": [("/", 640)], "memberPages": [("nancy-pelosi", 180)]}

    def test_build_traffic_email(self):
        tr = daily_report.build_traffic_email(
            self.TRAFFIC, "2026-07-24",
            member_names={"nancy-pelosi": "Nancy Pelosi"})
        self.assertEqual(tr["subject"], "📈 Traffic report — 2026-07-24")
        self.assertIn("1,284 page views", tr["markdown"])
        self.assertIn("Nancy Pelosi", tr["markdown"])
        self.assertIn("1,284 page views", tr["html"])
        self.assertNotIn("<script", tr["html"])


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
                      daily_report.STATE_JSON, daily_report.REPORT_JSON,
                      daily_report._gh)
        daily_report.TRADES_JSON = base / "trades.json"
        daily_report.AI_JSON = base / "ai.json"
        daily_report.STATE_JSON = self.state
        # main() publishes the web edition too — point it at the temp dir so a
        # test run never overwrites the repo's real landing/src/data/report.json.
        self.report_json = base / "report.json"
        daily_report.REPORT_JSON = self.report_json
        self.calls = []

        def fake_gh(method, url, token, payload=None):
            self.calls.append((method, url, payload))
            return 201, {"number": 99}
        daily_report._gh = fake_gh
        os.environ["REPO"] = "SDaian/crush-monitoring"
        os.environ["GH_TOKEN"] = "x"

    def tearDown(self):
        (daily_report.TRADES_JSON, daily_report.AI_JSON,
         daily_report.STATE_JSON, daily_report.REPORT_JSON,
         daily_report._gh) = self._orig
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

    def test_writes_report_json_for_the_web_page(self):
        daily_report.main()
        payload = json.loads(self.report_json.read_text())
        for key in ("date", "scorecard", "signals", "flips", "disclosures"):
            self.assertIn(key, payload)

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

    def test_force_overrides_idempotency(self):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        self.state.write_text(json.dumps(
            {"date": today, "issue_number": 42, "ratings": {}}))
        os.environ["REPORT_FORCE"] = "true"
        try:
            daily_report.main()
        finally:
            os.environ.pop("REPORT_FORCE", None)
        self.assertTrue([c for c in self.calls if c[0] == "POST"])  # posted anyway


class TestEmail(unittest.TestCase):
    def setUp(self):
        self._smtp = daily_report.smtplib.SMTP
        self.sent = []

        class FakeSMTP:
            def __init__(s, host, port, timeout=None):
                s.host = host
            def __enter__(s):
                return s
            def __exit__(s, *a):
                return False
            def starttls(s, context=None):
                pass
            def login(s, u, p):
                s.creds = (u, p)
            def send_message(s, msg):
                self.sent.append(msg)
        daily_report.smtplib.SMTP = FakeSMTP
        for k in ("SMTP_USER", "SMTP_PASS", "SMTP_HOST", "SMTP_PORT",
                  "REPORT_EMAIL_TO", "REPORT_EMAIL_FROM"):
            os.environ.pop(k, None)

    def tearDown(self):
        daily_report.smtplib.SMTP = self._smtp
        for k in ("SMTP_USER", "SMTP_PASS", "SMTP_HOST", "SMTP_PORT",
                  "REPORT_EMAIL_TO", "REPORT_EMAIL_FROM"):
            os.environ.pop(k, None)

    def test_no_creds_skips(self):
        self.assertFalse(daily_report.send_email("s", "t", "<p>h</p>"))
        self.assertEqual(self.sent, [])

    def test_sends_with_creds(self):
        os.environ["SMTP_USER"] = "me@gmail.com"
        os.environ["SMTP_PASS"] = "app-pw"
        os.environ["REPORT_EMAIL_TO"] = "you@example.com"
        self.assertTrue(daily_report.send_email("Subj", "text", "<p>html</p>"))
        self.assertEqual(len(self.sent), 1)
        msg = self.sent[0]
        self.assertEqual(msg["To"], "you@example.com")
        self.assertEqual(msg["From"], "me@gmail.com")
        self.assertEqual(msg["Subject"], "Subj")
        # multipart: has an HTML alternative
        self.assertTrue(any(p.get_content_type() == "text/html"
                            for p in msg.walk()))

    def test_from_defaults_to_login_but_can_be_overridden(self):
        os.environ["SMTP_USER"] = "me@gmail.com"
        os.environ["SMTP_PASS"] = "pw"
        daily_report.send_email("s", "t", "<p>h</p>")
        self.assertEqual(self.sent[0]["From"], "me@gmail.com")
        os.environ["REPORT_EMAIL_FROM"] = "daily@capitolledger.io"
        try:
            daily_report.send_email("s", "t", "<p>h</p>")
            self.assertEqual(self.sent[1]["From"], "daily@capitolledger.io")
        finally:
            os.environ.pop("REPORT_EMAIL_FROM", None)

    def test_defaults_recipient_to_user(self):
        os.environ["SMTP_USER"] = "solo@gmail.com"
        os.environ["SMTP_PASS"] = "pw"
        daily_report.send_email("s", "t", "<p>h</p>")
        self.assertEqual(self.sent[0]["To"], "solo@gmail.com")


if __name__ == "__main__":
    unittest.main()


class TestButtondown(unittest.TestCase):
    """The subscriber broadcast: gated, pure payload, never fatal."""

    def setUp(self):
        from congress import buttondown
        self.bd = buttondown
        os.environ.pop(buttondown.ENV_KEY, None)

    def tearDown(self):
        os.environ.pop(self.bd.ENV_KEY, None)

    def test_skips_without_key(self):
        self.assertFalse(self.bd.configured())
        self.assertFalse(self.bd.send("Subj", "<p>hi</p>"))

    def test_payload_shape(self):
        p = self.bd.build_payload("Morning report", "<p>hi</p>")
        self.assertEqual(p["subject"], "Morning report")
        self.assertEqual(p["body"], "<p>hi</p>")
        self.assertEqual(p["email_type"], "public")
        # Must ask to SEND — an implicit draft returns 201 and mails nobody.
        self.assertEqual(p["status"], "about_to_send")

    def test_api_failure_is_not_fatal(self):
        os.environ[self.bd.ENV_KEY] = "k"
        orig = self.bd._post
        try:
            def boom(payload, key):
                raise OSError("network down")
            self.bd._post = boom
            self.assertFalse(self.bd.send("Subj", "<p>hi</p>"))  # no raise
        finally:
            self.bd._post = orig

    def test_success(self):
        os.environ[self.bd.ENV_KEY] = "k"
        orig = self.bd._post
        seen = {}
        try:
            def ok(payload, key):
                seen.update(payload=payload, key=key)
                return 201, '{"status": "about_to_send", "id": "abc12345"}'
            self.bd._post = ok
            self.assertTrue(self.bd.send("Subj", "<p>hi</p>"))
            self.assertEqual(seen["key"], "k")
            self.assertEqual(seen["payload"]["subject"], "Subj")
        finally:
            self.bd._post = orig
