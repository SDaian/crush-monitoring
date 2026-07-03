"""Offline tests for congress.oge (OGE 278-T ingester) — fixtures, no network."""

import unittest
from collections import Counter
from pathlib import Path

from congress.oge import (
    OgeFiling,
    parse_transactions,
    parse_view_documents,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestViewEnumeration(unittest.TestCase):
    def setUp(self):
        xml = (FIXTURES / "oge_pas_index.xml").read_text(encoding="utf-8")
        self.docs = parse_view_documents([xml])

    def test_only_trump_278t_returned(self):
        # Abizaid's annual (other filer) and Trump's annual 278 are excluded;
        # only Trump's 278-T periodic report survives.
        self.assertEqual(len(self.docs), 1)
        doc = self.docs[0]
        self.assertIsInstance(doc, OgeFiling)
        self.assertEqual(doc.unid, "18353894FE440B3685258D430031A337")

    def test_document_fields(self):
        doc = self.docs[0]
        self.assertEqual(doc.filename, "Donald J. Trump 10.20.2025 278-T (2).pdf")
        self.assertEqual(doc.filing_date, "2025-10-20")  # from the filename date
        self.assertEqual(doc.label, "Periodic (10/20/2025)")

    def test_url_is_encoded_and_absolute(self):
        url = self.docs[0].url
        self.assertTrue(url.startswith("https://extapps2.oge.gov/201/Presiden.nsf/"))
        self.assertIn("18353894FE440B3685258D430031A337/$FILE/", url)
        self.assertNotIn(" ", url)  # spaces in the filename are percent-encoded
        self.assertIn("278-T", url.replace("%20", " "))

    def test_category_state_carries_across_pages(self):
        # A filer split across two view responses is still captured: the
        # category row on page 1, its document on page 2.
        xml = (FIXTURES / "oge_pas_index.xml").read_text(encoding="utf-8")
        cat_line = next(
            ln for ln in xml.splitlines() if 'category="true"' in ln and "Trump" in ln
        )
        doc_line = next(ln for ln in xml.splitlines() if "278-T" in ln)
        page1 = f"<viewentries>{cat_line}</viewentries>"
        page2 = f"<viewentries>{doc_line}</viewentries>"
        docs = parse_view_documents([page1, page2])
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].unid, "18353894FE440B3685258D430031A337")


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
        self.assertTrue(all(t.asset_type == "bond" for t in self.trades))

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
