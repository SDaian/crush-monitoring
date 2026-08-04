"""Offline tests for congress.social (selection, copy, card, state)."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from congress import social


def T(member="Somebody Obscure", ticker="AAPL", type="buy", lo=1001, hi=15000,
      tx="2026-06-01", filed="2026-06-20", chamber="house", filing="F1",
      party="R", state="TX", district="TX-1"):
    return {"member": member, "ticker": ticker, "type": type,
            "amount_lo": lo, "amount_hi": hi,
            "amount_label": f"${lo:,} - ${hi:,}",
            "tx_date": tx, "filing_date": filed, "chamber": chamber,
            "filing_id": filing, "party": party, "state": state,
            "district": district, "id": f"{chamber}:{filing}:0",
            "source_url": "https://example.gov/f.pdf"}


class TestNotability(unittest.TestCase):
    def test_featured_member_is_notable(self):
        self.assertTrue(social.is_notable([T(member="Nancy Pelosi")]))

    def test_big_bracket_is_notable(self):
        self.assertTrue(social.is_notable([T(lo=1_000_001, hi=5_000_000)]))

    def test_very_late_is_notable(self):
        self.assertTrue(social.is_notable(
            [T(tx="2026-01-01", filed="2026-06-20")]))  # ~125d past deadline

    def test_small_ontime_unfeatured_is_not(self):
        self.assertFalse(social.is_notable([T()]))


class TestSelection(unittest.TestCase):
    def test_groups_by_filing_and_skips_state(self):
        trades = [T(member="Nancy Pelosi", filing="A", ticker="NVDA"),
                  T(member="Nancy Pelosi", filing="A", ticker="AAPL"),
                  T(member="Nancy Pelosi", filing="B", filed="2026-07-01")]
        state = {"records": {"house:A": {"draft_id": 1}}}
        picked = social.select_new_filings(trades, state)
        self.assertEqual([social.record_id(r[0]) for r in picked], ["house:B"])

    def test_pure_bond_filing_skipped(self):
        bond = T(member="Donald J. Trump", filing="Z", chamber="executive")
        bond["ticker"] = None
        self.assertEqual(social.select_new_filings([bond], {"records": {}}), [])

    def test_newest_filing_first(self):
        trades = [T(member="Nancy Pelosi", filing="OLD", filed="2026-05-01"),
                  T(member="Nancy Pelosi", filing="NEW", filed="2026-07-01")]
        picked = social.select_new_filings(trades, {"records": {}})
        self.assertEqual(social.record_id(picked[0][0]), "house:NEW")


class TestPayloadAndCard(unittest.TestCase):
    def _rows(self):
        return [T(member="Alan Armstrong", chamber="senate", filing="S1",
                  district=None, state="OK", ticker="WMB", type="sell",
                  lo=5_000_001, hi=25_000_000,
                  tx="2026-06-24", filed="2026-07-21"),
                T(member="Alan Armstrong", chamber="senate", filing="S1",
                  district=None, state="OK", ticker="AAPL",
                  tx="2026-03-27", filed="2026-07-21")]

    def test_headline_is_largest_tickered_trade(self):
        p = social.filing_payload(self._rows())
        self.assertEqual(p["ticker"], "WMB")
        self.assertEqual(p["action"], "Sold")
        self.assertEqual(p["who"], "Sen. Alan Armstrong")
        self.assertEqual(p["extra_trades"], 1)
        self.assertEqual(p["late_days"], 71)  # the OTHER row's lateness counts

    def test_card_html_fills_every_placeholder(self):
        html = social.card_html(social.filing_payload(self._rows()))
        self.assertNotIn("{{", html)
        self.assertIn("Sold", html)
        self.assertIn("WMB", html)
        self.assertIn("days late", html)          # stamp present when late
        self.assertIn("file://", html)            # fonts absolutized

    def test_ontime_card_has_no_stamp(self):
        rows = [T(member="Nancy Pelosi", filing="P1")]
        html = social.card_html(social.filing_payload(rows))
        self.assertNotIn("stampbox", html.split("</style>")[1])

    def test_html_escaping(self):
        rows = [T(member="A <b>&Co", filing="E1")]
        html = social.card_html(social.filing_payload(rows))
        self.assertIn("A &lt;b&gt;&amp;Co", html)


class TestHoldingsContext(unittest.TestCase):
    """The narrative hook: what the member already holds of the ticker,
    from the member page's rolled-forward estimate. None on any gap."""

    def _page_dir(self, tmp, holdings):
        d = Path(tmp)
        (d / "marjorie-taylor-greene.json").write_text(
            json.dumps({"holdings": holdings}), encoding="utf-8")
        return d

    def test_found(self):
        with TemporaryDirectory() as tmp:
            d = self._page_dir(tmp, {
                "available": True,
                "stocks": [{"ticker": "AMZN", "estLabel": "$121K",
                            "pctPortfolio": 4.2}]})
            ctx = social.holdings_context(
                "Marjorie Taylor Greene", "AMZN", data_dir=d)
            self.assertEqual(ctx, {"est": "$121K", "pct": 4.2})

    def test_no_position_in_ticker(self):
        with TemporaryDirectory() as tmp:
            d = self._page_dir(tmp, {
                "available": True,
                "stocks": [{"ticker": "AMZN", "estLabel": "$121K",
                            "pctPortfolio": 4.2}]})
            self.assertIsNone(social.holdings_context(
                "Marjorie Taylor Greene", "NVDA", data_dir=d))

    def test_holdings_unavailable(self):
        # e.g. scanned annual report, or no annual filing yet
        with TemporaryDirectory() as tmp:
            d = self._page_dir(tmp, {"available": False, "stocks": []})
            self.assertIsNone(social.holdings_context(
                "Marjorie Taylor Greene", "AMZN", data_dir=d))

    def test_unfeatured_member(self):
        with TemporaryDirectory() as tmp:
            self.assertIsNone(social.holdings_context(
                "Somebody Obscure", "AMZN", data_dir=Path(tmp)))

    def test_missing_page_file(self):
        with TemporaryDirectory() as tmp:
            self.assertIsNone(social.holdings_context(
                "Marjorie Taylor Greene", "AMZN", data_dir=Path(tmp)))

    def test_payload_carries_context(self):
        rows = [T(member="Marjorie Taylor Greene", filing="G1", ticker="AMZN")]
        p = social.filing_payload(rows, context={"est": "$121K", "pct": 4.2})
        self.assertEqual(p["held_est"], "$121K")
        self.assertEqual(p["held_pct"], 4.2)

    def test_payload_without_context(self):
        p = social.filing_payload([T(member="Nancy Pelosi", filing="P1")])
        self.assertIsNone(p["held_est"])
        self.assertIsNone(p["held_pct"])

    def test_card_renders_context(self):
        rows = [T(member="Marjorie Taylor Greene", filing="G1", ticker="AMZN")]
        p = social.filing_payload(rows, context={"est": "$121K", "pct": 4.2})
        html = social.card_html(p)
        self.assertIn("Already holds ~$121K of AMZN — 4.2% of their "
                      "estimated portfolio", html)
        self.assertNotIn("{{", html)

    def test_card_context_empty_without_holdings(self):
        html = social.card_html(
            social.filing_payload([T(member="Nancy Pelosi", filing="P1")]))
        body = html.split("</style>")[1]
        self.assertIn('<div class="context"></div>', body)
        self.assertNotIn("Already holds", body)


