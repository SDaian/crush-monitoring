"""Offline tests for congress.normalize (pure stdlib, no network)."""

import unittest
from datetime import date

from congress.normalize import (
    AMOUNT_BRACKETS,
    Roster,
    Trade,
    canonical_name,
    enrich,
    load_featured,
    parse_amount,
    parse_date,
    parse_tx_type,
    prune_cutoff,
    trade_sort_key,
)


class TestAmounts(unittest.TestCase):
    def test_all_legal_brackets_round_trip(self):
        for label, (lo, hi) in AMOUNT_BRACKETS.items():
            got_lo, got_hi, got_label = parse_amount(label)
            self.assertEqual((got_lo, got_hi), (lo, hi), label)
            self.assertEqual(got_label, label)

    def test_dash_and_whitespace_variants(self):
        self.assertEqual(parse_amount("$15,001 – $50,000"),
                         (15001, 50000, "$15,001 - $50,000"))
        self.assertEqual(parse_amount("  $1,001-$15,000 "),
                         (1001, 15000, "$1,001 - $15,000"))

    def test_open_top_bracket_variants(self):
        self.assertEqual(parse_amount("Over $50,000,000"),
                         (50000000, None, "$50,000,000 +"))
        self.assertEqual(parse_amount("$50,000,001 +"),
                         (50000001, None, "$50,000,001 +"))

    def test_or_less_bracket(self):
        self.assertEqual(parse_amount("$15,000 or less"),
                         (0, 15000, "$15,000 or less"))

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            parse_amount("see attachment")


class TestTxTypes(unittest.TestCase):
    def test_house_codes(self):
        self.assertEqual(parse_tx_type("P"), ("buy", False))
        self.assertEqual(parse_tx_type("S"), ("sell", False))
        self.assertEqual(parse_tx_type("S (partial)"), ("sell", True))
        self.assertEqual(parse_tx_type("E"), ("exchange", False))

    def test_senate_labels(self):
        self.assertEqual(parse_tx_type("Purchase"), ("buy", False))
        self.assertEqual(parse_tx_type("Sale (Full)"), ("sell", False))
        self.assertEqual(parse_tx_type("Sale (Partial)"), ("sell", True))
        self.assertEqual(parse_tx_type("Exchange"), ("exchange", False))

    def test_unknown_raises(self):
        with self.assertRaises(ValueError):
            parse_tx_type("Gift")


class TestDates(unittest.TestCase):
    def test_us_format(self):
        self.assertEqual(parse_date("05/14/2026"), "2026-05-14")

    def test_iso_passthrough(self):
        self.assertEqual(parse_date("2026-05-14"), "2026-05-14")

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            parse_date("14 May 2026")


class TestNames(unittest.TestCase):
    def test_last_first_reorder(self):
        self.assertEqual(canonical_name("McCaul, Michael T."),
                         "michael t. mccaul")

    def test_honorific_and_suffix_stripped(self):
        self.assertEqual(canonical_name("Hon. Cleo Fields Jr."), "cleo fields")
        self.assertEqual(canonical_name("Senator Tommy Tuberville"),
                         "tommy tuberville")

    def test_whitespace_collapse(self):
        self.assertEqual(canonical_name("  Nancy   Pelosi "), "nancy pelosi")

    def test_comma_suffix_does_not_hijack_reorder(self):
        # Live eFD regression: ", Jr." must not be read as the first name.
        self.assertEqual(canonical_name("A. Mitchell McConnell, Jr."),
                         "a. mitchell mcconnell")
        self.assertEqual(canonical_name("Fields, Cleo, Jr."), "cleo fields")


class TestRoster(unittest.TestCase):
    def setUp(self):
        self.roster = Roster.load()

    def test_alias_hit(self):
        entry = self.roster.find("McCaul, Michael T.")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["name"], "Michael McCaul")
        self.assertEqual(entry["party"], "R")

    def test_middle_token_fallback(self):
        entry = self.roster.find("David Howard McCormick")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["state"], "PA")

    def test_chamber_mismatch_is_a_miss(self):
        self.assertIsNone(self.roster.find("Nancy Pelosi", chamber="senate"))

    def test_unknown_member_is_none(self):
        self.assertIsNone(self.roster.find("Jane Q. Nobody"))

    def test_featured_all_resolve(self):
        for name in load_featured():
            self.assertIsNotNone(self.roster.find(name), name)


def _trade(**kw):
    base = dict(
        id="house:1:0", chamber="house", member="McCaul, Michael T.",
        ticker="NVDA", asset="NVIDIA Corporation", type="buy",
        tx_date="2026-05-14", filing_date="2026-06-20",
        amount_lo=15001, amount_hi=50000,
        amount_label="$15,001 - $50,000", filing_id="1",
        source_url="https://example.gov/1.pdf",
    )
    base.update(kw)
    return Trade(**base)


class TestEnrich(unittest.TestCase):
    def test_roster_fills_and_renames(self):
        t = enrich(_trade(), Roster.load())
        self.assertEqual(t.member, "Michael McCaul")
        self.assertEqual((t.party, t.state, t.district), ("R", "TX", "TX-10"))

    def test_miss_keeps_scraped_fields(self):
        t = enrich(_trade(member="Jane Q. Nobody", state="WY", district="WY-0"),
                   Roster.load())
        self.assertEqual(t.member, "Jane Q. Nobody")
        self.assertIsNone(t.party)
        self.assertEqual(t.state, "WY")


class TestOrderingAndPruning(unittest.TestCase):
    def test_sort_is_filing_date_desc_then_member(self):
        rows = [
            _trade(id="a", filing_date="2026-06-01", member="Zed").to_dict(),
            _trade(id="b", filing_date="2026-06-20", member="Zed").to_dict(),
            _trade(id="c", filing_date="2026-06-20", member="Abe").to_dict(),
        ]
        rows.sort(key=trade_sort_key)
        self.assertEqual([r["id"] for r in rows], ["c", "b", "a"])

    def test_prune_cutoff_is_jan1_of_previous_year(self):
        self.assertEqual(prune_cutoff(date(2026, 7, 2)), "2025-01-01")


if __name__ == "__main__":
    unittest.main()
