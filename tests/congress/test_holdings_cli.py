"""Offline tests for the `congress holdings` command: what it publishes.

The parsers are tested in test_holdings.py. These tests hold the FILE to one
rule: it is a function of the annual reports it read, so it changes only when
a report does — never because the clock moved, and never because a source
refused us.
"""

import contextlib
import io
import itertools
import json
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from congress import cli, holdings, http, normalize, senate

ROSTER = {
    "Alice House": {"name": "Alice House", "chamber": "house", "state": "CA"},
    "Bob Senate": {"name": "Bob Senate", "chamber": "senate", "state": "AL"},
    "Pat President": {"name": "Pat President", "chamber": "executive"},
}
STOCKS = {
    "Alice House": [{"ticker": "AAPL", "value_lo": 15001, "value_hi": 50000}],
    "Bob Senate": [{"ticker": "NVDA", "value_lo": 1001, "value_hi": 15000},
                   {"ticker": "XOM", "value_lo": 1001, "value_hi": 15000}],
}


class _Clock(datetime):
    """A datetime whose now() is set by the test."""
    moment = datetime(2026, 11, 9, 8, 0, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.moment


class TestHoldingsFile(unittest.TestCase):
    def setUp(self):
        self._d = TemporaryDirectory()
        self.out = Path(self._d.name) / "holdings.json"
        self.stocks = {k: list(v) for k, v in STOCKS.items()}
        self.senate_down = False
        refusal = itertools.count(1)

        def accept_disclaimer(session):
            if self.senate_down:
                # A firewall names a new reference on every request.
                raise senate.EfdError(
                    f"eFD disclaimer POST refused: HTTP 403 "
                    f"(server=AkamaiGHost); Reference #18.{next(refusal)}")

        def fetch_holdings(session, ref, *, member):
            rows = [types.SimpleNamespace(to_dict=lambda r=r: dict(r))
                    for r in self.stocks[member]]
            return rows, holdings.REASON_OK

        patches = [
            mock.patch.object(cli, "datetime", _Clock),
            mock.patch.object(http, "make_session", lambda: None),
            mock.patch.object(normalize, "load_featured", lambda: list(ROSTER)),
            mock.patch.object(normalize.Roster, "load", lambda: types.SimpleNamespace(
                find=lambda name: ROSTER.get(name))),
            mock.patch.object(holdings, "house_latest_annual",
                              lambda s, last, state, years: holdings.AnnualRef(
                                  "house", "https://example.test/h.pdf",
                                  "2026-05-15", 2025)),
            mock.patch.object(holdings, "senate_latest_annual",
                              lambda s, last: holdings.AnnualRef(
                                  "senate", "https://example.test/s/",
                                  "2026-08-11", 2025)),
            mock.patch.object(holdings, "fetch_holdings", fetch_holdings),
            mock.patch.object(senate, "accept_disclaimer", accept_disclaimer),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self._d.cleanup)
        _Clock.moment = datetime(2026, 11, 9, 8, 0, 0, tzinfo=timezone.utc)

    def _run(self):
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            code = cli._cmd_holdings(types.SimpleNamespace(output=str(self.out)))
        self.assertEqual(code, 0)
        return log.getvalue()

    def test_a_later_run_writes_the_same_bytes(self):
        self._run()
        first = self.out.read_bytes()
        _Clock.moment = datetime(2026, 11, 10, 8, 20, 0, tzinfo=timezone.utc)
        self._run()
        self.assertEqual(self.out.read_bytes(), first)

    def test_the_file_carries_no_timestamp(self):
        self._run()
        self.assertNotIn("generated_at", json.loads(self.out.read_text())["meta"])

    def test_an_outage_leaves_the_file_unchanged(self):
        self._run()
        first = self.out.read_bytes()
        self.senate_down = True
        log1 = self._run()
        self.assertEqual(self.out.read_bytes(), first)
        log2 = self._run()            # a new reference number in the refusal
        self.assertEqual(self.out.read_bytes(), first)
        self.assertNotEqual(log1, log2)
        # The outage is in the run log, with the member and the cause.
        self.assertIn("Bob Senate: fetch failed; kept the published holdings", log2)
        self.assertIn("error: eFD disclaimer POST refused: HTTP 403", log2)
        self.assertIn("::warning::holdings unavailable for Bob Senate", log2)

    def test_a_failure_with_nothing_to_keep_publishes_no_error_text(self):
        self.senate_down = True
        log = self._run()
        text = self.out.read_text()
        rec = json.loads(text)["holdings"]["Bob Senate"]
        self.assertEqual(rec, {"chamber": "senate", "available": False,
                               "stocks": [], "reason": holdings.REASON_ERROR})
        self.assertNotIn("Akamai", text)
        self.assertNotIn("403", text)
        self.assertIn("Bob Senate: fetch or parse raised", log)
        self.assertIn("error: eFD disclaimer POST refused", log)

    def test_a_changed_report_changes_the_file(self):
        self._run()
        first = json.loads(self.out.read_text())
        self.stocks["Bob Senate"] = self.stocks["Bob Senate"][:1]   # sold XOM
        self._run()
        second = json.loads(self.out.read_text())
        self.assertEqual(len(second["holdings"]["Bob Senate"]["stocks"]), 1)
        self.assertEqual(second["holdings"]["Alice House"],
                         first["holdings"]["Alice House"])

    def test_the_other_members_are_published_as_before(self):
        self._run()
        recs = json.loads(self.out.read_text())["holdings"]
        self.assertTrue(recs["Alice House"]["available"])
        self.assertEqual(recs["Alice House"]["source_url"],
                         "https://example.test/h.pdf")
        self.assertEqual(recs["Pat President"]["reason"],
                         holdings.REASON_UNSUPPORTED)


if __name__ == "__main__":
    unittest.main()
