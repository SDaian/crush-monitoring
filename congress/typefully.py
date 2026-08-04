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

Image attachment IS automated (``upload_media``): the v2 three-step flow —
request an upload slot, PUT the bytes to the returned presigned S3 URL,
poll until the media is processed — then the draft is created with the
media id attached. If any step fails, the CLI falls back to the old manual
path: the draft carries a trailing "[attach card: …]" note and the PNG is
in the run's ``social-cards`` artifact for drag-dropping during approval.

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


def media_upload_endpoint(set_id) -> str:
    return f"{BASE}/social-sets/{set_id}/media/upload"


def media_status_endpoint(set_id, media_id) -> str:
    return f"{BASE}/social-sets/{set_id}/media/{media_id}"


RETRIES = 3
BACKOFF_S = 4.0
MEDIA_POLL_TRIES = 15
MEDIA_POLL_INTERVAL_S = 2.0


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


def _put_once(url: str, data: bytes, content_type: str) -> None:
    # An explicit (possibly empty) Content-Type always — urllib would
    # otherwise silently add application/x-www-form-urlencoded, which S3
    # folds into the signature check.
    req = urllib.request.Request(
        url, data=data, method="PUT",
        headers={"Content-Type": content_type},
    )
    with urllib.request.urlopen(req, timeout=60):
        pass


def _put_bytes(url: str, data: bytes, content_type: str) -> None:
    """PUT raw bytes to the presigned S3 URL. No auth header — the URL
    itself carries the authorization (that's what presigned means).

    S3 folds the Content-Type header into the signature, and whether the
    presigner included it isn't observable from the URL. A live run showed
    Typefully signs WITHOUT it (sending image/png got SignatureDoesNotMatch
    with image/png right there in S3's computed string-to-sign), so a
    signature rejection is retried once with the header suppressed."""
    last: urllib.error.HTTPError | None = None
    try:
        for ct in (content_type, ""):
            try:
                _put_once(url, data, ct)
                return
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                exc.msg = body  # keep for the final error message
                last = exc
                if not (exc.code == 403 and "SignatureDoesNotMatch" in body):
                    break
        # The S3 error XML says WHY the request was rejected — essential
        # for debugging a shape the docs sandbox cannot verify. Never log
        # the URL itself (it embeds the signing credentials).
        raise TypefullyError(
            f"presigned upload failed: HTTP {last.code}: "
            f"{last.msg[:1000]}") from None
    except (urllib.error.URLError, OSError) as exc:
        raise TypefullyError(
            f"presigned upload failed: {type(exc).__name__}") from None


def upload_media(key: str, set_id, path,
                 content_type: str = "image/png",
                 poll_interval_s: float = MEDIA_POLL_INTERVAL_S):
    """Upload a file and return its media id once Typefully has processed
    it. Three steps: request an upload slot, PUT the bytes to the returned
    presigned URL, poll status until "ready" ("error" or a timeout raise)."""
    slot = _request("POST", media_upload_endpoint(set_id), key,
                    {"file_name": path.name, "content_type": content_type})
    if isinstance(slot, dict) and isinstance(slot.get("data"), dict):
        slot = slot["data"]  # tolerate a conventional wrapper
    if not isinstance(slot, dict):
        raise TypefullyError("unexpected media/upload response shape")
    url = (slot.get("presigned_url") or slot.get("upload_url")
           or slot.get("url"))
    media_id = slot.get("media_id") if slot.get("media_id") is not None \
        else slot.get("id")
    if not url or media_id is None:
        # Keys only, never values — the presigned URL embeds credentials.
        raise TypefullyError("media/upload response missing presigned_url "
                             f"or media_id (keys: {sorted(slot)})")
    _put_bytes(url, path.read_bytes(), content_type)
    for attempt in range(MEDIA_POLL_TRIES):
        status_resp = _request(
            "GET", media_status_endpoint(set_id, media_id), key)
        status = str((status_resp or {}).get("status") or "").lower()
        if status == "ready":
            return media_id
        if status == "error":
            raise TypefullyError("media processing failed (status=error)")
        if attempt < MEDIA_POLL_TRIES - 1:
            time.sleep(poll_interval_s)
    raise TypefullyError(
        f"media not ready after {MEDIA_POLL_TRIES} status checks")


def create_draft(key: str, content: str, set_id=None,
                 media_ids: list | None = None) -> dict:
    """Create an UNPUBLISHED X draft. No schedule/publish fields are sent on
    purpose: an unscheduled draft sits in Drafts until a human queues or
    publishes it — the safest default the brief demands."""
    if set_id is None:
        set_id = resolve_social_set_id(key)
    post: dict = {"text": content}
    if media_ids:
        # Per post, not top-level: the drafts endpoint is strict
        # ("extra_forbidden") and rejected a top-level media array.
        post["media_ids"] = list(media_ids)
    payload = {
        "platforms": {
            "x": {"enabled": True, "posts": [post]},
        },
    }
    resp = _request("POST", drafts_endpoint(set_id), key, payload)
    return resp if isinstance(resp, dict) else {"raw": resp}
