"""Typefully API client — the publishing target for social drafts.

Why Typefully (owner's decision, recorded): drafts created via API sit
UNPUBLISHED until a human approves them in the Typefully UI, which is the
approval gate the owner wants; posting via the X API directly was ruled out
(paid per-post for new developers since 2026, and no approval step).

UNVERIFIED-API WARNING: the sandbox this was written in cannot reach
Typefully's documentation (their docs endpoint 403s our egress proxy), so
the endpoint shapes below are the widely-known public surface, NOT verified
against today's docs. Every shape is isolated in the constants right here.
Three safety layers compensate:

1. The pipeline defaults to DRY-RUN; live drafting requires both the
   TYPEFULLY_API_KEY secret and an explicit SOCIAL_LIVE=true repo variable.
2. Before drafting, ``probe()`` makes a read-only call; if it fails, the
   run aborts before any write.
3. Even a successful draft is unpublished by design — nothing goes to X
   without the owner pressing publish/queue in Typefully.

Image attachment is NOT automated yet for the same reason (the media-upload
endpoint is the least certain part of the surface). The card PNG is saved as
a run artifact and referenced in a trailing note line the owner deletes
after drag-dropping the image in Typefully — one manual step inside the
approval they were doing anyway. Wire the media endpoint once its docs have
been read from a machine that can reach them.

Auth: ``X-API-KEY: Bearer <key>`` per Typefully's published examples. The
key is never logged.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

BASE = "https://api.typefully.com/v1"
DRAFTS_ENDPOINT = f"{BASE}/drafts/"
# Read-only endpoint used to verify auth + reachability before any write.
PROBE_ENDPOINT = f"{BASE}/drafts/recently-scheduled/"

RETRIES = 3
BACKOFF_S = 4.0


class TypefullyError(RuntimeError):
    pass


def _request(method: str, url: str, key: str, payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"X-API-KEY": f"Bearer {key}",
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


def create_draft(key: str, content: str) -> dict:
    """Create an UNPUBLISHED draft. No schedule fields are sent on purpose:
    per Typefully's model an unscheduled draft sits in Drafts until a human
    queues or publishes it — the safest default the brief demands."""
    return _request("POST", DRAFTS_ENDPOINT, key, {"content": content})
