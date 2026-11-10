"""Offline tests for congress.fallback: when the cron run has nothing to do.

Two halves. The decision is pure and tested on API-shaped records. The wiring
is the workflow file itself, read as text: the title the workflow gives the
Pi's dispatch must be the title the gate looks for, and the refresh job must
run unless the gate said no in so many words.
"""

import contextlib
import io
import os
import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from congress import fallback

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / fallback.WORKFLOW

NOW = datetime(2026, 11, 10, 15, 17, tzinfo=timezone.utc)   # a late cron


def run(**over):
    """The Pi's run of this morning, as the Actions API lists it."""
    rec = {
        "id": 40470543318, "run_number": 353,
        "name": "Congress trades refresh", "display_title": "Daily refresh",
        "event": "workflow_dispatch", "status": "completed",
        "conclusion": "success", "head_branch": "main",
        "created_at": "2026-11-10T08:00:03Z",
    }
    rec.update(over)
    return rec


class TestDailyRun(unittest.TestCase):
    def found(self, *runs, now=NOW, branch="main"):
        return fallback.daily_run(list(runs), now, branch)

    def test_the_morning_run_is_found(self):
        self.assertEqual(self.found(run())["run_number"], 353)

    def test_no_runs_means_the_fallback_runs(self):
        self.assertIsNone(self.found())
        self.assertIsNone(fallback.daily_run(None, NOW, "main"))

    def test_a_failed_daily_run_does_not_count(self):
        self.assertIsNone(self.found(run(conclusion="failure")))

    def test_a_run_still_in_progress_does_not_count(self):
        self.assertIsNone(self.found(run(status="in_progress", conclusion=None)))

    def test_a_manual_dispatch_is_not_the_daily_run(self):
        # It refreshed the data but sent no report: the fallback still owes one.
        self.assertIsNone(self.found(
            run(display_title="Congress trades refresh (manual)")))

    def test_the_fallback_itself_is_not_the_daily_run(self):
        self.assertIsNone(self.found(
            run(event="schedule", display_title="Daily refresh (cron fallback)")))
        self.assertIsNone(self.found(run(event="schedule")))

    def test_a_run_on_another_branch_does_not_count(self):
        # A test dispatch of the workflow on a feature branch is not the product.
        self.assertIsNone(self.found(run(head_branch="some-feature-branch")))

    def test_yesterdays_run_does_not_count(self):
        self.assertIsNone(self.found(run(created_at="2026-11-09T08:00:03Z")))

    def test_a_cron_delayed_past_midnight_still_finds_the_morning_run(self):
        # "Today" would miss it, send tomorrow's report at 2am Madrid time,
        # and make the 9am run skip that report as already sent.
        late = datetime(2026, 11, 11, 0, 40, tzinfo=timezone.utc)
        self.assertIsNotNone(self.found(run(), now=late))

    def test_the_window_closes_before_the_next_morning(self):
        edge = datetime(2026, 11, 10, 8, 0, 3, tzinfo=timezone.utc) + fallback.MAX_AGE
        self.assertIsNone(self.found(run(), now=edge))
        self.assertIsNotNone(self.found(run(), now=edge - timedelta(seconds=1)))

    def test_a_run_from_the_future_or_without_a_date_does_not_count(self):
        self.assertIsNone(self.found(run(created_at="2026-11-10T16:00:00Z")))
        self.assertIsNone(self.found(run(created_at="")))
        self.assertIsNone(self.found(run(created_at="not a date")))
        rec = run(); del rec["created_at"]
        self.assertIsNone(self.found(rec))

    def test_the_right_run_is_picked_out_of_a_real_listing(self):
        runs = [
            run(event="schedule", display_title="Daily refresh (cron fallback)",
                created_at="2026-11-09T18:55:00Z", run_number=351),
            run(display_title="Congress trades refresh (manual)",
                created_at="2026-11-10T03:00:00Z", run_number=352),
            run(),
        ]
        self.assertEqual(self.found(*runs)["run_number"], 353)


