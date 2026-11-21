import unittest
from research.sportsdataio_nba_probe import probe, HOST


class SportsDataIOProbeTests(unittest.TestCase):
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
        self.assertEqual(r["decision"], "HOLD")

    def test_invalid_day_rejected(self):
        with self.assertRaises(ValueError):
            probe(day="yesterday", env={})
