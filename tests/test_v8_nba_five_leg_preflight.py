"""NBA five-leg risk gate: no market, quote or archived line is auto-bettable."""
import unittest

from v8_nba_five_leg_preflight import audit_five_leg_preflight


def game(eid="401"):
    return {"espn_event_id": eid,
            "nba_rest_back_to_back_last5_last10": {
                "home": {"rest_days": 1}, "away": {"rest_days": 0}}}


def slate():
    return {
        "champion_001_modified": False,
        "independently_certified_positive_ev_bets": 0,
        "date_et": "2026-11-13",
        "games": [game()],
        "all_paired_archived_markets": [],
    }


def calibration():
    return {"persisted_nba_original_forward_calibration_status":
            "HOLD_WAITING_FOR_100_FORWARD_GRADED_AND_WELL_POPULATED_BINS",
            "nba_original_graded_outcomes": 14}


def pair(market="moneyline"):
    return {
        "espn_event_id_research_match": "401",
        "market": market,
        "source_quote_not_executable": True,
        "certified_sharp_edge_pp": None,
        "certified_expected_roi_percent": None,
        "independently_calibrated_model_probability_percent": None,
        "player_team_assignment_verified": False if market.startswith("player_") else None,
    }


class FiveLegEvidenceTests(unittest.TestCase):
    def test_no_data_never_creates_five_leg_or_false_clv(self):
        report = audit_five_leg_preflight(slate(), calibration())
        self.assertEqual(report["requested_legs"], 5)
        self.assertEqual(report["certified_positive_ev_legs"], [])
        self.assertIsNone(report["approved_five_leg_parlay"])
        self.assertIsNone(report["five_leg_joint_win_probability"])
        self.assertIsNone(report["realized_clv_percent"])
        self.assertEqual(report["graded_forward_home_win_research_outcomes"], 14)
        self.assertEqual(report["rest_and_last5_last10_features_present_in_research"], 1)
        self.assertEqual(report["wagers_placed"], 0)

    def test_archived_game_prices_and_player_props_stay_quarantined(self):
        x = slate()
        x["all_paired_archived_markets"] = [pair(), pair("player_points")]
        r = audit_five_leg_preflight(x, calibration())
        self.assertEqual(r["archived_reference_market_categories"],
                         {"moneyline": 1, "player_prop": 1})
        self.assertEqual(r["unverified_prop_market_pairs_quarantined"], 1)
        self.assertEqual(r["bookmaker_checkout_quote_receipts_verified"], 0)
        self.assertEqual(r["certified_positive_ev_legs"], [])
        self.assertEqual(r["decision"], "HOLD_ZERO_QUALIFIED_LEGS_NOT_A_BET")

    def test_illegally_promoted_source_data_fail_closed(self):
        for edit, expected in [
            ({"source_quote_not_executable": False}, "archived_market_illegally"),
            ({"certified_sharp_edge_pp": 7}, "archived_market_illegally"),
            ({"certified_expected_roi_percent": 10}, "archived_market_illegally"),
            ({"independently_calibrated_model_probability_percent": 80}, "archived_market_illegally"),
        ]:
            x = slate()
            x["all_paired_archived_markets"] = [{**pair("player_points"), **edit}]
            with self.assertRaisesRegex(ValueError, expected):
                audit_five_leg_preflight(x, calibration())

    def test_untrusted_identity_and_duplicate_games_block(self):
        x = slate()
        x["all_paired_archived_markets"] = [{**pair("player_assists"),
                                            "player_team_assignment_verified": True}]
        with self.assertRaisesRegex(ValueError, "unverified_NBA_prop_roster"):
            audit_five_leg_preflight(x, calibration())
        x = slate()
        x["games"] = [game(), game()]
        with self.assertRaisesRegex(ValueError, "duplicate_NBA_event"):
            audit_five_leg_preflight(x, calibration())
        x = slate()
        x["champion_001_modified"] = True
        with self.assertRaisesRegex(ValueError, "unsafe_NBA_bet_promotion"):
            audit_five_leg_preflight(x, calibration())


if __name__ == "__main__":
    unittest.main()
