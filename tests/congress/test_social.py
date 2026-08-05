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

    def test_bracket_amount_not_on_card(self):
        # Owner's call: the bracket stays in the tweet copy but is too
        # easily read as an exact figure on the big card — keep it off.
        rows = [T(member="Nancy Pelosi", filing="P9")]
        html = social.card_html(social.filing_payload(rows))
        body = html.split("</style>")[1]
        self.assertNotIn("$1,001", body)
        text = social.post_copy(social.filing_payload(rows))
        self.assertIn("$1,001 – $15,000", text)  # copy keeps it

    def test_company_name_on_card(self):
        rows = [T(member="Nancy Pelosi", filing="P10")]
        rows[0]["asset"] = "Apple Inc. <Class A>"
        html = social.card_html(social.filing_payload(rows))
        self.assertIn("Apple Inc. &lt;Class A&gt;", html)


class TestFocusedPost(unittest.TestCase):
    """--focus aims a post at named tickers: a 60-row filing has more than
    one story, and the largest-bracket auto-pick tells only one."""

    def _rows(self):
        return [
            T(member="April McClain Delaney", filing="F", ticker="BWXT",
              lo=15001, hi=50000, tx="2026-07-24", filed="2026-08-03"),
            T(member="April McClain Delaney", filing="F", ticker="ENTG",
              lo=1001, hi=15000, tx="2026-07-08", filed="2026-08-03"),
            T(member="April McClain Delaney", filing="F", ticker="FWONK",
              lo=15001, hi=50000, tx="2026-07-31", filed="2026-08-03"),
        ]

    def test_focus_selects_named_tickers(self):
        picked = social.focus_rows(self._rows(), ["bwxt", " entg "])
        self.assertEqual(sorted(t["ticker"] for t in picked),
                         ["BWXT", "ENTG"])

    def test_no_focus_or_no_match_returns_empty(self):
        self.assertEqual(social.focus_rows(self._rows(), None), [])
        self.assertEqual(social.focus_rows(self._rows(), ["ZZZZ"]), [])

    def test_payload_covers_the_focused_rows(self):
        p = social.filing_payload(self._rows(), focus=["BWXT", "ENTG"])
        self.assertEqual(p["ticker"], "BWXT + ENTG")   # biggest name leads
        self.assertEqual(p["cashtags"], "$BWXT and $ENTG")
        self.assertEqual(p["primary_ticker"], "BWXT")  # for stats/holdings
        self.assertEqual(p["action"], "Bought")
        self.assertEqual(p["subject_trades"], 2)
        self.assertEqual(p["extra_trades"], 1)         # the unfocused FWONK
        self.assertEqual(p["company"], "")             # two firms, no one name
        # Brackets summed as a RANGE, never a single invented number.
        self.assertEqual(p["amount"], "$16,002 – $65,000 across 2 buys")
        self.assertEqual(p["tx_label"], "Jul 8–24, 2026")

    def test_unmatched_focus_falls_back_to_normal_post(self):
        p = social.filing_payload(self._rows(), focus=["ZZZZ"])
        plain = social.filing_payload(self._rows())
        self.assertEqual(p["ticker"], plain["ticker"])
        self.assertEqual(p["amount"], plain["amount"])

    def test_mixed_sides_read_as_traded(self):
        rows = self._rows()
        rows[1]["type"] = "sell"
        p = social.filing_payload(rows, focus=["BWXT", "ENTG"])
        self.assertEqual(p["action"], "Traded")
        self.assertIn("across 2 trades", p["amount"])

    def test_copy_names_both_cashtags(self):
        p = social.filing_payload(self._rows(), focus=["BWXT", "ENTG"])
        text = social.post_copy(p)
        self.assertIn("bought $BWXT and $ENTG", text)
        self.assertLessEqual(social._x_len(text), social.X_LIMIT)

    def test_single_ticker_focus_keeps_the_company_line(self):
        rows = self._rows() + [T(member="April McClain Delaney", filing="F",
                                 ticker="BWXT", lo=1001, hi=15000,
                                 tx="2026-07-27", filed="2026-08-03")]
        for r in rows:
            r["asset"] = "BWX Technologies Inc."
        p = social.filing_payload(rows, focus=["BWXT"])
        self.assertEqual(p["ticker"], "BWXT")
        self.assertEqual(p["company"], "BWX Technologies Inc.")
        self.assertEqual(p["subject_trades"], 2)


class TestHeadlineFit(unittest.TestCase):
    """A long headline must shrink, not ellipsis away — the portrait column
    leaves roughly half the width."""

    def test_short_label_keeps_full_size(self):
        self.assertEqual(social.headline_px("Bought TSM", False), 108)

    def test_long_label_shrinks_beside_a_portrait(self):
        wide = social.headline_px("Bought BWXT + ENTG", False)
        narrow = social.headline_px("Bought BWXT + ENTG", True)
        self.assertLess(narrow, wide)
        self.assertIn(narrow, social.HEADLINE_STEPS)

    def test_absurd_label_stops_at_the_floor(self):
        self.assertEqual(social.headline_px("Bought " + "X" * 80, True),
                         social.HEADLINE_STEPS[-1])

    def test_card_carries_the_size(self):
        p = social.filing_payload([T(member="Nancy Pelosi", filing="H1")])
        self.assertIn("font-size:108px", social.card_html(p))


