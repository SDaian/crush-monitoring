"""Offline tests for congress.house parsers (fixtures, no network)."""

import importlib.util
import unittest
from pathlib import Path

from congress.house import (
    HouseError,
    HouseFilingRef,
    parse_index,
    parse_ptr_text,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _ref(**kw):
    base = dict(
        doc_id="20026381",
        name="Michael T. McCaul",
        state="TX",
        district="TX-10",
        filing_date="2026-06-20",
        year=2026,
        url=(
            "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/"
            "2026/20026381.pdf"
        ),
    )
    base.update(kw)
    return HouseFilingRef(**base)


class TestIndex(unittest.TestCase):
    def setUp(self):
        text = (FIXTURES / "house_index_sample.txt").read_text()
        self.refs = parse_index(text, 2026)

    def test_only_ptrs_with_docids(self):
        # 7 FilingType=P rows in the fixture, one without a DocID → 6 kept.
        self.assertEqual(len(self.refs), 6)
        self.assertNotIn("Larry Lost", [r.name for r in self.refs])
        self.assertNotIn("Adam Smith", [r.name for r in self.refs])

    def test_fields(self):
        mccaul = self.refs[0]
        self.assertEqual(mccaul.doc_id, "20026381")
        self.assertEqual(mccaul.name, "Michael T. McCaul")
        self.assertEqual((mccaul.state, mccaul.district), ("TX", "TX-10"))
        self.assertEqual(mccaul.filing_date, "2026-06-20")
        self.assertEqual(
            mccaul.url,
            "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/"
            "2026/20026381.pdf",
        )

    def test_at_large_district(self):
        wendy = next(r for r in self.refs if r.name == "Wendy Atlarge")
        self.assertEqual((wendy.state, wendy.district), ("WY", "WY-0"))

    def test_bad_header_raises(self):
        with self.assertRaises(HouseError):
            parse_index("Foo\tBar\n1\t2\n", 2026)


class TestPtrText(unittest.TestCase):
    def setUp(self):
        text = (FIXTURES / "house_ptr_sample_text.txt").read_text()
        self.trades = parse_ptr_text(text, _ref())

    def test_row_count_and_ids(self):
        self.assertEqual(len(self.trades), 4)
        self.assertEqual(self.trades[0].id, "house:20026381:0")

    def test_simple_row(self):
        t = self.trades[0]
        self.assertEqual(t.owner, "SP")
        self.assertEqual(t.ticker, "NVDA")
        self.assertEqual(t.asset, "NVIDIA Corporation - Common Stock")
        self.assertEqual(t.asset_type, "Stock")
        self.assertEqual((t.type, t.partial), ("buy", False))
        self.assertEqual(t.tx_date, "2026-05-14")
        self.assertEqual((t.amount_lo, t.amount_hi), (15001, 50000))

    def test_wrapped_asset_name_and_amount(self):
        t = self.trades[1]
        self.assertEqual(t.owner, "JT")
        self.assertEqual(t.ticker, "ITOT")
        self.assertEqual(
            t.asset, "iShares Core S&P Total U.S. Stock Market ETF"
        )
        self.assertEqual(t.asset_type, "ETF")
        self.assertEqual((t.type, t.partial), ("sell", True))
        self.assertEqual((t.amount_lo, t.amount_hi), (1001, 15000))
        self.assertEqual(t.amount_label, "$1,001 - $15,000")

    def test_self_owned_row(self):
        t = self.trades[2]
        self.assertIsNone(t.owner)
        self.assertEqual(t.ticker, "AAPL")
        self.assertEqual((t.type, t.partial), ("sell", False))
        self.assertEqual((t.amount_lo, t.amount_hi), (100001, 250000))

    def test_no_ticker_asset(self):
        t = self.trades[3]
        self.assertIsNone(t.ticker)
        self.assertEqual(t.asset, "U.S. Treasury Bills")
        self.assertEqual(t.asset_type, "Government Security")
        self.assertEqual(t.type, "buy")

    def test_index_metadata_propagated(self):
        t = self.trades[0]
        self.assertEqual((t.state, t.district), ("TX", "TX-10"))
        self.assertEqual(t.filing_date, "2026-06-20")
        self.assertTrue(t.source_url.endswith("20026381.pdf"))

    def test_unparseable_text_raises(self):
        with self.assertRaises(HouseError):
            parse_ptr_text("PERIODIC TRANSACTION REPORT\nno rows here\n", _ref())


@unittest.skipUnless(
    importlib.util.find_spec("pdfplumber"), "pdfplumber not installed"
)
class TestPdfExtraction(unittest.TestCase):
    def test_short_text_means_scanned(self):
        # Covered properly in the Action environment; here we only assert the
        # module wires up when the dependency is present.
        from congress.house import extract_pdf_text  # noqa: F401


if __name__ == "__main__":
    unittest.main()
