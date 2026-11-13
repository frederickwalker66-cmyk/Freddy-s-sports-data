"""Leakage and cutoff tests for NBA last-five, last-ten and back-to-back inputs."""
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from historical_outcomes import normalize_game, scoreboard_url
from v8_nba_rest_form_features import build_features, FEATURE_VERSION

NY = ZoneInfo("America/New_York")
ASOF = datetime(2026, 11, 13, 16, 0, tzinfo=NY).astimezone(timezone.utc)
TIP = datetime(2026, 11, 13, 20, 0, tzinfo=NY).astimezone(timezone.utc)


def result(day, home_score=110, away_score=100):
    start = datetime(2026, 11, day, 19, 0, tzinfo=NY).astimezone(timezone.utc)
    observed = ASOF - timedelta(minutes=20)
    event = {
        "id": str(20000 + day), "date": start.isoformat(),
        "season": {"type": 2},
        "status": {"type": {"state": "post", "completed": True}},
        "competitions": [{"competitors": [
            {"homeAway": "home", "team": {"id": "101", "displayName": "Home"},
             "score": home_score},
            {"homeAway": "away", "team": {"id": "102", "displayName": "Away"},
             "score": away_score},
        ]}],
    }
    return normalize_game(event, "nba", scoreboard_url("nba", start.astimezone(NY).date()), observed)


def matchup(start=TIP):
    return {"league": "nba", "espn_event_id": "40000",
            "start_utc": start.isoformat(), "home_team_espn_id": "101",
            "away_team_espn_id": "102"}


class NBARecentFormTests(unittest.TestCase):
    def test_back_to_back_and_last5_last10_safely_separated(self):
        records = [result(day, 110 if day % 2 == 0 else 90, 100)
                   for day in range(1, 13)]
        context = build_features(records, [matchup()], ASOF)["40000"]
        home, away = context["home"], context["away"]
        self.assertEqual(context["feature_version"], FEATURE_VERSION)
        self.assertEqual(home["previous_game_date_et"], "2026-11-12")
        self.assertIs(home["back_to_back_second_night"], True)
        self.assertEqual(home["rest_days"], 0)
        self.assertEqual(home["days_between_game_dates"], 1)
        self.assertIs(away["back_to_back_second_night"], True)
        self.assertEqual(home["last5"]["available_matured_games"], 5)
        self.assertEqual(home["last10"]["available_matured_games"], 10)
        self.assertTrue(home["last5"]["complete_window"])
        self.assertEqual(home["last10"]["source_espn_event_ids"][-1], str(20000 + 10))
        self.assertNotIn(str(20000 + 12), home["last5"]["source_espn_event_ids"])
        self.assertNotIn(str(20000 + 11), home["last10"]["source_espn_event_ids"])
        self.assertFalse(context["applied_as_probability_weight"])
        # Yesterday's published score is known but embargoed; changing its
        # value must not change rolling-form features for this forecast.
        altered = records[:-1] + [result(12, 5, 250)]
        other = build_features(altered, [matchup()], ASOF)["40000"]
        self.assertEqual(other["home"]["last5"], home["last5"])
        self.assertEqual(other["home"]["last10"], home["last10"])
        self.assertEqual(other["home"]["rest_days"], home["rest_days"])

    def test_rest_two_or_more_days_not_back_to_back(self):
        context = build_features([result(10)], [matchup()], ASOF)["40000"]
        self.assertIs(context["home"]["back_to_back_second_night"], False)
        self.assertEqual(context["home"]["rest_days"], 2)
        self.assertEqual(context["home"]["last10"]["available_matured_games"], 1)
        self.assertFalse(context["home"]["last10"]["complete_window"])

    def test_unknown_previous_game_never_fabricates_zero_rest_or_form(self):
        context = build_features([], [matchup()], ASOF)["40000"]
        home = context["home"]
        self.assertIsNone(home["back_to_back_second_night"])
        self.assertIsNone(home["rest_days"])
        self.assertIsNone(home["last5"]["win_rate"])
        self.assertEqual(home["last10"]["available_matured_games"], 0)

    def test_postforecast_capture_and_duplicate_event_rejected(self):
        bad = result(10)
        bad["retrieved_at_utc"] = (ASOF + timedelta(seconds=1)).isoformat()
        with self.assertRaises(ValueError):
            build_features([bad], [matchup()], ASOF)
        with self.assertRaisesRegex(ValueError, "duplicate_NBA_history_event"):
            build_features([result(10), result(10)], [matchup()], ASOF)
        self.assertEqual(build_features([result(10)], [
            matchup(start=ASOF - timedelta(minutes=1))], ASOF), {})


if __name__ == "__main__":
    unittest.main()
