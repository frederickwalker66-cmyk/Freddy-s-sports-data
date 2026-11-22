import unittest
import urllib.error
from research.trusted_provider_gateway import SourceUnavailable
from research.sportsdataio_nba_probe import probe, schema_shape, HOST


class SportsDataIOProbeTests(unittest.TestCase):
    def test_schema_shape_omits_values(self):
        shape = schema_shape([{"Sportsbook": "DraftKings", "Odds": -110, "Nested": {"token": "secret"}}])
        self.assertEqual(shape["field_names"], ["Nested", "Odds", "Sportsbook"])
        self.assertNotIn("DraftKings", str(shape))
        self.assertNotIn("secret", str(shape))

    def test_missing_keys_hold(self):
        r = probe(day="2026-11-21", env={})
        self.assertEqual(r["certified_take_count"], 0)
        self.assertTrue(all(x["status"] == "HOLD_API_KEY_NOT_CONFIGURED"
                            for x in r["endpoints"].values()))

    def test_documented_urls_and_separate_keys(self):
        calls = []
        def fake_fetch(url, *, api_key, allowed_host):
            calls.append((url, api_key, allowed_host))
            return {"payload": [], "retrieved_at": "2026-11-21T15:00:00Z"}
        r = probe(day="2026-11-21", env={
            "SPORTSDATAIO_ODDS_API_KEY": "odds-test",
            "SPORTSDATAIO_NBA_API_KEY": "players-test",
        }, fetch=fake_fetch)
        self.assertEqual(len(calls), 4)
        self.assertIn("/odds/json/GameOddsByDate/2026-11-21", calls[0][0])
        self.assertIn("/odds/json/BettingEventsByDate/2026-11-21", calls[1][0])
        self.assertIn("/scores/json/Players", calls[2][0])
        self.assertIn("/projections/json/InjuredPlayers", calls[3][0])
        self.assertEqual([x[1] for x in calls], ["odds-test", "odds-test", "players-test", "players-test"])
        self.assertTrue(all(x[2] == HOST for x in calls))
        self.assertEqual(r["certified_take_count"], 0)
        self.assertEqual(r["endpoints"]["pregame_odds"]["status"], "HOLD_EMPTY_PROVIDER_RESPONSE")
        self.assertEqual(r["decision"], "HOLD")

    def test_provider_http_error_classified_without_leaking_message(self):
        def fetch(url, *, api_key, allowed_host):
            try:
                raise urllib.error.HTTPError(url, 403, "secret detail", {}, None)
            except urllib.error.HTTPError as cause:
                raise SourceUnavailable("provider_request_failed") from cause
        r = probe(day="2026-11-22", env={"SPORTSDATAIO_ODDS_API_KEY": "secret"}, fetch=fetch)
        self.assertEqual(r["endpoints"]["betting_events"]["status"], "HOLD_PROVIDER_HTTP_ERROR")
        self.assertEqual(r["endpoints"]["betting_events"]["http_status"], 403)
        self.assertNotIn("secret", str(r))

    def test_invalid_json_and_schema_hold_separately(self):
        def bad_json(url, *, api_key, allowed_host):
            try:
                raise ValueError("sensitive response")
            except ValueError as cause:
                raise SourceUnavailable("provider_request_failed") from cause
        env = {"SPORTSDATAIO_ODDS_API_KEY": "key"}
        r = probe(day="2026-11-22", env=env, fetch=bad_json)
        self.assertEqual(r["endpoints"]["betting_events"]["status"], "HOLD_PROVIDER_INVALID_JSON")
        def wrong_schema(url, *, api_key, allowed_host):
            return {"payload": {"message": "not a list"}, "retrieved_at": "2026-11-22T00:00:00Z"}
        r = probe(day="2026-11-22", env=env, fetch=wrong_schema)
        self.assertEqual(r["endpoints"]["betting_events"]["status"], "HOLD_UNEXPECTED_PROVIDER_SCHEMA")
        self.assertEqual(r["certified_take_count"], 0)

    def test_invalid_day_rejected(self):
        with self.assertRaises(ValueError):
            probe(day="yesterday", env={})
