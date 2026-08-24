"""Offline tests for congress.landing_data (landing feed + stats generator)."""

import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from congress import landing_data as ld


def T(member="A Member", ticker="AAPL", type="buy", lo=1001, hi=15000,
      tx="2026-06-01", filed="2026-06-20", chamber="house", district="TX-1",
      state="TX", id="x"):
    return {"member": member, "ticker": ticker, "type": type,
            "amount_lo": lo, "amount_hi": hi, "tx_date": tx,
            "filing_date": filed, "chamber": chamber,
            "district": district if chamber == "house" else None,
            "state": state, "id": id}


class TestDisplayName(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(ld.display_name("Nancy Pelosi"), "N. Pelosi")
        self.assertEqual(ld.display_name("Michael T. McCaul"), "M. McCaul")

    def test_suffixes_not_surnames(self):
        self.assertEqual(ld.display_name("James French Hill III"), "J. Hill")
        self.assertEqual(ld.display_name("Vern Buchanan Jr."), "V. Buchanan")
        self.assertEqual(ld.display_name("Gilbert Ray Cisneros, Jr."), "G. Cisneros")
        self.assertEqual(ld.display_name("Neal Dunn MD"), "N. Dunn")

    def test_single_token_passthrough(self):
        self.assertEqual(ld.display_name("Cher"), "Cher")


class TestDaysLate(unittest.TestCase):
    def test_within_deadline_is_zero(self):
        self.assertEqual(ld.days_late(T(tx="2026-01-01", filed="2026-02-15")), 0)

    def test_past_deadline_counts_excess(self):
        # gap 60 days → 15 past the 45-day statutory max
        self.assertEqual(ld.days_late(T(tx="2026-01-01", filed="2026-03-02")), 15)

    def test_missing_dates_none(self):
        self.assertIsNone(ld.days_late({"tx_date": None, "filing_date": "2026-01-01"}))


class TestCompactBucket(unittest.TestCase):
    def test_prototype_style(self):
        self.assertEqual(ld.compact_bucket(1_000_001, 5_000_000), "$1M – $5M")
        self.assertEqual(ld.compact_bucket(15_001, 50_000), "$15K – $50K")
        self.assertEqual(ld.compact_bucket(1_001, 15_000), "$1K – $15K")
        self.assertEqual(ld.compact_bucket(50_000_001, None), "$50M+")
        self.assertEqual(ld.compact_bucket(None, None), "—")


class TestSelectFeed(unittest.TestCase):
    def test_distinct_members(self):
        trades = [T(member="Same Member", ticker=t, id=str(i))
                  for i, t in enumerate(["A", "B", "C", "D", "E"])]
        trades += [T(member=f"M{i}", id=f"m{i}") for i in range(4)]
        picked = ld.select_feed(trades)
        members = [t["member"] for t in picked]
        self.assertEqual(len(members), len(set(members)))  # no repeats
        self.assertEqual(len(picked), 5)

    def test_prefers_bigger_amounts(self):
        small = [T(member=f"S{i}", lo=1001, hi=15000, id=f"s{i}") for i in range(6)]
        big = T(member="Big Fish", lo=1_000_001, hi=5_000_000, id="big")
        picked = ld.select_feed(small + [big])
        self.assertIn("Big Fish", [t["member"] for t in picked])

    def test_includes_late_row_when_one_exists(self):
        ontime = [T(member=f"O{i}", lo=100_000, hi=250_000, id=f"o{i}")
                  for i in range(6)]
        late = T(member="Tardy", lo=1001, hi=15000,
                 tx="2026-03-01", filed="2026-06-15", id="late")  # way past 45d
        picked = ld.select_feed(ontime + [late])
        self.assertIn("Tardy", [t["member"] for t in picked])

    def test_includes_both_sides_when_present(self):
        buys = [T(member=f"B{i}", type="buy", lo=500_000, hi=1_000_000, id=f"b{i}")
                for i in range(6)]
        sell = T(member="Seller", type="sell", lo=1001, hi=15000, id="sell")
        sides = {t["type"] for t in ld.select_feed(buys + [sell])}
        self.assertEqual(sides, {"buy", "sell"})

    def test_widens_window_when_quiet(self):
        # Only 2 members in the last 30 days; 3 more only ~80 days back.
        recent = [T(member=f"R{i}", filed="2026-06-20", id=f"r{i}") for i in range(2)]
        old = [T(member=f"Old{i}", tx="2026-03-01", filed="2026-04-01", id=f"g{i}")
               for i in range(3)]
        picked = ld.select_feed(recent + old)
        self.assertEqual(len(picked), 5)

    def test_display_order_chronological(self):
        trades = [T(member=f"M{i}", filed=f"2026-06-{10+i:02d}", id=str(i))
                  for i in range(5)]
        picked = ld.select_feed(trades)
        dates = [t["filing_date"] for t in picked]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_empty_ok(self):
        self.assertEqual(ld.select_feed([]), [])


class TestPayloads(unittest.TestCase):
    def test_feed_shape_fr2(self):
        rows = ld.feed_payload([T(member="Nancy Pelosi", chamber="house",
                                  district="CA-11", lo=1_000_001, hi=5_000_000)])
        r = rows[0]
        self.assertEqual(set(r), {"member", "memberSlug", "chamber",
                                  "district", "ticker", "tickerSlug",
                                  "side", "amountBucket", "filedDaysLate"})
        self.assertEqual(r["member"], "N. Pelosi")
        self.assertEqual(r["chamber"], "House")
        self.assertEqual(r["district"], "CA-11")
        self.assertEqual(r["side"], "BUY")
        self.assertEqual(r["amountBucket"], "$1M – $5M")

    def test_senate_district_is_state(self):
        r = ld.feed_payload([T(chamber="senate", state="AL")])[0]
        self.assertEqual(r["chamber"], "Senate")
        self.assertEqual(r["district"], "AL")

    def test_stats_scoped_per_noun(self):
        trades = [
            T(tx="2026-01-10", filed="2026-01-20", lo=1001, hi=15000),      # traded+filed 2026, on time
            T(tx="2026-02-01", filed="2026-05-01", lo=100_000, hi=250_000), # traded+filed 2026, late
            T(tx="2025-12-01", filed="2025-12-20", lo=1_000_000, hi=5_000_000),  # prior year both
            T(tx="2024-11-01", filed="2026-03-01", lo=1001, hi=15000),      # old trade FILED 2026, very late
        ]
        s = ld.stats_payload(trades, today=date(2026, 7, 12))
        # trades/volume scope by TRADE year
        self.assertEqual(s["tradesThisYear"], 2)
        self.assertEqual(s["estVolumeThisYearUsd"],
                         round((1001+15000)/2 + (100_000+250_000)/2))
        # late share scopes by FILING year: 3 filings arrived in 2026, 2 late
        self.assertEqual(s["pctFiledLate"], 67)
        # median trade→filing lag among this year's trades: gaps 10d and 89d
        # → upper-median 89
        self.assertEqual(s["medianLagDays"], 89)

    def test_median_lag_empty_year(self):
        s = ld.stats_payload([], today=date(2026, 7, 12))
        self.assertEqual(s["medianLagDays"], 0)

    def test_write_files(self):
        with TemporaryDirectory() as d:
            out = Path(d)
            n, stats = ld.write_files([T()], out, today=date(2026, 7, 12))
            self.assertEqual(n, 1)
            disc = json.loads((out / "disclosures.json").read_text())
            self.assertEqual(len(disc["disclosures"]), 1)
            st = json.loads((out / "stats.json").read_text())
            self.assertEqual(st["tradesThisYear"], 1)
            late = json.loads((out / "late.json").read_text())
            self.assertIn("worst", late)


class TestLatePayload(unittest.TestCase):
    TODAY = date(2026, 7, 12)

    def test_ranked_by_days_late_desc(self):
        trades = [
            T(member="Ann Mild", tx="2026-01-01", filed="2026-03-02", id="a"),   # 15 late
            T(member="Bob Worse", tx="2025-11-01", filed="2026-03-01", id="b"),  # 75 late
            T(member="Cal Ontime", tx="2026-05-01", filed="2026-06-01", id="c"), # on time
        ]
        p = ld.late_payload(trades, today=self.TODAY)
        self.assertEqual([r["member"] for r in p["worst"]],
                         ["B. Worse", "A. Mild"])
        self.assertEqual(p["worst"][0]["daysLate"], 75)
        self.assertEqual(p["totalLateFilings"], 2)

    def test_one_row_per_member_keeps_worst_and_counts(self):
        trades = [
            T(member="Batch Filer", tx="2026-01-01", filed="2026-03-02", id="a"),  # 15
            T(member="Batch Filer", tx="2025-10-01", filed="2026-03-02", id="b"),  # 107
            T(member="Batch Filer", tx="2026-02-01", filed="2026-04-15", id="c"),  # 28
        ]
        p = ld.late_payload(trades, today=self.TODAY)
        self.assertEqual(len(p["worst"]), 1)
        self.assertEqual(p["worst"][0]["daysLate"], 107)
        self.assertEqual(p["worst"][0]["lateCount"], 3)
        self.assertEqual(p["totalLateFilings"], 3)

    def test_scoped_by_filing_year(self):
        trades = [
            T(member="Old News", tx="2025-01-01", filed="2025-12-01", id="a"),  # late, filed 2025
            T(member="Ed Fresh", tx="2024-11-01", filed="2026-03-01", id="b"),  # filed 2026
        ]
        p = ld.late_payload(trades, today=self.TODAY)
        self.assertEqual([r["member"] for r in p["worst"]], ["E. Fresh"])

    def test_row_shape(self):
        p = ld.late_payload(
            [T(member="Nancy Pelosi", tx="2026-01-01", filed="2026-04-01",
               lo=1_000_001, hi=5_000_000, district="CA-11")],
            today=self.TODAY)
        r = p["worst"][0]
        self.assertEqual(set(r), {"member", "chamber", "district", "ticker",
                                  "side", "amountBucket", "daysLate",
                                  "tradeDate", "filedDate", "lateCount"})
        self.assertEqual(r["member"], "N. Pelosi")
        self.assertEqual(r["daysLate"], 45)  # 90-day gap, 45 past the max
        self.assertEqual(r["amountBucket"], "$1M – $5M")

    def test_caps_at_count(self):
        trades = [T(member=f"Mem Ber{i}", tx="2026-01-01", filed="2026-04-01",
                    id=str(i)) for i in range(15)]
        p = ld.late_payload(trades, today=self.TODAY)
        self.assertEqual(len(p["worst"]), ld.LATE_BOARD_SIZE)
        self.assertEqual(p["totalLateFilings"], 15)

    def test_empty_ok(self):
        p = ld.late_payload([], today=self.TODAY)
        self.assertEqual(p["worst"], [])
        self.assertEqual(p["totalLateFilings"], 0)


def MT(member="Nancy Pelosi", ticker="NVDA", type="buy", lo=1001, hi=15000,
       tx="2026-06-01", filed="2026-06-20", asset="NVIDIA Corp",
       party="D", state="CA", district="CA-11", src="http://x/1"):
    """A trade row with the extra fields the member payload reads."""
    t = T(member=member, ticker=ticker, type=type, lo=lo, hi=hi, tx=tx,
          filed=filed, state=state, district=district)
    t.update(asset=asset, party=party, source_url=src)
    return t


HOLDINGS = {
    "Nancy Pelosi": {
        "available": True, "report_year": 2025, "filing_date": "2026-05-15",
        "source_url": "http://x/annual",
        "stocks": [
            {"ticker": "NVDA", "asset": "NVIDIA Corp", "asset_type": "Stock",
             "value_lo": 1_000_001, "value_hi": 5_000_000},
            {"ticker": "AAPL", "asset": "Apple Inc.", "asset_type": "Stock",
             "value_lo": 250_001, "value_hi": 500_000},
        ],
    },
}


class TestMemberPayload(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(ld.slugify("Nancy Pelosi"), "nancy-pelosi")
        self.assertEqual(ld.slugify("Donald J. Trump"), "donald-j-trump")

    def test_summary_and_tickers(self):
        trades = [
            MT(ticker="NVDA", tx="2026-06-01"),
            MT(ticker="NVDA", tx="2026-05-01"),
            MT(ticker="AAPL", type="sell", tx="2026-04-01"),
            MT(member="Someone Else", ticker="TSLA"),  # excluded
        ]
        p = ld.member_payload("Nancy Pelosi", trades, HOLDINGS)
        self.assertEqual(p["slug"], "nancy-pelosi")
        self.assertEqual(p["summary"]["trades"], 3)
        self.assertEqual(p["summary"]["distinctTickers"], 2)
        self.assertEqual(p["summary"]["firstTx"], "2026-04-01")
        self.assertEqual(p["summary"]["lastTx"], "2026-06-01")
        self.assertEqual(p["topTickers"][0]["ticker"], "NVDA")
        self.assertEqual(p["topTickers"][0]["count"], 2)

    def test_trades_sorted_desc_and_capped(self):
        trades = [MT(ticker=f"T{i}", tx=f"2026-06-{i:02d}") for i in range(1, 26)]
        p = ld.member_payload("Nancy Pelosi", trades, {})
        self.assertEqual(p["summary"]["trades"], 25)
        # The whole record ships: a filter over a truncated list lies
        # (owner request, 2026-08-23), so there is no row cap any more.
        self.assertEqual(p["tradesShown"], len(trades))
        self.assertEqual(len(p["trades"]), len(trades))
        # Most recent first.
        self.assertEqual(p["trades"][0]["txDate"], "2026-06-25")

    def test_late_share_rounds_but_worst_kept(self):
        # One 100-day-late filing among many on-time → pctLate rounds to 0,
        # but worstLate stays non-zero (the page shows "<1%", not "0%").
        trades = [MT(tx="2026-01-01", filed="2026-02-10") for _ in range(99)]
        trades.append(MT(tx="2026-01-01", filed="2026-05-25"))  # ~99 days late
        p = ld.member_payload("Nancy Pelosi", trades, {})
        self.assertEqual(p["summary"]["pctLate"], 1)  # 1/100
        self.assertGreater(p["summary"]["worstLate"], 0)

    def test_holdings_snapshot_base(self):
        # A trade BEFORE the annual snapshot rolls nothing forward → the
        # holdings are the raw annual positions.
        p = ld.member_payload("Nancy Pelosi", [MT(tx="2025-01-01")], HOLDINGS,
                              today_iso="2026-07-01")
        h = p["holdings"]
        self.assertTrue(h["available"])
        self.assertEqual(h["reportYear"], 2025)
        self.assertEqual([s["ticker"] for s in h["stocks"]], ["NVDA", "AAPL"])
        self.assertIsNotNone(h["totalLabel"])
        self.assertTrue(all(s["estLabel"].startswith("$") for s in h["stocks"]))
        self.assertFalse(any(s["isNew"] for s in h["stocks"]))
        pcts = [s["pctPortfolio"] for s in h["stocks"]]
        self.assertAlmostEqual(sum(pcts), 100.0, delta=0.2)
        self.assertGreater(pcts[0], pcts[1])

    def test_rollforward_new_ticker_after_snapshot(self):
        trades = [MT(ticker="TSLA", type="buy", tx="2026-06-01",
                     lo=1_000_001, hi=5_000_000)]
        p = ld.member_payload("Nancy Pelosi", trades, HOLDINGS,
                              today_iso="2026-07-01")
        pos = {s["ticker"]: s for s in p["holdings"]["stocks"]}
        self.assertIn("TSLA", pos)
        self.assertTrue(pos["TSLA"]["isNew"])

    def test_rollforward_sell_drops_position(self):
        # Selling ~$3M of a ~$3M NVDA position rolls it to ~0 → dropped.
        trades = [MT(ticker="NVDA", type="sell", tx="2026-06-01",
                     lo=1_000_001, hi=5_000_000)]
        p = ld.member_payload("Nancy Pelosi", trades, HOLDINGS,
                              today_iso="2026-07-01")
        tickers = {s["ticker"] for s in p["holdings"]["stocks"]}
        self.assertNotIn("NVDA", tickers)
        self.assertIn("AAPL", tickers)

    def test_rollforward_live_option_shown_expired_dropped(self):
        live = MT(ticker="INTC", type="buy", tx="2026-06-01",
                  lo=1_000_001, hi=5_000_000)
        live["asset_type"] = "Option"
        live["option"] = {"type": "call", "strike": 50.0,
                          "expiration": "2027-03-19"}
        expired = MT(ticker="MU", type="buy", tx="2026-06-02",
                     lo=1_000_001, hi=5_000_000)
        expired["asset_type"] = "Option"
        expired["option"] = {"type": "call", "strike": 90.0,
                            "expiration": "2026-01-01"}
        p = ld.member_payload("Nancy Pelosi", [live, expired], HOLDINGS,
                              today_iso="2026-07-01")
        opts = {o["ticker"] for o in p["holdings"]["options"]}
        self.assertIn("INTC", opts)      # expires after today → live
        self.assertNotIn("MU", opts)     # expired before today → dropped

    def test_executive_chamber_not_mislabelled_house(self):
        # OGE 278-T filers (e.g. the President) are executive branch, not House.
        t = MT(member="Donald J. Trump", state="US", district=None)
        t["chamber"] = "executive"
        p = ld.member_payload("Donald J. Trump", [t], {})
        self.assertEqual(p["chamber"], "Executive")

    def test_holdings_absent_when_no_annual(self):
        p = ld.member_payload("Nancy Pelosi", [MT()], {})
        self.assertFalse(p["holdings"]["available"])
        self.assertEqual(p["holdings"]["stocks"], [])
        self.assertIsNone(p["holdings"]["totalLabel"])

    def test_write_member_files_skips_zero_trade_members(self):
        trades = [MT(member="Nancy Pelosi")]
        with TemporaryDirectory() as d:
            out = Path(d)
            written = ld.write_member_files(
                trades, HOLDINGS, out,
                names=["Nancy Pelosi", "Ghost Member"],
            )
            self.assertEqual(written, ["nancy-pelosi"])
            self.assertTrue((out / "members" / "nancy-pelosi.json").exists())
            self.assertFalse((out / "members" / "ghost-member.json").exists())
            index = json.loads((out / "members" / "_index.json").read_text())
            self.assertEqual([m["slug"] for m in index["members"]],
                             ["nancy-pelosi"])
            self.assertIn("worstLate", index["members"][0])


if __name__ == "__main__":
    unittest.main()


class TestTickerPages(unittest.TestCase):
    """Ticker pages: universe picked by substance, payload, and file writing."""

    def test_ticker_slug(self):
        self.assertEqual(ld.ticker_slug("NVDA"), "nvda")
        self.assertEqual(ld.ticker_slug("BRK.B"), "brk-b")

    def test_clean_company(self):
        self.assertEqual(
            ld.clean_company("NVIDIA Corporation - Common Stock", "NVDA"),
            "NVIDIA Corporation")
        self.assertEqual(
            ld.clean_company("Alphabet Inc. - Class C Capital Stock", "GOOG"),
            "Alphabet Inc.")
        self.assertEqual(
            ld.clean_company("Williams Companies, Inc. (The) Common Stock", "WMB"),
            "Williams Companies, Inc.")
        self.assertEqual(ld.clean_company("Apple Inc. (AAPL)", "AAPL"), "Apple Inc.")
        # No usable asset string → fall back to the symbol, never empty.
        self.assertEqual(ld.clean_company("", "XYZ"), "XYZ")

    def test_universe_excludes_thin_tickers(self):
        # 30 NVDA trades clear the bar; a 2-trade ticker must NOT get a page
        # (thin auto-generated pages are an SEO liability).
        trades = [MT(ticker="NVDA", tx="2026-06-01") for _ in range(30)]
        trades += [MT(ticker="THIN") for _ in range(2)]
        uni = ld.select_ticker_pages(trades, minimum=25, featured=[])
        self.assertEqual(uni, ["NVDA"])
        self.assertNotIn("THIN", uni)

    def test_universe_ranked_and_uncapped(self):
        # Every symbol clearing the bar earns a page — a top-N cap once cut
        # 66 qualifying symbols (ORCL, IBM, LMT …), which is a content gap.
        trades = ([MT(ticker="AAA") for _ in range(30)]
                  + [MT(ticker="BBB") for _ in range(40)]
                  + [MT(ticker="CCC") for _ in range(20)])
        self.assertEqual(
            ld.select_ticker_pages(trades, minimum=20, featured=[]),
            ["BBB", "AAA", "CCC"])

    def test_featured_tickers_get_a_page_even_when_thin(self):
        # The tracker's Featured tab links per ticker, so the page must
        # resolve; thin ones ride along after the qualifying set.
        trades = ([MT(ticker="NVDA") for _ in range(30)]
                  + [MT(ticker="NU") for _ in range(4)])
        uni = ld.select_ticker_pages(trades, minimum=25, featured=["NU"])
        self.assertEqual(uni, ["NVDA", "NU"])

    def test_featured_ticker_is_not_duplicated(self):
        trades = [MT(ticker="NVDA") for _ in range(30)]
        self.assertEqual(
            ld.select_ticker_pages(trades, minimum=25, featured=["NVDA"]),
            ["NVDA"])

    def test_only_substantive_pages_are_indexable(self):
        # The thin featured stub exists to make a link resolve — it must
        # never be offered to search engines.
        self.assertTrue(ld.ticker_is_indexable(25, minimum=25))
        self.assertFalse(ld.ticker_is_indexable(4, minimum=25))

    def test_payload_carries_the_index_flag(self):
        thin = [MT(ticker="NU", tx="2026-06-01") for _ in range(4)]
        fat = [MT(ticker="NVDA", tx="2026-06-01") for _ in range(30)]
        self.assertFalse(ld.ticker_payload("NU", thin)["indexable"])
        self.assertTrue(ld.ticker_payload("NVDA", fat)["indexable"])

    def test_payload_summary_and_members(self):
        trades = [
            MT(member="Nancy Pelosi", ticker="NVDA", type="buy", tx="2026-06-01"),
            MT(member="Nancy Pelosi", ticker="NVDA", type="buy", tx="2026-05-01"),
            MT(member="Tommy Tuberville", ticker="NVDA", type="sell",
               tx="2026-04-01"),
            MT(member="Nancy Pelosi", ticker="AAPL"),          # other ticker
        ]
        p = ld.ticker_payload("NVDA", trades)
        self.assertEqual(p["slug"], "nvda")
        self.assertEqual(p["ticker"], "NVDA")
        self.assertEqual(p["summary"]["trades"], 3)
        self.assertEqual(p["summary"]["members"], 2)
        self.assertEqual(p["summary"]["buys"], 2)
        self.assertEqual(p["summary"]["sells"], 1)
        self.assertEqual(p["summary"]["firstTx"], "2026-04-01")
        self.assertEqual(p["summary"]["lastTx"], "2026-06-01")
        # Most active filer first; featured members are flagged for linking.
        self.assertEqual(p["topMembers"][0]["name"], "Nancy Pelosi")
        self.assertEqual(p["topMembers"][0]["trades"], 2)
        self.assertTrue(p["topMembers"][0]["hasPage"])

    def test_payload_rows_have_source_and_are_capped(self):
        trades = [MT(ticker="NVDA", tx=f"2026-06-{i:02d}") for i in range(1, 30)]
        p = ld.ticker_payload("NVDA", trades)
        self.assertEqual(p["tradesShown"], ld.TICKER_TRADE_CAP)
        self.assertEqual(p["trades"][0]["txDate"], "2026-06-29")  # newest first
        self.assertTrue(p["trades"][0]["sourceUrl"])              # provenance

    def test_unfeatured_member_not_linked(self):
        p = ld.ticker_payload("NVDA", [MT(member="Random Filer", ticker="NVDA")])
        self.assertFalse(p["topMembers"][0]["hasPage"])
        self.assertFalse(p["trades"][0]["hasPage"])

    def test_write_ticker_files(self):
        trades = [MT(ticker="NVDA", tx="2026-06-01") for _ in range(30)]
        trades += [MT(ticker="THIN") for _ in range(2)]
        with TemporaryDirectory() as d:
            out = Path(d)
            written = ld.write_ticker_files(trades, out)
            self.assertEqual(written, ["nvda"])
            self.assertTrue((out / "tickers" / "nvda.json").exists())
            self.assertFalse((out / "tickers" / "thin.json").exists())
            idx = json.loads((out / "tickers" / "_index.json").read_text())
            self.assertEqual([r["ticker"] for r in idx["tickers"]], ["NVDA"])
            self.assertEqual(idx["tickers"][0]["trades"], 30)

    def test_industry_badge_rides_the_payload_and_the_index(self):
        trades = [MT(ticker="NVDA", tx="2026-06-01") for _ in range(30)]
        sd = {"sectors": {"tech": "Technology & semiconductors"},
              "committees": {}, "tickers": {"NVDA": "tech"}}
        p = ld.ticker_payload("NVDA", trades, sector_data=sd)
        self.assertEqual(p["industry"],
                         {"key": "tech", "label": "Technology & semiconductors"})
        with TemporaryDirectory() as d:
            out = Path(d)
            ld.write_ticker_files(trades, out)
            idx = json.loads((out / "tickers" / "_index.json").read_text())
        # The index ships the label map too: the filter builds its options
        # from it, so a page cannot offer an industry the data does not have.
        self.assertEqual(idx["tickers"][0]["industry"]["key"], "tech")
        self.assertIn("tech", idx["industries"])

    def test_an_unclassified_ticker_gets_no_badge(self):
        # None, not a blank label: the surfaces count it as uncovered and say
        # so, instead of drawing an empty box.
        p = ld.ticker_payload("ZZZZ", [MT(ticker="ZZZZ")],
                              sector_data={"sectors": {}, "committees": {},
                                           "tickers": {}})
        self.assertIsNone(p["industry"])

    def test_member_chips_link_to_ticker_pages(self):
        trades = [MT(ticker="NVDA", tx="2026-06-01") for _ in range(30)]
        p = ld.member_payload("Nancy Pelosi", trades, {},
                              ticker_pages={"NVDA"})
        chip = p["topTickers"][0]
        self.assertEqual(chip["slug"], "nvda")
        self.assertTrue(chip["hasPage"])
        # Without the set, chips stay plain (no link to a page that isn't built).
        plain = ld.member_payload("Nancy Pelosi", trades, {})
        self.assertFalse(plain["topTickers"][0]["hasPage"])


class TestGeneratedToday(unittest.TestCase):
    """The same-day guard on the rate-limited Twelve Data refreshes."""

    def test_fresh_and_stale(self):
        from congress import cli
        with TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            p.write_text(json.dumps(
                {"meta": {"generated_at": "2026-07-28T03:34:39Z"}}))
            self.assertTrue(cli.generated_today(p, "2026-07-28"))
            self.assertFalse(cli.generated_today(p, "2026-07-29"))

    def test_missing_or_unreadable_means_do_the_work(self):
        from congress import cli
        with TemporaryDirectory() as d:
            self.assertFalse(cli.generated_today(Path(d) / "nope.json", "2026-07-28"))
            bad = Path(d) / "bad.json"
            bad.write_text("not json")
            self.assertFalse(cli.generated_today(bad, "2026-07-28"))
            nometa = Path(d) / "n.json"
            nometa.write_text("{}")
            self.assertFalse(cli.generated_today(nometa, "2026-07-28"))


class TestPerformanceBlock(unittest.TestCase):
    def _trades(self, n=3):
        return [T(member="Nancy Pelosi", ticker="AAPL", type="buy",
                  tx=f"2026-06-{d:02d}", id=f"b{d}") for d in range(1, n + 1)]

    def _returns(self, ids, pct=20.0, bench=10.0):
        return {i: {"pct": pct, "bench_pct": bench} for i in ids}

    def test_available_with_kpis(self):
        ts = self._trades(4)
        returns = self._returns(["b1", "b2", "b3"])
        returns["b1"]["pct"] = 5.0  # below bench: not a beat
        perf = {"benchmark": {"label": "S&P 500", "asof_date": "2026-07-31"},
                "members": {"Nancy Pelosi": {"dates": ["2026-06-01"],
                                             "member": [100.0],
                                             "bench": [100.0], "buys": 3}}}
        p = ld.performance_block("Nancy Pelosi", ts, returns, perf)
        self.assertTrue(p["available"])
        self.assertEqual(p["kpis"]["priced"], 3)
        self.assertEqual(p["kpis"]["pricedOf"], 4)
        self.assertEqual(p["kpis"]["beat"], 2)
        self.assertEqual(p["kpis"]["medianPct"], 20.0)
        self.assertEqual(p["kpis"]["medianBenchPct"], 10.0)
        self.assertEqual(p["asofDate"], "2026-07-31")
        self.assertIsNotNone(p["series"])
        # newest trade first, excess computed
        self.assertEqual(p["rows"][0]["txDate"], "2026-06-03")
        self.assertEqual(p["rows"][0]["excess"], 10.0)

    def test_too_few_priced_buys_is_unavailable(self):
        ts = self._trades(3)
        p = ld.performance_block("Nancy Pelosi", ts,
                                 self._returns(["b1", "b2"]), {})
        self.assertFalse(p["available"])
        self.assertEqual(p["reason"], "not_enough_priced_buys")

    def test_returns_without_bench_pct_is_no_benchmark(self):
        # Committed returns.json predating the benchmark field: rows priced,
        # but none carries bench_pct.
        ts = self._trades(3)
        returns = {f"b{i}": {"pct": 20.0} for i in (1, 2, 3)}
        p = ld.performance_block("Nancy Pelosi", ts, returns, {})
        self.assertFalse(p["available"])
        self.assertEqual(p["reason"], "no_benchmark")

    def test_options_never_counted(self):
        ts = self._trades(3)
        for t in ts:
            t["asset_type"] = "Option"
        p = ld.performance_block("Nancy Pelosi", ts,
                                 self._returns(["b1", "b2", "b3"]), {})
        self.assertFalse(p["available"])

    def test_missing_series_keeps_block_available(self):
        ts = self._trades(3)
        p = ld.performance_block("Nancy Pelosi", ts,
                                 self._returns(["b1", "b2", "b3"]), {})
        self.assertTrue(p["available"])
        self.assertIsNone(p["series"])


class TestBondDeEmphasis(unittest.TestCase):
    def _bond(self, **kw):
        t = T(ticker=None, id=kw.pop("id", "bond1"), **kw)
        t["ticker"] = None
        t["asset_type"] = "bond"
        return t

    def test_bonds_out_of_headline_stats(self):
        from datetime import date as _date
        stock = T(tx="2026-06-01", filed="2026-06-20", id="s1")
        stock["asset_type"] = "Stock"
        bond = self._bond(tx="2026-06-01", filed="2026-06-20")
        s = ld.stats_payload([stock, bond], _date(2026, 7, 12))
        self.assertEqual(s["tradesThisYear"], 1)

    def test_tickered_rows_never_bond_filtered(self):
        t = T()
        t["asset_type"] = "Corporate Security"  # tickered CS row stays
        self.assertFalse(ld.is_bond(t))
        self.assertTrue(ld.is_bond(self._bond()))

    def test_bonds_stay_on_member_pages(self):
        bond = self._bond(tx="2026-06-01", filed="2026-06-20")
        bond["member"] = "Donald J. Trump"
        p = ld.member_payload("Donald J. Trump", [bond], {})
        self.assertEqual(p["summary"]["trades"], 1)


class TestFeedLinks(unittest.TestCase):
    def _pool(self):
        # Distinct members so select_feed keeps all rows.
        return [
            T(member="Nancy Pelosi", ticker="NVDA", id="a",
              tx="2026-06-01", filed="2026-06-20"),
            T(member="Somebody Unfeatured", ticker="ZZZQ", id="b",
              tx="2026-06-01", filed="2026-06-20"),
        ]

    def test_featured_member_and_paged_ticker_get_slugs(self):
        rows = ld.feed_payload(self._pool(), ticker_pages={"NVDA"})
        by_ticker = {r["ticker"]: r for r in rows}
        self.assertEqual(by_ticker["NVDA"]["memberSlug"], "nancy-pelosi")
        self.assertEqual(by_ticker["NVDA"]["tickerSlug"], "nvda")

    def test_unfeatured_member_and_unpaged_ticker_get_none(self):
        rows = ld.feed_payload(self._pool(), ticker_pages={"NVDA"})
        by_ticker = {r["ticker"]: r for r in rows}
        self.assertIsNone(by_ticker["ZZZQ"]["memberSlug"])
        self.assertIsNone(by_ticker["ZZZQ"]["tickerSlug"])

    def test_no_ticker_pages_argument_means_no_ticker_links(self):
        rows = ld.feed_payload(self._pool())
        self.assertTrue(all(r["tickerSlug"] is None for r in rows))


class TestLastFiling(unittest.TestCase):
    def test_member_summary_carries_newest_filing_date(self):
        ts = [T(member="Nancy Pelosi", tx="2026-06-01", filed="2026-06-20", id="a"),
              T(member="Nancy Pelosi", tx="2026-06-10", filed="2026-07-30", id="b")]
        p = ld.member_payload("Nancy Pelosi", ts, {})
        self.assertEqual(p["summary"]["lastFiling"], "2026-07-30")

    def test_ticker_summary_carries_newest_filing_date(self):
        ts = [MT(tx="2026-06-01", filed="2026-07-05"),
              MT(tx="2026-06-02", filed="2026-06-20")]
        p = ld.ticker_payload("NVDA", ts)
        self.assertEqual(p["summary"]["lastFiling"], "2026-07-05")


class TestMemberIndexPerf(unittest.TestCase):
    def _write(self, perf_members):
        perf = {"benchmark": {"label": "S&P 500", "asof_date": "2026-07-31"},
                "members": perf_members}
        trades = [MT(tx=f"2026-06-{d:02d}") for d in range(1, 5)]
        returns = {t["id"]: {"pct": 20.0, "bench_pct": 10.0} for t in trades}
        # MT() ids default to "x" — give them distinct ids for the returns map
        for i, t in enumerate(trades):
            t["id"] = f"b{i}"
        returns = {f"b{i}": {"pct": 20.0, "bench_pct": 10.0} for i in range(4)}
        with TemporaryDirectory() as d:
            out = Path(d)
            ld.write_member_files(trades, {}, out, names=["Nancy Pelosi"],
                                  returns=returns, perf=perf)
            return json.loads((out / "members" / "_index.json").read_text())

    def test_index_carries_race_totals_as_a_pair(self):
        idx = self._write({"Nancy Pelosi": {
            "dates": ["2026-06-01", "2026-07-31"],
            "member": [100.0, 135.3], "bench": [100.0, 117.1], "buys": 4}})
        row = idx["members"][0]
        self.assertEqual(row["perfPct"], 35)
        self.assertEqual(row["perfBenchPct"], 17)

    def test_every_member_gets_their_series_not_just_the_first(self):
        # Regression: the index writer once shadowed the shared `perf`
        # argument inside its loop, so only the FIRST member ever got a
        # series — a single-member test could not see it.
        series = {"dates": ["2026-06-01", "2026-07-31"],
                  "member": [100.0, 120.0], "bench": [100.0, 110.0],
                  "buys": 4}
        perf = {"benchmark": {"label": "S&P 500", "asof_date": "2026-07-31"},
                "members": {"Nancy Pelosi": dict(series),
                            "Marjorie Taylor Greene": dict(series)}}
        trades = []
        for i, member in enumerate(["Nancy Pelosi", "Marjorie Taylor Greene"]):
            for d in range(1, 5):
                tr = MT(member=member, tx=f"2026-06-{d:02d}")
                tr["id"] = f"{i}-{d}"
                trades.append(tr)
        returns = {t["id"]: {"pct": 20.0, "bench_pct": 10.0} for t in trades}
        with TemporaryDirectory() as d:
            out = Path(d)
            ld.write_member_files(
                trades, {}, out,
                names=["Nancy Pelosi", "Marjorie Taylor Greene"],
                returns=returns, perf=perf)
            idx = json.loads((out / "members" / "_index.json").read_text())
        pcts = {r["name"]: r["perfPct"] for r in idx["members"]}
        self.assertEqual(pcts, {"Nancy Pelosi": 20,
                                "Marjorie Taylor Greene": 20})

    def test_no_series_means_no_numbers(self):
        idx = self._write({})
        row = idx["members"][0]
        self.assertIsNone(row["perfPct"])
        self.assertIsNone(row["perfBenchPct"])


class TestTechnicalBlock(unittest.TestCase):
    """The ticker page's technical panel — featured watchlist only, and
    scored by the SAME function the tracker and the report use."""

    READINGS = {
        "NVDA": {"name": "NVIDIA", "asof_date": "2026-08-06", "price": 218.99,
                 "chg_1d": -0.1, "chg_1w": 12.3, "chg_1m": 7.3, "rsi14": 61.4,
                 "sma20": 206.2, "sma50": 205.9, "sma200": 193.8,
                 "vs_sma50": 6.4, "vs_sma200": 13.0, "rel_vol": 0.87,
                 "high_52w": 235.7, "low_52w": 165.2, "range_pos": 76.0,
                 "series": [{"d": "2026-08-03", "c": 218.99}],
                 "signals": [{"type": "golden_cross", "label": "Golden cross",
                              "asof": "2026-08-06"}]},
    }

    def test_featured_ticker_gets_a_panel(self):
        b = ld.technical_block("NVDA", self.READINGS)
        self.assertEqual(b["asOf"], "2026-08-06")
        self.assertEqual(b["rsi14"], 61.4)
        self.assertEqual(len(b["series"]), 1)
        self.assertEqual(len(b["signals"]), 1)

    def test_unfeatured_ticker_has_no_panel(self):
        self.assertIsNone(ld.technical_block("LMT", self.READINGS))
        self.assertIsNone(ld.technical_block("NVDA", {}))

    def test_score_matches_the_shared_function(self):
        from congress.indicators import ai_score
        b = ld.technical_block("NVDA", self.READINGS)
        self.assertEqual(b["score"], ai_score(self.READINGS["NVDA"]))

    def test_absent_earnings_is_none_not_invented(self):
        self.assertIsNone(ld.technical_block("NVDA", self.READINGS)["nextEarnings"])

    def test_payload_carries_the_panel_only_when_featured(self):
        trades = [MT(ticker="NVDA", tx="2026-06-01") for _ in range(30)]
        with_panel = ld.ticker_payload("NVDA", trades, indicators=self.READINGS)
        without = ld.ticker_payload("NVDA", trades)
        self.assertIsNotNone(with_panel["technical"])
        self.assertIsNone(without["technical"])

    def test_missing_indicator_file_degrades_to_empty(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            self.assertEqual(ld.load_indicators(Path(tmp) / "absent.json"), {})


class TestMarketFile(unittest.TestCase):
    """One market.json, imported by every ticker page."""

    READING = {"source": "vix", "label": "VIX", "level": 18.5,
               "band": "normal", "bandLabel": "Normal"}

    def _indicators(self, tmp, payload):
        path = Path(tmp) / "ai-indicators.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_reads_the_reading_from_the_indicators_file(self):
        with TemporaryDirectory() as tmp:
            path = self._indicators(tmp, {"tickers": {},
                                          "market": self.READING})
            self.assertEqual(ld.load_market(path), self.READING)

    def test_absent_or_unreadable_is_none(self):
        with TemporaryDirectory() as tmp:
            self.assertIsNone(ld.load_market(self._indicators(tmp, {"tickers": {}})))
            self.assertIsNone(ld.load_market(Path(tmp) / "missing.json"))

    def test_the_file_is_always_written(self):
        # Every ticker page imports it at build time, so a missing reading
        # must still produce a file — with a null reading, not no file.
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            ld.write_files([], out, today=date(2026, 8, 1))
            data = json.loads((out / "market.json").read_text())
            self.assertIn("market", data)


class TestCommitteeBlock(unittest.TestCase):
    """Seats on a member page: the seat only, and an empty list is not one thing."""

    DATA = {"members": {
        "Josh Gottheimer": {"reason": "assigned", "committees": [
            {"id": "HLIG", "name": "House Permanent Select Committee on Intelligence",
             "shortName": "House Intelligence", "url": "https://intelligence.house.gov/",
             "title": "Member",
             "subcommittees": [{"name": "National Security Agency and Cyber"}]}]},
        "Nancy Pelosi": {"reason": "none_current", "committees": []},
        "Donald J. Trump": {"reason": "not_in_congress", "committees": []},
    }}

    def test_assigned_member_gets_the_block(self):
        b = ld.committee_block("Josh Gottheimer", self.DATA)
        self.assertEqual(b["committees"][0]["name"], "House Intelligence")
        self.assertEqual(b["committees"][0]["subcommittees"],
                         ["National Security Agency and Cyber"])
        self.assertEqual(b["committees"][0]["title"], "Member")

    def test_short_name_wins_over_the_official_mouthful(self):
        # "House Permanent Select Committee on Intelligence" is correct and
        # unreadable in a card heading.
        self.assertNotIn("Permanent Select",
                         ld.committee_block("Josh Gottheimer", self.DATA)["committees"][0]["name"])

    def test_no_seats_renders_nothing(self):
        # A seatless sitting member, an executive filer and an unknown name
        # each produce no block: the page omits the heading rather than
        # showing an empty one.
        for name in ("Nancy Pelosi", "Donald J. Trump", "Nobody At All"):
            self.assertIsNone(ld.committee_block(name, self.DATA), name)

    def test_missing_file_is_not_an_error(self):
        self.assertIsNone(ld.committee_block("Josh Gottheimer", None))
        self.assertIsNone(ld.committee_block("Josh Gottheimer", {"members": {}}))

    def test_payload_carries_the_block(self):
        trades = [{"member": "Josh Gottheimer", "ticker": "NVDA", "type": "buy",
                   "amount_lo": 1001, "amount_hi": 15000, "tx_date": "2026-06-01",
                   "filing_date": "2026-06-20", "chamber": "house", "state": "NJ",
                   "id": "x", "asset": "NVIDIA"}]
        p = ld.member_payload("Josh Gottheimer", trades, {}, "2026-08-01",
                              committees=self.DATA)
        self.assertEqual(p["committees"]["committees"][0]["name"],
                         "House Intelligence")

    def test_payload_without_committee_data_still_builds(self):
        p = ld.member_payload("Josh Gottheimer", [], {}, "2026-08-01")
        self.assertIsNone(p["committees"])


class TestCommitteeOverlap(unittest.TestCase):
    """The seat beside the trade — two public facts, and never a third claim."""

    DATA = {"members": {
        "Josh Gottheimer": {"reason": "assigned", "committees": [
            {"id": "HSBA", "name": "House Committee on Financial Services",
             "shortName": "House Financial Services", "url": None,
             "title": None, "subcommittees": []},
            {"id": "HSSM", "name": "House Committee on Small Business",
             "shortName": "House Small Business", "url": None,
             "title": None, "subcommittees": []}]},
    }}

    SECTORS = {
        "sectors": {"finance": "Banks & financial services",
                    "tech": "Technology & semiconductors"},
        "committees": {"HSBA": ["finance"]},
        "tickers": {"JPM": "finance", "GS": "finance", "NVDA": "tech"},
    }

    def trades(self, *tickers):
        return [{"member": "Josh Gottheimer", "ticker": t} for t in tickers]

    def test_overlap_lists_only_the_overseen_industry(self):
        b = ld.committee_block("Josh Gottheimer", self.DATA,
                               self.trades("JPM", "JPM", "GS", "NVDA"),
                               self.SECTORS)
        self.assertEqual(len(b["overlap"]), 1)
        row = b["overlap"][0]
        self.assertEqual(row["label"], "Banks & financial services")
        self.assertEqual(row["committees"], ["House Financial Services"])
        self.assertEqual(row["trades"], 3)
        self.assertEqual(row["symbols"], 2)
        self.assertEqual([t["ticker"] for t in row["tickers"]], ["JPM", "GS"])

    def test_coverage_counts_distinct_symbols_not_trades(self):
        b = ld.committee_block("Josh Gottheimer", self.DATA,
                               self.trades("JPM", "JPM", "GS", "NVDA", "ZZZZ"),
                               self.SECTORS)
        # 4 symbols we classify (JPM, GS, NVDA) out of 4 disclosed — ZZZZ is
        # unclassified, and the page says so instead of implying no overlap.
        self.assertEqual(b["coverage"], {"classified": 3, "total": 4})

    def test_no_traded_symbol_in_the_sector_shows_nothing(self):
        b = ld.committee_block("Josh Gottheimer", self.DATA,
                               self.trades("NVDA"), self.SECTORS)
        self.assertNotIn("overlap", b)
        self.assertNotIn("coverage", b)
        self.assertEqual(len(b["committees"]), 2)

    def test_seats_sharing_a_sector_produce_one_row(self):
        data = {"members": {"A B": {"reason": "assigned", "committees": [
            {"id": "SSHR", "shortName": "Senate HELP", "subcommittees": []},
            {"id": "SSVA", "shortName": "Senate Veterans", "subcommittees": []},
        ]}}}
        sd = {"sectors": {"health": "Health care & pharma"},
              "committees": {"SSHR": ["health"], "SSVA": ["health"]},
              "tickers": {"LLY": "health"}}
        b = ld.committee_block("A B", data, [{"ticker": "LLY"}], sd)
        self.assertEqual(len(b["overlap"]), 1)
        self.assertEqual(b["overlap"][0]["committees"],
                         ["Senate HELP", "Senate Veterans"])

    def test_missing_sector_maps_leave_the_seats_untouched(self):
        b = ld.committee_block("Josh Gottheimer", self.DATA,
                               self.trades("JPM"), None)
        self.assertNotIn("overlap", b)
        self.assertEqual(b["committees"][0]["name"], "House Financial Services")

    def test_payload_carries_the_overlap(self):
        trades = [{"member": "Josh Gottheimer", "ticker": "JPM", "type": "buy",
                   "amount_lo": 1001, "amount_hi": 15000, "tx_date": "2026-06-01",
                   "filing_date": "2026-06-20", "chamber": "house", "state": "NJ",
                   "id": "x", "asset": "JPMorgan"}]
        p = ld.member_payload("Josh Gottheimer", trades, {}, "2026-08-01",
                              committees=self.DATA, sector_data=self.SECTORS)
        self.assertEqual(p["committees"]["overlap"][0]["sector"], "finance")


class TestFeaturedMemberSet(unittest.TestCase):
    def test_mcguire_earns_a_page(self):
        self.assertIn("John J. McGuire III", ld.MEMBER_PAGE_NAMES)

    def test_every_page_name_is_unique(self):
        self.assertEqual(len(set(ld.MEMBER_PAGE_NAMES)), len(ld.MEMBER_PAGE_NAMES))


def OPT(ticker="AMZN", type="buy", strike=120.0, exp="2027-01-15",
        tx="2025-12-30", lo=100001, hi=250000, contracts=20):
    return {"member": "Nancy Pelosi", "ticker": ticker, "type": type,
            "asset": f"{ticker} - Common Stock", "asset_type": "Option",
            "amount_lo": lo, "amount_hi": hi, "tx_date": tx,
            "filing_date": "2026-01-23", "chamber": "house",
            "filing_id": "f1", "id": f"{ticker}-{strike}-{exp}",
            "option": {"type": "call", "strike": strike,
                       "expiration": exp, "contracts": contracts}}


def SNAP(stocks=(), year=2025):
    return {"available": True, "report_year": year,
            "filing_date": f"{year + 1}-05-15", "stocks": list(stocks)}


class TestRolledOptions(unittest.TestCase):
    """The live-options half of the roll-forward.

    An option bought in the days BEFORE the snapshot date belongs to the
    annual report; when that report's parser misses it, the position used to
    exist in no path at all. Pelosi's Jan-2027 calls were bought 2025-12-30
    against a 2025-12-31 snapshot, so AMZN, GOOGL and NVDA vanished from her
    page while AAPL survived only because the parser caught that one.
    """

    TODAY = "2026-08-24"

    def roll(self, trades, snap=None):
        return ld.rolled_holdings(trades, snap or SNAP(), self.TODAY)

    def test_buy_before_the_snapshot_is_recovered(self):
        out = self.roll([OPT(tx="2025-12-30")])   # snapshot date 2025-12-31
        self.assertEqual([o["ticker"] for o in out["options"]], ["AMZN"])

    def test_snapshot_and_trade_collapse_to_one_entry(self):
        snap_opt = {"ticker": "AAPL", "asset_type": "Option",
                    "amount_lo": 250001, "amount_hi": 500000,
                    "option": {"type": "call", "strike": 100.0,
                               "expiration": "2027-01-15"}}
        out = self.roll([OPT(ticker="AAPL", strike=100.0)],
                        SNAP(stocks=[snap_opt]))
        self.assertEqual(len(out["options"]), 1)

    def test_expired_options_stay_out(self):
        out = self.roll([OPT(exp="2026-01-16")])  # expired before TODAY
        self.assertEqual(out["options"], [])

    def test_a_disclosed_sale_closes_the_position(self):
        out = self.roll([OPT(), OPT(type="sell")])
        self.assertEqual(out["options"], [])

    def test_a_sale_of_a_different_contract_leaves_it_alone(self):
        out = self.roll([OPT(strike=120.0), OPT(strike=150.0, type="sell")])
        self.assertEqual([o["strike"] for o in out["options"]], [120.0])

    def test_options_never_enter_the_stock_list(self):
        out = self.roll([OPT()])
        self.assertEqual(out["stocks"], [])

    def test_no_annual_baseline_means_no_estimate(self):
        out = ld.rolled_holdings([OPT()], {"available": False}, self.TODAY)
        self.assertEqual((out["stocks"], out["options"]), ([], []))


class TestExerciseRows(unittest.TestCase):
    """An exercise turns an option into shares, and is filed as a STOCK row
    that still names the contract it converted. Routing on the presence of
    that `option` key sent 5,000 real VST shares into the option pass, which
    dropped them for having no expiry left — so the position showed in
    neither list."""

    TODAY = "2026-08-24"

    def exercise(self, ticker="VST", lo=100001, hi=250000):
        return {"member": "Nancy Pelosi", "ticker": ticker, "type": "buy",
                "asset": "Vistra Corp. Common Stock", "asset_type": "Stock",
                "amount_lo": lo, "amount_hi": hi, "tx_date": "2026-01-16",
                "filing_date": "2026-01-23", "chamber": "house",
                "filing_id": "f9", "id": "ex1",
                "comment": ("Exercised 50 call options purchased 1/14/25 "
                            "(5,000 shares) at a strike price of $50."),
                "option": {"type": "call", "strike": 50.0}}

    def test_exercise_lands_in_stocks_not_options(self):
        out = ld.rolled_holdings([self.exercise()], SNAP(), self.TODAY)
        self.assertEqual([s["ticker"] for s in out["stocks"]], ["VST"])
        self.assertEqual(out["options"], [])

    def test_exercise_uses_its_own_bracket_midpoint(self):
        out = ld.rolled_holdings([self.exercise()], SNAP(), self.TODAY)
        self.assertAlmostEqual(out["stocks"][0]["est"], 175000.5)

    def test_a_real_option_row_still_routes_to_options(self):
        out = ld.rolled_holdings([OPT()], SNAP(), self.TODAY)
        self.assertEqual(out["stocks"], [])
        self.assertEqual(len(out["options"]), 1)

    def test_capital_call_is_not_an_option(self):
        # The free-text parser attaches {"type": "call"} to a hedge-fund
        # "Capital call of $3,723.39". It is not an option, and with no
        # ticker it must not reach either list.
        row = {"member": "Nancy Pelosi", "ticker": None, "type": "buy",
               "asset": "Some Fund LP", "asset_type": "HN",
               "amount_lo": 1001, "amount_hi": 15000,
               "tx_date": "2026-07-22", "filing_date": "2026-07-30",
               "chamber": "house", "id": "cc1",
               "comment": "Capital call of $3,723.39",
               "option": {"type": "call"}}
        out = ld.rolled_holdings([row], SNAP(), self.TODAY)
        self.assertEqual((out["stocks"], out["options"]), ([], []))


class TestExerciseClosesTheContract(unittest.TestCase):
    """An exercise both adds shares and closes the contract it consumed.

    Until expiry passed, an exercised contract stayed listed, so one
    exercised early counted twice — as the option and as the stock it became.
    Four of Pelosi's exercises sit on tickers that also carry a live contract.
    """

    TODAY = "2026-08-24"

    def ex(self, ticker="AMZN", strike=120.0, bought="12/30/25"):
        return {"member": "Nancy Pelosi", "ticker": ticker, "type": "buy",
                "asset": f"{ticker} Common Stock", "asset_type": "Stock",
                "amount_lo": 100001, "amount_hi": 250000,
                "tx_date": "2026-02-01", "filing_date": "2026-02-10",
                "chamber": "house", "id": "e1",
                "comment": (f"Exercised 20 call options purchased {bought} "
                            f"(2,000 shares) at a strike price of ${strike:.0f}."),
                "option": {"type": "call", "strike": strike}}

    def test_exercise_removes_the_contract_it_names(self):
        out = ld.rolled_holdings([OPT(), self.ex()], SNAP(), self.TODAY)
        self.assertEqual(out["options"], [])
        self.assertEqual([s["ticker"] for s in out["stocks"]], ["AMZN"])

    def test_same_ticker_same_strike_different_purchase_survives(self):
        # Pelosi's real case: a GOOGL $150 call bought 2025-12-30 is LIVE
        # while a GOOGL $150 call bought 2025-01-14 was exercised. Closing by
        # ticker and strike deleted the live one.
        out = ld.rolled_holdings(
            [OPT(ticker="GOOGL", strike=150.0, tx="2025-12-30"),
             self.ex(ticker="GOOGL", strike=150.0, bought="1/14/25")],
            SNAP(), self.TODAY)
        self.assertEqual([o["ticker"] for o in out["options"]], ["GOOGL"])

    def test_a_different_ticker_survives(self):
        out = ld.rolled_holdings([OPT(ticker="AMZN"), self.ex(ticker="GOOGL")],
                                 SNAP(), self.TODAY)
        self.assertEqual([o["ticker"] for o in out["options"]], ["AMZN"])

    def test_two_purchase_dates_both_close(self):
        out = ld.rolled_holdings(
            [OPT(tx="2024-02-12"), OPT(tx="2024-02-21", strike=200.0),
             self.ex(bought="2/12/24 & 2/21/24")], SNAP(), self.TODAY)
        self.assertEqual(out["options"], [])

    def test_an_unparseable_exercise_closes_nothing(self):
        bad = dict(self.ex(), comment="Exercised some options.")
        out = ld.rolled_holdings([OPT(), bad], SNAP(), self.TODAY)
        self.assertEqual(len(out["options"]), 1)

    def test_a_plain_stock_buy_closes_nothing(self):
        buy = dict(self.ex(), comment="Bought shares.", option=None)
        out = ld.rolled_holdings([OPT(), buy], SNAP(), self.TODAY)
        self.assertEqual(len(out["options"]), 1)


class TestContractShares(unittest.TestCase):
    """One contract is 100 shares — stated, never used to value a position."""

    def payload(self, trades):
        return ld.member_payload(
            "Nancy Pelosi", trades,
            {"Nancy Pelosi": SNAP()}, today_iso="2026-08-24")

    def test_shares_are_contracts_times_one_hundred(self):
        o = self.payload([OPT(contracts=20)])["holdings"]["options"][0]
        self.assertEqual((o["contracts"], o["shares"]), (20, 2000))

    def test_no_contract_count_means_no_share_figure(self):
        t = OPT()
        t["option"].pop("contracts")
        o = self.payload([t])["holdings"]["options"][0]
        self.assertIsNone(o["contracts"])
        self.assertIsNone(o["shares"])
