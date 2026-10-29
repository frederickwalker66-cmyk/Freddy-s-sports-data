"""Only synthetic fixtures; passing tests never demonstrates betting accuracy."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from challenger_feature_candidates import build_candidates


def historical(eid, hours, home_score=100, away_score=90,
               league="nba", home="1", away="2"):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=hours)
    return {
        "record_type": "historical_completed_game_research",
        "outcome_source": "espn_public_scoreboard",
        "official_league_result_verified": False,
        "provider_event_id_crosswalk_verified": False,
        "champion_001_modified": False,
        "league": league, "espn_event_id": str(eid),
        "event_start_utc": start.isoformat(),
        "home_team_espn_id": home, "away_team_espn_id": away,
        "home_score": home_score, "away_score": away_score,
        "result": "home" if home_score > away_score
                  else "away" if home_score < away_score else "draw",
        "source_url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20260101",
        "retrieved_at_utc": "2026-10-29T18:00:00+00:00",
    }


class HistoricalFeatureCandidateTests(unittest.TestCase):
    def test_future_result_leakage_blocked(self):
        first = historical(1, 0)
        first_reversed = historical(1, 0, home_score=90, away_score=100)
        second = historical(2, 1, home="1", away="3")
        later = historical(3, 49, home="1", away="4")
        rows_a, _ = build_candidates([first, second, later])
        rows_b, _ = build_candidates([first_reversed, second, later])
        self.assertEqual(rows_a[1]["features"], rows_b[1]["features"])
        self.assertNotEqual(rows_a[2]["features"], rows_b[2]["features"])
        self.assertEqual(rows_a[1]["features"]["pregame_home_prior_games"], 0)
        self.assertEqual(rows_a[2]["features"]["pregame_home_prior_games"], 1)

    def test_reject_conflicting_score_and_result(self):
        row = historical(1, 0)
        row["result"] = "away"
        with self.assertRaises(ValueError):
            build_candidates([row])

    def test_reject_duplicate_events(self):
        row = historical(1, 0)
        with self.assertRaises(ValueError):
            build_candidates([row, deepcopy(row)])

    def test_reject_bad_source(self):
        row = historical(1, 0)
        row["source_url"] = "http://test.example"
        with self.assertRaises(ValueError):
            build_candidates([row])

    def test_reject_backdated_retrieval(self):
        row = historical(1, 0)
        row["retrieved_at_utc"] = "2025-12-31T20:00:00+00:00"
        with self.assertRaises(ValueError):
            build_candidates([row])

    def test_ties_and_three_way_not_used(self):
        rows, rep = build_candidates([
            historical(1, 0, home_score=100, away_score=100),
            historical(2, 1, league="mls"),
        ])
        self.assertEqual(rows, [])
        self.assertEqual(rep["by_league"]["nba"]["excluded_ties"], 1)
        self.assertEqual(rep["by_league"]["mls"]["status"], "three_way_market_not_supported")

    def test_candidates_cannot_be_promoted(self):
        rows, rep = build_candidates([historical(1, 0)])
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["training_eligible"])
        self.assertFalse(rows[0]["historical_feature_availability_verified"])
        self.assertFalse(rows[0]["official_outcome_verified"])
        self.assertFalse(rows[0]["bet_ready"])
        self.assertEqual(rep["verified_training_examples"], 0)
        self.assertEqual(rep["certified_challenger_001_predictions"], 0)
        self.assertEqual(rep["certified_champion_001_predictions"], 0)
        self.assertFalse(rep["champion_001_modified"])

    def test_48h_embargo_minimum(self):
        with self.assertRaises(ValueError):
            build_candidates([], lag_hours=24)


if __name__ == "__main__":
    unittest.main()
