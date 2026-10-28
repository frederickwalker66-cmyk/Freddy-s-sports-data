"""Offline NBA/MLB source and crosswalk tests; fixtures do not certify live props."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nba_cdn_fallback import BOXSCORE_PREFIX, SCOREBOARD, collect_game_day_players
from mlb_identity_audit import reconcile
from official_source_refresh import refresh


class NBAFallbackTests(unittest.TestCase):
    def mock_sources(self, url):
        if url == SCOREBOARD:
            return {"scoreboard": {"gameDate": "2026-10-28", "games": [
                {"gameId": "0022600001"}]}}
        if url == BOXSCORE_PREFIX + "0022600001.json":
            return {"game": {"gameId": "0022600001", "gameStatus": 1,
                "homeTeam": {"teamId": 1610612752, "teamName": "Knicks",
                             "teamCity": "New York", "teamTricode": "NYK",
                             "players": [{"personId": 101, "name": "Fixture Player",
                                          "status": "ACTIVE"}]},
                "awayTeam": {"teamId": 1610612738, "teamName": "Celtics",
                             "teamCity": "Boston", "teamTricode": "BOS",
                             "players": [{"personId": 102, "name": "Another Player"}]}}}
        raise ValueError("unrecognized fixture URL")

    def test_game_day_evidence_is_never_roster_or_play_clearance(self):
        data = collect_game_day_players("2026-10-28", self.mock_sources)
        self.assertEqual(data["status"], "evidence_downloaded")
        self.assertEqual(data["player_entries"], 2)
        self.assertFalse(data["crosswalk_verified"])
        self.assertFalse(data["complete_rosters_verified"])
        self.assertFalse(data["game_day_active_verified"])

    def test_wrong_date_fails_closed(self):
        with self.assertRaises(ValueError):
            collect_game_day_players("2026-10-27", self.mock_sources)

    def test_wrong_boxscore_game_id_is_partial_not_confirmed(self):
        def incorrect(url):
            if url == SCOREBOARD:
                return self.mock_sources(url)
            return {"game": {"gameId": "0022609999"}}
        data = collect_game_day_players("2026-10-28", incorrect)
        self.assertEqual(data["status"], "partial")
        self.assertEqual(data["fetched_games"], 0)
        self.assertFalse(data["game_day_active_verified"])

    def test_source_refresh_keeps_game_evidence_unverified(self):
        def offline(*args, **kwargs):
            raise RuntimeError("offline")
        fake_evidence = self.mock_sources
        with TemporaryDirectory() as temp:
            r = refresh("2026-10-28", temp, offline, offline,
                lambda day: collect_game_day_players(day, fake_evidence))
            self.assertEqual(r["sources"]["nba_game_day"]["status"], "evidence_downloaded")
            self.assertFalse(r["sources"]["nba_game_day"]["complete_rosters_verified"])
            self.assertFalse(r["sources"]["nba_game_day"]["provider_id_crosswalk_verified"])
            self.assertEqual(r["player_props_cleared"], 0)
            self.assertEqual(r["model_probabilities_generated"], 0)
            self.assertFalse(r["champion_001_modified"])
            self.assertTrue((Path(temp) / "nba_game_day_evidence.json").exists())


class MLBIdCandidateTests(unittest.TestCase):
    def setUp(self):
        self.rosters = {"teams": [
            {"team_id": 111, "team_name": "Boston Red Sox",
             "source_url": "https://statsapi.mlb.com/api/v1/teams/111/roster",
             "players": [{"official_player_id": 777, "player_name": "Example Hitter"}]},
            {"team_id": 147, "team_name": "New York Yankees",
             "source_url": "https://statsapi.mlb.com/api/v1/teams/147/roster",
             "players": [{"official_player_id": 888, "player_name": "Example Pitcher"}]}]}

    def quote(self, **kwargs):
        v = {"league": "mlb", "is_player_prop": True, "player_name": "Example Hitter",
             "player_id": "book-123", "home_team": "Boston Red Sox",
             "away_team": "New York Yankees", "event_id": "event-42",
             "timestamp": "2026-10-28T20:00:00Z"}
        v.update(kwargs)
        return v

    def test_exact_candidate_requires_review(self):
        result = reconcile([self.quote()], self.rosters)
        self.assertEqual(result["counts"]["exact_match_review_candidates"], 1)
        self.assertEqual(result["candidates"][0]["official_player_id_candidate"], 777)
        self.assertEqual(result["candidates"][0]["status"], "manual_review_required_not_verified")
        self.assertFalse(result["crosswalk_independently_verified"])
        self.assertEqual(result["bet_ready_selections"], 0)

    def test_wrong_team_missing_id_or_ambiguous_names_are_not_candidates(self):
        ambiguous = json.loads(json.dumps(self.rosters))
        ambiguous["teams"][0]["players"].append(
            {"official_player_id": 779, "player_name": "Example Hitter"})
        rows = [self.quote(home_team="Chicago Cubs", away_team="New York Yankees"),
                self.quote(player_id=None),
                self.quote()]
        result = reconcile(rows, ambiguous)
        self.assertEqual(result["counts"]["exact_match_review_candidates"], 0)
        self.assertEqual(result["counts"]["unresolved_prop_records"], 3)
        self.assertEqual(result["reasons"]["no_exact_official_match_in_game"], 1)
        self.assertEqual(result["reasons"]["missing_provider_player_id"], 1)
        self.assertEqual(result["reasons"]["ambiguous_official_match"], 1)


if __name__ == "__main__":
    unittest.main()
