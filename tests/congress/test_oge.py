"""Offline tests for congress.oge (OGE 278-T ingester) — fixtures, no network."""

import unittest
from collections import Counter

from congress import oge
from pathlib import Path

from congress.oge import (
    OgeFiling,
    filing_url,
    parse_seed,
    parse_transactions,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestSeedFilings(unittest.TestCase):
    def setUp(self):
        seed = {
            "filer": "Donald J. Trump",
            "filings": [
                {
                    "unid": "18353894FE440B3685258D430031A337",
                    "filename": "Donald J. Trump 10.20.2025 278-T (2).pdf",
                },
                {  # explicit date overrides / supplements the filename
                    "unid": "ABCDEF0123456789ABCDEF0123456789",
                    "filename": "Donald J. Trump 278-T.pdf",
                    "date": "2026-02-26",
                },
            ],
        }
        self.docs = parse_seed(seed)

    def test_builds_one_ref_per_filing(self):
        self.assertEqual(len(self.docs), 2)
        self.assertIsInstance(self.docs[0], OgeFiling)
        self.assertEqual(self.docs[0].unid, "18353894FE440B3685258D430031A337")

    def test_filing_date_from_filename(self):
        self.assertEqual(self.docs[0].filing_date, "2025-10-20")

    def test_explicit_date_used_when_filename_has_none(self):
        self.assertEqual(self.docs[1].filing_date, "2026-02-26")

    def test_url_is_encoded_and_absolute(self):
        url = self.docs[0].url
        self.assertTrue(url.startswith("https://extapps2.oge.gov/201/Presiden.nsf/"))
        self.assertIn("18353894FE440B3685258D430031A337/$FILE/", url)
        self.assertNotIn(" ", url)  # spaces in the filename are percent-encoded
        self.assertIn("278-T", url.replace("%20", " "))

    def test_filing_url_helper(self):
        url = filing_url("DEADBEEF", "a b.pdf")
        self.assertEqual(
            url,
            "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/DEADBEEF/$FILE/a%20b.pdf",
        )

    def test_committed_seed_parses(self):
        # The real committed seed must load and produce valid refs.
        from congress.oge import load_seed
        docs = load_seed()
        self.assertTrue(docs)
        for d in docs:
            self.assertTrue(d.unid and d.filename and d.filing_date and d.url)


class TestTransactionParsing(unittest.TestCase):
    def setUp(self):
        text = (FIXTURES / "oge_278t_sample_text.txt").read_text(encoding="utf-8")
        self.trades = parse_transactions(
            text,
            unid="18353894FE440B3685258D430031A337",
            source_url="https://extapps2.oge.gov/x/y.pdf",
            filing_date="2025-10-20",
        )

    def test_all_57_rows_parsed(self):
        self.assertEqual(len(self.trades), 57)

    def test_all_purchases_no_ticker(self):
        self.assertEqual(Counter(t.type for t in self.trades), Counter({"buy": 57}))
        self.assertTrue(all(t.ticker is None for t in self.trades))
        self.assertTrue(all(t.chamber == "executive" for t in self.trades))
        self.assertTrue(all(t.member == "Donald J. Trump" for t in self.trades))
        # 56 debt rows; the SPDR High Yield Bond ETF is a tickered fund, so
        # it classifies as Stock (with the ticker refused, not guessed) —
        # a bond ETF trades as shares, whatever it holds.
        self.assertEqual(
            Counter(t.asset_type for t in self.trades),
            Counter({"bond": 56, "Stock": 1}))

    def test_ids_are_row_indexed(self):
        self.assertEqual(
            self.trades[0].id, "executive:18353894FE440B3685258D430031A337:1"
        )
        self.assertEqual(self.trades[0].filing_id, "18353894FE440B3685258D430031A337")

    def test_first_row_values(self):
        t = self.trades[0]
        self.assertTrue(t.asset.startswith("OCCIDENTAL PETE"))
        self.assertEqual(t.tx_date, "2025-09-24")  # OCR "9/24/202S" repaired
        self.assertEqual((t.amount_lo, t.amount_hi), (500_001, 1_000_000))

    def test_ocr_digit_repair_in_amount(self):
        # Row 4's amount was OCR'd "$50D,001 -$1,000,000"; snapped to a bracket.
        t = self.trades[3]
        self.assertTrue(t.asset.startswith("GENERAL MTRS"))
        self.assertEqual(t.amount_label, "$500,001 - $1,000,000")

    def test_bullet_separator_amount(self):
        # Some rows use a "•" bullet instead of a dash between the bracket ends.
        bulleted = next(t for t in self.trades if t.asset.startswith("UTAH WTR"))
        self.assertEqual((bulleted.amount_lo, bulleted.amount_hi), (15_001, 50_000))

    def test_brackets_all_canonical(self):
        from congress.normalize import AMOUNT_BRACKETS

        valid = {(lo, hi) for lo, hi in AMOUNT_BRACKETS.values()}
        for t in self.trades:
            self.assertIn((t.amount_lo, t.amount_hi), valid)

    def test_etf_row_present(self):
        etf = next(t for t in self.trades if "SPDR" in t.asset)
        self.assertEqual((etf.amount_lo, etf.amount_hi), (1_000_001, 5_000_000))
        self.assertEqual(etf.tx_date, "2025-09-19")

    def test_noise_lines_skipped(self):
        # "OGE RECEIVED: 10/28/2025" and header/footer lines are not trades.
        self.assertFalse(any("OGE RECEIVED" in t.asset for t in self.trades))
        self.assertFalse(any("Transactions" == t.asset for t in self.trades))


if __name__ == "__main__":
    unittest.main()


class TestEquityRows(unittest.TestCase):
    """The June-2026 filing shape: stocks and ETFs beside the bonds."""

    TEXT = """\
199 CINTAS CORP purchase 6/18/2026 Yes $1,000,001 - $5,000,000
206 BOEING PANY purchase 6/18/2026 Yes $250,001 - $500,000
216 SCHWAB CHARLES CORP PERP SUB 4.0000% purchase 6/1/2026 Yes $100,001 - $250,000
221 QUALM INC purchase 6/18/2026 Yes $100,001 - $250,000
"""
    INDEX = {"CINTAS": "CTAS", "BOEING": "BA"}

    def rows(self):
        return oge.parse_transactions(
            self.TEXT, unid="U1", source_url="u", filing_date="2026-08-22",
            name_index=self.INDEX)

    def test_equities_resolve_and_ship_as_stock(self):
        by = {t.asset: t for t in self.rows()}
        self.assertEqual(by["CINTAS CORP"].ticker, "CTAS")
        self.assertEqual(by["CINTAS CORP"].asset_type, "Stock")
        # OCR garble resolves through normalize_name, not a literal match.
        self.assertEqual(by["BOEING PANY"].ticker, "BA")

    def test_bond_rows_keep_the_old_contract(self):
        bond = [t for t in self.rows() if "SCHWAB" in t.asset][0]
        self.assertIsNone(bond.ticker)
        self.assertEqual(bond.asset_type, "bond")

    def test_curated_override_beats_an_empty_index(self):
        # QUALM INC is in tickermatch.OVERRIDES; no index entry needed.
        q = [t for t in self.rows() if "QUALM" in t.asset][0]
        self.assertEqual(q.ticker, "QCOM")

    def test_unresolved_equity_is_refused_not_guessed(self):
        rows = oge.parse_transactions(
            "1 MYSTERY NEWCO INC purchase 6/18/2026 Yes $1,001 - $15,000",
            unid="U2", source_url="u", filing_date="2026-08-22",
            name_index={})
        self.assertEqual(rows[0].asset_type, "Stock")
        self.assertIsNone(rows[0].ticker)

    def test_yes_notification_rows_parse(self):
        # Earlier filings said "No"; the June filing says "Yes" on every row.
        self.assertEqual(len(self.rows()), 4)


class TestDateClamp(unittest.TestCase):
    """A 278-T discloses past trades; the filing date bounds the trade date."""

    def one(self, date_token, filing="2026-05-08"):
        rows = oge.parse_transactions(
            f"1 DATADOG INC purchase {date_token} Yes $1,001 - $15,000",
            unid="U", source_url="u", filing_date=filing, name_index={})
        return rows[0].tx_date

    def test_ocr_year_overshoot_walks_back(self):
        # "202B" repairs to 2028; a March-2028 trade cannot sit in a
        # May-2026 filing, so the year walks back to the possible one.
        self.assertEqual(self.one("3/23/202B"), "2026-03-23")

    def test_late_year_trade_in_an_early_year_filing(self):
        # A December trade filed the next January crosses a year boundary.
        self.assertEqual(self.one("12/30/2026", filing="2026-01-14"),
                         "2025-12-30")

    def test_a_possible_date_is_untouched(self):
        self.assertEqual(self.one("3/23/2026"), "2026-03-23")
