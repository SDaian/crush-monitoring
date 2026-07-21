"""Offline tests for congress.analytics (Vercel Web Analytics → report block).

Pure parsing/formatting only — no network. The response shape is matched
defensively, so these lock in that a few plausible Vercel shapes all parse.
"""

import unittest
from unittest import mock

from congress import analytics as a


class TestParseTotal(unittest.TestCase):
    def test_direct(self):
        self.assertEqual(a.parse_total({"total": 42}), 42)

    def test_nested_dict(self):
        self.assertEqual(a.parse_total({"data": {"total": 7}}), 7)

    def test_nested_list(self):
        self.assertEqual(a.parse_total({"data": [{"count": 9}]}), 9)

    def test_alt_key(self):
        self.assertEqual(a.parse_total({"pageviews": 3}), 3)

    def test_missing_is_none(self):
        self.assertIsNone(a.parse_total({}))
        self.assertIsNone(a.parse_total({"data": []}))
        self.assertIsNone(a.parse_total("nonsense"))


class TestRowsAndTopPages(unittest.TestCase):
    ROWS = {"data": [
        {"key": "/members/nancy-pelosi", "pageviews": 30},
        {"requestPath": "/", "views": 120},
        {"path": "/late", "total": 15},
    ]}

    def test_parse_rows(self):
        self.assertEqual(len(a.parse_rows(self.ROWS)), 3)
        self.assertEqual(a.parse_rows({}), [])
        self.assertEqual(a.parse_rows({"data": {"rows": [{"k": 1}]}}), [{"k": 1}])

    def test_top_pages_sorted_desc(self):
        pages = a.top_pages(self.ROWS)
        self.assertEqual(pages[0], ("/", 120))
        self.assertEqual([p for p, _ in pages],
                         ["/", "/members/nancy-pelosi", "/late"])

    def test_top_pages_limit(self):
        self.assertEqual(len(a.top_pages(self.ROWS, limit=2)), 2)

    def test_missing_metric_is_zero(self):
        self.assertEqual(a.top_pages({"data": [{"key": "/x"}]}), [("/x", 0)])


class TestFormatBlock(unittest.TestCase):
    def test_markdown_and_html(self):
        md, html = a.format_block(
            {"total": 165, "pages": [("/", 120), ("/late", 15)], "windowDays": 7})
        self.assertIn("last 7 days", md)
        self.assertIn("165 page views", md)
        self.assertIn("`/`", md)
        self.assertIn("<h2>", html)
        self.assertIn("165 page views", html)

    def test_total_unavailable(self):
        md, _ = a.format_block({"total": None, "pages": [], "windowDays": 7})
        self.assertIn("unavailable", md)

    def test_html_escapes_path(self):
        _, html = a.format_block(
            {"total": 1, "pages": [("/x?<script>", 1)], "windowDays": 7})
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class TestDailySummaryGating(unittest.TestCase):
    def test_none_without_token(self):
        # No VERCEL_TOKEN configured → no network attempted, returns None.
        with mock.patch.dict("os.environ",
                             {a.ENV_TOKEN: "", a.ENV_PROJECT: ""}, clear=False):
            self.assertIsNone(a.daily_summary("2026-07-21"))


if __name__ == "__main__":
    unittest.main()
