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

Delivery is twofold: (1) **direct email via SMTP** (primary — reliable
regardless of GitHub notification settings; enabled by SMTP_USER/SMTP_PASS
secrets, e.g. a Gmail address + App Password), and (2) a **dated GitHub issue**
(archive + flip-diff state; assigned to the repo owner). It closes the previous
day's issue to keep the list tidy and records the issue number + the current
ratings in `congress/report_state.json` for tomorrow's diff.

Everything except the GitHub API and SMTP calls is pure stdlib (`smtplib` is
stdlib too); `build_report` is tested offline. Non-fatal by design — a failed
report must not fail the data refresh. Run as a module
(`python3 -m congress.daily_report`) so the package's `http.py` does not shadow
stdlib `http`.
"""

from __future__ import annotations

import json
import os
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
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


TRACKER_URL = "https://SDaian.github.io/crush-monitoring/trades.html"
# Read-label → email colour (green bull / red bear / grey hold).
_LABEL_COLOR = {
    "Strong Buy": "#0a7d33", "Buy": "#0a7d33",
    "Strong Sell": "#c0392b", "Sell": "#c0392b", "Hold": "#666",
}


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def build_report(trades: list[dict], ai_tickers: dict, new_signals: list[dict],
                 prev_ratings: dict, today_iso: str) -> dict:
    """Compose the digest in both markdown (GitHub issue) and HTML (email).
    Pure — no I/O. Returns ``{markdown, html, ratings, counts}`` where
    ``ratings`` is ticker→label for the next run's flip diff."""
    order = [s["ticker"] for s in indicators.AI_TICKERS if s["ticker"] in ai_tickers]
    order += sorted(tk for tk in ai_tickers if tk not in order)

    # --- Section 1: AI scorecard ---
    ratings: dict[str, str] = {}
    rows, html_rows = [], []
    for tk in order:
        t = ai_tickers[tk]
        sc = indicators.ai_score(t)
        ratings[tk] = sc["label"]
        price, chg = t.get("price", "—"), _pct(t.get("chg_1d"))
        rsi = "—" if t.get("rsi14") is None else round(t["rsi14"])
        trend = _trend(t)
        rows.append(
            f"| {tk} | ${price} | {chg} | {rsi} | {trend} | **{sc['label']}** |")
        color = _LABEL_COLOR.get(sc["label"], "#666")
        chg_color = "#0a7d33" if (t.get("chg_1d") or 0) > 0 else (
            "#c0392b" if (t.get("chg_1d") or 0) < 0 else "#666")
        html_rows.append(
            f"<tr><td style='padding:4px 8px'><b>{_esc(tk)}</b></td>"
            f"<td style='padding:4px 8px;text-align:right'>${_esc(price)}</td>"
            f"<td style='padding:4px 8px;text-align:right;color:{chg_color}'>{_esc(chg)}</td>"
            f"<td style='padding:4px 8px;text-align:right'>{_esc(rsi)}</td>"
            f"<td style='padding:4px 8px'>{_esc(trend)}</td>"
            f"<td style='padding:4px 8px;font-weight:700;color:{color}'>{_esc(sc['label'])}</td></tr>")
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
    sig_html = [
        f"<li><b>{_esc(s['ticker'])}</b> — {_esc(s.get('label', s.get('type', 'signal')))} "
        f"({_esc(s.get('asof', ''))})</li>"
        for s in (new_signals or [])
    ]
    flips, flips_html = [], []
    for tk, label in ratings.items():
        prev = prev_ratings.get(tk)
        if prev and prev != label:
            flips.append(f"- **{tk}** rating: {prev} → {label}")
            flips_html.append(
                f"<li><b>{_esc(tk)}</b>: {_esc(prev)} → "
                f"<span style='color:{_LABEL_COLOR.get(label, '#666')}'>{_esc(label)}</span></li>")
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
    disc_lines, disc_html = [], []
    for t in recent[:MAX_DISCLOSURES]:
        party = PARTY.get(t.get("party"))
        who = t.get("member", "?") + (f" ({party})" if party else "")
        name = t.get("ticker") or t.get("asset", "?")
        disc_lines.append(
            f"- {t.get('filing_date', '?')} · {who} · "
            f"**{name}** {t.get('type', '?')} · {t.get('amount_label', '—')}")
        disc_html.append(
            f"<li>{_esc(t.get('filing_date', '?'))} · {_esc(who)} · "
            f"<b>{_esc(name)}</b> {_esc(t.get('type', '?'))} · "
            f"{_esc(t.get('amount_label', '—'))}</li>")
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
        f"---\n_Full tracker: [AI stocks & trades]({TRACKER_URL})._"
    )

    # --- HTML email body ---
    def _ul(items, empty):
        return ("<ul>" + "".join(items) + "</ul>") if items else f"<p><i>{empty}</i></p>"
    table = ("<table style='border-collapse:collapse;font:13px system-ui,sans-serif'>"
             "<tr style='border-bottom:2px solid #ccc'>"
             + "".join(f"<th style='padding:4px 8px;text-align:left'>{h}</th>"
                       for h in ("Ticker", "Price", "1d", "RSI", "Trend", "Read"))
             + "</tr>" + "".join(html_rows) + "</table>") if html_rows else "<p><i>No indicator data.</i></p>"
    sig_block = ""
    if sig_html:
        sig_block += "<b>New signals</b>" + _ul(sig_html, "")
    if flips_html:
        sig_block += "<b>Rating changes</b>" + _ul(flips_html, "")
    if not sig_block:
        sig_block = "<p><i>No new signals or rating changes since yesterday.</i></p>"
    html = (
        "<div style='font:14px/1.5 system-ui,-apple-system,sans-serif;color:#222;max-width:720px'>"
        f"<p style='color:#666;font-size:12px'><i>{_esc(DISCLAIMER.replace('**', ''))}</i></p>"
        "<h2>🤖 AI stocks — technical read</h2>" + table +
        "<p style='color:#666;font-size:12px'>Read = a rule-based tally of the indicators "
        "(each votes buy/hold/sell), not a recommendation.</p>"
        "<h2>🔔 Signals overnight</h2>" + sig_block +
        f"<h2>🏛 New congressional disclosures <span style='font-weight:400;font-size:13px'>"
        f"(filed since {cutoff})</span></h2>" + _ul(disc_html, "No new disclosures in this window.") +
        f"<hr><p style='font-size:12px'>Full tracker: <a href='{TRACKER_URL}'>AI stocks &amp; trades</a></p></div>"
    )

    counts = {"tickers": len(rows), "new_signals": len(sig_lines),
              "flips": len(flips), "disclosures": len(recent)}
    return {"markdown": markdown, "html": html, "ratings": ratings, "counts": counts}


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


