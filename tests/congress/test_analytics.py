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

    def test_live_count_shape(self):
        # The exact shape the Vercel API returned in the probe: pageviews wins
        # over visitors as the headline "views" total.
        self.assertEqual(a.parse_total(
            {"version": 1, "query": {},
             "data": {"visitors": 6, "pageviews": 88}}), 88)


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

    def test_live_aggregate_shape(self):
        # The exact shape from the probe: by=route → [{route, visitors, pageviews}].
        payload = {"data": [
            {"route": "/", "visitors": 5, "pageviews": 46},
            {"route": "/members", "visitors": 2, "pageviews": 10},
        ]}
        self.assertEqual(a.top_pages(payload), [("/", 46), ("/members", 10)])

    def test_top_pages_sorted_desc(self):
        pages = a.top_pages(self.ROWS)
        self.assertEqual(pages[0], ("/", 120))
        self.assertEqual([p for p, _ in pages],
                         ["/", "/members/nancy-pelosi", "/late"])

    def test_top_pages_limit(self):
        self.assertEqual(len(a.top_pages(self.ROWS, limit=2)), 2)

    def test_missing_metric_is_zero(self):
        self.assertEqual(a.top_pages({"data": [{"key": "/x"}]}), [("/x", 0)])


class TestMemberPages(unittest.TestCase):
    def test_member_slug(self):
        self.assertEqual(a.member_slug("/members/nancy-pelosi"), "nancy-pelosi")
        self.assertEqual(a.member_slug("/members/donald-j-trump/"), "donald-j-trump")
        self.assertEqual(a.member_slug("/members/greene?ref=x"), "greene")
        self.assertIsNone(a.member_slug("/members"))
        self.assertIsNone(a.member_slug("/members/"))
        self.assertIsNone(a.member_slug("/late"))
        self.assertIsNone(a.member_slug("/"))

    def test_prettify_slug(self):
        self.assertEqual(a.prettify_slug("nancy-pelosi"), "Nancy Pelosi")

    def test_member_page_views_filters_and_sorts(self):
        payload = {"data": [
            {"route": "/", "pageviews": 120},
            {"route": "/members/nancy-pelosi", "pageviews": 46},
            {"route": "/members", "pageviews": 9},        # index → excluded
            {"route": "/members/josh-gottheimer", "pageviews": 60},
            {"route": "/late", "pageviews": 30},
        ]}
        self.assertEqual(a.member_page_views(payload),
                         [("josh-gottheimer", 60), ("nancy-pelosi", 46)])


class TestFormatBlock(unittest.TestCase):
    def test_member_breakdown_uses_real_names(self):
        md, html = a.format_block(
            {"total": 100, "pages": [("/", 50)], "windowDays": 7,
             "memberPages": [("nancy-pelosi", 46), ("donald-j-trump", 12)]},
            member_names={"nancy-pelosi": "Nancy Pelosi",
                          "donald-j-trump": "Donald J. Trump"})
        self.assertIn("Member pages:", md)
        self.assertIn("Nancy Pelosi — 46", md)
        self.assertIn("Donald J. Trump — 12", md)
        self.assertIn("Member pages", html)

    def test_member_breakdown_prettifies_unknown_slug(self):
        md, _ = a.format_block(
            {"total": 1, "pages": [], "windowDays": 7,
             "memberPages": [("marjorie-taylor-greene", 5)]})
        self.assertIn("Marjorie Taylor Greene — 5", md)

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
