"""Offline tests for congress.pipeline (stub sources, tempdirs, no network)."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from congress.normalize import Trade
from congress.pipeline import (
    ChamberSource,
    PaperFiling,
    dump_output,
    load_output,
    load_state,
    run,
)

TODAY = date(2026, 7, 2)  # cutoff = 2025-01-01


class StubRef:
    def __init__(self, fid, member="Stub Member", filed="2026-06-20"):
        self.fid = fid
        self.member = member
        self.filed = filed


def _trade(fid, row=0, filed="2026-06-20", member="Stub Member"):
    return Trade(
        id=f"senate:{fid}:{row}", chamber="senate", member=member,
        ticker="NVDA", asset="NVIDIA Corporation", type="buy",
        tx_date="2026-05-14", filing_date=filed,
        amount_lo=1001, amount_hi=15000, amount_label="$1,001 - $15,000",
        filing_id=fid, source_url=f"https://example.gov/{fid}/",
    )


def _source(refs, fetch, chamber="senate"):
    return ChamberSource(
        chamber=chamber,
        list_filings=lambda: refs,
        fetch_trades=fetch,
        ref_id=lambda r: r.fid,
        ref_member=lambda r: r.member,
        ref_filing_date=lambda r: r.filed,
        ref_url=lambda r: f"https://example.gov/{r.fid}/",
    )


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        base = Path(self.dir.name)
        self.output = base / "congress-trades.json"
        self.state = base / "state.json"

    def tearDown(self):
        self.dir.cleanup()

    def _run(self, refs, fetch, **kw):
        kw.setdefault("log", lambda msg: None)
        return run(
            [_source(refs, fetch)],
            today=TODAY,
            output_path=self.output,
            state_path=self.state,
            generated_at="2026-07-02T00:00:00Z",
            **kw,
        )

    def test_first_run_writes_sorted_output_and_state(self):
        refs = [StubRef("f1"), StubRef("f2", filed="2026-06-25")]
        result = self._run(refs, lambda r: [_trade(r.fid, filed=r.filed)])
        self.assertTrue(result.changed)
        self.assertEqual(result.new_trades, 2)
        data = json.loads(self.output.read_text())
        # filing_date desc: f2 (06-25) before f1 (06-20)
        self.assertEqual([t["filing_id"] for t in data["trades"]], ["f2", "f1"])
        self.assertEqual(data["meta"]["counts"]["trades"], 2)
        self.assertEqual(data["meta"]["data_version"], "2026-07-02.1")
        state = json.loads(self.state.read_text())
        self.assertEqual(set(state["processed"]["senate"]), {"f1", "f2"})

    def test_second_run_is_incremental_and_unchanged(self):
        refs = [StubRef("f1")]
        calls = []

        def fetch(r):
            calls.append(r.fid)
            return [_trade(r.fid)]

        self._run(refs, fetch)
        result = self._run(refs, fetch)
        self.assertEqual(calls, ["f1"])  # not refetched
        self.assertFalse(result.changed)

    def test_data_version_serial_increments_same_day(self):
        self._run([StubRef("f1")], lambda r: [_trade(r.fid)])
        self._run([StubRef("f2")], lambda r: [_trade(r.fid)])
        data = json.loads(self.output.read_text())
        self.assertEqual(data["meta"]["data_version"], "2026-07-02.2")

    def test_paper_filing_skipped_and_never_retried(self):
        def fetch(r):
            raise PaperFiling("scan")

        self._run([StubRef("p1")], fetch)
        data = json.loads(self.output.read_text())
        self.assertEqual(data["skipped_filings"][0]["reason"], "paper")
        state = json.loads(self.state.read_text())
        self.assertIn("p1", state["processed"]["senate"])

    def test_skipped_filing_member_name_normalized(self):
        def fetch(r):
            raise PaperFiling("scan")

        self._run([StubRef("p1", member="Tuberville, Thomas H.")], fetch)
        skip = json.loads(self.output.read_text())["skipped_filings"][0]
        self.assertEqual(skip["member"], "Tommy Tuberville")

    def test_parse_error_skipped_then_recovered_on_retry(self):
        def broken(r):
            raise ValueError("bad row")

        result = self._run([StubRef("e1")], broken)
        self.assertEqual(result.parse_errors, 1)
        data = json.loads(self.output.read_text())
        self.assertEqual(data["skipped_filings"][0]["reason"], "parse_error")
        state = json.loads(self.state.read_text())
        self.assertNotIn("e1", state["processed"]["senate"])  # will retry

        result = self._run([StubRef("e1")], lambda r: [_trade(r.fid)])
        self.assertEqual(result.recovered_errors, 1)
        data = json.loads(self.output.read_text())
        self.assertEqual(data["skipped_filings"], [])
        self.assertEqual(len(data["trades"]), 1)

    def test_old_filings_pruned_and_filtered(self):
        # A 2024 filing is outside the window: never fetched at all.
        fetched = []

        def fetch(r):
            fetched.append(r.fid)
            return [_trade(r.fid, filed=r.filed)]

        self._run([StubRef("old", filed="2024-12-31"), StubRef("new")], fetch)
        self.assertEqual(fetched, ["new"])
        # A stored trade that has aged out gets pruned on the next run.
        stored = json.loads(self.output.read_text())
        stored["trades"].append(
            _trade("aged", filed="2024-06-01").to_dict()
        )
        self.output.write_text(dump_output(stored))
        result = self._run([], lambda r: [])
        self.assertEqual(result.pruned_trades, 1)
        data = json.loads(self.output.read_text())
        self.assertEqual([t["filing_id"] for t in data["trades"]], ["new"])

    def test_limit_caps_fetches(self):
        refs = [StubRef(f"f{i}") for i in range(5)]
        result = self._run(refs, lambda r: [_trade(r.fid)], limit=2)
        self.assertEqual(result.fetched, 2)

    def test_dry_run_writes_nothing(self):
        self._run([StubRef("f1")], lambda r: [_trade(r.fid)], dry_run=True)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.state.exists())

    def test_dedupe_by_trade_id(self):
        self._run([StubRef("f1")], lambda r: [_trade(r.fid), _trade(r.fid)])
        data = json.loads(self.output.read_text())
        self.assertEqual(len(data["trades"]), 1)

    def test_roster_enrichment_applied(self):
        refs = [StubRef("f1", member="Tuberville, Thomas H.")]
        self._run(refs, lambda r: [_trade(r.fid, member=r.member)])
        trade = json.loads(self.output.read_text())["trades"][0]
        self.assertEqual(trade["member"], "Tommy Tuberville")
        self.assertEqual(trade["party"], "R")

    def test_stored_trades_re_enriched_on_later_runs(self):
        # A trade stored before its member was in the roster gets party/state
        # filled retroactively on the next run.
        stored = _trade("f0", member="Tuberville, Thomas H.").to_dict()
        self.assertIsNone(stored["party"])
        self.output.write_text(dump_output({
            "meta": {}, "trades": [stored], "skipped_filings": [],
        }))
        self._run([], lambda r: [])
        trade = json.loads(self.output.read_text())["trades"][0]
        self.assertEqual(trade["member"], "Tommy Tuberville")
        self.assertEqual(trade["party"], "R")

    def test_dump_output_is_valid_json_one_trade_per_line(self):
        self._run([StubRef("f1"), StubRef("f2")],
                  lambda r: [_trade(r.fid)])
        text = self.output.read_text()
        json.loads(text)  # valid
        trade_lines = [l for l in text.splitlines() if '"id":' in l]
        self.assertEqual(len(trade_lines), 2)

    def test_sample_output_is_discarded(self):
        self.output.write_text(json.dumps({
            "meta": {"_sample": True},
            "trades": [_trade("fake").to_dict()],
            "skipped_filings": [],
        }))
        loaded = load_output(self.output)
        self.assertEqual(loaded["trades"], [])

    def test_load_state_defaults(self):
        state = load_state(self.state)
        self.assertEqual(state["processed"], {"senate": {}, "house": {}})


if __name__ == "__main__":
    unittest.main()
