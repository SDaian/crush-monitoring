"""Offline tests for congress.senate parsers (fixtures, no network)."""

import json
import unittest
from pathlib import Path

from congress.senate import (
    EfdError,
    SenateFilingRef,
    parse_ptr_html,
    parse_search_rows,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _ref(**kw):
    base = dict(
        filing_id="abcd1234-0000-4e0a-9d2b-1111abcd5678",
        name="Thomas H Tuberville",
        filed_date="2026-06-15",
        url=(
            "https://efdsearch.senate.gov/search/view/ptr/"
            "abcd1234-0000-4e0a-9d2b-1111abcd5678/"
        ),
        is_paper=False,
        title="Periodic Transaction Report for 06/10/2026",
    )
    base.update(kw)
    return SenateFilingRef(**base)


class TestSearchRows(unittest.TestCase):
    def setUp(self):
        payload = json.loads(
            (FIXTURES / "senate_search_response.json").read_text()
        )
        self.refs = parse_search_rows(payload)

    def test_all_rows_parsed(self):
        self.assertEqual(len(self.refs), 3)

    def test_electronic_ptr_fields(self):
        ref = self.refs[0]
        self.assertEqual(ref.filing_id, "abcd1234-0000-4e0a-9d2b-1111abcd5678")
        self.assertEqual(ref.name, "Thomas H Tuberville")
        self.assertEqual(ref.filed_date, "2026-06-15")
        self.assertTrue(ref.url.startswith("https://efdsearch.senate.gov/"))
        self.assertFalse(ref.is_paper)

    def test_amendment_title_kept(self):
        self.assertIn("(Amendment)", self.refs[1].title)

    def test_paper_filing_detected(self):
        self.assertTrue(self.refs[2].is_paper)

    def test_missing_data_key_raises(self):
        with self.assertRaises(EfdError):
            parse_search_rows({"recordsTotal": 0})


class TestPtrHtml(unittest.TestCase):
    def setUp(self):
        html = (FIXTURES / "senate_ptr_sample.html").read_text()
        self.trades = parse_ptr_html(html, _ref())

    def test_row_count_and_ids(self):
        self.assertEqual(len(self.trades), 4)
        self.assertEqual(
            self.trades[0].id,
            "senate:abcd1234-0000-4e0a-9d2b-1111abcd5678:0",
        )

    def test_owners_mapped(self):
        self.assertEqual(
            [t.owner for t in self.trades], [None, "SP", "JT", "DC"]
        )

    def test_types_and_partial(self):
        self.assertEqual(
            [(t.type, t.partial) for t in self.trades],
            [("buy", False), ("sell", True), ("sell", False),
             ("exchange", False)],
        )

    def test_ticker_link_text_and_placeholder(self):
        self.assertEqual(self.trades[0].ticker, "MSFT")
        self.assertIsNone(self.trades[2].ticker)  # "--"
        self.assertEqual(self.trades[3].ticker, "VOO")

    def test_amount_with_wrapped_whitespace(self):
        t = self.trades[1]
        self.assertEqual((t.amount_lo, t.amount_hi), (50001, 100000))
        self.assertEqual(t.amount_label, "$50,001 - $100,000")

    def test_dates_and_asset_fields(self):
        t = self.trades[0]
        self.assertEqual(t.tx_date, "2026-05-12")
        self.assertEqual(t.filing_date, "2026-06-15")
        self.assertEqual(t.asset, "Microsoft Corporation")
        self.assertEqual(t.asset_type, "Stock")
        self.assertEqual(t.chamber, "senate")

    def test_entity_decoded(self):
        self.assertEqual(self.trades[3].asset, "Vanguard S&P 500 ETF")

    def test_no_table_raises(self):
        with self.assertRaises(EfdError):
            parse_ptr_html("<html><body><p>nothing</p></body></html>", _ref())


if __name__ == "__main__":
    unittest.main()
