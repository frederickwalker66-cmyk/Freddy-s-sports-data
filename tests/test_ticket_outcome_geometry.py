"""Synthetic regressions for same-event joint-win and NFL prop evidence gates."""
import unittest

from ticket_outcome_geometry import analyze_margin_overlap
from v8_parlay_risk_audit import audit_ticket
from challenger_ticket_preflight import audit_slip


def ml(side="home", event="example"):
    return {"league": "nba", "event_id": event, "market": "moneyline",
            "team_side": side, "selection": "synthetic", "line": None}


def spread(side="away", handicap=6.5, event="example"):
    return {"league": "nba", "event_id": event, "market": "point_spread",
            "team_side": side, "selection": "synthetic",
            "line": handicap}


class TicketOutcomeGeometryTests(unittest.TestCase):
    def test_moneyline_opposite_spread_narrow_overlap(self):
        report = analyze_margin_overlap([ml("home"), spread("away", 6.5)])
        row = report["margin_overlap_groups"][0]
        self.assertEqual((row["home_margin_min"], row["home_margin_max"]), (1, 6))
        self.assertEqual(row["number_of_integer_winning_margins"], 6)
        self.assertIn("moneyline_spread_only_seven_or_fewer_winning_margins",
                      report["margin_overlap_warning_codes"])
        self.assertFalse(report["probability_estimated"])

    def test_impossible_same_game_ticket_flagged(self):
        report = analyze_margin_overlap([ml("home"), spread("away", 0.5)])
        self.assertEqual(report["margin_overlap_groups"][0]["status"],
                         "NO_JOINT_WINNING_MARGIN")
        self.assertIn("moneyline_spread_joint_win_mathematically_impossible",
                      report["margin_overlap_warning_codes"])

    def test_unknown_home_away_identity_fail_closed(self):
        bad = ml()
        bad.pop("team_side")
        report = analyze_margin_overlap([bad, spread("away", 6.5)])
        self.assertEqual(report["margin_overlap_groups"][0]["status"],
                         "UNRESOLVED_TEAM_SIDE")
        self.assertIsNone(report["margin_overlap_groups"][0]["home_margin_min"])
        self.assertIn("moneyline_spread_team_side_unverified_block_joint_assessment",
                      report["margin_overlap_warning_codes"])

    def test_same_side_spread_requires_larger_margin(self):
        report = analyze_margin_overlap([ml("home"), spread("home", -6.5)])
        row = report["margin_overlap_groups"][0]
        self.assertEqual(row["home_margin_min"], 7)
        self.assertIsNone(row["home_margin_max"])

    def test_away_team_moneyline_and_home_team_spread(self):
        report = analyze_margin_overlap([ml("away"), spread("home", 6.5)])
        row = report["margin_overlap_groups"][0]
        self.assertEqual(row["home_margin_min"], -6)
        self.assertEqual(row["home_margin_max"], -1)

    def test_point_spread_push_not_in_winning_range(self):
        report = analyze_margin_overlap([ml("home"), spread("away", 3.0)])
        self.assertEqual(report["margin_overlap_groups"][0]["home_margin_max"], 2)

    def test_illegal_side_and_line_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_team_side"):
            analyze_margin_overlap([ml("neutral"), spread()])
        with self.assertRaisesRegex(ValueError, "signed_spread_line_required"):
            analyze_margin_overlap([ml(), spread(handicap=None)])

    def test_cross_game_and_unrelated_props_do_not_create_fake_overlap(self):
        report = analyze_margin_overlap([ml("home", "a"), spread("away", 6.5, "b"),
                                         {"market": "player_prop", "event_id": "a"}])
        self.assertEqual(report["margin_overlap_groups"], [])

    def test_private_ticket_auditor_reports_margin_condition(self):
        start = "2026-11-20T20:00:00-05:00"
        rows = [
            dict(ml("home"), event_start=start),
            dict(spread("away", 6.5), event_start=start),
        ]
        report = audit_ticket({
            "schema_version": 1, "ticket_kind": "placed", "bookmaker": "example",
            "accepted_at": "2026-11-20T18:00:00-05:00",
            "stake_usd": "5.00", "accepted_american_odds": 600,
            "displayed_total_payout_usd": "35.00", "legs": rows,
        })
        self.assertEqual(report["same_game_margin_overlap"][0]["home_margin_max"], 6)
        self.assertIn("moneyline_spread_only_seven_or_fewer_winning_margins",
                      report["warning_codes"])
        self.assertEqual(report["certified_positive_ev_bets"], 0)
        self.assertFalse(report["champion_001_modified"])

    def test_challenger_prop_requires_actual_workload_and_game_script_evidence(self):
        row = {"event_id": "game", "market_type": "player_receiving_yards",
               "selection": "Example OVER 39.5", "odds_american": -110,
               "is_player_prop": True, "player_name": "Example Player",
               "availability_verified": True, "dk_quote_verified": True,
               "model_probability": None, "model_probability_verified": False}
        report = audit_slip([row])
        self.assertIn("prop_minutes_snaps_or_expected_workload_unverified",
                      report["blockers"])
        self.assertIn("prop_game_script_sensitivity_not_reviewed",
                      report["blockers"])
        self.assertIn("exact_prop_market_forward_calibration_unverified",
                      report["blockers"])
        self.assertFalse(report["bet_ready"])

    def test_challenger_parlay_margin_constraint_integration(self):
        rows = [
            {"event_id": "g1", "league": "nba", "market_type": "moneyline",
             "selection": "Home", "team_side": "home",
             "odds_american": -110, "dk_quote_verified": False,
             "is_player_prop": False},
            {"event_id": "g1", "league": "nba", "market_type": "point_spread",
             "selection": "Away +6.5", "line": 6.5, "team_side": "away",
             "odds_american": -110, "dk_quote_verified": False,
             "is_player_prop": False},
        ]
        report = audit_slip(rows)
        self.assertEqual(report["same_event_moneyline_spread_margin_review"][0]
                         ["number_of_integer_winning_margins"], 6)
        self.assertEqual(report["decision"], "PASS")
        self.assertEqual(report["certified_champion_001_predictions"], 0)


if __name__ == "__main__":
    unittest.main()
