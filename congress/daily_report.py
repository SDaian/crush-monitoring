"""Compose and deliver a morning digest as a GitHub issue (→ email).

Run by the daily Action after the data refresh (before the slow price step, so
it is timely and needs only the trades + AI files). It builds a short markdown
report with three sections:

  1. **AI stocks technical read** — the mechanical buy/hold/sell tally for each
     tracked ticker (from `indicators.ai_score`), with price / 1d / RSI / trend.
  2. **Signals overnight** — mechanical signals that fired on the latest bar
     (from `ai-indicators.json` meta.new_signals) plus any ticker whose
     buy/sell/hold rating flipped versus yesterday's report.
  3. **New congressional disclosures** — trades newly filed in the last few days.

It opens a dated GitHub issue (which emails repo watchers), closes the previous
day's report issue to keep the list tidy, and records the issue number + the
current ratings in `congress/report_state.json` for tomorrow's diff.

Everything except the GitHub API calls is pure stdlib; `build_report` is tested
offline. Non-fatal by design — a failed report must not fail the data refresh.
Run as a module (`python3 -m congress.daily_report`) so the package's `http.py`
does not shadow stdlib `http`.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import indicators, pipeline

API = "https://api.github.com"
TRADES_JSON = pipeline.REPO_ROOT / "docs" / "data" / "congress-trades.json"
AI_JSON = pipeline.REPO_ROOT / "docs" / "data" / "ai-indicators.json"
STATE_JSON = pipeline.REPO_ROOT / "congress" / "report_state.json"
DISCLOSURE_WINDOW_DAYS = 3
MAX_DISCLOSURES = 20
PARTY = {"D": "D", "R": "R", "I": "I"}
DISCLAIMER = (
    "Mechanical technical readings from past daily closes + official STOCK Act "
    "disclosures (30–45-day legal lag, bracketed amounts). **Not investment "
    "advice.**"
)


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _trend(t: dict) -> str:
    if t.get("sma50") is None or t.get("sma200") is None:
        return "—"
    return "50d›200d" if t["sma50"] >= t["sma200"] else "50d‹200d"


def _pct(x) -> str:
    if x is None:
        return "—"
    return f"{'+' if x > 0 else ''}{x}%"


def build_report(trades: list[dict], ai_tickers: dict, new_signals: list[dict],
                 prev_ratings: dict, today_iso: str) -> dict:
    """Compose the markdown digest. Pure — no I/O. Returns
    ``{markdown, ratings, counts}`` where ``ratings`` is ticker→label for the
    next run's flip diff."""
    order = [s["ticker"] for s in indicators.AI_TICKERS if s["ticker"] in ai_tickers]
    order += sorted(tk for tk in ai_tickers if tk not in order)

    # --- Section 1: AI scorecard ---
    ratings: dict[str, str] = {}
    rows = []
    for tk in order:
        t = ai_tickers[tk]
        sc = indicators.ai_score(t)
        ratings[tk] = sc["label"]
        rows.append(
            f"| {tk} | ${t.get('price', '—')} | {_pct(t.get('chg_1d'))} | "
            f"{'—' if t.get('rsi14') is None else round(t['rsi14'])} | "
            f"{_trend(t)} | **{sc['label']}** |"
        )
    scorecard = (
        "## 🤖 AI stocks — technical read\n\n"
        "| Ticker | Price | 1d | RSI | Trend | Read |\n"
        "|---|---|---|---|---|---|\n" + "\n".join(rows) +
        "\n\n_Read = a rule-based tally of the indicators (each votes "
        "buy/hold/sell), not a recommendation._"
    ) if rows else "## 🤖 AI stocks — technical read\n\n_No indicator data._"

    # --- Section 2: signals + rating flips ---
    sig_lines = [
        f"- **{s['ticker']}** — {s.get('label', s.get('type', 'signal'))} "
        f"({s.get('asof', '')})"
        for s in (new_signals or [])
    ]
    flips = []
    for tk, label in ratings.items():
        prev = prev_ratings.get(tk)
        if prev and prev != label:
            flips.append(f"- **{tk}** rating: {prev} → {label}")
    signals_md = "## 🔔 Signals overnight\n\n"
    if sig_lines or flips:
        if sig_lines:
            signals_md += "**New signals:**\n" + "\n".join(sig_lines) + "\n\n"
        if flips:
            signals_md += "**Rating changes:**\n" + "\n".join(flips) + "\n"
    else:
        signals_md += "_No new signals or rating changes since yesterday._\n"

    # --- Section 3: new congressional disclosures ---
    cutoff = (date.fromisoformat(today_iso) -
              timedelta(days=DISCLOSURE_WINDOW_DAYS)).isoformat()
    recent = [t for t in trades if (t.get("filing_date") or "") >= cutoff]
    recent.sort(key=lambda t: (t.get("filing_date", ""), t.get("tx_date", "")),
                reverse=True)
    disc_lines = []
    for t in recent[:MAX_DISCLOSURES]:
        party = PARTY.get(t.get("party"))
        who = t.get("member", "?") + (f" ({party})" if party else "")
        name = t.get("ticker") or t.get("asset", "?")
        disc_lines.append(
            f"- {t.get('filing_date', '?')} · {who} · "
            f"**{name}** {t.get('type', '?')} · {t.get('amount_label', '—')}"
        )
    disclosures_md = "## 🏛 New congressional disclosures " \
        f"(filed since {cutoff})\n\n"
    if disc_lines:
        disclosures_md += "\n".join(disc_lines) + "\n"
        if len(recent) > MAX_DISCLOSURES:
            disclosures_md += f"\n_…and {len(recent) - MAX_DISCLOSURES} more._\n"
    else:
        disclosures_md += "_No new disclosures in this window._\n"

    markdown = (
        f"_{DISCLAIMER}_\n\n"
        f"{scorecard}\n\n{signals_md}\n{disclosures_md}\n"
        "---\n_Full tracker: "
        "[AI stocks & trades](https://SDaian.github.io/crush-monitoring/trades.html)._"
    )
    counts = {"tickers": len(rows), "new_signals": len(sig_lines),
              "flips": len(flips), "disclosures": len(recent)}
    return {"markdown": markdown, "ratings": ratings, "counts": counts}


