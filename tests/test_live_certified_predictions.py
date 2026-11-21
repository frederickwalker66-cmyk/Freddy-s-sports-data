import unittest
import contextlib
import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from tests.test_sharp_edge_certification import SharpEdgeCertificationTests
from datetime import datetime, timezone
from scripts.live_certified_predictions import run, main

class LiveCertificationTests(unittest.TestCase):
    def test_empty_feed_has_no_fake_predictions(self):
        result = run([], now=datetime(2026, 11, 20, tzinfo=timezone.utc))
        self.assertEqual(result["certified_take_count"], 0)
        self.assertTrue(result["no_certified_picks"])

    def test_unsigned_candidate_holds(self):
        result = run([{"selection": "NBA OVER"}])
        self.assertEqual(result["decisions"][0]["decision"], "HOLD")
        self.assertEqual(result["hold_count"], 1)

    def test_reject_unbounded_input(self):
        with self.assertRaises(ValueError):
            run([{}] * 501)

    def test_absent_feed_provenance_cannot_promote_even_signed_fixture(self):
        fixture = SharpEdgeCertificationTests("test_missing_keys_holds").candidate()
        with tempfile.TemporaryDirectory() as tmp:
            candidates = Path(tmp) / "candidates.json"
            output = Path(tmp) / "certified.json"
            candidates.write_text(json.dumps([fixture]))
            env = {
                "SHARP_MODEL_ATTESTATION_KEY": "m" * 40,
                "SHARP_ODDS_ATTESTATION_KEY": "o" * 40,
                "SHARP_RELEASE_ATTESTATION_KEY": "r" * 40,
                "SHARP_APPROVED_MODEL_VERSIONS": SharpEdgeCertificationTests.VERSION,
            }
            argv = ["live_certified_predictions", "--input", str(candidates),
                    "--output", str(output), "--feed-status", str(Path(tmp) / "missing.json")]
            with patch.dict(os.environ, env), patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
                main()
            d = json.loads(output.read_text())
            self.assertEqual(d["certified_take_count"], 0)
            self.assertEqual(d["feed_status"], "FEED_STATUS_MISSING")
            self.assertEqual(d["decisions"], [])
            self.assertIn("NO_SIGNED_CANDIDATES", d["certification_blockers"])

    def test_received_feed_count_mismatch_fails_closed(self):
        fixture = {"selection": "unsigned test candidate"}
        with tempfile.TemporaryDirectory() as tmp:
            candidates = Path(tmp) / "candidates.json"
            status = Path(tmp) / "status.json"
            output = Path(tmp) / "result.json"
            candidates.write_text(json.dumps([fixture]))
            status.write_text(json.dumps({"status": "FEED_RECEIVED", "candidate_count": 2}))
            argv = ["live_certified_predictions", "--input", str(candidates),
                    "--output", str(output), "--feed-status", str(status)]
            with patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
                main()
            result = json.loads(output.read_text())
            self.assertEqual(result["feed_status"], "FEED_CANDIDATE_COUNT_MISMATCH")
            self.assertEqual(result["certified_take_count"], 0)
            self.assertEqual(result["decisions"], [])
            self.assertIn("NO_SIGNED_CANDIDATES", result["certification_blockers"])

    def test_received_feed_matching_count_evaluates_unsigned_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            candidates = Path(tmp) / "candidates.json"
            status = Path(tmp) / "status.json"
            output = Path(tmp) / "result.json"
            candidates.write_text(json.dumps([{"selection": "unsigned test candidate"}]))
            status.write_text(json.dumps({"status": "FEED_RECEIVED", "candidate_count": 1}))
            argv = ["live_certified_predictions", "--input", str(candidates),
                    "--output", str(output), "--feed-status", str(status)]
            with patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
                main()
            result = json.loads(output.read_text())
            self.assertEqual(result["feed_status"], "FEED_RECEIVED")
            self.assertEqual(result["hold_count"], 1)
            self.assertEqual(result["certified_take_count"], 0)

if __name__ == "__main__":
    unittest.main()
