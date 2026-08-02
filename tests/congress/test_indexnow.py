"""Offline tests for congress.indexnow (URL list + payload; no network)."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from congress import indexnow


def write_indexes(root: Path, members: list[str], tickers: list[str]) -> None:
    (root / "members").mkdir(parents=True)
    (root / "tickers").mkdir(parents=True)
    (root / "members" / "_index.json").write_text(json.dumps(
        {"members": [{"name": s.title(), "slug": s} for s in members]}))
    (root / "tickers" / "_index.json").write_text(json.dumps(
        {"tickers": [{"ticker": s.upper(), "slug": s} for s in tickers]}))


class TestDailyUrls(unittest.TestCase):
    def test_sections_members_and_tickers(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            write_indexes(root, ["nancy-pelosi"], ["nvda", "tsm"])
            urls = indexnow.daily_urls(root)
        self.assertIn("https://capitolledger.io/", urls)
        self.assertIn("https://capitolledger.io/tracker", urls)
        self.assertIn("https://capitolledger.io/members/nancy-pelosi", urls)
        self.assertIn("https://capitolledger.io/tickers/nvda", urls)
        self.assertIn("https://capitolledger.io/tickers/tsm", urls)
        self.assertTrue(all(u.startswith(indexnow.SITE) for u in urls))

    def test_missing_indexes_still_submit_sections(self):
        with TemporaryDirectory() as d:
            urls = indexnow.daily_urls(Path(d))
        self.assertEqual(len(urls), len(indexnow.DAILY_PAGES))

    def test_real_repo_data(self):
        # Against the committed landing data: every generated page is present.
        urls = indexnow.daily_urls()
        self.assertGreater(len(urls), 20)
        self.assertIn("https://capitolledger.io/members/nancy-pelosi", urls)


class TestPayloadAndKey(unittest.TestCase):
    def test_payload_shape(self):
        p = indexnow.payload(["https://capitolledger.io/"])
        self.assertEqual(p["host"], "capitolledger.io")
        self.assertEqual(p["key"], indexnow.KEY)
        self.assertEqual(p["urlList"], ["https://capitolledger.io/"])

    def test_key_file_is_deployed_and_matches(self):
        # The ownership proof: /<key>.txt must exist in the site's static
        # assets and contain exactly the key the ping sends.
        key_file = (indexnow.pipeline.REPO_ROOT / "landing" / "public"
                    / f"{indexnow.KEY}.txt")
        self.assertTrue(key_file.exists(),
                        f"missing IndexNow key file {key_file}")
        self.assertEqual(key_file.read_text(encoding="utf-8").strip(),
                         indexnow.KEY)
