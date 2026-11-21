"""Pipeline integration tests: no credentials and no real-world source claims."""
import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from research.challenger_002_research_pipeline import run

def rows(n, raw):
    base = datetime(2024,1,1,tzinfo=timezone.utc)
    for i in range(n):
        start = base + timedelta(days=i)
        yield {
            "event_id": "game-" + str(i), "league":"NBA", "market":"moneyline",
            "event_start_at":start.isoformat(),
            "observed_at":(start-timedelta(hours=1)).isoformat(),
            "source_observed_at":(start-timedelta(hours=2)).isoformat(),
            "outcome_observed_at":(start+timedelta(hours=4)).isoformat(),
            "source_provider":"SportsDataIO", "source_record_id":"receipt-"+str(i),
            "source_payload_sha256":hashlib.sha256(raw).hexdigest(),
            "features":{"home_strength":float(i%7)}, "outcome":int(i%3==0)
        }

class ResearchPipelineTests(unittest.TestCase):
    def test_missing_receipts_block(self):
        with tempfile.TemporaryDirectory() as d:
            r = run(list(rows(5,b"test")), d, "NBA", "moneyline")
            self.assertEqual(r["status"],"BLOCKED")
            self.assertEqual(r["certified_take_count"],0)

    def test_market_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            raw = b'{"test":true}'
            data = list(rows(2,raw))
            for row in data:
                (Path(d)/(row["source_record_id"]+".json")).write_bytes(raw)
            r = run(data,d,"NBA","spread")
            self.assertEqual(r["status"],"BLOCKED")
            self.assertIn("MIXED_LEAGUE_OR_MARKET",r["blockers"])

    def test_research_only_with_receipts(self):
        with tempfile.TemporaryDirectory() as d:
            raw = b'{"synthetic":true}'
            data = list(rows(360,raw))
            for row in data:
                (Path(d)/(row["source_record_id"]+".json")).write_bytes(raw)
            r = run(data,d,"NBA","moneyline")
            self.assertEqual(r["status"],"RESEARCH_EVALUATED_NOT_CERTIFIED")
            self.assertEqual(r["certified_take_count"],0)
            self.assertIn("PROVIDER_AUTHENTICATION_AND_CUSTODY_REQUIRED",r["blockers"])

if __name__ == "__main__":
    unittest.main()
