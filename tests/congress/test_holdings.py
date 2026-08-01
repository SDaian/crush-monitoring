"""Offline tests for congress.holdings (annual-report holdings parsers)."""

import unittest
from pathlib import Path

from congress import holdings
from congress.holdings import (
    Holding,
    is_stock,
    normalize_asset_type,
    parse_house_annual_assets,
    parse_senate_annual_assets,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestSenateAnnualAssets(unittest.TestCase):
    def setUp(self):
        html = (FIXTURES / "senate_annual_sample.html").read_text(encoding="utf-8")
        self.h = parse_senate_annual_assets(
            html, member="Tommy Tuberville",
            source_url="https://efdsearch.senate.gov/search/view/annual/x/",
            filing_date="2025-05-15", report_year=2024,
        )

    def test_wrapper_rows_skipped(self):
        # The annuity + IRA "account" rows have value "--" → not holdings.
        # 9 asset rows, 2 are wrappers → 7 real holdings.
        self.assertEqual(len(self.h), 7)
        self.assertTrue(all(isinstance(x, Holding) for x in self.h))

    def test_ticker_prefix_split(self):
        goog = next(x for x in self.h if x.ticker == "GOOGL")
        self.assertEqual(goog.asset, "Alphabet Inc.")
        self.assertEqual(goog.asset_type, "Stock")
        self.assertEqual((goog.value_lo, goog.value_hi), (100_001, 250_000))

    def test_stock_vs_etf_classification(self):
        stocks = [x for x in self.h if is_stock(x)]
        self.assertEqual(
            sorted(x.ticker for x in stocks), ["AAPL", "C", "GOOGL", "NUE"]
        )
        qqq = next(x for x in self.h if x.ticker == "QQQ")
        self.assertEqual(qqq.asset_type, "ETF")  # not counted as a stock

    def test_owner_normalized(self):
        nue = next(x for x in self.h if x.ticker == "NUE")
        self.assertEqual(nue.owner, "JT")
        aapl = next(x for x in self.h if x.ticker == "AAPL")
        self.assertIsNone(aapl.owner)  # "Self" → None
        qqq = next(x for x in self.h if x.ticker == "QQQ")
        self.assertEqual(qqq.owner, "SP")

    def test_no_transaction_table_picked(self):
        # Only the assets table is parsed; the "Who Was Paid" table is ignored.
        self.assertFalse(any("US Senate" in x.asset for x in self.h))

    def test_to_dict_shape(self):
        d = self.h[0].to_dict()
        self.assertEqual(set(d), {
            "member", "chamber", "ticker", "asset", "asset_type",
            "value_lo", "value_hi", "value_label", "owner",
        })


class TestHouseAnnualAssets(unittest.TestCase):
    def setUp(self):
        text = (FIXTURES / "house_annual_sample_text.txt").read_text(encoding="utf-8")
        self.h = parse_house_annual_assets(
            text, member="Nancy Pelosi",
            source_url="https://disclosures-clerk.house.gov/x.pdf",
            filing_date="2026-05-15", report_year=2025,
        )

    def test_stocks_and_options_kept(self):
        # [OL] partnerships and [BA] bank accounts are excluded; stocks AND
        # options ([ST]/[OP]) are kept.
        stocks = [x for x in self.h if x.asset_type == "Stock"]
        options = [x for x in self.h if x.asset_type == "Option"]
        self.assertEqual(
            sorted(x.ticker for x in stocks),
            ["AAPL", "AMZN", "AVGO", "AXP", "GOOGL", "NVDA", "SQ", "T"],
        )
        # GOOGL/AMZN/AAPL are also held as options (AVGO option row has no value).
        self.assertEqual(sorted(x.ticker for x in options), ["AAPL", "AMZN", "GOOGL"])
        self.assertTrue(all(x.chamber == "house" for x in self.h))

    def test_option_detail_parsed(self):
        opt = next(x for x in self.h if x.asset_type == "Option" and x.ticker == "GOOGL")
        # code wrapped onto the next line ("[OP] $5,000,000"); value from lo.
        self.assertEqual((opt.value_lo, opt.value_hi), (1_000_001, 5_000_000))
        self.assertEqual(opt.option, {
            "type": "call", "strike": 150.0,
            "expiration": "2026-01-16", "contracts": 50,
        })
        aapl_opt = next(x for x in self.h if x.asset_type == "Option" and x.ticker == "AAPL")
        self.assertEqual(aapl_opt.option["strike"], 100.0)
        self.assertEqual(aapl_opt.option["expiration"], "2027-01-15")

    def test_value_bracket_resolved_from_lo(self):
        # Upper bound wraps to the next line; resolved from the lower bound.
        goog = next(x for x in self.h if x.ticker == "GOOGL" and x.asset_type == "Stock")
        self.assertEqual((goog.value_lo, goog.value_hi), (5_000_001, 25_000_000))
        self.assertEqual(goog.value_label, "$5,000,001 - $25,000,000")
        att = next(x for x in self.h if x.ticker == "T")
        self.assertEqual((att.value_lo, att.value_hi), (100_001, 250_000))

    def test_income_figure_not_mistaken_for_value(self):
        # AXP row: "$1,000,001 - Dividends $15,001 - $50,000" — value is the
        # first bracket ($1,000,001 - $5,000,000), not the income $15,001.
        axp = next(x for x in self.h if x.ticker == "AXP")
        self.assertEqual((axp.value_lo, axp.value_hi), (1_000_001, 5_000_000))

    def test_owner_optional(self):
        nvda = next(x for x in self.h if x.ticker == "NVDA")
        self.assertIsNone(nvda.owner)          # no owner token → self
        aapl = next(x for x in self.h if x.ticker == "AAPL")
        self.assertEqual(aapl.owner, "SP")

    def test_class_suffix_trimmed(self):
        avgo = next(x for x in self.h if x.ticker == "AVGO")
        self.assertEqual(avgo.asset, "Broadcom Inc.")
        sq = next(x for x in self.h if x.ticker == "SQ")
        self.assertEqual(sq.asset, "Block, Inc.")


class TestAssetTypeNormalization(unittest.TestCase):
    def test_classes(self):
        self.assertEqual(normalize_asset_type("Corporate SecuritiesStock"), "Stock")
        self.assertEqual(
            normalize_asset_type("Mutual FundsExchange Traded Fund/Note"), "ETF")
        self.assertEqual(normalize_asset_type("Mutual FundsMutual Fund"), "Fund")
        self.assertEqual(normalize_asset_type("Bank Deposit"), "Other")


if __name__ == "__main__":
    unittest.main()


class TestHoldingsCoverageReason(unittest.TestCase):
    """Why a member has no holdings — the distinction that drives triage."""

    def test_scanned_report_has_no_text(self):
        self.assertEqual(
            holdings.classify(has_text=False, parsed=0, kept=0),
            holdings.REASON_SCANNED,
        )

    def test_text_but_nothing_parsed_is_a_parser_gap(self):
        self.assertEqual(
            holdings.classify(has_text=True, parsed=0, kept=0),
            holdings.REASON_NO_ASSETS,
        )

    def test_funds_only_is_correct_data_not_a_gap(self):
        # Parsed 12 assets, none of them individual equities. This member
        # genuinely holds no stocks; flagging it for review would be wrong.
        reason = holdings.classify(has_text=True, parsed=12, kept=0)
        self.assertEqual(reason, holdings.REASON_NO_EQUITIES)
        self.assertNotIn(reason, holdings.NEEDS_REVIEW)

    def test_parsed_holdings_are_ok(self):
        reason = holdings.classify(has_text=True, parsed=12, kept=5)
        self.assertEqual(reason, holdings.REASON_OK)
        self.assertNotIn(reason, holdings.NEEDS_REVIEW)

    def test_every_reason_has_human_text(self):
        for r in holdings.NEEDS_REVIEW:
            self.assertIn(r, holdings.REASON_TEXT)
