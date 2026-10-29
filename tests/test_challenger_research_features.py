"""Synthetic-only checks for retrospective feature availability and integrity."""
import unittest
from datetime import datetime, timedelta, timezone

from challenger_research_features import build_candidates, LAG_HOURS

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def fixture(i, day, home="A", away="B", score_home=10, score_away=5,
            league="nba", hour=12):
    start = BASE + timedelta(days=day, hours=hour)
    return {
        "record_type": "historical_completed_game_research",
        "outcome_source": "espn_public_scoreboard",
        "source_url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20260101",
        "retrieved_at_utc": "2026-10-29T20:00:00+00:00",
        "official_league_result_verified": False,
        "champion_001_modified": False,
        "league": league,
        "espn_event_id": str(i),
        "event_start_utc": start.isoformat(),
        "home_team_espn_id": home,
        "away_team_espn_id": away,
        "home_score": score_home,
        "away_score": score_away,
        "result": "home" if score_home > score_away else "away" if score_home < score_away else "draw",
    }


class ResearchFeatureTests(unittest.TestCase):
    def test_prior_form_only_and_all_candidates_quarantined(self):
        games = [fixture(i + 1, i * 3) for i in range(5)]
        candidates, report = build_candidates(games)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["features"]["pregame_home_prior_games"], 3)
        self.assertEqual(candidates[0]["features"]["pregame_away_win_rate"], 0)
        self.assertTrue(all(not x["qualified_for_challenger_backtest"] for x in candidates))
        self.assertEqual(report["qualified_training_examples"], 0)
        self.assertEqual(report["bet_ready_selections"], 0)
        self.assertFalse(report["champion_001_modified"])

    def test_48_hour_cutoff_excludes_recent_results(self):
        games = [fixture(1, 0), fixture(2, 3), fixture(3, 6),
                 fixture(4, 8), fixture(5, 9)]
        candidates, _ = build_candidates(games)
        target = next(c for c in candidates if c["event_id"] == "5")
        self.assertEqual(target["features"]["pregame_home_prior_games"], 3)
        self.assertNotIn("4", target["lagged_result_event_ids"]["home"])
        self.assertIn("1", target["lagged_result_event_ids"]["home"])
        self.assertEqual(LAG_HOURS, 48)

    def test_same_start_time_cannot_influence_other_event(self):
        previous = [fixture(i + 1, i * 3) for i in range(3)]
        a = fixture(11, 10, home="A", away="B", score_home=20, score_away=0)
        b = fixture(12, 10, home="A", away="B", score_home=0, score_away=20)
        records, _ = build_candidates(previous + [a, b])
        self.assertEqual(records[-1]["features"], records[-2]["features"])
        self.assertTrue(set(records[-1]["lagged_result_event_ids"]["home"]).isdisjoint({"11", "12"}))

    def test_sports_with_three_way_markets_never_become_binary(self):
        rows = [fixture(i + 1, i * 3, league="mls") for i in range(5)]
        candidates, report = build_candidates(rows)
        self.assertEqual(len(candidates), 0)
        self.assertEqual(report["by_league"]["mls"]["excluded_three_way_market"], 5)

    def test_duplicate_or_forged_sources_are_rejected(self):
        g = fixture(1, 0)
        with self.assertRaises(ValueError):
            build_candidates([g, g])
        forged = dict(g, source_url="https://untrusted.example/scoreboard")
        with self.assertRaises(ValueError):
            build_candidates([forged])
        claimed_official = dict(g, official_league_result_verified=True)
        with self.assertRaises(ValueError):
            build_candidates([claimed_official])

    def test_no_feature_uses_current_final_result(self):
        prev = [fixture(i + 1, i * 3) for i in range(3)]
        p = fixture(50, 10, score_home=99, score_away=0)
        q = fixture(50, 10, score_home=0, score_away=99)
        a, _ = build_candidates(prev + [p])
        b, _ = build_candidates(prev + [q])
        self.assertEqual(a[-1]["features"], b[-1]["features"])
        self.assertNotEqual(a[-1]["outcome"], b[-1]["outcome"])


if __name__ == "__main__":
    unittest.main()