# --- Email (SMTP, stdlib) ------------------------------------------------

def send_email(subject: str, text_body: str, html_body: str) -> bool:
    """Send the report by SMTP if creds are configured, else no-op.

    Reads SMTP_USER / SMTP_PASS (required), SMTP_HOST (default smtp.gmail.com),
    SMTP_PORT (default 587 STARTTLS; 465 → implicit SSL) and REPORT_EMAIL_TO
    (default = SMTP_USER). Best-effort: returns False and warns on any failure
    so a mail outage never fails the refresh. Credentials come only from env
    (GitHub secrets) and are never logged.
    """
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()
    if not user or not password:
        print("SMTP_USER/SMTP_PASS not set — skipping email (issue still posted)")
        return False
    # GitHub renders undefined `vars.*` as empty strings, so fall back with `or`.
    host = os.environ.get("SMTP_HOST", "").strip() or "smtp.gmail.com"
    port = int(os.environ.get("SMTP_PORT", "").strip() or "587")
    to_addr = os.environ.get("REPORT_EMAIL_TO", "").strip() or user

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(),
                                  timeout=30) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(user, password)
                s.send_message(msg)
    except Exception as exc:  # noqa: BLE001 — best-effort, never fatal
        print(f"::warning::report email failed: {type(exc).__name__}")
        return False
    print(f"emailed report to {to_addr}")
    return True


def main() -> int:
    repo = os.environ.get("REPO") or os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if not repo or not token:
        print("no REPO / token — skipping morning report")
        return 0

    state = _load(STATE_JSON, {})
    today_iso = datetime.now(timezone.utc).date().isoformat()
    force = os.environ.get("REPORT_FORCE", "").strip().lower() in ("1", "true", "yes")
    # Idempotent per day: if a report was already posted today (e.g. an early
    # cron already ran), don't post a second — UNLESS forced (an explicit
    # on-demand send, which should always deliver).
    if not force and state.get("date") == today_iso and state.get("issue_number"):
        print(f"report already posted today (#{state['issue_number']}); skipping")
        return 0

    trades = _load(TRADES_JSON, {}).get("trades", [])
    ai = _load(AI_JSON, {})
    ai_tickers = ai.get("tickers", {})
    new_signals = ai.get("meta", {}).get("new_signals", [])
    prev_ratings = state.get("ratings", {})

    report = build_report(trades, ai_tickers, new_signals, prev_ratings, today_iso)
    title = f"📋 Morning report — {today_iso}"

    # Primary delivery: direct email via SMTP (reliable regardless of GitHub
    # notification settings). Best-effort — no-op if creds aren't configured.
    email_ok = send_email(title, report["markdown"], report["html"])

    # Secondary: a dated GitHub issue as an archive + the flip-diff state. Also
    # assign it to the repo owner (override REPORT_ASSIGNEE) so watchers/owners
    # are notified there too. Best-effort — a failure here must not lose state.
    assignee = os.environ.get("REPORT_ASSIGNEE") or repo.split("/")[0]
    new_number = None
    try:
        status, issue = _gh("POST", f"{API}/repos/{repo}/issues", token,
                            {"title": title, "body": report["markdown"],
                             "assignees": [assignee] if assignee else []})
        if 200 <= status < 300:
            new_number = issue.get("number")
            print(f"opened report issue #{new_number} ({report['counts']})")
        else:
            print(f"::warning::report issue POST returned {status}")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        print(f"::warning::report issue POST failed: {exc}")

    # Close yesterday's report issue so the list stays tidy (best-effort).
    prev_number = state.get("issue_number")
    if new_number and prev_number and prev_number != new_number:
        try:
            _gh("PATCH", f"{API}/repos/{repo}/issues/{prev_number}", token,
                {"state": "closed"})
            print(f"closed prior report issue #{prev_number}")
        except Exception as exc:  # noqa: BLE001 — best-effort
            print(f"::warning::could not close #{prev_number}: {exc}")

    if not (email_ok or new_number):
        # Nothing was delivered — don't record today as done, so the next run
        # retries rather than the idempotency gate skipping it.
        print("::warning::neither email nor issue delivered — not recording state")
        return 0
    STATE_JSON.write_text(
        json.dumps({"date": today_iso,
                    "issue_number": new_number or state.get("issue_number"),
                    "ratings": report["ratings"]},
                   separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
