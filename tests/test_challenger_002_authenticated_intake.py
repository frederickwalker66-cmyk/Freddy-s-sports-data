import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from research.challenger_002_authenticated_intake import capture

class AuthenticatedIntakeTests(unittest.TestCase):
    def test_missing_key_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            r=capture("2025-01-01","nba_scores",d,env={})
            self.assertEqual(r["status"],"BLOCKED")
            self.assertEqual(r["certified_take_count"],0)
    def test_authenticated_response_snapshot_is_not_pregame_proof(self):
        def fake_fetch(url,**kwargs):
            self.assertEqual(kwargs["allowed_host"],"api.sportsdata.io")
            self.assertEqual(kwargs["api_key"],"test-key")
            return {"payload":[{"GameID":1}],"retrieved_at":"2026-11-21T17:00:00Z"}
        with tempfile.TemporaryDirectory() as d:
            r=capture("2025-01-01","nba_scores",d,env={"SPORTSDATAIO_NBA_API_KEY":"test-key"},fetch=fake_fetch)
            self.assertEqual(r["status"],"AUTHENTICATED_SNAPSHOT_RESEARCH_ONLY")
            self.assertFalse(r["historical_pregame_availability_verified"])
            self.assertFalse(r["raw_http_body_preserved"])
            self.assertEqual(hashlib.sha256(Path(r["snapshot_path"]).read_bytes()).hexdigest(),r["canonical_payload_sha256"])
    def test_bad_schema_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            r=capture("2025-01-01","nba_scores",d,env={"SPORTSDATAIO_NBA_API_KEY":"test-key"},
                fetch=lambda *a,**k:{"payload":{},"retrieved_at":"2026-11-21T17:00:00Z"})
            self.assertEqual(r["status"],"BLOCKED")
    def test_invalid_date_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                capture("2025-1-1","nba_scores",d,env={})

if __name__ == "__main__":
    unittest.main()
