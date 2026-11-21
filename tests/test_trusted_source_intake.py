import io
import json
import unittest
from datetime import datetime, timezone
from research.trusted_source_intake import collect, collect_one


class Response:
    status = 200
    def __init__(self, data):
        self.stream = io.BytesIO(json.dumps(data).encode())
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, n):
        return self.stream.read(n)


class TrustedSourceTests(unittest.TestCase):
    def test_missing_credentials_fail_closed(self):
        result = collect(env={})
        self.assertEqual(result["certified_take_count"], 0)
        self.assertEqual(result["sources"]["sportsbook"]["status"], "HOLD_NOT_CONFIGURED")
        self.assertEqual(result["native_champion_001"]["verified_predictions"], 0)

    def test_authenticated_transport_not_certified(self):
        def opener(req, **kwargs):
            self.assertIn("Ocp-apim-Subscription-key", {k.lower().replace("key","key").title():v for k,v in []} if False else [k for k in req.headers])
            return Response([{"game": "test"}])
        env = {"FREDDY_ODDS_URL": "https://api.example.com/odds",
               "FREDDY_ODDS_API_KEY": "test-token"}
        result = collect_one("sportsbook", env=env, opener=opener,
                             now=datetime(2026, 11, 21, tzinfo=timezone.utc))
        self.assertEqual(result["status"], "RECEIVED_AUTHENTICATED_HTTPS_UNVERIFIED_CONTENT")
        self.assertFalse(result["authenticated"])

    def test_rejects_insecure_endpoint(self):
        result = collect_one("sportsbook", env={"FREDDY_ODDS_URL": "http://localhost/odds",
                                              "FREDDY_ODDS_API_KEY": "secret"})
        self.assertEqual(result["status"], "HOLD_INVALID_ENDPOINT")
