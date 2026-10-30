"""Offline, deterministic prospective pregame evidence safety tests."""
import unittest
from datetime import datetime, timezone, timedelta
from challenger_prospective_pregame import (
    LEAGUES, build, team_form, validated_odds, name_key,
)

NOW = datetime(2026, 10, 29, 21, 30, tzinfo=timezone.utc)
START = "2026-10-30T00:00:00Z"


def schedule():
    return {
        "collected_at_utc": "2026-10-29T21:29:00Z",
        "events": [{"league": "nba", "home_team": "Atlanta Hawks",
                    "away_team": "Cleveland Cavaliers",
                    "start_utc": START, "status": "scheduled",
                    "provider_game_id": "401001",
                    "source_url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261029",
                    "observed_at_utc": "2026-10-29T21:29:00Z"}],
        "sources": {"nba": {"status": "retrieved"}},
    }


def odds():
    return {"source": "sportsgameodds_v2", "sportsbook": "draftkings",
            "certified_prediction": False, "model_probability": None,
            "league": "nba", "home_team": "Atlanta Hawks",
            "away_team": "Cleveland Cavaliers", "event_id": "sgo:88",
            "market_type": "moneyline", "selection_type": "home",
            "selection": "Atlanta Hawks", "odds_american": -130, "line": None,
            "timestamp": "2026-10-29T21:25:00Z",
            "recorded_at": "2026-10-29T21:26:00Z",
            "event_start_time": START}


def history():
    rows = []
    for team, opponent, home in (("Atlanta Hawks", "Orlando Magic", True),
                                  ("Atlanta Hawks", "Chicago Bulls", False),
                                  ("Atlanta Hawks", "Toronto Raptors", True),
                                  ("Cleveland Cavaliers", "Miami Heat", True),
                                  ("Cleveland Cavaliers", "Boston Celtics", False),
                                  ("Cleveland Cavaliers", "Brooklyn Nets", True)):
        n = len(rows)
        day = datetime(2026, 10, 15, tzinfo=timezone.utc) + timedelta(days=n)
        rows.append({
            "league": "nba", "season_type": 2, "record_type": "historical_completed_game_research",
            "home_team": team if home else opponent,
            "away_team": opponent if home else team,
            "home_score": 105 if home else 94, "away_score": 98 if home else 110,
            "event_start_utc": day.isoformat(),
            "retrieved_at_utc": "2026-10-29T21:29:40Z",
            "espn_event_id": str(n + 100),
            "source_url": "https://site.api.espn.com/record" + str(n),
        })
    return rows


class ProspectiveTests(unittest.TestCase):
    def test_all_eight_leagues_present_in_report_no_phantom_games(self):
        records, report = build({"collected_at_utc": "2026-10-29T21:00:00Z",
                                 "events": []}, [], [], None, NOW)
        self.assertEqual(records, [])
        self.assertEqual(set(report["by_league"]), set(LEAGUES))
        self.assertEqual(report["verified_historical_training_examples"], 0)
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_links_current_odds_but_never_certifies(self):
        item, report = build(schedule(), history(), [odds()], {
            "retrieved_at_utc": "2026-10-29T20:00:00Z",
            "sources": {"nba": {"status": "evidence_downloaded"}},
            "champion_001_modified": False, "model_probabilities_generated": 0,
            "player_props_cleared": 0,
        }, NOW)
        self.assertEqual(len(item), 1)
        row = item[0]
        self.assertTrue(row["team_form_available_for_both_teams"])
        self.assertEqual(len(row["odds_observations"]), 1)
        self.assertTrue(row["league_source_scan_before_event"])
        self.assertFalse(row["player_level_status_parsed_and_verified"])
        self.assertFalse(row["draftkings_direct_checkout_verified"])
        self.assertIsNone(row["model_probability"])
        self.assertFalse(row["qualified_for_challenger_backtest"])
        self.assertEqual(report["verified_historical_training_examples"], 0)
        self.assertEqual(report["certified_champion_001_predictions"], 0)

    def test_post_start_quotes_and_pregame_snapshot_rejected(self):
        a = odds()
        a["recorded_at"] = "2026-10-30T00:00:01Z"
        self.assertIsNotNone(validated_odds(a, NOW)[1])
        records, report = build(schedule(), [], [a], None, NOW)
        self.assertEqual(len(records[0]["odds_observations"]), 0)
        self.assertNotEqual(report["quotes_rejected_or_unlinked"], {})
        s = schedule()
        s["events"][0]["start_utc"] = "2026-10-29T21:00:00Z"
        records, _ = build(s, [], [], None, NOW)
        self.assertEqual(records, [])

    def test_missing_player_evidence_never_clears_props(self):
        a = odds()
        a["market_type"] = "player_points"
        a["selection"] = "Example Player Over"
        a["player_id"] = "987"
        rows, report = build(schedule(), [], [a], None, NOW)
        self.assertEqual(rows[0]["odds_observations"][0]["player_available_verified"], False)
        self.assertEqual(report["verified_player_availability_entries"], 0)

    def test_ambiguous_duplicate_schedule_is_rejected(self):
        s = schedule()
        s["events"].append(dict(s["events"][0]))
        with self.assertRaises(ValueError):
            build(s, [], [], None, NOW)

    def test_preseason_and_untyped_results_cannot_influence_nba_team_form(self):
        sample=history()
        for g in sample:
            g["season_type"]=1
        self.assertIsNone(team_form(sample,"atlanta hawks",
                                   datetime.fromisoformat(START.replace("Z","+00:00")),NOW))
        for g in sample:
            del g["season_type"]
        self.assertIsNone(team_form(sample,"atlanta hawks",
                                   datetime.fromisoformat(START.replace("Z","+00:00")),NOW))

    def test_partial_team_history_is_unknown_not_zero(self):
        self.assertIsNone(team_form([], "atlanta hawks", datetime.fromisoformat(START.replace("Z","+00:00")), NOW))
        rows, _ = build(schedule(), history()[:4], [], None, NOW)
        self.assertFalse(rows[0]["team_form_available_for_both_teams"])

    def test_rejects_bad_source_and_future_quote(self):
        a = odds()
        a["source"] = "fake_source"
        self.assertEqual(validated_odds(a, NOW)[1], "not_quarantined_draftkings_research")
        a = odds()
        a["timestamp"] = "2026-10-29T21:29:00Z"
        self.assertIsNotNone(validated_odds(a, NOW)[1])

    def test_no_future_completed_scores_or_post_start_retrieval(self):
        a = history()
        a[0]["retrieved_at_utc"] = "2026-10-30T01:00:00Z"
        self.assertIsNone(team_form(a[:3], "atlanta hawks", datetime.fromisoformat(START.replace("Z","+00:00")), NOW))

    def test_bad_official_evidence_fails_closed(self):
        with self.assertRaises(ValueError):
            build(schedule(), [], [], {
                "retrieved_at_utc": "2026-10-29T20:00:00Z",
                "champion_001_modified": True,
                "model_probabilities_generated": 0, "player_props_cleared": 0
            }, NOW)

    def test_team_name_normalization_is_not_nickname_guessing(self):
        self.assertEqual(name_key("  Atlanta--Hawks"), "atlanta hawks")
        self.assertNotEqual(name_key("Atlanta Hawks"), name_key("Hawks"))


if __name__ == "__main__":
    unittest.main()
