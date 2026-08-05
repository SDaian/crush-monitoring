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
MEMBERS_DATA_DIR = pipeline.REPO_ROOT / "landing" / "src" / "data" / "members"
TEMPLATE_DIR = pipeline.REPO_ROOT / "congress" / "social"
COPY_TEMPLATE = TEMPLATE_DIR / "copy_template.txt"
# Official portraits, committed per featured member as <slug>.jpg/.png
# (they are U.S. government works — public domain). A member without a
# file simply gets the no-portrait layout.
PORTRAITS_DIR = TEMPLATE_DIR / "portraits"

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


def focus_rows(rows: list[dict], focus: list[str] | None) -> list[dict]:
    """The rows a FOCUSED post is about (``--focus BWXT,ENTG``). A 60-row
    filing holds many stories and the largest-bracket auto-pick chooses
    only one; this lets the owner aim a post at the names that matter.
    Returns [] when no focus is given or nothing matches — the caller then
    falls back to the whole filing (normal behaviour)."""
    if not focus:
        return []
    want = {t.strip().upper() for t in focus if t.strip()}
    return [t for t in rows if (t.get("ticker") or "").upper() in want]


def _combined_action(rows: list[dict]) -> str:
    kinds = {t.get("type") for t in rows}
    return {frozenset({"buy"}): "Bought",
            frozenset({"sell"}): "Sold"}.get(frozenset(kinds), "Traded")


def _summed_amount(rows: list[dict]) -> str:
    """Brackets cannot be added into ONE number, but they can be added into
    a range: the true total lies between the sum of the floors and the sum
    of the ceilings. That is a fact about the filing — unlike a midpoint,
    which is an estimate."""
    lo = sum(t.get("amount_lo") or 0 for t in rows)
    hi = sum(t.get("amount_hi") or t.get("amount_lo") or 0 for t in rows)
    return f"${lo:,} – ${hi:,}"


def _date_span(rows: list[dict]) -> tuple[str, str]:
    """(long, short) trade-date labels — a span when the rows straddle days.
    Within one month the month is not repeated ("Jul 8–30, 2026"): the card's
    meta strip is tight, and the repetition reads as noise."""
    dates = sorted(d for d in (t.get("tx_date") for t in rows) if d)
    if not dates:
        return "—", "—"
    first, last = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
    if first == last:
        return _fmt(dates[0]), _fmt(dates[0], year=False)
    if (first.year, first.month) == (last.year, last.month):
        return (f"{first.strftime('%b %-d')}–{last.strftime('%-d, %Y')}",
                f"{first.strftime('%b %-d')}–{last.strftime('%-d')}")
    return (f"{_fmt(dates[0], year=False)} – {_fmt(dates[-1])}",
            f"{_fmt(dates[0], year=False)}–{_fmt(dates[-1], year=False)}")


# Headline auto-fit. The headline is one clamped line, so a long label
# ("Bought BWXT + ENTG") must shrink rather than ellipsis away. Libre
# Franklin 900 with -3px tracking averages ~0.56em per character; the
# usable width is the card minus padding, minus the portrait column when
# one is present.
HEADLINE_STEPS = (108, 88, 74, 62)


def headline_px(text: str, has_portrait: bool) -> int:
    usable = (1600 - 660 - 72) if has_portrait else (1600 - 144)
    for size in HEADLINE_STEPS:
        if len(text) * size * 0.56 <= usable:
            return size
    return HEADLINE_STEPS[-1]


def _who(t: dict) -> tuple[str, str]:
    """("Sen. Alan Armstrong", "R · OK") — executive filers get no prefix."""
    chamber = t.get("chamber")
    prefix = {"senate": SENATE_PREFIX, "house": HOUSE_PREFIX}.get(chamber, "")
    seat_geo = t.get("district") or t.get("state") or "US"
    return f"{prefix}{t.get('member', '?')}", f"{t.get('party') or '?'} · {seat_geo}"


def compact_amount(t: dict) -> str:
    label = t.get("amount_label") or "amount not stated"
    return label.replace(" - ", " – ")


