"""Broadcast the morning digest to Buttondown subscribers.

The report content already exists — `daily_report.build_report` composes the
same HTML the owner receives by SMTP — so this is delivery, not new logic: one
API call hands that HTML to Buttondown, which owns the subscriber list,
double opt-in, unsubscribe links and deliverability.

Design (matches ROADMAP contact stage 1):

- **Gated + non-fatal.** Needs ``BUTTONDOWN_API_KEY``. Unset, or any API error,
  returns False and the run continues — the owner's SMTP email and the GitHub
  issue still go out. A newsletter outage must never fail the data refresh.
- **Subscriber PII never touches this repo.** We only ever POST content; we do
  not read, store or log the subscriber list. git stays the public audit record
  of *trades*, never of people.
- **Network is confined to ``_post``** (stdlib ``urllib``, no new deps); the
  payload builder is pure and offline-tested.

API: POST https://api.buttondown.com/v1/emails
     Authorization: Token <key>
     {"subject": ..., "body": ..., "email_type": "public"}
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

API_URL = "https://api.buttondown.com/v1/emails"
ENV_KEY = "BUTTONDOWN_API_KEY"
TIMEOUT = 30


def configured() -> bool:
    """True when a key is present — otherwise the broadcast is skipped."""
    return bool(os.environ.get(ENV_KEY, "").strip())


# Buttondown can create an email as a DRAFT. Left implicit, a broadcast can
# return 201 and simply never send — success in the log, nothing in the inbox.
# Say "send it now" explicitly: if this value is ever wrong the API answers
# with a loud 4xx, which is far easier to debug than a silent draft.
SEND_STATUS = "about_to_send"


def build_payload(subject: str, html: str) -> dict:
    """The request body for one broadcast (pure).

    ``email_type: public`` publishes it to the archive as well as sending it,
    which gives each issue a shareable URL at no extra cost.
    """
    return {"subject": subject, "body": html, "email_type": "public",
            "status": SEND_STATUS}


def _post(payload: dict, key: str) -> tuple[int, str]:
    """POST the broadcast (network). The key rides in the Authorization
    header and is never logged."""
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Token {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "capitol-ledger-morning-report",
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def send(subject: str, html: str) -> bool:
    """Broadcast the digest to confirmed subscribers. Best-effort: returns
    False and warns on any failure so a newsletter problem never fails the
    refresh or blocks the owner's own copy."""
    key = os.environ.get(ENV_KEY, "").strip()
    if not key:
        print("BUTTONDOWN_API_KEY not set — skipping subscriber broadcast")
        return False
    try:
        status, body = _post(build_payload(subject, html), key)
    except urllib.error.HTTPError as exc:
        # Surface the status and a short reason; the body can echo the request,
        # so keep it clipped and never print the key.
        detail = exc.read().decode("utf-8", "replace")[:200] if exc.fp else ""
        print(f"::warning::Buttondown broadcast failed: HTTP {exc.code} {detail}")
        return False
    except Exception as exc:  # noqa: BLE001 — best-effort, never fatal
        print(f"::warning::Buttondown broadcast failed: {type(exc).__name__}")
        return False
    if 200 <= status < 300:
        # Echo the returned status/id: it is the only way to tell a real send
        # from a draft that was merely created. No subscriber data is in this
        # response — it describes the email, not the list.
        state = ""
        try:
            data = json.loads(body)
            state = f" status={data.get('status')!r} id={data.get('id', '')[:8]}"
        except (ValueError, AttributeError, TypeError):
            pass
        print(f"broadcast accepted by Buttondown (HTTP {status}){state}")
        return True
    print(f"::warning::Buttondown returned HTTP {status}: {body[:200]}")
    return False
