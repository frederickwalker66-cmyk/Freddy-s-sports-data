"""Fictional NBA/MLB source and matching tests. No certified predictions."""
import unittest
from nba_cdn_fallback import collect_game_day_players, SCOREBOARD
from mlb_identity_audit import reconcile


def nba_fixture(url):
    if url == SCOREBOARD:
        return {"scoreboard": {"gameDate": "2026-10-28",
                               "games": [{"gameId": "0022600001"}]}}
    return {"game": {"gameId": "0022600001", "gameStatus": 1,
                     "homeTeam": {"teamId": 1610612737, "teamName": "Hawks",
                                  "teamCity": "Atlanta", "teamTricode": "ATL",
                                  "players": [{"personId": 12345, "name": "Fixture Player",
                                               "status": "ACTIVE", "notPlayingReason": None}]},
                     "awayTeam": {"teamId": 1610612741, "teamName": "Bulls",
                                  "teamCity": "Chicago", "teamTricode": "CHI",
                                  "players": []}}}


class NbaFallbackTests(unittest.TestCase):
    def test_game_player_evidence_not_approved_bet(self):
        r = collect_game_day_players("2026-10-28", nba_fixture)
        self.assertEqual(r["status"], "evidence_downloaded")
        self.assertEqual(r["fetched_games"], 1)
        self.assertEqual(r["player_entries"], 1)
        self.assertEqual(r["games"][0]["teams"][0]["players"][0]["official_player_id"], 12345)
        self.assertFalse(r["crosswalk_verified"])
        self.assertFalse(r["game_day_active_verified"])
        self.assertFalse(r["complete_rosters_verified"])

    def test_stale_scoreboard_never_accepted(self):
        with self.assertRaisesRegex(ValueError, "date mismatch"):
            collect_game_day_players("2026-10-29", nba_fixture)

    def test_wrong_boxscore_game_id_is_partial(self):
        def wrong(url):
            data = nba_fixture(url)
            if url != SCOREBOARD:
                data["game"]["gameId"] = "0022600002"
            return data
        r = collect_game_day_players("2026-10-28", wrong)
        self.assertEqual(r["status"], "partial")
        self.assertEqual(r["fetched_games"], 0)

    def test_missing_team_players_is_partial(self):
        def missing(url):
            data = nba_fixture(url)
            if url != SCOREBOARD:
                del data["game"]["homeTeam"]["players"]
            return data
        r = collect_game_day_players("2026-10-28", missing)
        self.assertEqual(r["status"], "partial")


def mlb_roster(name="Example Hitter", team="Milwaukee Brewers", pid=12345):
    return {"teams": [
        {"team_name": team, "team_id": 158,
         "source_url": "https://statsapi.mlb.com/api/v1/teams/158/roster",
         "players": [{"official_player_id": pid, "player_name": name}]},
        {"team_name": "Tampa Bay Rays", "team_id": 139,
         "source_url": "https://statsapi.mlb.com/api/v1/teams/139/roster",
         "players": [{"official_player_id": 12346, "player_name": "Other Hitter"}]}]}


def quote(**updates):
    data = {"league": "mlb", "is_player_prop": True,
            "event_id": "fixture-game", "home_team": "Tampa Bay Rays",
            "away_team": "Milwaukee Brewers", "player_name": "Example Hitter",
            "player_id": "sharpapi-xyz", "timestamp": "2026-10-28T21:00:00Z"}
    data.update(updates)
    return data


class MlbCrosswalkTests(unittest.TestCase):
    def test_exact_match_only_manual_review(self):
        r = reconcile([quote()], mlb_roster())
        self.assertEqual(r["counts"]["exact_match_review_candidates"], 1)
        candidate = r["candidates"][0]
        self.assertEqual(candidate["official_player_id_candidate"], 12345)
        self.assertEqual(candidate["provider_player_id"], "sharpapi-xyz")
        self.assertEqual(candidate["status"], "manual_review_required_not_verified")
        self.assertFalse(r["crosswalk_independently_verified"])
        self.assertEqual(r["bet_ready_selections"], 0)

    def test_missing_provider_id_rejected(self):
        r = reconcile([quote(player_id=None)], mlb_roster())
        self.assertEqual(r["counts"]["exact_match_review_candidates"], 0)
        self.assertEqual(r["reasons"]["missing_provider_player_id"], 1)

    def test_player_no_longer_on_game_team_rejected(self):
        r = reconcile([quote()], mlb_roster(team="Other Club"))
        self.assertEqual(r["counts"]["exact_match_review_candidates"], 0)
        self.assertEqual(r["reasons"]["no_exact_official_match_in_game"], 1)

    def test_ambiguous_same_name_rejected(self):
        r = reconcile([quote()], {"teams": [
            {"team_name": "Milwaukee Brewers", "team_id": 158,
             "players": [{"official_player_id": 12, "player_name": "Example Hitter"}]},
            {"team_name": "Tampa Bay Rays", "team_id": 139,
             "players": [{"official_player_id": 13, "player_name": "Example Hitter"}]}]})
        self.assertEqual(r["counts"]["exact_match_review_candidates"], 0)
        self.assertEqual(r["reasons"]["ambiguous_official_match"], 1)

    def test_multiple_odds_snapshots_not_certified(self):
        r = reconcile([quote(), quote()], mlb_roster())
        self.assertEqual(r["counts"]["exact_match_review_candidates"], 2)
        self.assertEqual(r["certified_champion_001_predictions"], 0)
        self.assertFalse(r["champion_001_modified"])

if __name__ == "__main__":
    unittest.main()
