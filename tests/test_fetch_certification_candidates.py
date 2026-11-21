"""Offline regression tests for the independently controlled candidate intake."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.fetch_certification_candidates import SCHEMA, collect, fetch


class FakeResponse:
    def __init__(self, payload, url="https://evidence.example/api/candidates"):
        self.payload = payload
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def geturl(self):
        return self.url

    def read(self, n):
        return self.payload[:n]


class FeedTests(unittest.TestCase):
    URL = "https://evidence.example/api/candidates"
    TOKEN = "t" * 40

    def open_response(self, body, url=None):
        return lambda request, timeout: FakeResponse(body, url or self.URL)

    def test_no_feed_is_explicit_and_old_candidates_are_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "input.json"
            report = Path(tmp) / "feed_status.json"
            inp.write_text('[{"stale":true}]')
            status = collect("", "", out=inp, status_out=report)
            self.assertEqual(status["status"], "FEED_NOT_CONFIGURED")
            self.assertFalse(inp.exists())
            self.assertFalse(status["certification_performed"])
            self.assertEqual(json.loads(report.read_text())["candidate_count"], 0)

    def test_fetch_valid_signed_candidate_container_not_certification(self):
        body = json.dumps({"schema": SCHEMA, "candidates": [{"model_attestation": {}, "odds_attestation": {}}]}).encode()
        result = fetch(self.URL, self.TOKEN, open_request=self.open_response(body))
        self.assertEqual(len(result), 1)
        with tempfile.TemporaryDirectory() as tmp:
            status = collect(self.URL, self.TOKEN, out=Path(tmp) / "input.json",
                             status_out=Path(tmp) / "status.json",
                             open_request=self.open_response(body))
            self.assertEqual(status["status"], "FEED_RECEIVED")
            self.assertFalse(status["certification_performed"])
            self.assertFalse(status["checkout_quote_authenticated"])

    def test_empty_feed_is_not_a_certified_pick(self):
        body = json.dumps({"schema": SCHEMA, "candidates": []}).encode()
        with tempfile.TemporaryDirectory() as tmp:
            status = collect(self.URL, self.TOKEN, out=Path(tmp) / "input.json",
                             status_out=Path(tmp) / "status.json",
                             open_request=self.open_response(body))
            self.assertEqual(status["status"], "FEED_EMPTY")
            self.assertEqual(status["candidate_count"], 0)

    def test_unsafe_feed_endpoint_and_missing_token_are_rejected(self):
        body = json.dumps({"schema": SCHEMA, "candidates": []}).encode()
        for url in ["http://evidence.example/api/candidates",
                    "https://user:password@evidence.example/api/candidates",
                    "https://evidence.example/api/candidates#fragment"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                fetch(url, self.TOKEN, open_request=self.open_response(body))
        with self.assertRaises(ValueError):
            fetch(self.URL, "short", open_request=self.open_response(body))

    def test_redirects_and_oversized_batches_are_rejected(self):
        good = json.dumps({"schema": SCHEMA, "candidates": []}).encode()
        with self.assertRaises(ValueError):
            fetch(self.URL, self.TOKEN, open_request=self.open_response(
                good, "https://other.example/api/candidates"))
        huge = b"x" * 1_000_001
        with self.assertRaises(ValueError):
            fetch(self.URL, self.TOKEN, open_request=self.open_response(huge))
        batch = json.dumps({"schema": SCHEMA, "candidates": [{}] * 501}).encode()
        with self.assertRaises(ValueError):
            fetch(self.URL, self.TOKEN, open_request=self.open_response(batch))

    def test_invalid_schema_and_nonobject_candidate_are_rejected(self):
        for data in [{"schema": "wrong", "candidates": []},
                     {"schema": SCHEMA, "candidates": ["not an object"]}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                fetch(self.URL, self.TOKEN, open_request=self.open_response(json.dumps(data).encode()))

    def test_failed_feed_reports_blocker_and_zero_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = collect(self.URL, self.TOKEN, out=Path(tmp)/"input.json",
                             status_out=Path(tmp)/"status.json",
                             open_request=lambda request, timeout: (_ for _ in ()).throw(OSError("source offline")))
            self.assertEqual(status["status"], "FEED_UNAVAILABLE_OR_INVALID")
            self.assertEqual(status["candidate_count"], 0)


if __name__ == "__main__":
    unittest.main()