class TestPortrait(unittest.TestCase):
    def test_found_by_slug_and_extension(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "cleo-fields.png").write_bytes(b"png")
            p = social.portrait_path("Cleo Fields", portraits_dir=d)
            self.assertEqual(p, d / "cleo-fields.png")

    def test_absent(self):
        with TemporaryDirectory() as tmp:
            self.assertIsNone(social.portrait_path(
                "Cleo Fields", portraits_dir=Path(tmp)))

    def test_card_with_portrait(self):
        with TemporaryDirectory() as tmp:
            img = Path(tmp) / "cleo-fields.jpg"
            img.write_bytes(b"jpg")
            p = social.filing_payload([T(member="Cleo Fields", filing="F1")])
            p["portrait"] = img
            html = social.card_html(p)
            self.assertIn('class="card has-portrait"', html)
            self.assertIn(img.as_uri(), html)
            self.assertIn("Official portrait · public domain", html)

    def test_card_without_portrait(self):
        p = social.filing_payload([T(member="Somebody Obscure", filing="F2",
                                     lo=1_000_001, hi=5_000_000)])
        html = social.card_html(p)
        self.assertIn('class="card "', html)
        self.assertNotIn("class='portrait'", html.split("</style>")[1])


class TestTickerStats(unittest.TestCase):
    def _trades(self):
        return [T(member="Nancy Pelosi", filing="A", ticker="TSM"),
                T(member="Cleo Fields", filing="B", ticker="TSM",
                  type="sell"),
                T(member="Cleo Fields", filing="B2", ticker="TSM",
                  tx="2025-06-01"),          # other year: excluded
                T(member="Nancy Pelosi", filing="C", ticker="NVDA")]

    def test_counts_by_year_and_ticker(self):
        s = social.ticker_stats(self._trades(), "TSM", "2026")
        self.assertEqual(s, {"members": 2, "trades": 2, "buys": 1,
                             "sells": 1, "year": "2026"})

    def test_none_without_ticker_or_rows(self):
        self.assertIsNone(social.ticker_stats(self._trades(), "", "2026"))
        self.assertIsNone(social.ticker_stats(self._trades(), "ZZZ", "2026"))

    def test_stats_band_rendered(self):
        rows = [T(member="Nancy Pelosi", filing="S1", ticker="TSM")]
        stats = {"members": 12, "trades": 50, "buys": 34, "sells": 16,
                 "year": "2026"}
        html = social.card_html(social.filing_payload(rows, stats=stats))
        self.assertIn("TSM in Congress · 2026", html)
        self.assertIn("<b>12 members</b> have disclosed", html)
        self.assertIn("34 buys", html)
        self.assertIn("16 sells", html)

    def test_stats_band_singular_first_trade(self):
        rows = [T(member="Nancy Pelosi", filing="S2", ticker="TSM")]
        stats = {"members": 1, "trades": 1, "buys": 1, "sells": 0,
                 "year": "2026"}
        html = social.card_html(social.filing_payload(rows, stats=stats))
        self.assertIn("<b>1 member</b> has disclosed <b>1 trade</b>", html)
        self.assertNotIn("0 sells", html)  # no buy/sell split on n=1

    def test_stats_band_absent_without_stats(self):
        rows = [T(member="Nancy Pelosi", filing="S3")]
        html = social.card_html(social.filing_payload(rows))
        self.assertNotIn("in Congress", html.split("</style>")[1])


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
        text = social.post_copy(p, include_link=False)
        self.assertNotIn("Already holds", text)
        self.assertIn("past the legal 45-day deadline", text)
        self.assertLessEqual(social._x_len(text), social.X_LIMIT)

    def test_link_counts_as_tco(self):
        p = social.filing_payload([T(member="Nancy Pelosi", filing="P3")])
        text = social.post_copy(p, include_link=True)
        self.assertIn("🔗 https://capitolledger.io/members/nancy-pelosi",
                      text)
        self.assertLessEqual(social._x_len(text), social.X_LIMIT)

    def test_link_included_by_default_for_featured(self):
        p = social.filing_payload([T(member="Nancy Pelosi", filing="P4")])
        self.assertIn("🔗 https://capitolledger.io/members/nancy-pelosi",
                      social.post_copy(p))

    def test_no_link_or_stray_emoji_for_unfeatured(self):
        # Big bracket makes an unfeatured member notable; they have no
        # member page, so no URL — and no orphaned 🔗 either.
        p = social.filing_payload(
            [T(member="Somebody Obscure", filing="P5",
               lo=1_000_001, hi=5_000_000)])
        text = social.post_copy(p)
        self.assertNotIn("capitolledger.io", text)
        self.assertNotIn("🔗", text)


class TestCliParser(unittest.TestCase):
    def test_empty_social_cap_env_falls_back_to_default(self):
        # The workflow always exports SOCIAL_CAP from a repo variable; unset
        # it arrives as "" and int("") crashed the whole CLI (every
        # subcommand — the parser is built before dispatch).
        import os
        from congress import cli
        old = os.environ.get("SOCIAL_CAP")
        os.environ["SOCIAL_CAP"] = ""
        try:
            args = cli.build_parser().parse_args(["social", "--dry-run"])
            self.assertEqual(args.cap, social.DEFAULT_CAP)
        finally:
            if old is None:
                del os.environ["SOCIAL_CAP"]
            else:
                os.environ["SOCIAL_CAP"] = old


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
