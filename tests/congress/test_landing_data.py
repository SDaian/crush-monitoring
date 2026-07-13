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


if __name__ == "__main__":
    unittest.main()
