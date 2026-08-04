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
        self.assertIn("🏛 New disclosures", md)
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
        self.assertIn("No new stock/option disclosures", r["markdown"])
        self.assertNotIn("bond & muni", r["markdown"])  # no zero-count line

    def test_bond_filings_collapse_to_a_count(self):
        # Ticker-less debt rows drowned the email (one senator's muni
        # ladder is a dozen lines) — the email collapses them to a count
        # that links the /report page, which shows the WHOLE undivided
        # picture (payload carries every row, bonds included).
        bonds = [{"member": "Rick Scott", "party": "R", "ticker": None,
                  "asset": f"Muni Bond {i}", "asset_type": "Municipal Security",
                  "type": "sell", "amount_label": "$100,001 - $250,000",
                  "tx_date": "2026-07-03", "filing_date": "2026-07-06"}
                 for i in range(3)]
        r = build_report(TRADES + bonds, AI, [],
                         prev_ratings=dict(self.r["ratings"]),
                         today_iso="2026-07-07")
        md = r["markdown"]
        self.assertNotIn("Muni Bond", md)               # no bond rows in md
        self.assertIn("plus 3 bond & muni filings", md)  # the count line
        self.assertIn("see the full report", md)         # …linking /report
        self.assertIn("Nancy Pelosi", md)                # equities intact
        self.assertEqual(r["counts"]["disclosures"], 4)  # the whole window
        self.assertEqual(r["counts"]["bonds"], 3)
        self.assertEqual(r["payload"]["bondCount"], 3)
        # The page payload is the full picture; the email showed 1 row.
        self.assertEqual(len(r["payload"]["disclosures"]), 4)
        self.assertEqual(r["payload"]["emailShown"], 1)
        self.assertIn("plus 3 bond &amp; muni filings", r["html"])
        self.assertIn("see the full report", r["html"])
        self.assertNotIn("Muni Bond", r["html"])

    def test_disclosures_lead_the_email(self):
        html = self.r["html"]
        self.assertLess(html.index("New disclosures"),
                        html.index("Technical read"))
        self.assertIn("New disclosures",
                      self.r["markdown"].split("Featured stocks")[0])

    def test_tickered_rows_never_counted_as_bonds(self):
        # is_bond must stay narrow: a tickered row is never a "bond" even
        # with a bond-ish asset type.
        odd = [{"member": "Somebody", "party": "D", "ticker": "BOND",
                "asset": "PIMCO Active Bond ETF", "asset_type": "Municipal Security",
                "type": "buy", "amount_label": "$1,001 - $15,000",
                "tx_date": "2026-07-03", "filing_date": "2026-07-06"}]
        r = build_report(TRADES + odd, AI, [],
                         prev_ratings=dict(self.r["ratings"]),
                         today_iso="2026-07-07")
        self.assertEqual(r["counts"]["bonds"], 0)
        self.assertIn("**BOND** buy", r["markdown"])

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

    def test_embed_variant_for_newsletter_providers(self):
        # Providers wrap content in their own template: a full document would
        # nest two HTML documents and break the styling, and their footer has
        # the real unsubscribe link so ours must not duplicate it.
        full, embed = self.r["html"], self.r["html_embed"]
        self.assertTrue(full.lstrip().startswith("<!DOCTYPE"))
        self.assertNotIn("<!DOCTYPE", embed)
        self.assertNotIn("</html>", embed)
        self.assertIn("Unsubscribe</a>", full)
        self.assertNotIn("Unsubscribe</a>", embed)
        # Same content either way.
        self.assertIn("Nancy Pelosi", embed)
        self.assertIn("Strong Buy", embed)

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
                      daily_report.REPORTS_DIR, daily_report.HOLDINGS_JSON,
                      daily_report._gh)
        daily_report.TRADES_JSON = base / "trades.json"
        daily_report.AI_JSON = base / "ai.json"
        daily_report.STATE_JSON = self.state
        # main() publishes the web edition too — point it at the temp dir so a
        # test run never overwrites the repo's real landing/src/data/report.json.
        self.report_json = base / "report.json"
        daily_report.REPORT_JSON = self.report_json
        # ... and the dated archive dir, for the same reason.
        self.reports_dir = base / "reports"
        daily_report.REPORTS_DIR = self.reports_dir
        # Missing file → no coverage section; gap tests write their own.
        daily_report.HOLDINGS_JSON = base / "holdings.json"
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
         daily_report.REPORTS_DIR, daily_report.HOLDINGS_JSON,
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

    def test_sends_the_confirmation_header(self):
        # Without X-Buttondown-Live-Dangerously the API refuses to send:
        # 400 sending_requires_confirmation. Lock the header in.
        import urllib.request
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["headers"] = {k.lower(): v for k, v in req.header_items()}

            class R:
                status = 201
                def read(self): return b'{"status": "about_to_send"}'
                def __enter__(self): return self
                def __exit__(self, *a): return False
            return R()

        orig = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            self.bd._post({"subject": "s"}, "key123")
        finally:
            urllib.request.urlopen = orig
        self.assertEqual(captured["headers"].get("X-buttondown-live-dangerously".lower()),
                         "true")
        # And the key is sent as a Token, never in the URL.
        self.assertEqual(captured["headers"].get("authorization"), "Token key123")

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


