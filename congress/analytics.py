"""Vercel Web Analytics → the morning report's traffic block.

Pulls the site's aggregated, cookieless traffic (the same numbers the Vercel
dashboard shows) through Vercel's public Web Analytics API, so views land in
the daily email next to the trade digest.

Design:
- **Gated + non-fatal.** Needs the ``VERCEL_TOKEN`` secret (+ ``VERCEL_PROJECT_ID``,
  optional ``VERCEL_TEAM_ID``). Unset, or any API error, returns ``None`` and the
  report simply omits the traffic section — it never fails the run.
- **Network is confined to ``_fetch_json``** (stdlib ``urllib`` — no new deps);
  everything else is pure and offline-tested. The API response shape is parsed
  defensively (Vercel's field names are matched against a few candidates) so a
  minor shape change degrades to "no data" instead of a crash.

API (https://vercel.com/docs/analytics/web-analytics-api):
- count:     GET /v1/query/web-analytics/visits/count      → a single total
- aggregate: GET /v1/query/web-analytics/visits/aggregate  → rows grouped by `by`
  Auth: ``Authorization: Bearer <token>``; params: projectId, [teamId], since,
  until (ISO dates), and for aggregate ``by`` (path/country/referrer/day).
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import date, timedelta

API_BASE = "https://api.vercel.com/v1/query/web-analytics"
ENV_TOKEN = "VERCEL_TOKEN"
ENV_PROJECT = "VERCEL_PROJECT_ID"
ENV_TEAM = "VERCEL_TEAM_ID"

# Two reports, two windows. The daily one is noisy at this traffic level and
# the weekly one is the honest read; both ship because a spike is worth seeing
# the morning it happens, not the following Monday.
DAILY = "daily"
WEEKLY = "weekly"
PERIOD_DAYS = {DAILY: 1, WEEKLY: 7}

TOP_PAGES = 5
TIMEOUT = 20            # seconds

# The aggregate dimension for per-page rows. Confirmed against the live API:
# `route` (and `requestPath`) return 200; `path`/`page`/`pathname` return 400.
AGG_BY = "route"

# Response field names, confirmed live: count → data:{visitors, pageviews};
# aggregate → data:[{route, visitors, pageviews}]. Still matched against a few
# candidates so a minor shape change degrades to "no data" rather than crashing.
_TOTAL_KEYS = ("pageviews", "views", "total", "count", "value", "visits")
_METRIC_KEYS = ("pageviews", "views", "total", "count", "visits", "value")
_KEY_KEYS = ("route", "requestPath", "path", "key", "value", "name")


def config() -> tuple[str, str, str]:
    """(token, projectId, teamId) from the environment; empty strings if unset."""
    return (
        os.environ.get(ENV_TOKEN, "").strip(),
        os.environ.get(ENV_PROJECT, "").strip(),
        os.environ.get(ENV_TEAM, "").strip(),
    )


def window_bounds(kind: str, today_iso: str) -> tuple[tuple, tuple]:
    """((since, until), (prev_since, prev_until)) for a period and the one
    before it — adjacent, equal length, and never touching today.

    `until` is treated as EXCLUSIVE, which is what the existing call shape
    implies: it passed `until=today` for a window described as trailing, and
    today is still in progress. That matters because a partial day compared
    against a complete one invents a fall every morning.

    The assumption is not load-bearing for the comparison: both windows use
    identical arithmetic, so if the API reads the bound the other way, both
    shift by the same day and the delta between them still means what it says.
    """
    days = PERIOD_DAYS[kind]
    today = date.fromisoformat(today_iso)
    cur_until = today
    cur_since = today - timedelta(days=days)
    return (
        (cur_since.isoformat(), cur_until.isoformat()),
        ((cur_since - timedelta(days=days)).isoformat(), cur_since.isoformat()),
    )


def pct_delta(current, previous) -> float | None:
    """Percent change, or None when there is nothing honest to compare.

    None whenever a number is missing OR the baseline is zero: "+100%" off a
    zero week says nothing a reader can use, and the surfaces hide the delta
    rather than print it.
    """
    if current is None or previous is None or previous <= 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _base_params(project_id: str, team_id: str, since: str, until: str) -> dict:
    params = {"projectId": project_id, "since": since, "until": until}
    if team_id:
        params["teamId"] = team_id
    return params


def _fetch_json(path: str, params: dict, token: str) -> dict:
    """GET the API and return parsed JSON (network). Never log the URL with the
    token; the token rides in the Authorization header, not the query string."""
    url = f"{API_BASE}/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --- pure parsers (offline-tested) --------------------------------------

def _first_int(d: dict, keys) -> int | None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return int(v)
    return None


def parse_total(payload: dict) -> int | None:
    """Pull the single total from a /count response, tolerating a few shapes:
    ``{"total": N}``, ``{"data": {"total": N}}``, ``{"data": [{"total": N}]}``."""
    if not isinstance(payload, dict):
        return None
    direct = _first_int(payload, _TOTAL_KEYS)
    if direct is not None:
        return direct
    data = payload.get("data")
    if isinstance(data, dict):
        return _first_int(data, _TOTAL_KEYS)
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return _first_int(data[0], _TOTAL_KEYS)
    return None


def parse_rows(payload: dict) -> list[dict]:
    """The list of grouped rows from an /aggregate response (``data``)."""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        return [r for r in data["rows"] if isinstance(r, dict)]
    return []


def _row_key(row: dict) -> str:
    for k in _KEY_KEYS:
        v = row.get(k)
        if isinstance(v, str) and v:
            return v
    return "—"


def _row_metric(row: dict) -> int:
    return _first_int(row, _METRIC_KEYS) or 0


def _all_page_views(payload: dict) -> list[tuple[str, int]]:
    """[(route, views), …] for every row, sorted by views desc."""
    pairs = [(_row_key(r), _row_metric(r)) for r in parse_rows(payload)]
    pairs.sort(key=lambda p: p[1], reverse=True)
    return pairs


def top_pages(payload: dict, limit: int = TOP_PAGES) -> list[tuple[str, int]]:
    """[(route, views), …] sorted by views desc, limited to the top ``limit``."""
    return _all_page_views(payload)[:limit]


def member_slug(route: str) -> str | None:
    """"/members/nancy-pelosi" → "nancy-pelosi"; None for the index or non-member
    routes. Trailing slashes and query strings are tolerated."""
    if not isinstance(route, str):
        return None
    path = route.split("?", 1)[0].rstrip("/")
    prefix = "/members/"
    if not path.startswith(prefix):
        return None
    slug = path[len(prefix):]
    return slug or None  # "/members" (index) → "" → None


def prettify_slug(slug: str) -> str:
    """"nancy-pelosi" → "Nancy Pelosi" (fallback when no real name is known)."""
    return " ".join(w.capitalize() for w in slug.split("-"))


def member_page_views(payload: dict) -> list[tuple[str, int]]:
    """[(slug, views), …] for the /members/<slug> routes, sorted by views desc."""
    out = []
    for route, views in _all_page_views(payload):
        slug = member_slug(route)
        if slug:
            out.append((slug, views))
    return out


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def period_label(summary: dict) -> str:
    """"yesterday" / "last 7 days" — what the window actually covers."""
    return ("yesterday" if summary.get("windowDays") == 1
            else f"last {summary.get('windowDays', 7)} days")


def delta_text(current, previous) -> str:
    """" (+18% vs the previous week)" — or "" when there is no baseline.

    An absent comparison prints nothing at all. A reader who sees a delta on
    one line and none on the next learns that we could not compare that one,
    which is true; a "+100%" off a zero baseline would be noise dressed as a
    fact (owner request, 2026-09-10).
    """
    pct = pct_delta(current, previous)
    if pct is None:
        return ""
    return f" ({pct:+.1f}%)"


def _lookup(rows, key):
    """The metric for `key` in a [(key, value)] list, or None if absent."""
    for k, v in rows or []:
        if k == key:
            return v
    return None


def format_block(summary: dict, member_names: dict | None = None) -> tuple[str, str]:
    """(markdown, html) for a traffic email from a ``period_summary`` dict.
    ``member_names`` maps slug→display name for the member-page breakdown; any
    missing slug falls back to a prettified slug."""
    total = summary.get("total")
    pages = summary.get("pages") or []
    member_pages = summary.get("memberPages") or []
    prev = summary.get("previous") or {}
    window = period_label(summary)
    against = ("the day before" if summary.get("windowDays") == 1
               else "the previous week")
    names = member_names or {}

    head = f"## 📈 Traffic — {window}"
    total_txt = f"{total:,} page views" if total is not None else "views unavailable"
    total_d = delta_text(total, prev.get("total"))
    # The comparison is named once, on the total, rather than repeated on
    # every row — the per-row percentages then read as the same comparison.
    vs = f" vs {against}" if total_d else ""

    md = f"{head}\n\n**{total_txt}{total_d}{vs}**"
    html = (f"<h2>📈 Traffic <span style='font-weight:400;font-size:13px'>"
            f"({_esc(window)})</span></h2><p><b>{_esc(total_txt)}"
            f"{_esc(total_d)}{_esc(vs)}</b></p>")
    if pages:
        md += "\n\nTop pages:\n" + "\n".join(
            f"- `{p}` — {v:,}{delta_text(v, _lookup(prev.get('pages'), p))}"
            for p, v in pages)
        html += "<ul>" + "".join(
            f"<li><code>{_esc(p)}</code> — {v:,}"
            f"{_esc(delta_text(v, _lookup(prev.get('pages'), p)))}</li>"
            for p, v in pages) + "</ul>"
    if member_pages:
        def label(slug):
            return names.get(slug) or prettify_slug(slug)
        md += "\n\nMember pages:\n" + "\n".join(
            f"- {label(s)} — {v:,}"
            f"{delta_text(v, _lookup(prev.get('memberPages'), s))}"
            for s, v in member_pages)
        html += ("<p style='margin:8px 0 2px'><b>Member pages</b></p><ul>"
                 + "".join(
                     f"<li>{_esc(label(s))} — {v:,}"
                     f"{_esc(delta_text(v, _lookup(prev.get('memberPages'), s)))}"
                     "</li>"
                     for s, v in member_pages) + "</ul>")
    return md, html


# --- orchestration (network) --------------------------------------------

def _fetch_window(since, until, token, project_id, team_id) -> dict | None:
    """One window's numbers, or None when neither endpoint answered.

    The total and the per-page rows are fetched independently: a failure in one
    (a plan limit on aggregate, say) must not discard the other.
    """
    base = _base_params(project_id, team_id, since, until)
    total = None
    try:
        total = parse_total(_fetch_json("visits/count", base, token))
    except Exception:
        pass
    pages: list[tuple[str, int]] = []
    member_pages: list[tuple[str, int]] = []
    try:
        agg = _fetch_json("visits/aggregate", {**base, "by": AGG_BY}, token)
        pages = top_pages(agg)
        member_pages = member_page_views(agg)
    except Exception:
        pass
    if total is None and not pages:
        return None
    return {"since": since, "until": until, "total": total,
            "pages": pages, "memberPages": member_pages}


def period_summary(kind: str, today_iso: str) -> dict | None:
    """A period's traffic plus the period before it, or ``None`` when analytics
    is not configured or the API is unreachable (the report skips the email).

    The previous window is best-effort on its own: losing it costs the deltas,
    never the report. `previous` is None then, and every surface hides the
    comparison rather than printing a number it cannot stand behind.
    """
    token, project_id, team_id = config()
    if not token or not project_id:
        return None
    (since, until), (prev_since, prev_until) = window_bounds(kind, today_iso)
    current = _fetch_window(since, until, token, project_id, team_id)
    if current is None:
        return None
    previous = _fetch_window(prev_since, prev_until, token, project_id, team_id)
    return {
        "kind": kind,
        "windowDays": PERIOD_DAYS[kind],
        "since": since, "until": until,
        "total": current["total"],
        "pages": current["pages"],
        "memberPages": current["memberPages"],
        "previous": previous,
    }
