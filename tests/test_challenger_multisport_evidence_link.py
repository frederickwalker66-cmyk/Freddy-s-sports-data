"""Multisport linkage is evidence bookkeeping, never model qualification."""
import copy
import unittest

from challenger_multisport_evidence_link import LEAGUES, assess


class AllSportReadinessTests(unittest.TestCase):
    def setUp(self):
        self.result = {
            "record_type": "historical_completed_game_research",
            "outcome_source": "espn_public_scoreboard",
            "source_url": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates=20260801",
            "retrieved_at_utc": "2026-10-29T20:00:00Z",
            "league": "mlb", "espn_event_id": "401234",
            "event_start_utc": "2026-08-01T23:00:00Z",
            "home_team": "New York Yankees", "home_team_espn_id": "10",
            "away_team": "Boston Red Sox", "away_team_espn_id": "20",
            "home_score": 5, "away_score": 3, "result": "home",
            "official_league_result_verified": False,
            "champion_001_modified": False,
        }
        self.candidate = {
            "record_type": "retrospective_challenger_candidate_not_training_ready",
            "league": "mlb", "event_id": "401234",
            "event_start_utc": "2026-08-01T23:00:00Z",
            "outcome_publication_time_verified": False,
            "pregame_feature_availability_verified": False,
            "pregame_player_availability_verified": False,
            "historical_odds_snapshot_verified": False,
            "independent_league_outcome_verified": False,
            "qualified_for_challenger_backtest": False,
            "bet_ready": False, "champion_001_modified": False,
        }
        self.check = {
            "league": "mlb", "espn_event_id": "401234",
            "result_check_status": "published_result_cross_checked",
            "secondary_source_class": "league_operated_published_feed",
            "secondary_source_url": "https://statsapi.mlb.com/api/v1/schedule",
            "historical_pregame_availability_verified": False,
            "qualified_for_challenger_backtest": False, "bet_ready": False,
        }

    def test_every_configured_league_gets_report_without_inventing_data(self):
        self.assertEqual(len(LEAGUES), 8)
        for league in LEAGUES:
            with self.subTest(league=league):
                linked, report = assess(league, [], [], coverage=None)
                self.assertEqual(linked, [])
                self.assertEqual(report["research_candidates"], 0)
                self.assertEqual(report["qualified_training_examples"], 0)
                self.assertEqual(report["bet_ready_selections"], 0)
                self.assertFalse(report["champion_001_modified"])
        self.assertFalse(assess("mls", [], [])[1]["binary_moneyline_backtest_supported"])
        self.assertFalse(assess("uefa_champions_league", [], [])[1]["binary_moneyline_backtest_supported"])

    def test_independent_score_link_is_not_training_approval(self):
        linked, report = assess("mlb", [self.result], [self.candidate], [self.check],
                                {"league": "mlb", "coverage_complete": True,
                                 "scoreboard_days_failed": 0})
        self.assertEqual(report["primary_rows_with_secondary_published_score_agreement"], 1)
        self.assertEqual(report["scoreboard_coverage_complete"], True)
        self.assertEqual(linked[0]["secondary_score_status"], "published_result_cross_checked")
        self.assertNotIn("independent_score_corroboration", linked[0]["missing_training_evidence"])
        self.assertIn("point_in_time_pregame_features", report["missing_evidence_categories"])
        self.assertEqual(report["qualified_training_examples"], 0)
        self.assertFalse(linked[0]["qualified_for_challenger_backtest"])

    def test_unmatched_check_is_explicit_and_not_promoted(self):
        self.check["result_check_status"] = "ambiguous_secondary_match"
        linked, report = assess("mlb", [self.result], [self.candidate], [self.check])
        self.assertIn("independent_score_corroboration", linked[0]["missing_training_evidence"])
        self.assertEqual(report["qualified_training_examples"], 0)

    def test_missing_check_is_explicit(self):
        linked, report = assess("mlb", [self.result], [self.candidate], [])
        self.assertEqual(linked[0]["secondary_score_status"], "no_independent_check_archive")
        self.assertEqual(report["independent_checks_received"], 0)

    def test_blocks_candidate_provenance_upgrade(self):
        self.candidate["pregame_feature_availability_verified"] = True
        with self.assertRaises(ValueError):
            assess("mlb", [self.result], [self.candidate], [self.check])

    def test_rejects_secondary_unknown_and_duplicate_event(self):
        self.check["espn_event_id"] = "not-a-primary"
        with self.assertRaises(ValueError):
            assess("mlb", [self.result], [self.candidate], [self.check])
        with self.assertRaises(ValueError):
            assess("mlb", [self.result, copy.deepcopy(self.result)], [self.candidate])

    def test_shared_archive_filters_other_leagues(self):
        other = dict(self.result, league="nba", espn_event_id="888")
        linked, report = assess("mlb", [self.result, other], [self.candidate])
        self.assertEqual(len(linked), 1)
        self.assertEqual(report["source_outcome_rows"], 1)

    def test_coverage_requires_correct_league(self):
        with self.assertRaises(ValueError):
            assess("mlb", [self.result], [self.candidate], coverage={
                "league": "nba", "coverage_complete": True})


if __name__ == "__main__":
    unittest.main()
