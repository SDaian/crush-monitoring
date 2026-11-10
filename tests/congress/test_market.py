"""Offline tests for congress.market (the reading is pure math)."""

import json
import math
import unittest
from datetime import date, datetime, timezone

from congress import indicators, market


def series(closes, start_day=1):
    """Ascending parse_series-shaped rows for a list of closes."""
    return [{"date": f"2026-06-{start_day + i:02d}", "close": c,
             "volume": float("nan")} for i, c in enumerate(closes)]


def td_body(closes):
    """A Twelve Data time_series body, newest-first as the API answers."""
    rows = series(closes)
    return json.dumps({"status": "ok", "values": [
        {"datetime": r["date"], "close": str(r["close"]), "volume": "0"}
        for r in reversed(rows)]})


class TestBands(unittest.TestCase):
    def test_each_band(self):
        self.assertEqual(market.band(11.0), ("calm", "Calm"))
        self.assertEqual(market.band(18.4), ("normal", "Normal"))
        self.assertEqual(market.band(28.0), ("elevated", "Elevated"))
        self.assertEqual(market.band(62.0), ("stressed", "Stressed"))

    def test_boundaries_belong_to_the_higher_band(self):
        self.assertEqual(market.band(15.0)[0], "normal")
        self.assertEqual(market.band(25.0)[0], "elevated")
        self.assertEqual(market.band(35.0)[0], "stressed")

    def test_unknown_level(self):
        self.assertEqual(market.band(None), ("", ""))


class TestRealizedVol(unittest.TestCase):
    def test_a_flat_tape_has_no_volatility(self):
        self.assertEqual(market.realized_vol([100.0] * 25), 0.0)

    def test_matches_the_definition(self):
        # A ±1% alternating tape: 20 log returns of ±ln(1.01) about a mean of
        # exactly 0. The sample standard deviation divides by n-1, so the
        # annualised figure is ln(1.01)·√(20/19)·√252, in percent.
        closes = [100.0 * (1.01 ** (i % 2)) for i in range(40)]
        got = market.realized_vol(closes, window=20)
        want = math.log(1.01) * math.sqrt(20 / 19) * math.sqrt(252) * 100
        self.assertAlmostEqual(got, want, places=6)

    def test_too_little_history(self):
        self.assertIsNone(market.realized_vol([100.0] * 10, window=20))
        self.assertIsNone(market.realized_vol([], window=20))

    def test_a_bad_close_never_raises(self):
        self.assertIsNone(market.realized_vol([100.0] * 20 + [0.0], window=20))


class TestReading(unittest.TestCase):
    """One source: our own realized volatility of the S&P 500."""

    ALTERNATING = [100.0 * (1.01 ** (i % 2)) for i in range(40)]

    def test_computes_our_own_reading(self):
        r = market.reading(series(self.ALTERNATING))
        want = math.log(1.01) * math.sqrt(20 / 19) * math.sqrt(252) * 100
        self.assertEqual(r["level"], round(want, 2))
        self.assertEqual(r["label"], "S&P 500 volatility")
        self.assertEqual(r["band"], market.band(want)[0])
        self.assertEqual(r["asofDate"], "2026-06-40")  # the newest bar's date

    def test_never_calls_itself_the_vix(self):
        # Realized volatility is a different measurement. Labelling it "VIX"
        # would be a lie a reader who knows the index would catch; the note
        # says so in plain words.
        r = market.reading(series([100.0 + i for i in range(40)]))
        self.assertNotIn("VIX", r["label"])
        self.assertIn("not the VIX", r["note"])

    def test_the_move_is_in_points_against_the_session_before(self):
        # Calm for 20 sessions, then one 5% day: volatility rose.
        closes = [100.0] * 25 + [105.0]
        r = market.reading(series(closes))
        self.assertEqual(
            r["chg_1d"],
            round(market.realized_vol(closes) - market.realized_vol(closes[:-1]), 2))
        self.assertGreater(r["chg_1d"], 0)

    def test_the_first_reading_has_no_move(self):
        # Exactly window + 1 closes: one reading exists, none before it.
        r = market.reading(series(self.ALTERNATING[:21]))
        self.assertIsNotNone(r)
        self.assertNotIn("chg_1d", r)

    def test_not_enough_history_is_no_reading(self):
        self.assertIsNone(market.reading(series([100.0, 101.0])))
        self.assertIsNone(market.reading([]))

    def test_an_error_body_is_no_reading(self):
        # What parse_series returns when the source refuses the symbol.
        self.assertIsNone(market.reading(
            indicators.parse_series('{"status":"error","message":"nope"}')))

    def test_reads_a_real_api_body(self):
        rows = indicators.parse_series(td_body(self.ALTERNATING))
        self.assertEqual(market.reading(rows), market.reading(series(self.ALTERNATING)))

    def test_carries_the_index_one_year_volatility(self):
        closes = [100.0 * (1.01 ** (i % 2)) for i in range(300)]
        r = market.reading(series(closes))
        self.assertEqual(r["vol1y"],
                         round(market.realized_vol(closes, market.YEAR), 1))

    def test_short_history_omits_the_one_year_number(self):
        self.assertNotIn("vol1y", market.reading(series(self.ALTERNATING)))

    def test_the_reading_carries_its_own_labelling(self):
        r = market.reading(series([100.0 + i * 0.5 for i in range(40)]))
        for key in ("label", "note", "bandLabel", "bandNote", "asofDate"):
            self.assertTrue(r[key], f"{key} missing")

    def test_there_is_one_source_and_no_field_to_name_it(self):
        # The VIX path is gone (the plan never served it), so a "source"
        # field would have one value for ever.
        self.assertNotIn("source", market.reading(series(self.ALTERNATING)))
        for gone in ("from_vix", "build", "VIX_SYMBOL", "SOURCE_VIX"):
            self.assertFalse(hasattr(market, gone), gone)


