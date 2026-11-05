"""Synthetic #78 NBA league-owned game identity and no-bet regression tests."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_eight_sport_independent_identity import audit, run
from challenger_nba_official_pregame_schedule import parse_original
from challenger_nba_schedule_clock import (
    NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL, stats_scoreboard_url,
)

NOW = datetime(2026, 11, 5, 18, 2, tzinfo=timezone.utc)
OBS = NOW.isoformat()
TIP = "2026-11-05T23:00:00Z"
GAME_ID = "0022600010"


def game(start=TIP, gid=GAME_ID, status=1,
         home_name="Knicks", home_id=1610612752,
         away_name="Celtics", away_id=1610612738):
    return {
        "gameId": gid, "gameStatus": status,
        "gameDateTimeUTC": start, "gameTimeUTC": start,
        "homeTeam": {"teamCity": "New York", "teamName": home_name, "teamId": home_id},
        "awayTeam": {"teamCity": "Boston", "teamName": away_name, "teamId": away_id},
    }


def season(games=None, league="00"):
    return json.dumps({"leagueSchedule": {
        "leagueId": league, "seasonYear": "2026-27",
        "gameDates": [{"gameDate": "2026-11-05",
                       "games": [game()] if games is None else games}],
    }}).encode("utf8")


def daily(games=None, day="2026-11-05", league="00"):
    return json.dumps({"scoreboard": {
        "gameDate": day, "leagueId": league,
        "games": [game()] if games is None else games,
    }}).encode("utf8")


def espn_row(gid="401", start=TIP, **changes):
    result = {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": "nba", "espn_schedule_event_id": gid,
        "home_team": "New York Knicks", "away_team": "Boston Celtics",
        "event_start_utc": start, "snapshot_completed_at_utc": "2026-11-05T18:01:00Z",
        "schedule_observed_at_utc": "2026-11-05T18:00:00Z",
        "odds_observations": [],
        "qualified_for_challenger_backtest": False,
        "model_probability": None, "certified_prediction": False,
        "bet_ready": False, "champion_001_modified": False,
    }
    return dict(result, **changes)


def receipt(body=None, url=NBA_SCHEDULE_URL, observed=OBS):
    return {url: {
        "raw": season() if body is None else body,
        "source_url": url,
        "observed_at_utc": observed,
    }}


class OfficialNBAOriginalTests(unittest.TestCase):
    def test_original_season_source_has_canonical_team_ids(self):
        games, checksum, kind = parse_original(season(), NBA_SCHEDULE_URL, NOW)
        self.assertEqual(len(games), 1)
        self.assertEqual(kind, "nba_season_schedule")
        self.assertEqual(games[0]["nba_game_id"], GAME_ID)
        self.assertEqual((games[0]["home_id"], games[0]["away_id"]),
                         ("1610612752", "1610612738"))
        self.assertEqual(checksum, hashlib.sha256(season()).hexdigest())

    def test_genuine_daily_and_stats_scoreboard_validated_for_current_et_date(self):
        urls = [NBA_TODAY_SCOREBOARD_URL, stats_scoreboard_url("2026-11-05")]
        for url in urls:
            with self.subTest(url=url):
                games, checksum, kind = parse_original(daily(), url, NOW)
                self.assertEqual(games[0]["nba_game_id"], GAME_ID)
                self.assertTrue(checksum)
        with self.assertRaisesRegex(ValueError, "source_url_not_allowed"):
            parse_original(daily(), stats_scoreboard_url("2026-11-04"), NOW)
        with self.assertRaisesRegex(ValueError, "stale_or_wrong_league"):
            parse_original(daily(day="2026-11-04"), NBA_TODAY_SCOREBOARD_URL, NOW)

    def test_bad_league_team_ids_and_missing_original_bytes_fail(self):
        for body in (
            season(league="01"),
            season([game(home_id=1610612738)]),
            season([game(gid="bad")]),
            season([game(), game()]),
            b"{}", b"",
        ):
            with self.subTest(body=body[:60]), self.assertRaises(ValueError):
                parse_original(body, NBA_SCHEDULE_URL, NOW)

    def test_started_or_completed_nba_game_is_not_upcoming_proof(self):
        result, _, _ = parse_original(season([game(status=3)]), NBA_SCHEDULE_URL, NOW)
        self.assertEqual(result, [])
        past = "2026-11-05T17:00:00Z"
        result, _, _ = parse_original(daily([game(start=past)]),
                                      NBA_TODAY_SCOREBOARD_URL, NOW)
        self.assertEqual(result, [])


class NBAIdentityCrosscheckTests(unittest.TestCase):
    def test_exact_nba_source_corrob_and_zero_certification(self):
        rows, report = audit([espn_row()], {}, {}, receipt())
        self.assertEqual(report["independently_observed_nba_pregame_identity_matches_research_only"], 1)
        self.assertEqual(rows[0]["nba_official_game_id"], GAME_ID)
        self.assertEqual(rows[0]["nba_official_home_team_id"], "1610612752")
        self.assertEqual(rows[0]["nba_original_response_sha256"],
                         hashlib.sha256(season()).hexdigest())
        self.assertTrue(rows[0]["official_league_pregame_identity_matched_research_only"])
        self.assertFalse(rows[0]["exact_draftkings_market_identity_verified"])
        self.assertFalse(rows[0]["bet_ready"])
        self.assertFalse(report["champion_001_modified"])
        for key in ("direct_draftkings_checkout_markets_verified",
                    "verified_native_model_probabilities",
                    "qualified_chronological_training_games",
                    "certified_champion_001_predictions",
                    "certified_challenger_001_predictions",
                    "certified_positive_ev_bets",
                    "automated_bets_placed"):
            self.assertEqual(report[key], 0)

    def test_missing_invalid_or_source_denial_does_not_invent_game(self):
        rows, _ = audit([espn_row()], {}, {}, {})
        self.assertEqual(rows[0]["identity_status"], "nba_official_response_not_captured")
        rows, report = audit([espn_row()], {}, {}, receipt(body=b"{}"))
        self.assertEqual(rows[0]["identity_status"], "invalid_nba_original_response")
        self.assertIn(NBA_SCHEDULE_URL, report["nba_source_errors"])

    def test_late_capture_missing_team_or_start_clock_mismatch(self):
        rows, _ = audit([espn_row()], {}, {}, receipt(observed="2026-11-06T00:00:00Z"))
        self.assertEqual(rows[0]["identity_status"], "nba_response_not_observed_pregame")
        rows, _ = audit([espn_row()], {}, {}, receipt(body=season([game(home_name="Unknown")])))
        self.assertEqual(rows[0]["identity_status"], "invalid_nba_original_response")
        rows, _ = audit([espn_row()], {}, {}, receipt(body=season([
            game(start="2026-11-05T23:02:00Z")])))
        self.assertEqual(rows[0]["identity_status"], "nba_kickoff_disagrees")

    def test_multiple_ids_same_match_not_arbitrarily_selected(self):
        rows, _ = audit([espn_row()], {}, {}, receipt(body=season([
            game(), game(gid="0022600011")])))
        self.assertEqual(rows[0]["identity_status"], "nba_match_missing_or_ambiguous")

    def test_same_nba_id_cannot_map_to_two_espn_ids(self):
        with self.assertRaisesRegex(ValueError, "nba_official_game_reused"):
            audit([espn_row(), espn_row(gid="402")], {}, {}, receipt())

    def test_two_original_nba_feeds_with_conflicting_start_quarantined(self):
        packets = {
            **receipt(),
            **receipt(url=NBA_TODAY_SCOREBOARD_URL,
                      body=daily([game(start="2026-11-05T23:02:00Z")]))
        }
        rows, _ = audit([espn_row()], {}, {}, packets)
        self.assertEqual(rows[0]["identity_status"],
                         "nba_conflicting_official_game_revisions")

    def test_model_and_archive_safety_refuse_promoted_evidence(self):
        for changes in (
            {"snapshot_completed_at_utc": TIP},
            {"model_probability": 0.6},
            {"certified_prediction": True},
            {"bet_ready": True},
            {"champion_001_modified": True},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                audit([espn_row(**changes)], {}, {}, receipt())

    def test_runner_writes_original_nba_bytes_and_no_extra_nhl_mlb_requests(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "source"
            src.mkdir()
            (src / "prospective_event_evidence.jsonl").write_text(
                json.dumps(espn_row()) + "\n")
            (src / "eight_sport_schedule_coverage.json").write_text(json.dumps({
                "archived_games_matching_exact_original_event_fields": 1,
                "original_espn_source_responses_verified": 1,
                "certified_positive_ev_bets": 0,
                "champion_001_modified": False,
            }))
            calls = []
            def nba_fetch(url):
                calls.append(url)
                return season()
            out = Path(tmp) / "independent"
            result = run(src, out,
                         fetcher=lambda day: self.fail("Unexpected NHL call"),
                         mlb_fetcher=lambda day: self.fail("Unexpected MLB call"),
                         nba_fetcher=nba_fetch, clock=lambda: NOW)
            self.assertEqual(calls, [NBA_SCHEDULE_URL])
            self.assertEqual((out / "nba_official_season_schedule.json").read_bytes(), season())
            self.assertEqual(result["independently_observed_nba_pregame_identity_matches_research_only"], 1)
            self.assertEqual(result["certified_positive_ev_bets"], 0)

    def test_denied_season_falls_back_to_current_day_but_never_guesses(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "source"
            src.mkdir()
            (src / "prospective_event_evidence.jsonl").write_text(json.dumps(espn_row()) + "\n")
            (src / "eight_sport_schedule_coverage.json").write_text(json.dumps({
                "archived_games_matching_exact_original_event_fields": 1,
                "original_espn_source_responses_verified": 1,
                "certified_positive_ev_bets": 0, "champion_001_modified": False,
            }))
            calls = []
            def nba_fetch(url):
                calls.append(url)
                if url == NBA_SCHEDULE_URL:
                    raise OSError("blocked public CDN")
                if url == NBA_TODAY_SCOREBOARD_URL:
                    return daily()
                self.fail("Unexpected third source call")
            report = run(src, Path(tmp) / "second",
                         nba_fetcher=nba_fetch, clock=lambda: NOW)
            self.assertEqual(calls, [NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL])
            self.assertEqual(report["independently_observed_nba_pregame_identity_matches_research_only"], 1)
            self.assertIn(NBA_SCHEDULE_URL, report["network_nba_source_failures_by_url"])

    def test_all_public_nba_source_denials_remain_zero_confirmations(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "source"
            src.mkdir()
            (src / "prospective_event_evidence.jsonl").write_text(json.dumps(espn_row()) + "\n")
            (src / "eight_sport_schedule_coverage.json").write_text(json.dumps({
                "archived_games_matching_exact_original_event_fields": 1,
                "original_espn_source_responses_verified": 1,
                "certified_positive_ev_bets": 0, "champion_001_modified": False,
            }))
            calls = []
            def denied(url):
                calls.append(url)
                raise OSError("denied")
            report = run(src, Path(tmp) / "empty", nba_fetcher=denied, clock=lambda: NOW)
            self.assertEqual(calls, [NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL,
                                     stats_scoreboard_url("2026-11-05")])
            self.assertEqual(report["independently_observed_nba_pregame_identity_matches_research_only"], 0)
            self.assertEqual(report["independent_identity_unverified"], 1)
            self.assertEqual(report["certified_positive_ev_bets"], 0)


if __name__ == "__main__":
    unittest.main()
