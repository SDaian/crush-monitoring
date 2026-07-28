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
        self.assertEqual(set(r), {"member", "chamber", "district", "ticker",
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
        self.assertEqual(p["tradesShown"], ld.MEMBER_TRADE_CAP)
        self.assertEqual(len(p["trades"]), ld.MEMBER_TRADE_CAP)
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
        uni = ld.select_ticker_pages(trades, minimum=25)
        self.assertEqual(uni, ["NVDA"])
        self.assertNotIn("THIN", uni)

    def test_universe_ranked_and_capped(self):
        trades = ([MT(ticker="AAA") for _ in range(30)]
                  + [MT(ticker="BBB") for _ in range(40)])
        self.assertEqual(ld.select_ticker_pages(trades, minimum=5), ["BBB", "AAA"])
        self.assertEqual(ld.select_ticker_pages(trades, count=1, minimum=5), ["BBB"])

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
