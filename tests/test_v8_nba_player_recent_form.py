"""Player last-5/10 pregame features never contain unobserved or fresh finals."""
import unittest
from datetime import datetime, timedelta, timezone

from v8_nba_player_recent_form import build_player_form, SOURCE_PREFIX

ASOF = datetime(2026, 11, 13, 21, tzinfo=timezone.utc)
TIP = ASOF + timedelta(hours=3)


def row(day, *, value=20, dnp=False):
    start = datetime(2026, 11, day, 19, tzinfo=timezone.utc)
    return {
        "sport": "nba", "event_id": str(5000 + day), "player_id": "101",
        "team_id": "20", "source_url": SOURCE_PREFIX + str(5000 + day),
        "event_start_utc": start.isoformat(),
        "fetched_at_utc": (ASOF - timedelta(minutes=1)).isoformat(),
        "independently_verified_player_stats": False,
        "historical_prop_settlement_verified": False,
        "qualified_for_player_prop_training": False, "champion_001_modified": False,
        "did_not_play": dnp, "minutes": None if dnp else 30.0,
        "points": None if dnp else value, "rebounds": None if dnp else 8,
        "assists": None if dnp else 5, "threes_made": None if dnp else 2,
        "steals": None if dnp else 1, "blocks": None if dnp else 0,
    }


def target():
    return {"player_id": "101", "espn_event_id": "9000",
            "start_utc": TIP.isoformat()}


class NBAPlayerFeatureTests(unittest.TestCase):
    def test_last_five_and_ten_never_use_yesterdays_immature_result(self):
        history = [row(day, value=day) for day in range(1, 13)]
        report = build_player_form(history, [target()], ASOF.isoformat())
        p = report["players"]["9000:101"]
        self.assertEqual(report["excluded_history"]["result_not_matured_48h"], 1)
        self.assertEqual(p["player_last5"]["source_game_event_ids"],
                         [str(5000 + d) for d in range(7, 12)])
        self.assertEqual(p["player_last10"]["source_game_event_ids"],
                         [str(5000 + d) for d in range(2, 12)])
        self.assertEqual(p["player_last5"]["averages_when_every_selected_game_has_stat"]["points"], 9)
        self.assertTrue(p["player_last10"]["full_window"])
        self.assertIsNone(p["prop_probability"])
        self.assertEqual(report["certified_positive_ev_bets"], 0)
        modified = history[:-1] + [row(12, value=100)]
        other = build_player_form(modified, [target()], ASOF.isoformat())
        self.assertEqual(report["players"], other["players"])

    def test_missing_or_dnp_does_not_pad_window(self):
        report = build_player_form([row(9), row(10, dnp=True), row(11)],
                                   [target()], ASOF.isoformat())
        p = report["players"]["9000:101"]
        self.assertEqual(p["player_last5"]["matured_appearances_available"], 2)
        self.assertFalse(p["player_last5"]["full_window"])
        self.assertEqual(report["excluded_history"]["DNP_not_an_appearance"], 1)
        no_stat = row(9)
        no_stat["threes_made"] = None
        form = build_player_form([no_stat], [target()], ASOF.isoformat())
        self.assertIsNone(form["players"]["9000:101"]["player_last5"]
                          ["averages_when_every_selected_game_has_stat"]["threes_made"])

    def test_bad_receipt_and_fake_verification_rejected(self):
        future = row(9)
        future["fetched_at_utc"] = (ASOF + timedelta(minutes=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "observed_after_forecast"):
            build_player_form([future], [target()], ASOF.isoformat())
        x = row(9)
        x["qualified_for_player_prop_training"] = True
        with self.assertRaisesRegex(ValueError, "untrusted_NBA_player_box_row"):
            build_player_form([x], [target()], ASOF.isoformat())
        with self.assertRaisesRegex(ValueError, "duplicate_ESPN_player_game_box"):
            build_player_form([row(9), row(9)], [target()], ASOF.isoformat())

    def test_full_nba_slate_can_stage_more_than_100_unverified_candidates(self):
        many = [{"player_id": str(i + 1000), "espn_event_id": "9000",
                 "start_utc": TIP.isoformat()} for i in range(180)]
        x = build_player_form([], many, ASOF.isoformat())
        self.assertEqual(x["target_count"], 180)
        self.assertEqual(x["certified_positive_ev_bets"], 0)
        self.assertTrue(all(not player["player_last5"]["full_window"]
                            for player in x["players"].values()))
        over_cap = [{"player_id": str(i + 1000), "espn_event_id": "9000",
                     "start_utc": TIP.isoformat()} for i in range(401)]
        with self.assertRaisesRegex(ValueError, "input_budget_exceeded"):
            build_player_form([], over_cap, ASOF.isoformat())

    def test_missing_game_date_explicitly_excluded_and_duplicate_target_blocked(self):
        x = row(9)
        x["event_start_utc"] = None
        report = build_player_form([x], [target()], ASOF.isoformat())
        self.assertEqual(report["excluded_history"]["missing_independent_source_event_start"], 1)
        self.assertEqual(report["players"]["9000:101"]["player_last10"]["matured_appearances_available"], 0)
        with self.assertRaisesRegex(ValueError, "duplicate_NBA_target_identity"):
            build_player_form([], [target(), target()], ASOF.isoformat())


if __name__ == "__main__":
    unittest.main()
