"""IndexNow ping — tell Bing-family search engines what changed today.

The site's content changes every day (trades, member pages, ticker pages,
the report), but crawlers only find that out on their own schedule. IndexNow
is the push half: after the daily refresh we POST the list of URLs that carry
fresh data to api.indexnow.org, which fans out to every participating engine
(Bing, and via Bing's index DuckDuckGo and Yahoo; plus Yandex, Seznam,
Naver). Google does not use IndexNow — the sitemap covers it.

Ownership proof is the key file: ``landing/public/<KEY>.txt`` contains the
key and deploys to the site root. The key is NOT a secret — the protocol is
that anyone can verify ``https://<host>/<key>.txt`` matches the key in the
ping, which only the site owner could have placed there.

Pure + offline-testable except ``ping`` (stdlib urllib, same pattern as
analytics.py). Always non-fatal at the call site: a search-engine ping must
never fail the data refresh.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import pipeline

SITE = "https://capitolledger.io"
HOST = "capitolledger.io"
ENDPOINT = "https://api.indexnow.org/indexnow"
KEY = "7610b8012cebcb63302e0aa237eaa347"

LANDING_DATA = pipeline.REPO_ROOT / "landing" / "src" / "data"

# Pages whose content moves with the daily refresh, beyond the generated
# member/ticker sets.
DAILY_PAGES = ["/", "/tracker", "/report", "/late", "/tickers", "/members"]


def _slugs(index_path: Path, list_key: str, slug_key: str = "slug") -> list[str]:
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [row[slug_key] for row in data.get(list_key, []) if row.get(slug_key)]


def daily_urls(data_dir: Path = LANDING_DATA) -> list[str]:
    """Every page whose content changed with today's data refresh."""
    urls = [f"{SITE}{p}" for p in DAILY_PAGES]
    urls += [f"{SITE}/members/{s}"
             for s in _slugs(data_dir / "members" / "_index.json", "members")]
    urls += [f"{SITE}/tickers/{s}"
             for s in _slugs(data_dir / "tickers" / "_index.json", "tickers")]
    return urls


def payload(urls: list[str]) -> dict:
    return {"host": HOST, "key": KEY, "urlList": urls}


def ping(urls: list[str]) -> int:
    """POST the URL list to IndexNow; returns the HTTP status (network)."""
    import urllib.request

    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload(urls)).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


def main() -> int:
    urls = daily_urls()
    if not urls:
        print("indexnow: no URLs to submit")
        return 0
    status = ping(urls)
    # 200 = accepted; 202 = accepted, key validation pending (first pings).
    print(f"indexnow: submitted {len(urls)} URLs → HTTP {status}")
    return 0 if status in (200, 202) else 1
