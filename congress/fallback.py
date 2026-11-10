"""Is the cron run needed? It is the FALLBACK, and only that.

A Raspberry Pi dispatches the daily workflow at 09:00 Europe/Madrid. The
workflow's own cron exists for the day the Pi is off. For months it ran the
whole job every day regardless: GitHub starts it 6 to 10 hours late (14:35 to
18:55 UTC over three weeks), so it was an afternoon run, not a fallback. On 12
of 15 days it changed nothing. On the two Mondays it found filings and sent
the "morning" report at eight in the evening, Madrid time.

So the cron run now asks the Actions API one question first: did the daily
run already succeed? The Pi's run is the workflow_dispatch whose run-name is
``DAILY_TITLE`` (the workflow sets it when ``scheduled=true``), on the same
branch. If one concluded with success inside ``MAX_AGE``, this run has nothing
to do and the refresh job is skipped.

The window is 20 hours, not "today": a cron delayed past midnight UTC must
still find the morning's run, or it would send the next day's report at 2am
and the 9am run would then skip it as already sent.

Fail OPEN, twice. Any error here prints a warning and answers "run"; and the
workflow runs the refresh job unless this step said ``run=false``, so a gate
that crashes cannot stop the daily job. A needless second run is harmless
(every step is idempotent); a missing fallback is the failure.

Network is confined to ``_fetch_runs`` (stdlib ``urllib``); the decision is
pure and tested offline. Run as ``python3 -m congress.fallback``.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.github.com"
WORKFLOW = "congress-trades.yml"
# The run-name the workflow gives the Pi's dispatch. tests/congress/
# test_fallback.py fails if the workflow file stops saying exactly this.
DAILY_TITLE = "Daily refresh"
MAX_AGE = timedelta(hours=20)


def _created(run: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(
            str(run.get("created_at", "")).replace("Z", "+00:00"))
    except ValueError:
        return None


def daily_run(runs: list[dict], now: datetime, branch: str) -> dict | None:
    """The daily run that already succeeded, or None. Pure.

    Every condition is checked here, whatever the API query filtered: the
    Pi's dispatch (by its run-name, never a manual one: a manual run sends no
    report), on ``branch`` (a test dispatch on another branch is not the
    product), concluded ``success``, and created inside ``MAX_AGE``.
    """
    for run in runs or []:
        created = _created(run)
        if (run.get("event") == "workflow_dispatch"
                and run.get("display_title") == DAILY_TITLE
                and run.get("head_branch") == branch
                and run.get("conclusion") == "success"
                and created is not None
                and timedelta(0) <= now - created < MAX_AGE):
            return run
    return None


def _fetch_runs(repo: str, branch: str, token: str) -> list[dict]:
    url = (f"{API}/repos/{repo}/actions/workflows/{WORKFLOW}/runs"
           f"?event=workflow_dispatch&branch={branch}&per_page=30")
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("workflow_runs", [])


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    found = None
    try:
        found = daily_run(_fetch_runs(repo, branch, token),
                          datetime.now(timezone.utc), branch)
    except Exception as exc:  # noqa: BLE001 — fail open: when unsure, run
        print(f"::warning::could not ask whether the daily run succeeded "
              f"({type(exc).__name__}: {exc}); running the fallback")
    if found:
        print(f"::notice::The daily run already succeeded "
              f"(#{found.get('run_number')}, {found.get('created_at')}). "
              f"The cron fallback has nothing to do.")
    else:
        print("No successful daily run in the last "
              f"{int(MAX_AGE.total_seconds() // 3600)} hours: "
              "the fallback runs the refresh.")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"run={'false' if found else 'true'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