# --- GitHub API (network) ------------------------------------------------

def _gh(method: str, url: str, token: str, payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "crush-monitoring-morning-report",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, (json.loads(body) if body else {})


def main() -> int:
    repo = os.environ.get("REPO") or os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if not repo or not token:
        print("no REPO / token — skipping morning report")
        return 0

    trades = _load(TRADES_JSON, {}).get("trades", [])
    ai = _load(AI_JSON, {})
    ai_tickers = ai.get("tickers", {})
    new_signals = ai.get("meta", {}).get("new_signals", [])
    state = _load(STATE_JSON, {})
    prev_ratings = state.get("ratings", {})
    today_iso = datetime.now(timezone.utc).date().isoformat()

    report = build_report(trades, ai_tickers, new_signals, prev_ratings, today_iso)
    title = f"📋 Morning report — {today_iso}"

    try:
        status, issue = _gh("POST", f"{API}/repos/{repo}/issues", token,
                            {"title": title, "body": report["markdown"]})
        if not (200 <= status < 300):
            print(f"::warning::report issue POST returned {status}")
            return 0
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        print(f"::warning::report issue POST failed: {exc}")
        return 0
    new_number = issue.get("number")
    print(f"opened report issue #{new_number} ({report['counts']})")

    # Close yesterday's report issue so the list stays tidy (best-effort).
    prev_number = state.get("issue_number")
    if prev_number and prev_number != new_number:
        try:
            _gh("PATCH", f"{API}/repos/{repo}/issues/{prev_number}", token,
                {"state": "closed"})
            print(f"closed prior report issue #{prev_number}")
        except Exception as exc:  # noqa: BLE001 — best-effort
            print(f"::warning::could not close #{prev_number}: {exc}")

    STATE_JSON.write_text(
        json.dumps({"date": today_iso, "issue_number": new_number,
                    "ratings": report["ratings"]},
                   separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