class TestReportArchive(TestMainDelivery):
    """The dated archive written alongside report.json."""

    def test_dated_copy_and_index_written(self):
        self.assertEqual(daily_report.main(), 0)
        import json as _json
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        dated = self.reports_dir / f"{today}.json"
        self.assertTrue(dated.exists())
        payload = _json.loads(dated.read_text())
        current = _json.loads(self.report_json.read_text())
        # Same payload as report.json — the permalink can't disagree with
        # what went out.
        self.assertEqual(payload["date"], current["date"])
        self.assertEqual(payload["disclosures"], current["disclosures"])
        index = _json.loads((self.reports_dir / "_index.json").read_text())
        self.assertEqual(index["reports"][0]["date"], today)

    def test_rerun_same_day_does_not_duplicate_index(self):
        import os as _os
        self.assertEqual(daily_report.main(), 0)
        _os.environ["REPORT_FORCE"] = "true"
        try:
            self.assertEqual(daily_report.main(), 0)
        finally:
            _os.environ.pop("REPORT_FORCE", None)
        import json as _json
        index = _json.loads((self.reports_dir / "_index.json").read_text())
        self.assertEqual(len(index["reports"]), 1)

    def test_email_links_the_dated_permalink(self):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        self.assertIn(f"/report/{today}", daily_report.report_url(today))


class TestHoldingsGaps(unittest.TestCase):
    def _holdings(self, reason, name="Alan Armstrong"):
        return {"holdings": {name: {"available": reason == "ok",
                                    "reason": reason}}}

    def test_needs_review_reasons_are_gaps(self):
        gaps = daily_report.holdings_gaps(self._holdings("scanned_no_text"))
        self.assertTrue(any(g.startswith("Alan Armstrong — ") for g in gaps))

    def test_ok_and_correct_data_reasons_are_not_gaps(self):
        for reason in ("ok", "no_individual_equities", "unsupported_chamber"):
            gaps = daily_report.holdings_gaps(self._holdings(reason))
            self.assertFalse(any("Alan Armstrong" in g for g in gaps), reason)

    def test_unfetched_featured_member_is_a_gap(self):
        gaps = daily_report.holdings_gaps({"holdings": {}})
        self.assertIn("Alan Armstrong — not fetched yet", gaps)

    def test_gaps_reach_email_and_markdown(self):
        r = daily_report.build_report(
            [], {}, [], {}, "2026-08-02",
            coverage_gaps=["Alan Armstrong — scanned report"])
        self.assertIn("Holdings coverage", r["markdown"])
        self.assertIn("Alan Armstrong", r["markdown"])
        self.assertIn("Holdings we could not parse", r["html"])

    def test_clean_day_renders_no_coverage_section(self):
        r = daily_report.build_report([], {}, [], {}, "2026-08-02",
                                      coverage_gaps=[])
        self.assertNotIn("Holdings coverage", r["markdown"])
        self.assertNotIn("Holdings we could not parse", r["html"])
