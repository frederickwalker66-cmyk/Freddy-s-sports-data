"""Offline fail-closed tests for SportsDataIO NBA schedule adapter."""
import unittest
from urllib.error import HTTPError
from challenger_sportsdataio_nba_schedule import (
    schedule_url, parsed_games, corroborate,
)
from test_challenger_nba_schedule_clock import unaccepted


class SportsDataIOAdapterTests(unittest.TestCase):
    def test_url_validation(self):
        self.assertEqual(schedule_url("2026-11-01"),
                         "https://api.sportsdata.io/v3/nba/scores/json/GamesByDate/2026-11-01")
        for day in ("2026-1-1", "bad", "2026-11-01/other"):
            with self.assertRaises(ValueError):
                schedule_url(day)

    def test_timezone_naive_games_not_misread_as_utc(self):
        self.assertEqual(parsed_games([{
            "GameID": 123, "HomeTeam": "BOS", "AwayTeam": "NY",
            "DateTime": "2026-11-01T19:00:00",
            "DateTimeUTC": "2026-11-02T00:00:00",
        }]), [])

    def test_explicit_utc_games_accepted(self):
        games = parsed_games([{
            "GameID": 123, "HomeTeam": "BOS", "AwayTeam": "NY",
            "DateTimeUTC": "2026-11-02T00:00:00Z",
        }])
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["id"], "123")

    def test_invalid_and_identical_team_codes_rejected(self):
        rows = [
            {"GameID": 1, "HomeTeam": "BOS", "AwayTeam": "BOS",
             "DateTimeUTC": "2026-11-02T00:00:00Z"},
            {"GameID": 2, "HomeTeam": "FAKE", "AwayTeam": "NY",
             "DateTimeUTC": "2026-11-02T00:00:00Z"},
            {"GameID": 3, "HomeTeam": "BOS", "AwayTeam": "NY",
             "DateTimeUTC": "2026-11-02T00:00:00Z"},
        ]
        self.assertEqual([g["id"] for g in parsed_games(rows)], ["3"])

    def test_success_still_quarantined(self):
        calls = []
        def fetch(day, key):
            calls.append((day, key))
            return [{"GameID": 123, "HomeTeam": "ATL",
                     "AwayTeam": "CLE", "DateTimeUTC": "2026-10-30T00:00:00Z"}]
        report = corroborate(unaccepted(), "test-only", fetch)
        self.assertEqual(len(calls), 1)
        self.assertEqual(report["qualified_utc_games_by_day"]["2026-10-29"], 1)
        self.assertEqual(report["near_time_mismatches_promoted"], 0)
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertEqual(report["bet_ready_selections"], 0)
        self.assertTrue(report["cases"][0]["remains_quarantined"])
        self.assertNotIn("test-only", str(report))

    def test_clock_corroboration_stays_quarantined(self):
        def fetch(day, key):
            return [{"GameID": 123, "HomeTeam": "ATL", "AwayTeam": "CLE",
                     "DateTimeUTC": "2026-10-30T00:00:00Z"}]
        report = corroborate(unaccepted(), "test-only", fetch)
        self.assertEqual(report["classification_counts"],
                         {"sportsdataio_clock_agrees_with_espn": 1})
        self.assertEqual(report["cases"][0]["sportsdataio_game_id"], "123")
        self.assertTrue(report["cases"][0]["remains_quarantined"])
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_alias_same_franchise_rejected(self):
        self.assertEqual(parsed_games([{
            "GameID": 321, "HomeTeam": "NY", "AwayTeam": "NYK",
            "DateTimeUTC": "2026-11-02T00:00:00Z"}]), [])

    def test_missing_credential_reports_configuration_gap_without_network(self):
        calls = []
        def forbidden(day, key):
            calls.append((day, key))
            raise AssertionError("no provider request permitted without credential")
        report = corroborate(unaccepted(), "", forbidden)
        self.assertEqual(calls, [])
        self.assertFalse(report["api_key_configured"])
        self.assertEqual(report["source_errors_by_day"],
                         {"2026-10-29": "credential_not_configured"})
        self.assertEqual(report["classification_counts"],
                         {"sportsdataio_source_unavailable": 1})
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_whitespace_only_credential_is_not_configured(self):
        report = corroborate(unaccepted(), "  ", lambda d, k: self.fail("network called"))
        self.assertFalse(report["api_key_configured"])
        self.assertEqual(report["source_errors_by_day"]["2026-10-29"],
                         "credential_not_configured")

    def test_collector_uses_existing_secret_alias_and_keeps_report(self):
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/collect-sharpapi.yml").read_text()
        self.assertIn("secrets.Sportsdataio || secrets.SPORTSDATAIO_API_KEY", workflow)
        self.assertIn("validation_output/sportsdataio_nba_diagnostic.json", workflow)
        self.assertIn("independently_verified_sportsbook_prices", workflow)
        self.assertNotIn("echo \"$SPORTSDATAIO_API_KEY\"", workflow)

    def test_scheduled_mls_job_cannot_show_false_success(self):
        from pathlib import Path
        yaml = (Path(__file__).resolve().parents[1] /
                ".github/workflows/sportsdataio-research-intake.yml").read_text()
        # Scheduled workflow has six source-backed jobs; manually dispatched
        # entitlement test may include MLS, and it MUST run the collector.
        self.assertIn("github.event_name == 'workflow_dispatch'", yaml)
        self.assertIn("'[\"nba\",\"nfl\",\"mlb\",\"nhl\",\"ncaaf\",\"ncaab\",\"mls\"]'", yaml)
        self.assertIn("'[\"nba\",\"nfl\",\"mlb\",\"nhl\",\"ncaaf\",\"ncaab\"]'", yaml)
        collector = yaml.split("- name: Collect ${{ matrix.league }} source evidence", 1)[1]
        self.assertIn("run: python sportsdataio_collector.py", collector)
        self.assertTrue(collector.index("run: python sportsdataio_collector.py") <
                        collector.index("- name: Validate quarantined"))
        self.assertNotIn("if: github.event_name == 'workflow_dispatch' || contains", yaml)

    def test_denial_does_not_disclose_secret(self):
        def fetch(day, key):
            raise HTTPError("https://example.com", 403, "denied", {}, None)
        report = corroborate(unaccepted(), "secret-example", fetch)
        self.assertEqual(report["source_errors_by_day"]["2026-10-29"], "HTTP_403")
        self.assertNotIn("secret-example", str(report))
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_unsafe_manifest_rejected(self):
        manifest = unaccepted()
        manifest["bet_ready_selections"] = 1
        with self.assertRaisesRegex(ValueError, "unsafe"):
            corroborate(manifest, "test", lambda d, k: [])


if __name__ == "__main__":
    unittest.main()