class TestSummary(unittest.TestCase):
    def test_one_sentence(self):
        r = {"label": "S&P 500 volatility", "level": 18.5, "chg_1d": 2.5,
             "bandLabel": "Normal"}
        self.assertEqual(market.summary(r),
                         "S&P 500 volatility 18.5 (+2.5 pts) — normal")

    def test_a_fall_carries_its_own_sign(self):
        r = {"label": "S&P 500 volatility", "level": 14.2, "chg_1d": -0.8,
             "bandLabel": "Calm"}
        self.assertEqual(market.summary(r),
                         "S&P 500 volatility 14.2 (-0.8 pts) — calm")

    def test_no_move_is_left_out(self):
        r = {"label": "S&P 500 volatility", "level": 14.2, "bandLabel": "Calm"}
        self.assertEqual(market.summary(r), "S&P 500 volatility 14.2 — calm")

    def test_no_reading_is_an_empty_string(self):
        self.assertEqual(market.summary(None), "")


class TestSessionCalendar(unittest.TestCase):
    """When a paced fetch cannot return anything new.

    The dates below are the REAL run log from 2026-08-10..19, which is what
    proved the naive weekend guard wrong: our crons fire hours before the US
    close, so each run captures the previous session.
    """

    @staticmethod
    def utc(text: str) -> datetime:
        return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)

    def test_a_run_before_the_close_sees_the_previous_session(self):
        # Friday 05:00 UTC — Friday's bell has not rung yet.
        self.assertEqual(market.last_closed_session(self.utc("2026-08-14 05:00")),
                         date(2026, 8, 13))

    def test_saturday_is_the_run_that_captures_friday(self):
        # The one weekend run that earns its keep. Skipping it would leave
        # the site on Thursday's numbers until Tuesday.
        self.assertEqual(market.last_closed_session(self.utc("2026-08-15 05:00")),
                         date(2026, 8, 14))

    def test_sunday_and_monday_repeat_friday(self):
        for stamp in ("2026-08-16 05:00", "2026-08-17 05:00"):
            self.assertEqual(market.last_closed_session(self.utc(stamp)),
                             date(2026, 8, 14), stamp)

    def test_tuesday_sees_monday(self):
        self.assertEqual(market.last_closed_session(self.utc("2026-08-18 05:00")),
                         date(2026, 8, 17))

    def test_after_the_settle_hour_the_same_day_counts(self):
        self.assertEqual(market.last_closed_session(self.utc("2026-08-18 23:00")),
                         date(2026, 8, 18))

    def test_holding_fridays_close_skips_sunday_and_monday(self):
        for stamp in ("2026-08-16 05:00", "2026-08-17 05:00"):
            self.assertTrue(
                market.have_newest_close("2026-08-14", self.utc(stamp)), stamp)

    def test_holding_thursdays_close_still_fetches_on_saturday(self):
        self.assertFalse(
            market.have_newest_close("2026-08-13", self.utc("2026-08-15 05:00")))

    def test_no_held_date_means_do_the_work(self):
        # A first run, a wiped file, or a garbled date must never skip.
        for held in (None, "", "not-a-date", "2026-13-99"):
            self.assertFalse(
                market.have_newest_close(held, self.utc("2026-08-17 05:00")), held)
