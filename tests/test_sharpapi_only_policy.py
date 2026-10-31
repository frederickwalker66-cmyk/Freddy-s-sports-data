"""Offline tests for the SharpAPI-only collection policy and 429 handling.

Synthetic provider responses only. No API requests, model forecasts or wagers.
"""
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from collector import get_page


class WorkflowProviderPolicyTests(unittest.TestCase):
    def test_sportsgameodds_collection_workflow_is_disabled(self):
        self.assertFalse(Path(".github/workflows/collect-sportsgameodds.yml").exists())

    def test_sharpapi_jobs_are_not_triggered_by_code_pushes(self):
        workflow = Path(".github/workflows/collect-sharpapi.yml").read_text(encoding="utf-8")
        self.assertNotIn("\n  push:\n", workflow)
        self.assertIn("\n  schedule:\n", workflow)
        self.assertIn("\n  workflow_dispatch:\n", workflow)
        self.assertIn("group: sharpapi-odds-api", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("challenger_ticket_preflight.py --staged validation_output/research_only.jsonl", workflow)

    def test_429_retry_after_then_success(self):
        error = HTTPError("https://example.test", 429, "throttled", {"Retry-After": "70"}, None)
        payload = io.BytesIO(json.dumps({"data": [], "pagination": {}}).encode("utf-8"))
        with patch("collector.urlopen", side_effect=[error, payload]) as opener, patch("collector.time.sleep") as sleeper:
            result = get_page("test-secret", "nba", "main")
        self.assertEqual(result["data"], [])
        self.assertEqual(opener.call_count, 2)
        sleeper.assert_called_once_with(70)

    def test_429_exhaustion_is_error_not_empty_quote_set(self):
        errors = [HTTPError("https://example.test", 429, "throttled", {}, None) for _ in range(2)]
        with patch("collector.urlopen", side_effect=errors), patch("collector.time.sleep") as sleeper:
            with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
                get_page("test-secret", "nba", "props")
        sleeper.assert_called_once_with(60)

    def test_long_retry_after_fails_closed_and_does_not_sleep(self):
        error = HTTPError("https://example.test", 429, "throttled", {"Retry-After": "3600"}, None)
        with patch("collector.urlopen", side_effect=[error]), patch("collector.time.sleep") as sleeper:
            with self.assertRaisesRegex(RuntimeError, "deferred by provider"):
                get_page("test-secret", "nba", "main")
        sleeper.assert_not_called()

    def test_non_429_http_error_does_not_retry_or_expose_key(self):
        error = HTTPError("https://example.test", 401, "unauthorized", {}, None)
        with patch("collector.urlopen", side_effect=[error]), patch("collector.time.sleep") as sleeper:
            with self.assertRaises(RuntimeError) as caught:
                get_page("private-test-secret", "nba", "props")
        self.assertNotIn("private-test-secret", str(caught.exception))
        sleeper.assert_not_called()


if __name__ == "__main__":
    unittest.main()
