"""Offline tests for the Typefully v2 client (no network — _request is
stubbed; the shapes it sends/parses are the part we own)."""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from congress import typefully


class TestEndpoints(unittest.TestCase):
    def test_v2_surface(self):
        self.assertEqual(typefully.BASE, "https://api.typefully.com/v2")
        self.assertEqual(typefully.PROBE_ENDPOINT,
                         "https://api.typefully.com/v2/me")
        self.assertEqual(typefully.drafts_endpoint(7),
                         "https://api.typefully.com/v2/social-sets/7/drafts")


class TestExtractSets(unittest.TestCase):
    def test_bare_list(self):
        self.assertEqual(typefully._extract_sets([{"id": 1}]), [{"id": 1}])

    def test_wrapped_list(self):
        for key in ("data", "results", "items", "social_sets"):
            self.assertEqual(typefully._extract_sets({key: [{"id": 2}]}),
                             [{"id": 2}])

    def test_garbage(self):
        self.assertEqual(typefully._extract_sets("nope"), [])
        self.assertEqual(typefully._extract_sets({"data": "nope"}), [])


class TestResolveSocialSet(unittest.TestCase):
    def test_env_pin_wins_without_network(self):
        with mock.patch.dict(os.environ,
                             {"TYPEFULLY_SOCIAL_SET_ID": "abc"}):
            with mock.patch.object(typefully, "_request") as req:
                self.assertEqual(
                    typefully.resolve_social_set_id("k"), "abc")
                req.assert_not_called()

    def test_first_set_from_api(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TYPEFULLY_SOCIAL_SET_ID", None)
            with mock.patch.object(
                    typefully, "_request",
                    return_value={"data": [{"id": 11}, {"id": 22}]}):
                self.assertEqual(typefully.resolve_social_set_id("k"), 11)

    def test_no_sets_raises(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TYPEFULLY_SOCIAL_SET_ID", None)
            with mock.patch.object(typefully, "_request", return_value=[]):
                with self.assertRaises(typefully.TypefullyError):
                    typefully.resolve_social_set_id("k")


class TestUploadMedia(unittest.TestCase):
    def _png(self, tmp):
        p = Path(tmp) / "card.png"
        p.write_bytes(b"\x89PNG-not-really")
        return p

    def test_three_step_happy_path(self):
        with TemporaryDirectory() as tmp:
            png = self._png(tmp)
            responses = [
                {"presigned_url": "https://s3/put-here", "media_id": "m1"},
                {"status": "processing"},
                {"status": "ready"},
            ]
            with mock.patch.object(typefully, "_request",
                                   side_effect=responses) as req, \
                 mock.patch.object(typefully, "_put_bytes") as put:
                mid = typefully.upload_media("k", 5, png,
                                             poll_interval_s=0)
            self.assertEqual(mid, "m1")
            slot_call = req.call_args_list[0].args
            self.assertEqual(slot_call[1],
                             typefully.media_upload_endpoint(5))
            self.assertEqual(slot_call[3],
                             {"file_name": "card.png",
                              "content_type": "image/png"})
            put.assert_called_once_with("https://s3/put-here",
                                        b"\x89PNG-not-really", "image/png")

    def test_error_status_raises(self):
        with TemporaryDirectory() as tmp:
            png = self._png(tmp)
            responses = [{"upload_url": "https://s3/x", "id": 9},
                         {"status": "error"}]
            with mock.patch.object(typefully, "_request",
                                   side_effect=responses), \
                 mock.patch.object(typefully, "_put_bytes"):
                with self.assertRaises(typefully.TypefullyError):
                    typefully.upload_media("k", 5, png, poll_interval_s=0)

    def test_missing_presigned_url_raises_before_upload(self):
        with TemporaryDirectory() as tmp:
            png = self._png(tmp)
            with mock.patch.object(typefully, "_request",
                                   return_value={"media_id": "m1"}), \
                 mock.patch.object(typefully, "_put_bytes") as put:
                with self.assertRaises(typefully.TypefullyError):
                    typefully.upload_media("k", 5, png, poll_interval_s=0)
                put.assert_not_called()


class TestCreateDraft(unittest.TestCase):
    def test_unpublished_x_draft_payload(self):
        with mock.patch.object(typefully, "_request",
                               return_value={"id": 99}) as req:
            resp = typefully.create_draft("k", "hello", set_id=5)
        self.assertEqual(resp["id"], 99)
        method, url, key, payload = req.call_args.args
        self.assertEqual(method, "POST")
        self.assertEqual(url, typefully.drafts_endpoint(5))
        self.assertEqual(
            payload,
            {"platforms": {"x": {"enabled": True,
                                 "posts": [{"text": "hello"}]}}})
        # No schedule/publish fields — the draft must stay unpublished.
        flat = str(payload)
        self.assertNotIn("schedule", flat)
        self.assertNotIn("publish", flat)

    def test_media_attached_at_top_level(self):
        with mock.patch.object(typefully, "_request",
                               return_value={"id": 1}) as req:
            typefully.create_draft("k", "hi", set_id=5, media_ids=["m1"])
        payload = req.call_args.args[3]
        self.assertEqual(payload["media"], ["m1"])

    def test_no_media_key_when_empty(self):
        with mock.patch.object(typefully, "_request",
                               return_value={"id": 1}) as req:
            typefully.create_draft("k", "hi", set_id=5, media_ids=[])
        self.assertNotIn("media", req.call_args.args[3])
