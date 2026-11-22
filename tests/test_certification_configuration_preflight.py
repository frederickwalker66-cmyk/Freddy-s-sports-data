import unittest
from scripts.certification_configuration_preflight import assess

class ConfigurationPreflightTests(unittest.TestCase):
    def test_missing_configuration_is_hold(self):
        r = assess({})
        self.assertFalse(r["configuration_ready_for_live_fetch"])
        self.assertEqual(r["decision"], "HOLD")
        self.assertEqual(r["certified_take_count"], 0)

    def test_distinct_configured_values_still_not_certified(self):
        env = {
            "SHARP_CERTIFICATION_FEED_URL": "https://example.com/feed",
            "SHARP_CERTIFICATION_FEED_TOKEN": "t"*40,
            "SHARP_MODEL_ATTESTATION_KEY": "a"*40,
            "SHARP_ODDS_ATTESTATION_KEY": "b"*40,
            "SHARP_RELEASE_ATTESTATION_KEY": "c"*40,
            "SHARP_APPROVED_MODEL_VERSIONS": "Champion-001",
        }
        r = assess(env)
        self.assertTrue(r["configuration_ready_for_live_fetch"])
        self.assertFalse(r["candidate_feed_authenticated"])
        self.assertEqual(r["certified_take_count"], 0)

    def test_same_signing_key_fails(self):
        env = {
            "SHARP_CERTIFICATION_FEED_URL": "https://example.com/feed",
            "SHARP_CERTIFICATION_FEED_TOKEN": "t"*40,
            "SHARP_MODEL_ATTESTATION_KEY": "a"*40,
            "SHARP_ODDS_ATTESTATION_KEY": "a"*40,
            "SHARP_RELEASE_ATTESTATION_KEY": "c"*40,
            "SHARP_APPROVED_MODEL_VERSIONS": "Champion-001",
        }
        self.assertIn("INDEPENDENT_SIGNING_KEYS_NOT_DISTINCT",
                      assess(env)["missing_or_invalid_configuration_names"])

if __name__ == "__main__":
    unittest.main()
