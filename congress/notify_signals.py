"""Open a GitHub issue for each brand-new AI technical signal.

Run by the daily Action *after* ``congress ai`` writes ai-indicators.json.
Reads ``meta.new_signals`` (signals fired this run that were not previously
emitted) and opens one GitHub issue per signal — which emails everyone
watching the repo. That is the "notification" channel: zero third-party
services, no server, no extra secret (uses the workflow's ``GITHUB_TOKEN``).

To avoid a burst (a market-wide move, or the very first run after the sample
file), more than ``CAP`` new signals collapse into a single summary issue.

Pure stdlib (urllib) so it needs no dependencies. Non-fatal by design: any
failure prints a warning and exits 0 — a missed alert must never fail the
data refresh, and the signals stay visible on the page regardless.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CAP = 8  # more new signals than this → one summary issue instead of a flood
AI_JSON = Path("docs/data/ai-indicators.json")
API = "https://api.github.com"

DISCLAIMER = (
    "This is a **mechanical technical signal** — a named event computed from "
    "past daily closes (a daily snapshot, not real-time). It is **not** a "
    "buy/sell/hold recommendation and **not** investment advice; it just "
    "reports that the event occurred. Draw your own conclusions."
)


def _page_url(repo: str) -> str:
    owner, _, name = repo.partition("/")
    return f"https://{owner}.github.io/{name}/trades.html"


def _post_issue(repo: str, token: str, title: str, body: str) -> bool:
    req = urllib.request.Request(
        f"{API}/repos/{repo}/issues",
        data=json.dumps({"title": title, "body": body}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "crush-monitoring-signal-notifier",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as exc:
        print(f"::warning::issue POST failed: HTTP {exc.code} {exc.reason}")
    except Exception as exc:  # noqa: BLE001 — best-effort, never fatal
        print(f"::warning::issue POST error: {exc}")
    return False


def _readings(tk: str, t: dict) -> str:
    def g(k):
        v = t.get(k)
        return "—" if v is None else v
    return (
        f"price ${g('price')}, 1-day {g('chg_1d')}%, RSI(14) {g('rsi14')}, "
        f"SMA50 ${g('sma50')}, SMA200 ${g('sma200')}, "
        f"52-week range ${g('low_52w')}–${g('high_52w')}"
    )


def main() -> int:
    repo = os.environ.get("REPO") or os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if not repo or not token:
        print("no REPO / token — skipping signal notification")
        return 0
    try:
        data = json.loads(AI_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"::warning::cannot read {AI_JSON}: {exc}")
        return 0

    new = data.get("meta", {}).get("new_signals") or []
    if not new:
        print("no new AI signals — nothing to notify")
        return 0

    tickers = data.get("tickers", {})
    page = _page_url(repo)

    if len(new) > CAP:
        lines = [
            f"- **{s['ticker']}** ({s.get('name', '')}): {s['label']} "
            f"— {_readings(s['ticker'], tickers.get(s['ticker'], {}))} "
            f"(as of {s['asof']})"
            for s in new
        ]
        body = (
            f"{len(new)} new technical signals fired on the latest session.\n\n"
            + "\n".join(lines)
            + f"\n\nSee the [AI stocks tab]({page}).\n\n---\n{DISCLAIMER}"
        )
        ok = _post_issue(repo, token, f"🔔 {len(new)} new AI signals", body)
        print(f"summary issue: {'ok' if ok else 'failed'}")
        return 0

    opened = 0
    for s in new:
        tk = s["ticker"]
        t = tickers.get(tk, {})
        title = f"🔔 {tk} — {s['label']} ({s['asof']})"
        body = (
            f"**{tk}** ({s.get('name', '')}) — {s['label']} on {s['asof']}.\n\n"
            f"Readings: {_readings(tk, t)}.\n\n"
            f"See the [AI stocks tab]({page}).\n\n---\n{DISCLAIMER}"
        )
        if _post_issue(repo, token, title, body):
            opened += 1
    print(f"opened {opened}/{len(new)} signal issue(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
