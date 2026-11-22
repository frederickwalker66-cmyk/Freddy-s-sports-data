import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from research.sportsdataio_historical_quarantine import capture

class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit):
        return self.payload

class FakeOpener:
    def __init__(self, payload):
        self.payload = payload
    def open(self, request, timeout=15):
        assert request.full_url.startswith("https://api.sportsdata.io/v3/nba/")
        return FakeResponse(self.payload)

class QuarantineTests(unittest.TestCase):
    def test_original_bytes_preserved_and_never_promoted(self):
        raw = b'[ {"GameID":123,"Bookmaker":"DraftKings"} ]'
        with tempfile.TemporaryDirectory() as folder:
            r = capture("2026-11-05", "test-key", folder, opener=FakeOpener(raw))
            self.assertEqual((Path(folder)/r["original_response_path"]).read_bytes(), raw)
            self.assertEqual(r["original_response_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertFalse(r["historical_entitlement_independently_verified"])
            self.assertEqual(r["qualified_training_rows"], 0)
            self.assertEqual(r["certified_take_predictions"], 0)
            with self.assertRaises(ValueError):
                capture("2026-11-05", "test-key", folder, opener=FakeOpener(raw))
    def test_non_list_response_not_archived(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                capture("2026-11-05", "test-key", folder, opener=FakeOpener(b'{"error":"trial"}'))
            self.assertEqual(list(Path(folder).iterdir()), [])

if __name__ == "__main__":
    unittest.main()
