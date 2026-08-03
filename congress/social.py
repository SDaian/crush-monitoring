"""X/Twitter draft pipeline: notable new filings → card + copy → Typefully.

Pure logic lives here (selection, grouping, copy, state); the Typefully
client is ``typefully.py`` and the card renderer is ``scripts/render_card.mjs``
(Playwright screenshot of ``congress/social/card_template.html``). The CLI
entry is ``python3 -m congress social`` — see cli.py.

What gets posted (per the owner's decision): one draft per NEW filing that
clears the notability bar —

- the filer is a featured member (``landing_data.MEMBER_PAGE_NAMES``), OR
- any trade in the filing has a bracket floor >= $1M, OR
- any trade in the filing arrived more than 90 days past the 45-day deadline

— and the filing contains at least one tickered trade (pure-bond filings
have no headline symbol and are skipped). A filing with many rows becomes
ONE post headlined by its largest trade.

Dedup/state: ``congress/social_state.json`` maps record id (chamber:filing_id)
→ {drafted_at, draft_id}. A record enters the state ONLY after its draft is
created (or would have been, in dry-run it never enters), so failures retry
on the next run. The daily Action commits the state file; the repo's
workflow-path guards keep that honest.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from . import pipeline
from .landing_data import MEMBER_PAGE_NAMES, days_late

STATE_PATH = pipeline.REPO_ROOT / "congress" / "social_state.json"
TEMPLATE_DIR = pipeline.REPO_ROOT / "congress" / "social"
COPY_TEMPLATE = TEMPLATE_DIR / "copy_template.txt"

# Notability thresholds. BIG is the bracket FLOOR (amount_lo), so ">= $1M"
# means the filer disclosed at least the $1,000,001+ band.
BIG_TRADE_FLOOR = 1_000_001
VERY_LATE_DAYS = 90
# First-run backlog guard: never draft more than this per run unless
# overridden (--cap / SOCIAL_CAP). Truncation is always logged, never silent.
DEFAULT_CAP = 5

X_LIMIT = 280
# Every URL counts as 23 chars on X regardless of its real length.
TCO_LEN = 23

SENATE_PREFIX = "Sen. "
HOUSE_PREFIX = "Rep. "


def record_id(t: dict) -> str:
    """Stable id for the FILING a trade belongs to (chamber:filing_id)."""
    return f"{t.get('chamber', '?')}:{t.get('filing_id', '?')}"


def _fmt(iso: str | None, year: bool = True) -> str:
    if not iso:
        return "—"
    d = date.fromisoformat(iso)
    return d.strftime("%b %-d, %Y") if year else d.strftime("%b %-d")


def is_notable(rows: list[dict]) -> bool:
    member = rows[0].get("member")
    if member in MEMBER_PAGE_NAMES:
        return True
    if any((t.get("amount_lo") or 0) >= BIG_TRADE_FLOOR for t in rows):
        return True
    return any((days_late(t) or 0) > VERY_LATE_DAYS for t in rows)


def select_new_filings(trades: list[dict], state: dict) -> list[list[dict]]:
    """Group trades by filing, keep notable filings not yet in the state.

    Newest filings first (by filing_date), so a cap keeps the most current.
    """
    posted = set(state.get("records", {}))
    by_filing: dict[str, list[dict]] = {}
    for t in trades:
        by_filing.setdefault(record_id(t), []).append(t)
    picked = []
    for rid, rows in by_filing.items():
        if rid in posted:
            continue
        if not any(t.get("ticker") for t in rows):
            continue  # pure-bond filing: no headline symbol
        if not is_notable(rows):
            continue
        picked.append(rows)
    picked.sort(key=lambda rows: max(t.get("filing_date") or "" for t in rows),
                reverse=True)
    return picked


# ---------------------------------------------------------------------------
# Per-filing payload (feeds both the card and the copy)
# ---------------------------------------------------------------------------

def _headline_trade(rows: list[dict]) -> dict:
    """The largest tickered trade fronts the post."""
    tickered = [t for t in rows if t.get("ticker")]
    return max(tickered, key=lambda t: (t.get("amount_lo") or 0,
                                        t.get("tx_date") or ""))


def _who(t: dict) -> tuple[str, str]:
    """("Sen. Alan Armstrong", "R · OK") — executive filers get no prefix."""
    chamber = t.get("chamber")
    prefix = {"senate": SENATE_PREFIX, "house": HOUSE_PREFIX}.get(chamber, "")
    seat_geo = t.get("district") or t.get("state") or "US"
    return f"{prefix}{t.get('member', '?')}", f"{t.get('party') or '?'} · {seat_geo}"


def compact_amount(t: dict) -> str:
    label = t.get("amount_label") or "amount not stated"
    return label.replace(" - ", " – ")


def filing_payload(rows: list[dict]) -> dict:
    """Everything the card template and copy template need, precomputed."""
    head = _headline_trade(rows)
    who, seat = _who(head)
    late = max((days_late(t) or 0) for t in rows)
    action = {"buy": "Bought", "sell": "Sold"}.get(head.get("type"), "Traded")
    extra_n = len(rows) - 1
    return {
        "record_id": record_id(head),
        "member": head.get("member", "?"),
        "who": who,
        "seat": seat,
        "party_state": f"{head.get('party') or '?'}-{head.get('state') or 'US'}",
        "action": action,
        "ticker": head.get("ticker") or "—",
        "amount": compact_amount(head),
        "tx_date": head.get("tx_date"),
        "filed_date": head.get("filing_date"),
        "late_days": late,
        "extra_trades": extra_n,
        "source_url": head.get("source_url"),
    }


# ---------------------------------------------------------------------------
# Card HTML (template file + substitution — no markup in this module)
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def card_html(p: dict) -> str:
    tpl = (TEMPLATE_DIR / "card_template.html").read_text(encoding="utf-8")
    # Strip the template's documentation comment: it mentions the literal
    # placeholder names, which must not be substituted (or linger).
    tpl = re.sub(r"<!--.*?-->\n?", "", tpl, count=1, flags=re.S)
    # The generated HTML is written to the run's out-dir, not next to the
    # template — absolutize the font URLs so @font-face still resolves
    # (relative paths keep working when the template itself is opened for
    # design iteration).
    tpl = tpl.replace("url(fonts/", f"url({(TEMPLATE_DIR / 'fonts').as_uri()}/")
    late = p["late_days"]
    subs = {
        "DISCLOSED_LONG": f"Disclosed {_fmt(p['filed_date'])}",
        "WHO": _esc(p["who"]),
        "SEAT": _esc(p["seat"]),
        "ACTION": p["action"],
        "SIDE_CLASS": {"Bought": "side-buy", "Sold": "side-sell"}.get(
            p["action"], "side-neutral"),
        "TICKER": _esc(p["ticker"]),
        "AMOUNT": _esc(p["amount"]),
        "EXTRA": (f"+ {p['extra_trades']} more "
                  f"trade{'s' if p['extra_trades'] != 1 else ''} in this filing"
                  if p["extra_trades"] else ""),
        "TX_DATE": _fmt(p["tx_date"]),
        "FILED_DATE": _fmt(p["filed_date"]),
        "DEADLINE_HTML": (f"<b class='late'>missed by {late} days</b>"
                          if late else "<b>on time</b>"),
        "STAMP_HTML": (f"<div class='stampbox'>{late} days late</div>"
                       if late else ""),
    }
    for key, val in subs.items():
        tpl = tpl.replace("{{" + key + "}}", val)
    return tpl


# ---------------------------------------------------------------------------
# Post copy (template file; 280-char enforcement with graceful degradation)
# ---------------------------------------------------------------------------

def _copy_template() -> str:
    lines = [ln for ln in COPY_TEMPLATE.read_text(encoding="utf-8").splitlines()
             if not ln.startswith("#")]
    return "\n".join(lines).strip("\n")


def _x_len(text: str) -> int:
    """X counts every URL as TCO_LEN chars regardless of length."""
    n = len(text)
    for m in re.finditer(r"https?://\S+", text):
        n -= len(m.group()) - TCO_LEN
    return n


def post_copy(p: dict, include_link: bool = False) -> str:
    who_short = f"{p['who']} ({p['party_state']})"
    late_line = (f"Filed {p['late_days']} days past the legal 45-day deadline."
                 if p["late_days"] else "")
    link = ""
    if include_link and p["member"] in MEMBER_PAGE_NAMES:
        from .landing_data import slugify
        link = f"https://capitolledger.io/members/{slugify(p['member'])}"
    fields = {
        "who": who_short,
        "action": p["action"].lower(),
        "ticker": p["ticker"],
        "amount": p["amount"],
        "tx_date": _fmt(p["tx_date"], year=False),
        "filed_date": _fmt(p["filed_date"], year=False),
        "extra": (f" (+{p['extra_trades']} more trades in the same filing)"
                  if p["extra_trades"] else ""),
        "late_line": late_line,
        "link": link,
    }
    text = _copy_template().format(**fields)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if _x_len(text) > X_LIMIT and late_line:
        # Degrade: drop the late line first (the card still carries it).
        fields["late_line"] = ""
        text = re.sub(r"\n{3,}", "\n\n",
                      _copy_template().format(**fields)).strip()
    if _x_len(text) > X_LIMIT:
        raise ValueError(
            f"{p['record_id']}: copy is {_x_len(text)} chars even after "
            "degrading — refusing to draft a broken cut")
    return text


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def load_state(path: Path = STATE_PATH) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"records": {}}


def mark_drafted(state: dict, rid: str, draft_id) -> None:
    state.setdefault("records", {})[rid] = {
        "drafted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "draft_id": draft_id,
    }


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    payload = {
        "_comment": ("Which filings already have a Typefully draft — written "
                     "by `python3 -m congress social` (daily Action). Delete "
                     "an entry to re-draft that filing on the next run. Do "
                     "not hand-edit otherwise."),
        "records": dict(sorted(state.get("records", {}).items())),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