def holdings_context(member: str, ticker: str,
                     data_dir: Path = MEMBERS_DATA_DIR) -> dict | None:
    """The narrative hook, honestly: what this member ALREADY holds of the
    headline ticker, from the rolled-forward estimated holdings that power
    their member page (annual report + every trade filed since; bracket
    midpoints, so always "~" and "estimated"). None when the member has no
    page, no parsed holdings, or no position in the ticker — the post simply
    runs without the context line."""
    if member not in MEMBER_PAGE_NAMES:
        return None
    from .landing_data import slugify
    try:
        page = json.loads((data_dir / f"{slugify(member)}.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    holdings = page.get("holdings") or {}
    if not holdings.get("available"):
        return None
    for stock in holdings.get("stocks", []):
        if stock.get("ticker") == ticker:
            return {"est": stock.get("estLabel"),
                    "pct": stock.get("pctPortfolio")}
    return None


def ticker_stats(trades: list[dict], ticker: str, year: str) -> dict | None:
    """The ticker across Congress: how many members disclosed how many
    trades of this symbol in ``year`` (by trade date), split buy/sell.
    Powers the card's stats band — one filing becomes a pattern."""
    if not ticker:
        return None
    rows = [t for t in trades
            if t.get("ticker") == ticker
            and (t.get("tx_date") or "").startswith(year)]
    if not rows:
        return None
    return {
        "members": len({t.get("member") for t in rows}),
        "trades": len(rows),
        "buys": sum(1 for t in rows if t.get("type") == "buy"),
        "sells": sum(1 for t in rows if t.get("type") == "sell"),
        "year": year,
    }


def filing_payload(rows: list[dict],
                   context: dict | None = None,
                   stats: dict | None = None,
                   focus: list[str] | None = None) -> dict:
    """Everything the card template and copy template need, precomputed.
    ``context`` is ``holdings_context()``'s answer for the headline ticker
    and ``stats`` is ``ticker_stats()``'s (the caller looks both up so
    this stays pure). ``focus`` narrows the post to named tickers — one
    post about the two names that matter instead of the auto-picked
    largest bracket in a 60-row filing."""
    matched = focus_rows(rows, focus)
    subject = matched or rows
    head = _headline_trade(subject)
    who, seat = _who(head)
    late = max((days_late(t) or 0) for t in rows)
    if len(matched) > 1:
        # Ordered by bracket floor so the biggest name leads the headline.
        ordered = sorted(subject, key=lambda t: (t.get("amount_lo") or 0),
                         reverse=True)
        tickers = list(dict.fromkeys(t["ticker"] for t in ordered
                                     if t.get("ticker")))
        ticker_label = " + ".join(tickers)
        cashtags = " and ".join(f"${t}" for t in tickers)
        action = _combined_action(subject)
        noun = {"Bought": "buy", "Sold": "sale"}.get(action, "trade")
        n = len(subject)
        amount = (f"{_summed_amount(subject)} across {n} "
                  f"{noun if n == 1 else noun + 's'}")
        tx_long, tx_short = _date_span(subject)
        # Two companies have no single name; one ticker bought repeatedly
        # keeps its company line.
        company = head.get("asset", "") if len(tickers) == 1 else ""
    else:
        ticker_label = head.get("ticker") or "—"
        cashtags = f"${ticker_label}"
        action = {"buy": "Bought", "sell": "Sold"}.get(head.get("type"),
                                                       "Traded")
        amount = compact_amount(head)
        tx_long, tx_short = _fmt(head.get("tx_date")), _fmt(
            head.get("tx_date"), year=False)
        company = head.get("asset") or ""
    return {
        "record_id": record_id(head),
        "member": head.get("member", "?"),
        "who": who,
        "seat": seat,
        "party_state": f"{head.get('party') or '?'}-{head.get('state') or 'US'}",
        "action": action,
        "ticker": ticker_label,
        "primary_ticker": head.get("ticker") or "—",
        "cashtags": cashtags,
        "company": company,
        "amount": amount,
        "tx_date": head.get("tx_date"),
        "tx_label": tx_long,
        "tx_short": tx_short,
        "filed_date": head.get("filing_date"),
        "late_days": late,
        # A normal post is about ONE trade (the headline) however many rows
        # the filing has; a focused post covers all its matched rows.
        "subject_trades": len(matched) if len(matched) > 1 else 1,
        "extra_trades": len(rows) - (len(matched) if len(matched) > 1 else 1),
        "source_url": head.get("source_url"),
        "held_est": (context or {}).get("est"),
        "held_pct": (context or {}).get("pct"),
        "stats": stats,
        "portrait": portrait_path(head.get("member", "")),
    }


# ---------------------------------------------------------------------------
# Card HTML (template file + substitution — no markup in this module)
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def portrait_path(member: str,
                  portraits_dir: Path = PORTRAITS_DIR) -> Path | None:
    """The member's committed official portrait, or None."""
    from .landing_data import slugify
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = portraits_dir / f"{slugify(member)}.{ext}"
        if p.is_file():
            return p
    return None


def _portrait_html(p: dict) -> str:
    path = p.get("portrait")
    if not path:
        return ""
    return (f"<div class='portrait'><img src='{Path(path).as_uri()}'>"
            f"<div class='credit'>Official portrait · public domain</div>"
            f"</div>")


def _stats_html(p: dict) -> str:
    s = p.get("stats")
    if not s:
        return ""
    members = f"{s['members']} member{'s' if s['members'] != 1 else ''}"
    have = "have" if s["members"] != 1 else "has"
    trades = f"{s['trades']} trade{'s' if s['trades'] != 1 else ''}"
    split = (f" — <b class='up'>{s['buys']} "
             f"buy{'s' if s['buys'] != 1 else ''}</b> / "
             f"<b class='down'>{s['sells']} "
             f"sell{'s' if s['sells'] != 1 else ''}</b>"
             if s["trades"] > 1 else "")
    return (f"<div class='stats'>"
            f"<div class='k'>"
            f"{_esc(p.get('primary_ticker') or p['ticker'])} in Congress · "
            f"{_esc(s['year'])}</div>"
            f"<div class='v'><b>{members}</b> {have} disclosed "
            f"<b>{trades}</b>{split}</div>"
            f"</div>")


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
        "HEADLINE_PX": str(headline_px(f"{p['action']} {p['ticker']}",
                                       bool(p.get("portrait")))),
        "TICKER": _esc(p["ticker"]),
        "COMPANY": _esc(p.get("company") or ""),
        "STATS_HTML": _stats_html(p),
        "CARD_CLASS": "has-portrait" if p.get("portrait") else "",
        "PORTRAIT_HTML": _portrait_html(p),
        "EXTRA": (f"+ {p['extra_trades']} more "
                  f"trade{'s' if p['extra_trades'] != 1 else ''} in this filing"
                  if p["extra_trades"] else ""),
        "CONTEXT": (
            f"Already holds ~{p['held_est']} of "
            f"{_esc(p.get('primary_ticker') or p['ticker'])}"
            + (f" — {p['held_pct']}% of their estimated portfolio"
               if p.get("held_pct") is not None else "")
            if p.get("held_est") else ""),
        "TX_DATE": p.get("tx_label") or _fmt(p["tx_date"]),
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
    """X counts every URL as TCO_LEN chars regardless of length, and
    weights emoji (astral-plane code points, e.g. 🚨) as 2."""
    n = len(text)
    for m in re.finditer(r"https?://\S+", text):
        n -= len(m.group()) - TCO_LEN
    n += sum(1 for c in text if ord(c) > 0xFFFF)
    return n


def post_copy(p: dict, include_link: bool = True) -> str:
    who_short = f"{p['who']} ({p['party_state']})"
    late_line = (f"Filed {p['late_days']} days past the legal 45-day deadline."
                 if p["late_days"] else "")
    context_line = ""
    if p.get("held_est"):
        context_line = ("Already holds ~"
                        f"{p['held_est']} of "
                        f"${p.get('primary_ticker') or p['ticker']}")
        if p.get("held_pct") is not None:
            context_line += f" — {p['held_pct']}% of their estimated portfolio"
        context_line += "."
    link = ""
    if include_link and p["member"] in MEMBER_PAGE_NAMES:
        from .landing_data import slugify
        link = ("🔗 https://capitolledger.io/members/"
                f"{slugify(p['member'])}")
    fields = {
        "who": who_short,
        "action": p["action"].lower(),
        "ticker": p["ticker"],
        "cashtags": p.get("cashtags") or f"${p['ticker']}",
        "amount": p["amount"],
        "tx_date": p.get("tx_short") or _fmt(p["tx_date"], year=False),
        "filed_date": _fmt(p["filed_date"], year=False),
        "extra": (f" (+{p['extra_trades']} more trades in the same filing)"
                  if p["extra_trades"] else ""),
        "context_line": context_line,
        "late_line": late_line,
        "link": link,
    }

    def render() -> str:
        return re.sub(r"\n{3,}", "\n\n",
                      _copy_template().format(**fields)).strip()

    text = render()
    # Degradation order: the context estimate goes first (nice-to-have),
    # then the late line (the card still stamps it); never a broken cut.
    if _x_len(text) > X_LIMIT and context_line:
        fields["context_line"] = ""
        text = render()
    if _x_len(text) > X_LIMIT and late_line:
        fields["late_line"] = ""
        text = render()
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