class TestMain(unittest.TestCase):
    def setUp(self):
        self._d = TemporaryDirectory()
        self.addCleanup(self._d.cleanup)
        self.out = Path(self._d.name) / "github_output"
        env = {"GITHUB_REPOSITORY": "SDaian/crush-monitoring",
               "GITHUB_REF_NAME": "main", "GH_TOKEN": "x",
               "GITHUB_OUTPUT": str(self.out)}
        p = mock.patch.dict(os.environ, env)
        p.start(); self.addCleanup(p.stop)

    def _main(self, fetch):
        log = io.StringIO()
        with mock.patch.object(fallback, "_fetch_runs", fetch), \
             contextlib.redirect_stdout(log):
            code = fallback.main()
        self.assertEqual(code, 0)          # the gate step never fails the job
        return log.getvalue()

    def _recent(self):
        created = (datetime.now(timezone.utc) - timedelta(hours=7))
        return run(created_at=created.strftime("%Y-%m-%dT%H:%M:%SZ"))

    def test_a_successful_daily_run_skips_the_refresh(self):
        log = self._main(lambda repo, branch, token: [self._recent()])
        self.assertEqual(self.out.read_text(), "run=false\n")
        self.assertIn("::notice::The daily run already succeeded (#353", log)

    def test_no_daily_run_runs_the_refresh(self):
        log = self._main(lambda repo, branch, token: [])
        self.assertEqual(self.out.read_text(), "run=true\n")
        self.assertIn("the fallback runs the refresh", log)

    def test_an_api_error_fails_open(self):
        def boom(repo, branch, token):
            raise OSError("HTTP Error 403: Resource not accessible")
        log = self._main(boom)
        self.assertEqual(self.out.read_text(), "run=true\n")
        self.assertIn("::warning::could not ask", log)

    def test_a_malformed_answer_fails_open(self):
        self._main(lambda repo, branch, token: [{"unexpected": True}, "junk"])
        self.assertEqual(self.out.read_text(), "run=true\n")

    def test_the_query_names_the_branch_it_runs_on(self):
        seen = {}
        def fetch(repo, branch, token):
            seen.update(repo=repo, branch=branch)
            return []
        self._main(fetch)
        self.assertEqual(seen, {"repo": "SDaian/crush-monitoring", "branch": "main"})

    def test_no_output_file_is_not_an_error(self):
        os.environ.pop("GITHUB_OUTPUT")
        self._main(lambda repo, branch, token: [])


class TestWorkflowWiring(unittest.TestCase):
    """The gate only works if the workflow file agrees with it."""

    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_the_workflow_file_is_the_one_the_gate_queries(self):
        self.assertTrue(WORKFLOW.exists())

    def test_the_pi_dispatch_gets_exactly_the_title_the_gate_looks_for(self):
        m = re.search(r"^run-name: >-\n((?:  .*\n)+)", self.text, re.M)
        self.assertIsNotNone(m, "the workflow lost its run-name")
        block = m.group(1)
        self.assertIn(
            f"(inputs.scheduled == 'true' && '{fallback.DAILY_TITLE}')", block)
        # Only the Pi's dispatch may carry it: one exact match among the titles.
        titles = re.findall(r"&& '([^']+)'\)|\|\| '([^']+)'", block)
        titles = [a or b for a, b in titles]
        self.assertEqual(titles.count(fallback.DAILY_TITLE), 1)
        self.assertEqual(len(titles), 3)

    def test_the_gate_runs_on_the_cron_only(self):
        self.assertRegex(
            self.text,
            r"\n  gate:\n(?:    #.*\n)*    if: github\.event_name == 'schedule'\n")
        self.assertIn("run: python3 -m congress.fallback\n", self.text)
        self.assertIn("      run: ${{ steps.decide.outputs.run }}\n", self.text)

    def test_the_refresh_fails_open(self):
        # It runs unless the gate said run=false: a skipped gate (every
        # dispatch) or a crashed one must not stop the daily job.
        self.assertIn("    needs: gate\n", self.text)
        self.assertIn(
            "    if: ${{ !cancelled() && needs.gate.outputs.run != 'false' }}\n",
            self.text)

    def test_the_token_may_read_the_runs(self):
        self.assertRegex(self.text, r"\npermissions:\n(?:  .*\n)*?  actions: read")


if __name__ == "__main__":
    unittest.main()
