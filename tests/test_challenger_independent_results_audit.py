"""Offline fixtures: independent outcomes never become training-ready."""
from datetime import datetime, timezone
import unittest
from challenger_independent_results_audit import audit, evidence_request, independent_games


class SecondaryAuditTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "record_type": "historical_completed_game_research",
            "outcome_source": "espn_public_scoreboard", "official_league_result_verified": False,
            "champion_001_modified": False, "league": "mlb",
            "source_url": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates=20260801",
            "retrieved_at_utc": "2026-10-29T19:00:00+00:00",
            "event_start_utc": "2026-08-01T23:00:00+00:00",
            "espn_event_id": "401234", "home_team_espn_id": "10", "away_team_espn_id": "20",
            "home_team": "New York Yankees", "away_team": "Boston Red Sox",
            "home_score": 5, "away_score": 3, "result": "home",
        }
        self.candidate = {"league": "mlb", "event_id": "401234",
                          "qualified_for_challenger_backtest": False, "bet_ready": False}
        self.g = {"gamePk": 999, "gameDate": "2026-08-01T23:00:00Z",
                  "status": {"abstractGameState": "Final"}, "teams": {
                      "home": {"team": {"name": "New York Yankees"}, "score": 5},
                      "away": {"team": {"name": "Boston Red Sox"}, "score": 3}}}
        self.payload = {"dates": [{"games": [self.g]}]}

    def run_audit(self):
        return audit([self.row], [self.candidate], "mlb", self.payload,
                     "https://statsapi.mlb.com/api/v1/schedule", datetime(2026, 10, 29, tzinfo=timezone.utc))

    def test_independent_score_agreement_is_not_training_qualification(self):
        rows, report = self.run_audit()
        self.assertEqual(rows[0]["result_check_status"], "published_result_cross_checked")
        self.assertFalse(rows[0]["qualified_for_challenger_backtest"])
        self.assertEqual(report["verified_pregame_training_examples"], 0)
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_score_disagreement_is_separate_from_identity(self):
        self.g["teams"]["home"]["score"] = 6
        rows, _ = self.run_audit()
        self.assertEqual(rows[0]["result_check_status"], "secondary_score_disagreement")

    def test_ambiguous_doubleheader_fails_closed(self):
        another = dict(self.g)
        another["gamePk"] = 1000
        self.payload["dates"][0]["games"].append(another)
        rows, _ = self.run_audit()
        self.assertEqual(rows[0]["result_check_status"], "ambiguous_secondary_match")

    def test_wrong_teams_never_matched_on_scores_alone(self):
        self.g["teams"]["home"]["team"]["name"] = "New York Mets"
        rows, _ = self.run_audit()
        self.assertEqual(rows[0]["result_check_status"], "no_unambiguous_secondary_match")

    def test_reject_promoted_candidate(self):
        self.candidate["qualified_for_challenger_backtest"] = True
        with self.assertRaises(ValueError):
            self.run_audit()

    def test_reject_duplicate_espn_id(self):
        with self.assertRaises(ValueError):
            audit([self.row, self.row], [self.candidate], "mlb", self.payload,
                  "https://statsapi.mlb.com/api/v1/schedule")

    def test_nba_schedule_adapter(self):
        data = {"leagueSchedule": {"gameDates": [{"games": [{"gameStatus": 3,
            "gameId": "0022500100", "gameDateTimeUTC": "2026-02-01T22:00:00Z",
            "homeTeam": {"teamCity": "New York", "teamName": "Knicks", "score": 100},
            "awayTeam": {"teamCity": "Boston", "teamName": "Celtics", "score": 98}}]}]}}
        r = independent_games("nba", data)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["home_name"], "newyorkknicks")

    def test_mlb_request_bounded_to_game_dates(self):
        urls = []
        def fake(url):
            urls.append(url)
            return {"dates": []}
        evidence_request("mlb", [self.row], fetcher=fake)
        self.assertEqual(len(urls), 1)
        self.assertIn("sportId=1", urls[0])

    def test_archive_parser_rejects_nonfinal_and_preserves_source_distinction(self):
        payload = {"league": {"id": "nba"}, "events": [
            {"id": "nba-a", "date": "2026-02-01T22:00:00Z",
             "status": "Final", "teams": {"home": {"name": "New York Knicks"},
             "away": {"name": "Boston Celtics"}},
             "scores": {"total": {"home": 101, "away": 99}}},
            {"id": "nba-b", "date": "2026-02-02T22:00:00Z",
             "status": "Scheduled", "teams": {"home": {"name": "New York Knicks"},
             "away": {"name": "Boston Celtics"}}}
        ]}
        games = independent_games("nba", payload)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["home_score"], 101)
        nba_row = dict(self.row, league="nba", home_team="New York Knicks",
                       away_team="Boston Celtics", home_score=101, away_score=99,
                       event_start_utc="2026-02-01T22:00:00Z")
        nba_candidate = dict(self.candidate, league="nba")
        checks, report = audit([nba_row], [nba_candidate], "nba", payload,
                               "https://cache.sportsblaze.com/schedule/nba/2025")
        self.assertEqual(checks[0]["result_check_status"], "published_result_cross_checked")
        self.assertEqual(report["secondary_source_class"], "third_party_sportsblaze_published_archive")
        self.assertEqual(report["verified_pregame_training_examples"], 0)
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_nba_uses_season_archive_when_current_nba_cdn_lacks_games(self):
        nba_row = dict(self.row, league="nba", event_start_utc="2026-02-01T22:00:00Z")
        seen = []
        def fake(url):
            seen.append(url)
            if "cdn.nba.com" in url:
                return {"leagueSchedule": {"gameDates": [{"games": []}]}}
            return {"league": {"id": "nba"}, "events": [
                {"id": "archived", "date": "2026-02-01T22:00:00Z",
                 "status": "Final", "teams": {"home": {"name": "New York Yankees"},
                 "away": {"name": "Boston Red Sox"}},
                 "scores": {"total": {"home": 5, "away": 3}}}]}
        payload, source = evidence_request("nba", [nba_row], fetcher=fake)
        self.assertEqual(source, "https://cache.sportsblaze.com/schedule/nba/2025")
        self.assertEqual(len(seen), 2)
        self.assertEqual(len(independent_games("nba", payload)), 1)

    def test_nba_no_historical_source_fails_closed(self):
        nba_row = dict(self.row, league="nba", event_start_utc="2026-02-01T22:00:00Z")
        def fake(_url):
            return {"leagueSchedule": {"gameDates": [{"games": []}]}}
        with self.assertRaises(ValueError):
            evidence_request("nba", [nba_row], fetcher=fake)


if __name__ == "__main__":
    unittest.main()
