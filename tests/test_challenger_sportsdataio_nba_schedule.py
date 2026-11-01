"""Offline fail-closed tests for SportsDataIO NBA schedule adapter."""
import unittest
from urllib.error import HTTPError
from challenger_sportsdataio_nba_schedule import (
    schedule_url, parsed_games, parse_games_with_diagnostics, corroborate,
)
from test_challenger_nba_schedule_clock import unaccepted


class SportsDataIOAdapterTests(unittest.TestCase):
    def test_url_validation(self):
        self.assertEqual(schedule_url("2026-11-01"),
                         "https://api.sportsdata.io/v3/nba/scores/json/GamesByDate/2026-11-01")
        for day in ("2026-1-1", "bad", "2026-11-01/other"):
            with self.assertRaises(ValueError):
                schedule_url(day)

    def test_documented_naive_utc_field_checked_against_eastern(self):
        games, info = parse_games_with_diagnostics([{
            "GameID": 123, "HomeTeam": "BOS", "AwayTeam": "NY",
            "DateTime": "2026-11-01T19:00:00",
            "DateTimeUTC": "2026-11-02T00:00:00",
        }])
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["start"].isoformat(), "2026-11-02T00:00:00+00:00")
        self.assertEqual(info["naive_named_utc_clocks_validated"], 1)
        self.assertEqual(info["rejection_causes"], {})

    def test_real_sportsdataio_serialization_from_archived_nba_games(self):
        # Schema from a genuine, previously archived NBA provider response;
        # do not publish the archived raw payload or treat this as current odds.
        rows = [
            {"GameID": 24024, "HomeTeam": "UTA", "AwayTeam": "POR",
             "DateTime": "2026-10-31T15:00:00",
             "DateTimeUTC": "2026-10-31T19:00:00", "Status": "Final"},
            {"GameID": 24025, "HomeTeam": "CHA", "AwayTeam": "PHI",
             "DateTime": "2026-10-31T18:00:00",
             "DateTimeUTC": "2026-10-31T22:00:00", "Status": "Final"},
            {"GameID": 24030, "HomeTeam": "HOU", "AwayTeam": "OKC",
             "DateTime": "2026-10-31T20:30:00",
             "DateTimeUTC": "2026-11-01T00:30:00", "Status": "Final"},
        ]
        games, info = parse_games_with_diagnostics(rows)
        self.assertEqual(len(games), 3)
        self.assertEqual(info["provider_rows_received"], 3)
        self.assertEqual(info["naive_named_utc_clocks_validated"], 3)
        self.assertEqual(info["rejection_causes"], {})

    def test_conflicting_local_and_utc_fields_remain_quarantined(self):
        good = {"GameID": 100, "HomeTeam": "BOS", "AwayTeam": "NY",
                "DateTimeUTC": "2026-11-02T00:00:00"}
        rows = [dict(good, DateTime="2026-11-01T18:00:00"),
                {"GameID": 101, "HomeTeam": "BOS", "AwayTeam": "NY",
                 "DateTimeUTC": "2026-11-02T00:00:00-05:00"},
                {"GameID": 102, "HomeTeam": "BOS", "AwayTeam": "BOS",
                 "DateTimeUTC": "2026-11-02T00:00:00Z"}]
        games, info = parse_games_with_diagnostics(rows)
        self.assertEqual(games, [])
        self.assertEqual(info["rejection_causes"],
                         {"non_utc_offset_in_utc_field": 1,
                          "unknown_or_conflicting_team_codes": 1,
                          "utc_eastern_clock_disagreement": 1})

    def test_fall_back_dst_clock_is_validated_from_utc_instant(self):
        rows = [{"GameID": 10, "HomeTeam": "BOS", "AwayTeam": "NY",
                 "DateTime": "2026-11-01T01:30:00",
                 "DateTimeUTC": "2026-11-01T05:30:00"},
                {"GameID": 11, "HomeTeam": "BOS", "AwayTeam": "NY",
                 "DateTime": "2026-11-01T01:30:00",
                 "DateTimeUTC": "2026-11-01T06:30:00"}]
        games, info = parse_games_with_diagnostics(rows)
        self.assertEqual(len(games), 2)
        self.assertNotEqual(games[0]["start"], games[1]["start"])
        self.assertEqual(info["naive_named_utc_clocks_validated"], 2)

    def test_duplicate_deleted_and_invalid_rows_reported_only_in_counts(self):
        rows = [{"GameID": 1, "HomeTeam": "BOS", "AwayTeam": "NY",
                 "DateTimeUTC": "2026-11-02T00:00:00"},
                {"GameID": 1, "HomeTeam": "BOS", "AwayTeam": "NY",
                 "DateTimeUTC": "2026-11-02T00:00:00"},
                {"GameID": 2, "HomeTeam": "BOS", "AwayTeam": "NY",
                 "DateTimeUTC": "2026-11-02T00:00:00", "Deleted": True},
                {"GameID": True, "HomeTeam": "BOS", "AwayTeam": "NY",
                 "DateTimeUTC": "2026-11-02T00:00:00"}]
        games, info = parse_games_with_diagnostics(rows)
        self.assertEqual(games, [])
        self.assertEqual(info["rejection_causes"],
                         {"duplicate_game_id": 2,
                          "deleted_or_cancelled_game": 1,
                          "invalid_game_id": 1})
        self.assertNotIn("HomeTeam", str(info))

    def test_naive_utc_corroboration_never_approves_market_or_model(self):
        def fetch(day, key):
            return [{"GameID": 123, "HomeTeam": "ATL",
                     "AwayTeam": "CLE", "DateTime": "2026-10-29T20:00:00",
                     "DateTimeUTC": "2026-10-30T00:00:00"}]
        report = corroborate(unaccepted(), "test-only", fetch)
        self.assertEqual(report["provider_rows_by_day"], {"2026-10-29": 1})
        self.assertEqual(report["qualified_utc_games_by_day"], {"2026-10-29": 1})
        self.assertEqual(report["naive_named_utc_clocks_validated_by_day"],
                         {"2026-10-29": 1})
        self.assertEqual(report["classification_counts"],
                         {"sportsdataio_clock_agrees_with_espn": 1})
        self.assertTrue(report["cases"][0]["remains_quarantined"])
        self.assertEqual(report["bet_ready_selections"], 0)
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertNotIn("test-only", str(report))

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
