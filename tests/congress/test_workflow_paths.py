"""The daily Action must commit everything the generators write.

`congress landing` regenerates the landing site's data every run, but the
workflow's commit step stages an explicit list of paths. When the two drift,
nothing fails: the generator succeeds, the log reports how many pages it
wrote, and the output is silently discarded because it was never staged.
That is exactly how `landing/src/data/tickers` went two months stale while
the tracker was current.

So this test does not hard-code the expected list. It RUNS the generators
into a temp directory, collects the paths they actually produced, and asserts
the workflow stages every one. Add a new output and this fails until the
workflow lists it.
"""

import re
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from congress import landing_data as ld

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "congress-trades.yml"
# Where `congress landing` writes, relative to the repo root (cli.py's
# DEFAULT_LANDING_DATA).
LANDING_DATA = "landing/src/data"


def _trade(member="Nancy Pelosi", ticker="NVDA", tx="2026-06-01",
           filed="2026-07-30", type="buy"):
    return {"member": member, "ticker": ticker, "type": type,
            "amount_lo": 1001, "amount_hi": 15000, "tx_date": tx,
            "filing_date": filed, "chamber": "house", "district": "CA-11",
            "state": "CA", "id": f"{ticker}:{tx}", "asset": f"{ticker} Inc."}


def generated_paths() -> set[str]:
    """Repo-relative paths a full `congress landing` run produces.

    The fixture is shaped to trigger every kind of output: a featured member
    (so member pages are written) trading one symbol enough times to clear
    TICKER_PAGE_MIN_TRADES (so ticker pages are written).
    """
    trades = [
        _trade(tx=f"2026-06-{day:02d}")
        for day in range(1, ld.TICKER_PAGE_MIN_TRADES + 6)
    ]
    with TemporaryDirectory() as tmp:
        out = Path(tmp)
        ld.write_files(trades, out, today=date(2026, 8, 1))
        members = ld.write_member_files(trades, {}, out,
                                        today_iso="2026-08-01")
        tickers = ld.write_ticker_files(trades, out)
        assert members, "fixture produced no member pages — test is not testing them"
        assert tickers, "fixture produced no ticker pages — test is not testing them"
        return {
            f"{LANDING_DATA}/{p.relative_to(out).as_posix()}"
            for p in out.rglob("*") if p.is_file()
        }


def staged_paths() -> set[str]:
    """Every path the workflow stages, from all its `git add` invocations.

    Handles the indirection: the commit step builds a FILES="..." variable and
    runs `git add $FILES`.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    variables = {
        name: value.split()
        for name, value in re.findall(r'^\s*(\w+)="([^"]*)"\s*$', text, re.M)
    }
    staged: set[str] = set()
    for args in re.findall(r"^\s*git add (.+)$", text, re.M):
        for token in args.split():
            if token.startswith("$"):
                staged.update(variables.get(token.lstrip("${").rstrip("}"), []))
            else:
                staged.add(token)
    return staged


def is_covered(path: str, staged: set[str]) -> bool:
    """A path is staged directly or via one of its parent directories."""
    candidate = Path(path)
    return any(
        str(parent) in staged for parent in (candidate, *candidate.parents)
    )


class TestWorkflowStagesGeneratedData(unittest.TestCase):
    def test_workflow_exists(self):
        self.assertTrue(WORKFLOW.exists(), f"missing {WORKFLOW}")

    def test_git_add_paths_are_parsed(self):
        # Guards the parser itself: if the workflow is restructured so no path
        # is found, every coverage assertion below would pass vacuously.
        staged = staged_paths()
        self.assertGreater(len(staged), 3)
        self.assertIn("docs/data/congress-trades.json", staged)

    def test_every_generated_landing_file_is_staged(self):
        staged = staged_paths()
        missing = sorted(
            p for p in generated_paths() if not is_covered(p, staged)
        )
        self.assertEqual(
            missing, [],
            "congress landing writes these, but the daily workflow never "
            "stages them, so the refresh is thrown away every run. Add them "
            f"to the commit step's FILES list in {WORKFLOW.name}: {missing}",
        )

    def test_ticker_pages_specifically(self):
        # The regression that prompted this test, named so a future reader
        # sees what it is protecting.
        self.assertTrue(
            is_covered(f"{LANDING_DATA}/tickers/nvda.json", staged_paths()),
            "landing/src/data/tickers is not staged by the daily workflow",
        )


class TestStagedPathsNotGitignored(unittest.TestCase):
    """A gitignored path in a `git add` fails the whole Action run.

    That is exactly how the report archive broke: the root .gitignore's
    Playwright rule ("reports/", unanchored) also matched
    landing/src/data/reports, `git add` refused it, the step exited 1, and
    every downstream step (prices, commit, verify) was skipped — while the
    verify guard itself was blind, because `git status` does not show
    ignored files. So check-ignore every staged path at test time.
    """

    def test_no_git_add_path_is_ignored(self):
        import subprocess
        staged = sorted(staged_paths())
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", *staged],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        # Exit 1 = nothing ignored (what we want); 0 = some path matched.
        ignored = result.stdout.strip().splitlines()
        self.assertEqual(
            ignored, [],
            "these workflow-staged paths are gitignored — git add will fail "
            f"the daily run: {ignored}",
        )
