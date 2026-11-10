"""Offline tests for amended reports (congress.pipeline.apply_amendments).

Every case is the shape of a real one. The Senate listing was read on
10 Nov 2026: 27 of its 309 filings were amendments, and treated as new
filings they counted 143 rows twice and showed 320 rows as filed late that
were filed on time.
"""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from congress import pipeline, senate
from congress.normalize import Trade
from congress.pipeline import ChamberSource, Version, apply_amendments, run

TODAY = date(2026, 11, 10)  # the window opens 2025-01-01


class Filing:
    """One listed filing and the rows its document states."""

    def __init__(self, fid, title, filed, rows, member="Tommy Tuberville",
                 paper=False):
        self.fid, self.title, self.filed = fid, title, filed
        self.rows, self.member, self.paper = rows, member, paper


def _title(report_date, amendment=None):
    us = date.fromisoformat(report_date).strftime("%m/%d/%Y")
    tail = "" if amendment is None else (
        " (Amendment)" if amendment == "" else f" (Amendment {amendment})")
    return f"Periodic Transaction Report for {us}{tail}"


def _row(ticker, tx_date="2025-04-15", kind="sell", partial=False,
         lo=15001, hi=50000):
    return {"ticker": ticker, "tx_date": tx_date, "type": kind,
            "partial": partial, "amount_lo": lo, "amount_hi": hi}


def _trades(f):
    return [Trade(
        id=f"senate:{f.fid}:{i}", chamber="senate", member=f.member,
        ticker=r["ticker"], asset=f"{r['ticker']} Inc", asset_type="Stock",
        type=r["type"], partial=r["partial"], owner="JT",
        tx_date=r["tx_date"], filing_date=f.filed,
        amount_lo=r["amount_lo"], amount_hi=r["amount_hi"],
        amount_label="bracket", filing_id=f.fid,
        source_url=f"https://example.gov/{f.fid}/",
    ) for i, r in enumerate(f.rows)]


def _source(filings, chamber="senate", versions=True, fetched=None):
    def fetch(f):
        if fetched is not None:
            fetched.append(f.fid)
        if f.paper:
            raise pipeline.PaperFiling(f.fid)
        return _trades(f)

    return ChamberSource(
        chamber=chamber,
        list_filings=lambda: list(filings),
        fetch_trades=fetch,
        ref_id=lambda f: f.fid,
        ref_member=lambda f: f.member,
        ref_filing_date=lambda f: f.filed,
        ref_url=lambda f: f"https://example.gov/{f.fid}/",
        ref_version=(lambda f: senate.report_version(f.title)) if versions else None,
    )


FOUR = [_row("GOOGL"), _row("AAPL"), _row("GS"), _row("MA")]


