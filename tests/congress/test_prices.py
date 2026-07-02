"""Offline tests for congress.prices (fixtures, no network)."""

import unittest
from pathlib import Path

from congress.prices import (
    PriceSeries,
    buy_return,
    compute_returns,
    distinct_buy_tickers,
    parse_history,
    yahoo_symbol,
)

FIXTURES = Path(__file__).parent / "fixtures"
AAPL = (FIXTURES / "yahoo_aapl.json").read_text()


class TestSymbol(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(yahoo_symbol("AAPL"), "AAPL")

    def test_share_class_dot_becomes_hyphen(self):
        self.assertEqual(yahoo_symbol("BRK.B"), "BRK-B")

    def test_whitespace_and_case(self):
        self.assertEqual(yahoo_symbol(" msft "), "MSFT")


class TestParse(unittest.TestCase):
    def setUp(self):
        self.hist = parse_history(AAPL)

    def test_dates_and_closes(self):
        self.assertEqual(self.hist["2026-05-29"], 192.5)
        self.assertEqual(self.hist["2026-06-02"], 197.4)
        self.assertEqual(len(self.hist), 5)

    def test_unlisted_returns_empty(self):
        # Yahoo's not-found / error / anti-bot bodies all yield no series.
        self.assertEqual(parse_history('{"chart":{"result":null,"error":{"code":"Not Found"}}}'), {})
        self.assertEqual(parse_history("<!DOCTYPE html><html>bot check</html>"), {})
        self.assertEqual(parse_history(""), {})


class TestSeries(unittest.TestCase):
    def setUp(self):
        self.s = PriceSeries(parse_history(AAPL))

    def test_exact_day(self):
        self.assertEqual(self.s.close_on_or_before("2026-05-29"), ("2026-05-29", 192.5))

    def test_weekend_resolves_to_prior_session(self):
        # 2026-05-30/31 is a weekend; a buy dated then uses Friday 05-29.
        self.assertEqual(self.s.close_on_or_before("2026-05-31"), ("2026-05-29", 192.5))

    def test_before_series_start_is_none(self):
        self.assertIsNone(self.s.close_on_or_before("2025-01-01"))

    def test_latest(self):
        self.assertEqual(self.s.latest(), ("2026-06-02", 197.4))

    def test_empty_series_is_falsy(self):
        self.assertFalse(PriceSeries({}))


class TestBuyReturn(unittest.TestCase):
    def setUp(self):
        self.s = PriceSeries(parse_history(AAPL))

    def test_pct_from_entry_to_latest(self):
        rec = buy_return(self.s, "2026-05-29")
        self.assertEqual(rec["entry_date"], "2026-05-29")
        self.assertEqual(rec["entry_close"], 192.5)
        self.assertEqual(rec["latest_close"], 197.4)
        self.assertEqual(rec["pct"], round((197.4 - 192.5) / 192.5 * 100, 1))

    def test_unpriced_when_no_series(self):
        self.assertIsNone(buy_return(PriceSeries({}), "2026-05-29"))

    def test_unpriced_when_buy_predates_series(self):
        self.assertIsNone(buy_return(self.s, "2024-01-01"))


class TestComputeReturns(unittest.TestCase):
    def _trade(self, tid, ticker, ttype, tx):
        return {"id": tid, "ticker": ticker, "type": ttype, "tx_date": tx}

    def test_only_priceable_buys_get_returns(self):
        series = {"AAPL": PriceSeries(
            parse_history(AAPL))}
        trades = [
            self._trade("a", "AAPL", "buy", "2026-05-29"),   # priced
            self._trade("b", "AAPL", "sell", "2026-05-29"),  # sells ignored
            self._trade("c", "NVDA", "buy", "2026-05-29"),   # no series → unpriced
            self._trade("d", None, "buy", "2026-05-29"),     # no ticker
        ]
        returns, prices, stats = compute_returns(trades, series)
        self.assertEqual(set(returns), {"a"})
        self.assertEqual(prices["AAPL"]["asof_close"], 197.4)
        # total_buys = buys that carry a ticker (the priceable universe): a, c.
        self.assertEqual(stats["total_buys"], 2)
        self.assertEqual(stats["priced_buys"], 1)
        self.assertEqual(stats["tickers"], 1)

    def test_distinct_buy_tickers(self):
        trades = [
            self._trade("a", "AAPL", "buy", "x"),
            self._trade("b", "AAPL", "buy", "y"),
            self._trade("c", "MU", "sell", "z"),  # sell excluded
            self._trade("d", "NVDA", "buy", "w"),
        ]
        self.assertEqual(distinct_buy_tickers(trades), ["AAPL", "NVDA"])


if __name__ == "__main__":
    unittest.main()
