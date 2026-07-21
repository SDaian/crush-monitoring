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

WINDOW_DAYS = 7          # traffic reported over a trailing week (steadier than 1 day)
TOP_PAGES = 5
TIMEOUT = 20            # seconds

# Response field-name candidates (Vercel's exact keys aren't in the public docs
# snapshot we could reach; match defensively and degrade to "no data").
_TOTAL_KEYS = ("total", "count", "value", "pageviews", "views", "visits")
_METRIC_KEYS = ("pageviews", "views", "total", "count", "visits", "value")
_KEY_KEYS = ("key", "requestPath", "path", "route", "value", "name")


def config() -> tuple[str, str, str]:
    """(token, projectId, teamId) from the environment; empty strings if unset."""
    return (
        os.environ.get(ENV_TOKEN, "").strip(),
        os.environ.get(ENV_PROJECT, "").strip(),
        os.environ.get(ENV_TEAM, "").strip(),
    )


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


def top_pages(payload: dict, limit: int = TOP_PAGES) -> list[tuple[str, int]]:
    """[(path, views), …] sorted by views desc, from an /aggregate?by=path body."""
    pairs = [(_row_key(r), _row_metric(r)) for r in parse_rows(payload)]
    pairs.sort(key=lambda p: p[1], reverse=True)
    return pairs[:limit]


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def format_block(summary: dict) -> tuple[str, str]:
    """(markdown, html) for the report's traffic section from a daily_summary."""
    total = summary.get("total")
    pages = summary.get("pages") or []
    days = summary.get("windowDays", WINDOW_DAYS)
    head = f"## 📈 Traffic — last {days} days"
    total_txt = f"{total:,} page views" if total is not None else "views unavailable"

    md = f"{head}\n\n**{total_txt}**"
    html = (f"<h2>📈 Traffic <span style='font-weight:400;font-size:13px'>"
            f"(last {days} days)</span></h2><p><b>{_esc(total_txt)}</b></p>")
    if pages:
        md += "\n\nTop pages:\n" + "\n".join(
            f"- `{p}` — {v:,}" for p, v in pages)
        html += "<ul>" + "".join(
            f"<li><code>{_esc(p)}</code> — {v:,}</li>" for p, v in pages) + "</ul>"
    return md, html


# --- orchestration (network) --------------------------------------------

def daily_summary(today_iso: str, window_days: int = WINDOW_DAYS) -> dict | None:
    """Fetch the trailing-window traffic summary, or ``None`` if analytics is
    not configured or the API is unreachable (the report skips the section)."""
    token, project_id, team_id = config()
    if not token or not project_id:
        return None
    until = today_iso
    since = (date.fromisoformat(today_iso) - timedelta(days=window_days)).isoformat()
    base = _base_params(project_id, team_id, since, until)
    try:
        total = parse_total(_fetch_json("visits/count", base, token))
        pages = top_pages(
            _fetch_json("visits/aggregate", {**base, "by": "path"}, token))
    except Exception:
        return None
    if total is None and not pages:
        return None
    return {
        "since": since, "until": until, "windowDays": window_days,
        "total": total, "pages": pages,
    }
