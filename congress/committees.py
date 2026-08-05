"""Committee assignments — where each member sits.

A trade tells you what a member bought; the committee tells you what they
oversee while buying it. We publish BOTH as facts and let the reader draw
the line: this module never asserts that a seat explains a trade.

Source: the ``unitedstates/congress-legislators`` open dataset (the same
project the roster comes from), which publishes
``committee-membership-current.json`` (bioguide → committee codes) and
``committees-current.json`` (codes → names, urls, subcommittees).

Joins are by **bioguide id, never by name**: the roster contains both a
"Lisa C. McClain" and an "April McClain Delaney", and substring matching
crosses them. ``roster`` gained a ``bioguide`` field for exactly this.

Network lives in ``fetch_raw``; everything else is pure and offline-tested.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import pipeline

BASE = ("https://raw.githubusercontent.com/unitedstates/"
        "congress-legislators/gh-pages")
MEMBERSHIP_URL = f"{BASE}/committee-membership-current.json"
COMMITTEES_URL = f"{BASE}/committees-current.json"

OUTPUT_PATH = pipeline.REPO_ROOT / "docs" / "data" / "committees.json"

REASON_ASSIGNED = "assigned"
REASON_NONE_CURRENT = "none_current"
REASON_FORMER_MEMBER = "former_member"
REASON_NOT_IN_CONGRESS = "not_in_congress"
REASON_UNMATCHED = "unmatched"

#: Reasons that mean "we could not look it up", as opposed to a true zero.
#: A sitting member with no seats (a Speaker Emerita) genuinely has none —
#: flagging that as a gap would be wrong, exactly as with holdings.
NEEDS_REVIEW = frozenset({REASON_UNMATCHED})

REASON_TEXT = {
    REASON_ASSIGNED: "assigned",
    REASON_NONE_CURRENT: "sitting member with no current committee seats",
    REASON_FORMER_MEMBER: "not listed as a sitting member — the committee "
                          "file covers sitting members only",
    REASON_NOT_IN_CONGRESS: "executive-branch filer — committees do not apply",
    REASON_UNMATCHED: "no bioguide id on the roster entry — cannot join",
}


def classify(*, chamber: str | None, bioguide: str | None,
             sitting: bool, seats: int) -> str:
    """Why does this member have `seats` committees? Pure, so it is tested.

    The four zeroes are four different facts and must not collapse into one
    blank: an executive filer has no committees by definition, a former
    member's seats are simply not in a *current* file, a sitting member can
    genuinely hold none, and a missing bioguide is our own coverage gap.
    """
    if chamber == "executive":
        return REASON_NOT_IN_CONGRESS
    # Former members are checked BEFORE the bioguide: the roster only gets
    # ids from the sitting-members file, so someone who has left Congress
    # has no id — reporting that as our coverage gap would be wrong.
    if not sitting:
        return REASON_FORMER_MEMBER
    if not bioguide:
        return REASON_UNMATCHED
    return REASON_ASSIGNED if seats else REASON_NONE_CURRENT


def short_name(name: str) -> str:
    """"House Committee on Science, Space, and Technology" → "House Science,
    Space & Technology" — the official strings are too long for a card or a
    tweet. Mechanical only: no renaming, no editorialising."""
    out = name
    for chamber in ("House", "Senate"):
        for pattern in (f"{chamber} Committee on ",
                        f"{chamber} Permanent Select Committee on ",
                        f"{chamber} Select Committee on ",
                        f"{chamber} Special Committee on "):
            if out.startswith(pattern):
                out = f"{chamber} {out[len(pattern):]}"
                break
    return out.replace(", and ", " & ").replace(" and ", " & ")


def index_committees(committees: list[dict]) -> tuple[dict, dict]:
    """(full committees by code, subcommittees by parent+code)."""
    full, subs = {}, {}
    for c in committees:
        code = c.get("thomas_id")
        if not code:
            continue
        full[code] = c
        for s in c.get("subcommittees", []):
            subs[code + s.get("thomas_id", "")] = (code, s)
    return full, subs


def seats_for(bioguide: str | None, membership: dict,
              full: dict, subs: dict) -> list[dict]:
    """Every committee this member sits on, subcommittees nested under their
    parent. Codes we cannot resolve are dropped rather than guessed."""
    if not bioguide:
        return []
    by_code: dict[str, dict] = {}
    pending_subs: list[tuple[str, dict, str | None]] = []
    for code, members in membership.items():
        for m in members:
            if m.get("bioguide") != bioguide:
                continue
            title = m.get("title")
            if code in full:
                by_code.setdefault(code, {
                    "id": code,
                    "name": full[code]["name"],
                    "shortName": short_name(full[code]["name"]),
                    "url": full[code].get("url"),
                    "title": title,
                    "subcommittees": [],
                })
                if title:
                    by_code[code]["title"] = title
            elif code in subs:
                parent_code, sub = subs[code]
                pending_subs.append((parent_code, sub, title))
    for parent_code, sub, title in pending_subs:
        parent = by_code.get(parent_code)
        if parent is None:
            # Serving on a subcommittee without the parent listed happens;
            # surface the parent so the seat is not silently dropped.
            if parent_code not in full:
                continue
            parent = by_code.setdefault(parent_code, {
                "id": parent_code,
                "name": full[parent_code]["name"],
                "shortName": short_name(full[parent_code]["name"]),
                "url": full[parent_code].get("url"),
                "title": None,
                "subcommittees": [],
            })
        parent["subcommittees"].append(
            {"name": sub.get("name"), "title": title})
    for c in by_code.values():
        c["subcommittees"].sort(key=lambda s: s.get("name") or "")
    return sorted(by_code.values(), key=lambda c: c["name"])


def build(roster: list[dict], membership: dict,
          committees: list[dict], sitting_bioguides: set[str]) -> dict:
    """The generated committees.json payload: one record per roster member."""
    full, subs = index_committees(committees)
    members = {}
    for m in roster:
        bioguide = m.get("bioguide")
        seats = seats_for(bioguide, membership, full, subs)
        # Two independent signals: the roster's own flag (set when an entry
        # survives a refresh that no longer lists the member), and — only
        # when we HAVE an id — whether that id is in the sitting file. A
        # missing id must fall through to `unmatched`, not to "former".
        sitting = (m.get("sitting", True)
                   and (not bioguide or bioguide in sitting_bioguides))
        reason = classify(chamber=m.get("chamber"), bioguide=bioguide,
                          sitting=sitting, seats=len(seats))
        if reason != REASON_ASSIGNED:
            seats = []
        members[m["name"]] = {
            "bioguide": bioguide,
            "chamber": m.get("chamber"),
            "committees": seats,
            "reason": reason,
        }
    return {
        "_comment": ("Committee seats per member, joined by bioguide id from "
                     "the unitedstates/congress-legislators dataset. "
                     "GENERATED by `python3 -m congress committees` — do not "
                     "hand-edit. `reason` says why a member has no seats; the "
                     "four zeroes are four different facts."),
        "source": MEMBERSHIP_URL,
        "members": members,
    }


def fetch_raw(session) -> tuple[dict, list, list]:
    """(membership, committees, legislators) — the only network in here."""
    from .http import polite_get

    membership = polite_get(session, MEMBERSHIP_URL).json()
    committees = polite_get(session, COMMITTEES_URL).json()
    legislators = polite_get(
        session, f"{BASE}/legislators-current.json").json()
    return membership, committees, legislators


def sitting_ids(legislators: list[dict]) -> set[str]:
    """Bioguide ids of members currently serving — the file lists only them,
    so absence is what distinguishes a former member from a seatless one."""
    out = set()
    for leg in legislators:
        bioguide = (leg.get("id") or {}).get("bioguide")
        if bioguide:
            out.add(bioguide)
    return out


def save(payload: dict, path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def load(path: Path = OUTPUT_PATH) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"members": {}}


def for_member(name: str, data: dict | None = None) -> dict:
    """A member's record, defaulting to 'unmatched' when absent."""
    data = data if data is not None else load()
    return (data.get("members", {}).get(name)
            or {"committees": [], "reason": REASON_UNMATCHED})
