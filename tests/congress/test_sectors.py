"""The curated committee→industry and ticker→industry maps."""

import json
import re
import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from congress import sectors

INDEX_PATH = (Path(__file__).resolve().parents[2]
              / "landing" / "src" / "data" / "tickers" / "_index.json")


class TestLoad(unittest.TestCase):
    def test_the_shipped_file_parses(self):
        d = sectors.load()
        self.assertTrue(d["sectors"])
        self.assertTrue(d["committees"])
        self.assertTrue(d["tickers"])

    def test_a_missing_file_costs_the_feature_not_the_build(self):
        with TemporaryDirectory() as tmp:
            d = sectors.load(Path(tmp) / "nope.json")
        self.assertEqual(d, {"sectors": {}, "committees": {}, "tickers": {}})

    def test_broken_json_is_not_an_error(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "sectors.json"
            p.write_text("{ not json", encoding="utf-8")
            self.assertEqual(sectors.load(p)["tickers"], {})


class TestShippedMaps(unittest.TestCase):
    """The file is hand-maintained, so the suite guards its shape."""

    DATA = sectors.load()

    def test_every_committee_maps_to_known_sector_keys(self):
        known = set(self.DATA["sectors"])
        for cid, keys in self.DATA["committees"].items():
            for k in keys:
                self.assertIn(k, known, f"{cid} maps to unknown sector {k}")

    def test_every_ticker_maps_to_a_known_sector_key(self):
        known = set(self.DATA["sectors"])
        for tk, k in self.DATA["tickers"].items():
            self.assertIn(k, known, f"{tk} maps to unknown sector {k}")

    def test_symbols_are_upper_case_and_trimmed(self):
        for tk in self.DATA["tickers"]:
            self.assertEqual(tk, tk.strip().upper(), tk)

    def test_the_broad_committees_stay_unmapped(self):
        # Appropriations, Judiciary and the tax committees touch every
        # industry. Mapping them would flag almost every trade, and a flag
        # that always fires says nothing.
        for cid in ("HSAP", "SSAP", "HSJU", "SSJU", "HSWM", "SSFI", "HSBU"):
            self.assertNotIn(cid, self.DATA["committees"], cid)

    def test_every_industry_classifies_at_least_one_ticker(self):
        # NOT "every industry maps to a committee": six of them deliberately
        # map to none. They exist so every stock page carries a badge, and
        # adding them to a committee would widen the member-page flag.
        used = set(self.DATA["tickers"].values())
        self.assertEqual(used, set(self.DATA["sectors"]))

    def test_no_ticker_is_listed_twice(self):
        # json.loads keeps the LAST duplicate key silently, so a repeated
        # symbol changes the map with no error anywhere.
        raw = sectors.SECTORS_PATH.read_text(encoding="utf-8")
        keys = re.findall(r'^\s*"([A-Z0-9.]+)":\s*"\w+",?$', raw, re.M)
        dupes = [k for k, n in Counter(keys).items() if n > 1]
        self.assertEqual(dupes, [])

    def test_every_ticker_page_carries_an_industry(self):
        # The badge and the /tickers filter both assume full coverage of the
        # generated page set. A new page arriving unclassified must fail here,
        # not ship a blank badge.
        try:
            index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        except OSError:
            self.skipTest("ticker index not generated")
        missing = [t["ticker"] for t in index["tickers"]
                   if not sectors.ticker_sector(t["ticker"], self.DATA)]
        self.assertEqual(missing, [])

    def test_labels_fit_the_industry_select(self):
        # The <select> on /tickers takes its width from its longest option, so
        # a long label pushes the control off a 320px screen. Measured, not
        # guessed: 21 characters plus the " (NN)" count is the fit.
        for key, label in self.DATA["sectors"].items():
            self.assertLessEqual(len(label), 21, f"{key}: {label!r}")

    def test_the_file_declares_that_the_grouping_is_ours(self):
        raw = json.loads(sectors.SECTORS_PATH.read_text(encoding="utf-8"))
        self.assertIn("not an official one", raw["_comment"])


class TestClassify(unittest.TestCase):
    DATA = {"sectors": {"tech": "Technology", "health": "Health"},
            "committees": {"HSSY": ["tech"]},
            "tickers": {"NVDA": "tech", "AMD": "tech", "LLY": "health"}}

    def test_counts_trades_per_symbol_and_distinct_symbols(self):
        g = sectors.classify(
            [{"ticker": "NVDA"}, {"ticker": "NVDA"}, {"ticker": "LLY"},
             {"ticker": "ZZZZ"}, {"ticker": None}], self.DATA)
        self.assertEqual(dict(g["by_sector"]["tech"]), {"NVDA": 2})
        self.assertEqual(g["classified"], 2)
        self.assertEqual(g["total"], 3)

    def test_lower_case_and_padded_symbols_still_match(self):
        g = sectors.classify([{"ticker": " nvda "}], self.DATA)
        self.assertEqual(dict(g["by_sector"]["tech"]), {"NVDA": 1})

    def test_ticker_less_rows_are_ignored_entirely(self):
        # The President's 278-T bond rows carry no ticker.
        g = sectors.classify([{"ticker": ""}, {}], self.DATA)
        self.assertEqual(g, {"by_sector": {}, "classified": 0, "total": 0})


class TestOverlap(unittest.TestCase):
    DATA = {"sectors": {"tech": "Technology", "health": "Health",
                        "energy": "Energy"},
            "committees": {"HSSY": ["tech"], "HSIF": ["energy", "health"]},
            "tickers": {"NVDA": "tech", "LLY": "health", "XOM": "energy"}}

    def rows(self, seats, trades):
        g = sectors.classify(trades, self.DATA)
        return sectors.overlap(seats, g, self.DATA)

    def test_rows_sort_by_trade_count(self):
        seats = [{"id": "HSIF", "name": "Energy & Commerce"}]
        rows = self.rows(seats, [{"ticker": "XOM"}, {"ticker": "LLY"},
                                 {"ticker": "LLY"}])
        self.assertEqual([r["label"] for r in rows], ["Health", "Energy"])

    def test_a_seat_we_map_no_sector_to_yields_nothing(self):
        rows = self.rows([{"id": "HSAP", "name": "Appropriations"}],
                         [{"ticker": "NVDA"}])
        self.assertEqual(rows, [])

    def test_a_sector_with_no_traded_symbol_yields_nothing(self):
        rows = self.rows([{"id": "HSSY", "name": "Science"}],
                         [{"ticker": "LLY"}])
        self.assertEqual(rows, [])

    def test_cap_truncates_and_reports_the_remainder(self):
        data = dict(self.DATA)
        data["tickers"] = {f"T{i}": "tech" for i in range(14)}
        g = sectors.classify([{"ticker": f"T{i}"} for i in range(14)], data)
        rows = sectors.overlap([{"id": "HSSY", "name": "Science"}], g, data,
                               cap=10)
        self.assertEqual(len(rows[0]["tickers"]), 10)
        self.assertEqual(rows[0]["more"], 4)
        self.assertEqual(rows[0]["symbols"], 14)

    def test_a_seat_with_no_name_never_reaches_the_page(self):
        rows = self.rows([{"id": "HSSY"}], [{"ticker": "NVDA"}])
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
