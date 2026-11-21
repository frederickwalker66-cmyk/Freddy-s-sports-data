import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.trusted_provider_gateway import (
    SourceUnavailable, collect_configured_sources, execute_frozen_champion,
    fetch_provider_json, readiness,
)


class TrustedGatewayTests(unittest.TestCase):
    def test_missing_configuration_fails_closed(self):
        result = readiness({})
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["certified_predictions"], 0)
        self.assertEqual(result["sources"]["odds"]["status"], "HOLD_NOT_CONFIGURED")
        self.assertEqual(result["sources"]["roster_injury"]["status"], "HOLD_NOT_CONFIGURED")

    def test_disallow_unpinned_or_insecure_hosts(self):
        for url in ("http://api.example.com/odds", "https://evil.example.com/odds",
                    "https://api.example.com:8443/odds", "https://user@api.example.com/odds"):
            with self.assertRaises(SourceUnavailable):
                fetch_provider_json(url, api_key="test", allowed_host="api.example.com")

    def test_configured_sources_do_not_certify(self):
        env = {"FREDDY_ODDS_URL": "https://api.example.com/odds",
               "FREDDY_ODDS_HOST": "api.example.com",
               "FREDDY_ODDS_API_KEY": "test"}
        with patch("research.trusted_provider_gateway.fetch_provider_json", return_value={
            "payload": [{"event": "x"}], "retrieved_at": "2026-11-21T00:00:00+00:00",
            "provider_host": "api.example.com"}):
            result = collect_configured_sources(env)
        self.assertEqual(result["odds"]["status"], "RECEIVED_UNVERIFIED_CONTENT")
        self.assertFalse(result["odds"]["provider_signature_verified"])

    def test_missing_champion_artifact_fails_closed(self):
        with self.assertRaises(SourceUnavailable):
            execute_frozen_champion({}, artifact_path="/missing/model",
                                    expected_sha256="0" * 64, runner_path="/missing/runner")
