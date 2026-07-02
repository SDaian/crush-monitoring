"""Polite HTTP session helpers — the only module that imports requests.

Everything network-facing goes through ``polite_get``/``polite_post`` so the
whole fetcher shares one user agent, one retry policy and a global >=1s
spacing between requests to the government sites.
"""

from __future__ import annotations

import time

USER_AGENT = (
    "crush-monitoring congress-trades bot "
    "(+https://github.com/SDaian/crush-monitoring)"
)
DEFAULT_TIMEOUT = 30  # seconds
MIN_INTERVAL = 1.0    # seconds between any two requests

_last_request = 0.0


def make_session():
    """Build a requests.Session with UA + retry/backoff on 429/5xx."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=None,  # retry POSTs too: search endpoints are idempotent
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _pace() -> None:
    global _last_request
    wait = MIN_INTERVAL - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def polite_get(session, url: str, **kwargs):
    _pace()
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    resp = session.get(url, **kwargs)
    resp.raise_for_status()
    return resp


def polite_post(session, url: str, **kwargs):
    _pace()
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    resp = session.post(url, **kwargs)
    resp.raise_for_status()
    return resp
