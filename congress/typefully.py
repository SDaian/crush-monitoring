"""Typefully API v2 client — the publishing target for social drafts.

Why Typefully (owner's decision, recorded): drafts created via API sit
UNPUBLISHED until a human approves them in the Typefully UI, which is the
approval gate the owner wants; posting via the X API directly was ruled out
(paid per-post for new developers since 2026, and no approval step).

This is the **v2** surface: the first live run's probe came back
``HTTP 403: API v1 access via API keys is disabled`` — exactly the failure
mode the probe-before-write design exists to catch. The v2 shapes below come
from Typefully's published migration guidance and a working open-source v2
client (the docs site itself still 403s our egress proxy), so treat them as
well-sourced but not doc-verified. The same three safety layers hold:

1. The pipeline defaults to DRY-RUN; live drafting requires both the
   TYPEFULLY_API_KEY secret and an explicit SOCIAL_LIVE=true repo variable.
2. Before drafting, ``probe()`` makes a read-only call (GET /me); if it
   fails, the run aborts before any write.
3. Even a successful draft is unpublished by design — no schedule/publish
   fields are ever sent, so nothing goes to X without the owner pressing
   publish/queue in Typefully.

v2 scopes drafts under a **social set** (a group of connected accounts), so
drafting is a two-step: GET /social-sets to resolve the set id (the first
set by default; TYPEFULLY_SOCIAL_SET_ID pins one if the account ever has
several), then POST the draft into it. Responses are parsed defensively —
field names are matched against candidates, like analytics.py does.

Image attachment is NOT automated yet (the v2 media upload is a three-step
presigned-S3 flow — the least certain part of the surface). The card PNG is
saved as a run artifact and referenced in a trailing note line the owner
deletes after drag-dropping the image in Typefully — one manual step inside
the approval they were doing anyway.

Auth: ``Authorization: Bearer <key>`` (v2 renamed the v1 X-API-KEY header).
The key is never logged.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

BASE = "https://api.typefully.com/v2"
# Read-only endpoint used to verify auth + reachability before any write.
PROBE_ENDPOINT = f"{BASE}/me"
SOCIAL_SETS_ENDPOINT = f"{BASE}/social-sets"


def drafts_endpoint(set_id) -> str:
    return f"{BASE}/social-sets/{set_id}/drafts"


RETRIES = 3
BACKOFF_S = 4.0


class TypefullyError(RuntimeError):
    pass


def _request(method: str, url: str, key: str, payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
    )
    last_err: Exception | None = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return json.loads(body) if body.strip() else {}
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500 and exc.code != 429:
                # Client errors are real answers — never retried.
                detail = exc.read().decode("utf-8", errors="replace")[:300]
                raise TypefullyError(f"HTTP {exc.code}: {detail}") from None
            last_err = exc
        except (urllib.error.URLError, OSError) as exc:
            last_err = exc
        if attempt < RETRIES - 1:
            time.sleep(BACKOFF_S * (2 ** attempt))
    raise TypefullyError(f"unreachable after {RETRIES} tries: "
                         f"{type(last_err).__name__}")


def probe(key: str) -> bool:
    """Read-only auth/reachability check. Raises TypefullyError on failure."""
    _request("GET", PROBE_ENDPOINT, key)
    return True


def _extract_sets(resp) -> list:
    """The /social-sets response shape isn't doc-verified: accept either a
    bare list or a list under a conventional wrapper key."""
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict):
        for k in ("data", "results", "items", "social_sets"):
            if isinstance(resp.get(k), list):
                return resp[k]
    return []


def resolve_social_set_id(key: str):
    """The set drafts land in: TYPEFULLY_SOCIAL_SET_ID when set, else the
    account's first (usually only) social set."""
    pinned = os.environ.get("TYPEFULLY_SOCIAL_SET_ID", "").strip()
    if pinned:
        return pinned
    sets = _extract_sets(_request("GET", SOCIAL_SETS_ENDPOINT, key))
    for s in sets:
        if isinstance(s, dict) and s.get("id") is not None:
            return s["id"]
    raise TypefullyError("no social set found — connect an account in "
                         "Typefully or set TYPEFULLY_SOCIAL_SET_ID")


def create_draft(key: str, content: str, set_id=None) -> dict:
    """Create an UNPUBLISHED X draft. No schedule/publish fields are sent on
    purpose: an unscheduled draft sits in Drafts until a human queues or
    publishes it — the safest default the brief demands."""
    if set_id is None:
        set_id = resolve_social_set_id(key)
    payload = {
        "platforms": {
            "x": {"enabled": True, "posts": [{"text": content}]},
        },
    }
    resp = _request("POST", drafts_endpoint(set_id), key, payload)
    return resp if isinstance(resp, dict) else {"raw": resp}