class AmendmentRunTest(unittest.TestCase):
    """Through pipeline.run, as the daily job applies it."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name)
        self.output, self.state = base / "trades.json", base / "state.json"
        self.log = []

    def _run(self, filings, **kw):
        source = kw.pop("source", None) or _source(filings)
        return run([source], today=TODAY, output_path=self.output,
                   state_path=self.state, log=self.log.append,
                   generated_at="2026-11-10T08:00:00Z", **kw)

    def _rows(self):
        return json.loads(self.output.read_text())["trades"]

    # --- the common case: Tuberville, 15 May 2025, amended 5 Aug 2026 ------

    def _original_and_amendment(self):
        original = Filing("orig", _title("2025-05-15"), "2025-05-15", FOUR)
        corrected = [dict(r, partial=True) if r["ticker"] in ("GS", "MA") else r
                     for r in FOUR]
        amendment = Filing("amend", _title("2025-05-15", 1), "2026-08-05",
                           corrected)
        return original, amendment

    def test_an_amended_report_counts_once(self):
        result = self._run(self._original_and_amendment())
        rows = self._rows()
        self.assertEqual(len(rows), 4)                      # not 8
        self.assertEqual({t["filing_id"] for t in rows}, {"amend"})
        self.assertEqual(result.superseded_trades, 4)

    def test_the_rows_shown_are_the_corrected_ones(self):
        self._run(self._original_and_amendment())
        partial = {t["ticker"]: t["partial"] for t in self._rows()}
        self.assertEqual(partial, {"GOOGL": False, "AAPL": False,
                                   "GS": True, "MA": True})

    def test_the_report_keeps_the_date_it_was_first_filed(self):
        # Trades of 15 Apr 2025, filed 15 May 2025: 30 days, on time. The
        # amendment's own date would make them 477 days.
        self._run(self._original_and_amendment())
        for t in self._rows():
            self.assertEqual(t["filing_date"], "2025-05-15")
            self.assertEqual(t["amended"], "2026-08-05")
            self.assertEqual(t["source_url"], "https://example.gov/amend/")

    def test_a_row_of_a_report_never_amended_has_no_amended_field(self):
        self._run([Filing("orig", _title("2025-05-15"), "2025-05-15", FOUR)])
        for t in self._rows():
            self.assertNotIn("amended", t)
            self.assertEqual(t["filing_date"], "2025-05-15")

    def test_the_amendment_arrives_in_a_later_run(self):
        original, amendment = self._original_and_amendment()
        self._run([original])
        self.assertEqual(len(self._rows()), 4)
        result = self._run([original, amendment])
        self.assertEqual({t["filing_id"] for t in self._rows()}, {"amend"})
        self.assertEqual(result.superseded_trades, 4)

    def test_a_later_run_changes_nothing_and_fetches_nothing(self):
        filings = self._original_and_amendment()
        self._run(filings)
        first = self.output.read_bytes()
        state = self.state.read_bytes()
        fetched = []
        result = self._run(filings, source=_source(filings, fetched=fetched))
        self.assertFalse(result.changed)
        self.assertEqual(result.superseded_trades, 0)
        self.assertEqual(self.output.read_bytes(), first)
        self.assertEqual(self.state.read_bytes(), state)
        # The removed original stays "processed": it is never downloaded again.
        self.assertEqual(fetched, [])

    def test_the_log_says_what_was_done_once(self):
        filings = self._original_and_amendment()
        self._run(filings)
        said = [m for m in self.log if "amended reports" in m]
        self.assertEqual(len(said), 1)
        self.assertIn("removed 4 rows", said[0])
        self.assertIn("re-dated 4 rows", said[0])
        self.log.clear()
        self._run(filings)
        self.assertEqual([m for m in self.log if "amended reports" in m], [])

    # --- Boozman: two reports on one day ------------------------------------

    def test_content_says_which_of_two_reports_an_amendment_corrects(self):
        a = Filing("a", _title("2025-06-14"), "2025-06-14",
                   [_row("ACN"), _row("SPYM"), _row("FTGC")], member="John Boozman")
        b = Filing("b", _title("2025-06-14"), "2025-06-14",
                   [_row("XOM"), _row("CVX")], member="John Boozman")
        fix = Filing("a1", _title("2025-06-14", 1), "2025-07-09",
                     [_row("ACN"), _row("SPYM"), _row("FTGC", partial=True)],
                     member="John Boozman")
        self._run([a, b, fix])
        by = {}
        for t in self._rows():
            by.setdefault(t["filing_id"], []).append(t["ticker"])
        self.assertEqual(set(by), {"b", "a1"})        # "a" replaced, "b" kept
        self.assertEqual(sorted(by["b"]), ["CVX", "XOM"])

    def test_the_other_report_of_that_day_never_warns(self):
        # After the amendment replaced report "a", report "b" is still a
        # filing of that member for that date that shares nothing. That is
        # the normal state on every later run, not a problem to report.
        a = Filing("a", _title("2025-06-14"), "2025-06-14",
                   [_row("ACN"), _row("SPYM"), _row("FTGC")], member="John Boozman")
        b = Filing("b", _title("2025-06-14"), "2025-06-14",
                   [_row("XOM"), _row("CVX")], member="John Boozman")
        fix = Filing("a1", _title("2025-06-14", 1), "2025-07-09",
                     [_row("ACN"), _row("SPYM"), _row("FTGC", partial=True)],
                     member="John Boozman")
        for _ in range(3):
            self._run([a, b, fix])
        self.assertEqual([m for m in self.log if "::warning::" in m], [])

    def test_nothing_is_removed_when_no_report_shares_the_rows(self):
        # An amendment that fits neither report of that day. A guess would
        # delete a report the amendment never touched.
        a = Filing("a", _title("2025-06-14"), "2025-06-14",
                   [_row("ACN"), _row("SPYM")], member="John Boozman")
        b = Filing("b", _title("2025-06-14"), "2025-06-14",
                   [_row("XOM"), _row("CVX")], member="John Boozman")
        odd = Filing("odd", _title("2025-06-14", 1), "2025-07-09",
                     [_row("IBM"), _row("ORCL")], member="John Boozman")
        result = self._run([a, b, odd])
        self.assertEqual(result.superseded_trades, 0)
        self.assertEqual(len(self._rows()), 6)
        warned = [m for m in self.log if m.startswith("::warning::senate:odd")]
        self.assertEqual(len(warned), 1)
        self.assertIn("nothing was removed", warned[0])
        # Said on the run that first reads it, not every morning after.
        self._run([a, b, odd])
        self.assertEqual(
            len([m for m in self.log if m.startswith("::warning::")]), 1)
        # It is still an amendment of a 14 June report, and dated as one.
        for t in self._rows():
            if t["filing_id"] == "odd":
                self.assertEqual(t["filing_date"], "2025-06-14")
                self.assertEqual(t["amended"], "2025-07-09")

    def test_one_shared_row_in_a_long_report_is_not_enough(self):
        # Two reports of one day can state one identical trade (two accounts).
        long_a = Filing("a", _title("2025-06-14"), "2025-06-14",
                        [_row(t) for t in ("ACN", "SPYM", "FTGC", "IBM", "KO")],
                        member="John Boozman")
        fix = Filing("x1", _title("2025-06-14", 1), "2025-07-09",
                     [_row(t) for t in ("ACN", "PEP", "MMM", "CAT", "DE")],
                     member="John Boozman")
        result = self._run([long_a, fix])
        self.assertEqual(result.superseded_trades, 0)
        self.assertEqual(len(self._rows()), 10)

    # --- McCormick: the listing's title is one day off ----------------------

    def test_a_title_one_day_off_still_finds_its_report(self):
        rows = [_row("PHL", tx_date="2024-02-18", kind="buy"), _row("AAPL"),
                _row("MSFT")]
        fixed = [_row("PHL", tx_date="2025-02-18", kind="buy"), _row("AAPL"),
                 _row("MSFT")]
        original = Filing("o", _title("2025-03-05"), "2025-03-05", rows,
                          member="David McCormick")
        amendment = Filing("a", _title("2025-03-06", 1), "2025-03-19", fixed,
                           member="David McCormick")
        self._run([original, amendment])
        rows = self._rows()
        self.assertEqual({t["filing_id"] for t in rows}, {"a"})
        # The date comes from the report we held, not from the title.
        self.assertEqual({t["filing_date"] for t in rows}, {"2025-03-05"})
        self.assertEqual({t["tx_date"] for t in rows if t["ticker"] == "PHL"},
                         {"2025-02-18"})

    def test_a_report_two_days_away_is_another_report(self):
        original = Filing("o", _title("2025-03-05"), "2025-03-05", FOUR)
        amendment = Filing("a", _title("2025-03-07", 1), "2025-03-19", FOUR)
        result = self._run([original, amendment])
        self.assertEqual(result.superseded_trades, 0)
        self.assertEqual(len(self._rows()), 8)

    # --- the original is not ours to hold -----------------------------------

    def test_without_the_original_the_title_dates_the_report(self):
        # Rick Scott, report of 3 Mar 2025 amended 13 Aug 2026, original lost.
        amendment = Filing("a", _title("2025-03-03", 1), "2026-08-13", FOUR,
                           member="Rick Scott")
        self._run([amendment])
        for t in self._rows():
            self.assertEqual(t["filing_date"], "2025-03-03")
            self.assertEqual(t["amended"], "2026-08-13")

    def test_a_report_first_filed_before_the_window_leaves_with_its_year(self):
        # Mullin amended three 2024 reports in Aug 2025. The window opens
        # 1 Jan 2025 for every member; an amendment does not reopen it.
        old = Filing("old", _title("2024-01-26", 1), "2025-08-12", FOUR,
                     member="Markwayne Mullin")
        new = Filing("new", _title("2025-09-01"), "2025-09-01", [_row("KO")],
                     member="Markwayne Mullin")
        filings = [old, new]
        self._run(filings)
        self.assertEqual({t["filing_id"] for t in self._rows()}, {"new"})
        # It is not downloaded again on every run for ever.
        fetched = []
        self._run(filings, source=_source(filings, fetched=fetched))
        self.assertEqual(fetched, [])

    def test_a_second_amendment_replaces_the_first(self):
        # Tuberville, report of 15 Nov 2024: Amendment 1 and Amendment 2 both
        # filed 5 Aug 2026, the original before the window.
        one = Filing("a1", _title("2025-02-14", 1), "2026-08-05", FOUR)
        two = Filing("a2", _title("2025-02-14", 2), "2026-08-05",
                     FOUR[:3] + [_row("MA", partial=True)])
        self._run([two, one])            # listing order must not matter
        rows = self._rows()
        self.assertEqual({t["filing_id"] for t in rows}, {"a2"})
        self.assertEqual({t["filing_date"] for t in rows}, {"2025-02-14"})

    def test_original_then_two_amendments_keep_the_first_date(self):
        original = Filing("o", _title("2025-02-14"), "2025-02-14", FOUR)
        one = Filing("a1", _title("2025-02-14", 1), "2025-06-01", FOUR)
        two = Filing("a2", _title("2025-02-14", 2), "2026-08-05", FOUR)
        self._run([original, one])
        self._run([original, one, two])
        rows = self._rows()
        self.assertEqual({t["filing_id"] for t in rows}, {"a2"})
        self.assertEqual({t["filing_date"] for t in rows}, {"2025-02-14"})
        self.assertEqual({t["amended"] for t in rows}, {"2026-08-05"})

    def test_an_original_that_parses_late_is_still_replaced(self):
        # The original failed to parse for a week; the amendment came first.
        original = Filing("o", _title("2025-05-15"), "2025-05-15", FOUR)
        amendment = Filing("a", _title("2025-05-16", 1), "2026-08-05", FOUR)
        self._run([amendment])
        self.assertEqual({t["filing_date"] for t in self._rows()}, {"2025-05-16"})
        self._run([original, amendment])
        rows = self._rows()
        self.assertEqual({t["filing_id"] for t in rows}, {"a"})
        self.assertEqual({t["filing_date"] for t in rows}, {"2025-05-15"})

    # --- what the rule must not touch ---------------------------------------

    def test_another_members_report_of_that_day_is_untouched(self):
        mine = Filing("m", _title("2025-05-15"), "2025-05-15", FOUR,
                      member="Rick Scott")
        amendment = Filing("a", _title("2025-05-15", 1), "2026-08-05", FOUR)
        self._run([mine, amendment])
        self.assertEqual({t["filing_id"] for t in self._rows()}, {"m", "a"})

    def test_a_paper_amendment_cannot_replace_a_report_we_can_read(self):
        original = Filing("o", _title("2025-10-02"), "2025-10-02", FOUR,
                          member="Richard Blumenthal")
        paper = Filing("p", _title("2025-10-02", ""), "2025-10-20", [],
                       member="Richard Blumenthal", paper=True)
        result = self._run([original, paper])
        self.assertEqual(result.superseded_trades, 0)
        self.assertEqual({t["filing_id"] for t in self._rows()}, {"o"})

    def test_a_source_that_names_no_versions_is_taken_as_listed(self):
        # The House index does not say which report a filing corrects, and
        # two identical rows in two House filings are both "New".
        filings = self._original_and_amendment()
        self._run(filings, source=_source(filings, chamber="house",
                                          versions=False))
        self.assertEqual(len(self._rows()), 8)

    def test_a_failed_listing_changes_nothing(self):
        filings = self._original_and_amendment()
        self._run([filings[0]])
        before = self.output.read_bytes()

        def refused():
            raise RuntimeError("HTTP 403")

        source = _source(filings)
        source.list_filings = refused
        result = self._run(filings, source=source)
        self.assertEqual(result.failed_sources, ["senate"])
        self.assertEqual(self.output.read_bytes(), before)

    def test_an_amendment_with_an_unknown_title_is_left_as_listed(self):
        odd = Filing("x", "Periodic Transaction Report (Amendment 1)",
                     "2026-08-05", FOUR)
        self._run([odd])
        for t in self._rows():
            self.assertEqual(t["filing_date"], "2026-08-05")
            self.assertNotIn("amended", t)
        self.assertTrue(any("names no report date" in m for m in self.log))


class ApplyAmendmentsTest(unittest.TestCase):
    """The pure pass, on rows as the output file holds them."""

    def _held(self, *filings):
        trades = {}
        for f in filings:
            for t in _trades(f):
                trades[t.id] = t.to_dict()
        return trades

    def _listed(self, *filings):
        return {f.fid: Version(f.filed, *senate.report_version(f.title))
                for f in filings}

    def test_returns_what_it_removed_and_what_it_dated(self):
        o = Filing("o", _title("2025-05-15"), "2025-05-15", FOUR)
        a = Filing("a", _title("2025-05-15", 1), "2026-08-05", FOUR)
        trades = self._held(o, a)
        self.assertEqual(
            apply_amendments(trades, self._listed(o, a), "senate", print), (4, 4))
        self.assertEqual(
            apply_amendments(trades, self._listed(o, a), "senate", print), (0, 0))

    def test_only_the_named_chamber_is_read(self):
        o = Filing("o", _title("2025-05-15"), "2025-05-15", FOUR)
        a = Filing("a", _title("2025-05-15", 1), "2026-08-05", FOUR)
        trades = self._held(o, a)
        self.assertEqual(
            apply_amendments(trades, self._listed(o, a), "house", print), (0, 0))
        self.assertEqual(len(trades), 8)

    def test_a_filing_missing_from_the_listing_is_never_a_candidate(self):
        o = Filing("o", _title("2025-05-15"), "2025-05-15", FOUR)
        a = Filing("a", _title("2025-05-15", 1), "2026-08-05", FOUR)
        trades = self._held(o, a)
        self.assertEqual(
            apply_amendments(trades, self._listed(a), "senate", print), (0, 4))
        self.assertEqual(len(trades), 8)

    def test_an_identical_trade_stated_twice_is_two_rows(self):
        # Two lots of one trade inside one report are both real; the amended
        # report restates both, and both stay.
        twice = [_row("AAPL"), _row("AAPL"), _row("MSFT")]
        o = Filing("o", _title("2025-05-15"), "2025-05-15", twice)
        a = Filing("a", _title("2025-05-15", 1), "2026-08-05", twice)
        trades = self._held(o, a)
        apply_amendments(trades, self._listed(o, a), "senate", print)
        self.assertEqual(sorted(t["ticker"] for t in trades.values()),
                         ["AAPL", "AAPL", "MSFT"])


class ReportVersionTest(unittest.TestCase):
    """The three title shapes of the real listing."""

    def test_an_original(self):
        self.assertEqual(senate.report_version(
            "Periodic Transaction Report for 05/15/2025"), ("2025-05-15", 0))

    def test_a_numbered_amendment(self):
        self.assertEqual(senate.report_version(
            "Periodic Transaction Report for 11/15/2024 (Amendment 2)"),
            ("2024-11-15", 2))

    def test_a_paper_amendment_has_no_number(self):
        self.assertEqual(senate.report_version(
            "Periodic Transaction Report for 10/02/2025 (Amendment)"),
            ("2025-10-02", 1))

    def test_a_title_without_a_date(self):
        self.assertEqual(senate.report_version("Annual Report for CY 2024"),
                         (None, 0))
        self.assertEqual(senate.report_version(
            "Periodic Transaction Report (Amendment 1)"), (None, 1))
        self.assertEqual(senate.report_version(""), (None, 0))

    def test_an_impossible_date_is_no_date(self):
        self.assertEqual(senate.report_version(
            "Periodic Transaction Report for 13/45/2025"), (None, 0))


if __name__ == "__main__":
    unittest.main()