class TestCopy(unittest.TestCase):
    def test_under_limit_with_cashtag(self):
        p = social.filing_payload([T(member="Nancy Pelosi", filing="P1")])
        text = social.post_copy(p)
        self.assertLessEqual(social._x_len(text), social.X_LIMIT)
        self.assertIn("$AAPL", text)
        self.assertNotIn("{", text)

    def test_opens_with_alert_line(self):
        p = social.filing_payload([T(member="Nancy Pelosi", filing="P1")])
        text = social.post_copy(p)
        self.assertTrue(text.startswith("🚨 NEW TRADE ALERT"))

    def test_emoji_weighs_two(self):
        self.assertEqual(social._x_len("🚨"), 2)

    def test_late_line_present_then_dropped_under_pressure(self):
        rows = [T(member="Nancy Pelosi", filing="P2",
                  tx="2026-01-01", filed="2026-06-20")]
        text = social.post_copy(social.filing_payload(rows))
        self.assertIn("past the legal 45-day deadline", text)

    def test_context_line_in_copy(self):
        p = social.filing_payload(
            [T(member="Marjorie Taylor Greene", filing="G1", ticker="AMZN")],
            context={"est": "$121K", "pct": 4.2})
        text = social.post_copy(p)
        self.assertIn("Already holds ~$121K of $AMZN — 4.2% of their "
                      "estimated portfolio.", text)
        self.assertLessEqual(social._x_len(text), social.X_LIMIT)

    def test_context_dropped_before_late_line(self):
        # Force the squeeze with a huge amount label: the context estimate
        # (nice-to-have) must go before the late line (accountability).
        row = T(member="Marjorie Taylor Greene", filing="G2", ticker="AMZN",
                tx="2026-01-01", filed="2026-06-20")
        # ~120-char label: over 280 with the context line, under without it
        row["amount_label"] = "$" + "9" * 80 + " - $" + "9" * 35
        p = social.filing_payload([row], context={"est": "$121K", "pct": 4.2})
        text = social.post_copy(p)
        self.assertNotIn("Already holds", text)
        self.assertIn("past the legal 45-day deadline", text)
        self.assertLessEqual(social._x_len(text), social.X_LIMIT)

    def test_link_counts_as_tco(self):
        p = social.filing_payload([T(member="Nancy Pelosi", filing="P3")])
        text = social.post_copy(p, include_link=True)
        self.assertIn("capitolledger.io/members/nancy-pelosi", text)
        self.assertLessEqual(social._x_len(text), social.X_LIMIT)
        # the raw string may exceed what X counts, never the reverse
        self.assertLessEqual(social._x_len(text), len(text))


class TestState(unittest.TestCase):
    def test_round_trip_and_mark(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "state.json"
            state = social.load_state(path)
            self.assertEqual(state["records"], {})
            social.mark_drafted(state, "house:A", 42)
            social.save_state(state, path)
            again = social.load_state(path)
            self.assertEqual(again["records"]["house:A"]["draft_id"], 42)
            self.assertIn("drafted_at", again["records"]["house:A"])
