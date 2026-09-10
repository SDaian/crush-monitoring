"""Offline tests for congress.analytics (Vercel Web Analytics → report block).

Pure parsing/formatting only — no network. The response shape is matched
defensively, so these lock in that a few plausible Vercel shapes all parse.
"""

import unittest
from datetime import date
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


class TestPeriodSummaryGating(unittest.TestCase):
    def test_none_without_token(self):
        # No VERCEL_TOKEN configured → no network attempted, returns None.
        with mock.patch.dict("os.environ",
                             {a.ENV_TOKEN: "", a.ENV_PROJECT: ""}, clear=False):
            self.assertIsNone(a.period_summary(a.DAILY, "2026-07-21"))
            self.assertIsNone(a.period_summary(a.WEEKLY, "2026-07-21"))


class TestWindowBounds(unittest.TestCase):
    """Two adjacent windows of equal length, neither touching today."""

    def test_daily_reads_yesterday_not_today(self):
        (since, until), _ = a.window_bounds(a.DAILY, "2026-09-10")
        self.assertEqual((since, until), ("2026-09-09", "2026-09-10"))

    def test_weekly_reads_the_seven_days_behind_today(self):
        (since, until), _ = a.window_bounds(a.WEEKLY, "2026-09-10")
        self.assertEqual((since, until), ("2026-09-03", "2026-09-10"))

    def test_the_previous_window_is_adjacent_and_equal(self):
        span = lambda lo, hi: date.fromisoformat(hi) - date.fromisoformat(lo)
        for kind in (a.DAILY, a.WEEKLY):
            (since, until), (psince, puntil) = a.window_bounds(kind, "2026-09-10")
            self.assertEqual(puntil, since, "windows must not gap or overlap")
            self.assertEqual(span(psince, puntil), span(since, until),
                             "a comparison needs two windows of one length")


class TestDelta(unittest.TestCase):
    """A percentage appears only where there is something to compare."""

    def test_a_real_change_reads_as_a_percentage(self):
        self.assertEqual(a.pct_delta(118, 100), 18.0)
        self.assertEqual(a.delta_text(118, 100), " (+18.0%)")

    def test_a_fall_keeps_its_sign(self):
        self.assertEqual(a.delta_text(82, 100), " (-18.0%)")

    def test_no_baseline_prints_nothing(self):
        self.assertEqual(a.delta_text(118, None), "")

    def test_a_zero_baseline_prints_nothing(self):
        # "+100%" off a zero week is noise dressed as a fact.
        self.assertIsNone(a.pct_delta(118, 0))
        self.assertEqual(a.delta_text(118, 0), "")

    def test_a_missing_current_prints_nothing(self):
        self.assertEqual(a.delta_text(None, 100), "")


class TestFormatBlockComparison(unittest.TestCase):
    CURRENT = {
        "kind": a.WEEKLY, "windowDays": 7,
        "total": 1180, "pages": [("/", 600), ("/tracker", 200)],
        "memberPages": [("nancy-pelosi", 180)],
        "previous": {"total": 1000, "pages": [("/", 500)],
                     "memberPages": [("nancy-pelosi", 200)]},
    }

    def test_the_total_carries_its_change_and_names_the_comparison(self):
        md, html = a.format_block(self.CURRENT)
        self.assertIn("1,180 page views (+18.0%) vs the previous week", md)
        self.assertIn("+18.0%", html)

    def test_a_page_present_in_both_periods_carries_its_change(self):
        md, _ = a.format_block(self.CURRENT)
        self.assertIn("`/` — 600 (+20.0%)", md)

    def test_a_page_absent_from_the_previous_period_carries_none(self):
        md, _ = a.format_block(self.CURRENT)
        self.assertIn("`/tracker` — 200\n", md + "\n")
        self.assertNotIn("/tracker` — 200 (", md)

    def test_a_member_page_that_fell_shows_the_fall(self):
        md, _ = a.format_block(self.CURRENT)
        self.assertIn("Nancy Pelosi — 180 (-10.0%)",
                      md.replace("nancy-pelosi", "Nancy Pelosi"))

    def test_without_a_previous_period_no_percentage_appears(self):
        md, html = a.format_block({**self.CURRENT, "previous": None})
        self.assertIn("1,180 page views", md)
        self.assertNotIn("%", md)
        self.assertNotIn("vs the previous week", md)
        self.assertNotIn("%", html)

    def test_the_daily_window_names_itself(self):
        md, _ = a.format_block({**self.CURRENT, "kind": a.DAILY,
                                "windowDays": 1})
        self.assertIn("Traffic — yesterday", md)
        self.assertIn("vs the day before", md)


if __name__ == "__main__":
    unittest.main()
