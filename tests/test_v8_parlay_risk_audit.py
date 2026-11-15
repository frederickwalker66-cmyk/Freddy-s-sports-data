"""Placed parlays must never be confused with calibrated research or CLV."""
import json
import tempfile
import unittest
from pathlib import Path

from v8_parlay_risk_audit import audit_ticket, main


START = "2026-11-12T19:00:00-05:00"
ENTRY = "2026-11-12T17:25:00-05:00"


def leg(event, market="moneyline", selection="home", line=None,
        player_name=None, prop_stat=None, league="nba", **extra):
    result = {"event_id": event, "event_start": START, "league": league,
              "market": market, "selection": selection, "line": line}
    if player_name is not None:
        result["player_name"] = player_name
        result["prop_stat"] = prop_stat
    result.update(extra)
    return result


def placed(legs):
    return {
        "schema_version": 1, "ticket_kind": "placed",
        "bookmaker": "example-book", "accepted_at": ENTRY,
        "stake_usd": "5.00", "accepted_american_odds": 8104,
        "displayed_total_payout_usd": "410.20", "legs": legs,
    }


class ParlayRiskAuditTests(unittest.TestCase):
    def test_nine_leg_placed_receipt_price_math_and_correlations(self):
        tor = "nba:TOR-PHI:2026-11-12"
        nfl = "nfl:WAS-NYG:2026-11-12"
        legs = [
            leg("nba:DAL-MIN"), leg("nba:DET-WAS", "point_spread", "detroit", -8.5),
            leg(tor, "player_prop", "over", 1.5, "Player One", "assists"),
            leg(tor, "player_prop", "under", 1.5, "Player Two", "assists"),
            leg(tor, "moneyline", "philadelphia"),
            leg(tor, "player_prop", "under", 5.5, "Player Three", "assists"),
            leg(nfl, "point_spread", "washington", 3.5, league="nfl"),
            leg(nfl, "player_prop", "over", 39.5, "Player Four", "receiving_yards", league="nfl"),
            leg(nfl, "player_prop", "over", 4.5, "Player Four", "receptions", league="nfl"),
        ]
        report = audit_ticket(placed(legs))
        self.assertEqual(report["leg_count"], 9)
        self.assertEqual(report["reported_placed_bets"], 1)
        self.assertEqual(report["research_ticket_count"], 0)
        self.assertEqual(report["payout_price_math"]["calculated_payout_usd"], "410.20")
        self.assertTrue(report["payout_price_math"]["reported_payout_math_matches"])
        self.assertAlmostEqual(report["payout_price_math"]["break_even_price_percent"], 100/82.04, places=3)
        self.assertEqual(len(report["same_event_groups"]), 2)
        self.assertEqual(report["same_event_groups"][0]["leg_numbers"], [3, 4, 5, 6])
        self.assertEqual(report["same_player_groups"][0]["leg_numbers"], [8, 9])
        self.assertTrue(report["correlation_risk_flagged"])
        self.assertIsNone(report["joint_model_win_probability_percent"])
        self.assertIsNone(report["certified_parlay_expected_value_percent"])
        self.assertIsNone(report["verified_realized_clv_percent"])
        self.assertIsNone(report["parlay_settlement"])
        self.assertEqual(report["certified_positive_ev_bets"], 0)
        self.assertFalse(report["champion_001_modified"])
        self.assertEqual(report["automated_wagers"], 0)

    def test_claimed_results_model_probability_and_close_never_upgrade(self):
        sample = placed([leg("nba:TOR-PHI", "player_prop", "under", 5.5,
                             "Example Athlete", "assists",
                             reported_outcome="win",
                             model_probability=0.91,
                             closing_quote={"american_odds": -500,
                                            "claimed_source": "draftkings"})])
        result = audit_ticket(sample)
        self.assertEqual(result["reported_outcome_claim_count_not_graded"], 1)
        self.assertEqual(result["reported_model_probability_claim_count_not_certified"], 1)
        self.assertEqual(result["reported_closing_quote_claim_count_not_verified"], 1)
        self.assertEqual(result["independently_verified_outcomes"], 0)
        self.assertIsNone(result["actual_winnings_usd"])
        self.assertIsNone(result["verified_realized_clv_percent"])
        self.assertFalse(result["independently_certified_calibration"])
        self.assertIn("user_reported_outcomes_unverified_no_settlement_grading",
                      result["warning_codes"])

    def test_research_does_not_count_as_placed_wager(self):
        research = {"schema_version": 1, "ticket_kind": "research",
                    "bookmaker": "example-book", "legs": [leg("nba:TOR-PHI")]}
        result = audit_ticket(research)
        self.assertEqual(result["research_ticket_count"], 1)
        self.assertEqual(result["reported_placed_bets"], 0)
        self.assertIsNone(result["payout_price_math"]["calculated_payout_usd"])
        research["stake_usd"] = "1.00"
        with self.assertRaisesRegex(ValueError, "research_ticket_cannot_have_accepted_wager"):
            audit_ticket(research)

    def test_missing_or_invalid_source_fields_fail_closed(self):
        sample = placed([leg("nba:TOR-PHI")])
        bads = [
            ("accepted_american_odds", 0),
            ("stake_usd", -1),
            ("stake_usd", "1.001"),
            ("accepted_at", "2026-11-12T17:25:00"),
        ]
        for field, value in bads:
            bad = dict(sample)
            bad[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                audit_ticket(bad)
        sample["accepted_at"] = "2026-11-12T19:00:01-05:00"
        with self.assertRaisesRegex(ValueError, "accepted_after_event_start"):
            audit_ticket(sample)

    def test_exact_line_identity_and_duplicates_are_required(self):
        with self.assertRaisesRegex(ValueError, "exact_market_line_required"):
            audit_ticket(placed([leg("nba:TOR-PHI", "player_prop", "over",
                                     None, "Example Athlete", "assists")]))
        with self.assertRaisesRegex(ValueError, "player_name_required"):
            audit_ticket(placed([leg("nba:TOR-PHI", "player_prop", "over", 5.5)]))
        with self.assertRaisesRegex(ValueError, "duplicate_exact_leg"):
            audit_ticket(placed([leg("nba:TOR-PHI"), leg("nba:TOR-PHI")]))
        with self.assertRaisesRegex(ValueError, "moneyline_must_not_have_handicap_line"):
            audit_ticket(placed([leg("nba:TOR-PHI", "moneyline", "home", 1.5)]))

    def test_mismatched_display_is_only_a_warning_not_a_fake_price(self):
        ticket = placed([leg("nba:TOR-PHI")])
        ticket["displayed_total_payout_usd"] = "400.00"
        result = audit_ticket(ticket)
        self.assertFalse(result["payout_price_math"]["reported_payout_math_matches"])
        self.assertIn("displayed_payout_disagrees_with_american_odds_check_boost_and_receipt",
                      result["warning_codes"])

    def test_loss_audit_is_descriptive_and_flags_structural_risk(self):
        # Fictional four-leg receipt: no user ticket or private identifier in Git.
        receipt = placed([
            leg("nfl:AAA-BBB", "player_prop", "over", 6.5,
                "Sample Athlete", "receptions", league="nfl",
                direction="over", reported_outcome="loss"),
            leg("nfl:AAA-BBB", "player_prop", "over", 270.5,
                "Sample Athlete", "passing_yards", league="nfl",
                direction="over", reported_outcome="loss"),
            leg("nfl:CCC-DDD", "player_prop", "over", 2.5,
                "Sample Player", "receptions", league="nfl",
                direction="over", prior_disposition="PASS",
                reported_outcome="win"),
            leg("nfl:EEE-FFF", "total_points", "over", 42.5,
                league="nfl", direction="over", reported_outcome="pending"),
        ])
        report = audit_ticket(receipt)
        self.assertEqual(report["reported_outcomes_as_supplied_not_verified"]["loss"], 2)
        self.assertEqual(report["reported_outcomes_as_supplied_not_verified"]["win"], 1)
        self.assertEqual(report["reported_outcomes_as_supplied_not_verified"]["pending"], 1)
        self.assertAlmostEqual(
            report["reported_settled_hit_rate_descriptive_not_model_accuracy"], 1/3,
            places=6)
        self.assertEqual(report["prior_pass_hold_reject_leg_numbers"], [3])
        self.assertIn("four_or_more_legs_high_variance_not_a_certified_edge",
                      report["structural_risk_flags"])
        self.assertIn("all_overs_directional_concentration",
                      report["structural_risk_flags"])
        self.assertIn("same_player_multiple_props_require_joint_distribution",
                      report["structural_risk_flags"])
        self.assertIn("previously_PASS_HOLD_REJECT_legs_included",
                      report["structural_risk_flags"])
        self.assertTrue(report["reported_ticket_has_a_losing_leg"])
        self.assertTrue(report["all_legs_have_reported_outcomes"])
        self.assertIsNone(report["parlay_settlement"])
        self.assertEqual(report["certified_positive_ev_bets"], 0)
        self.assertFalse(report["champion_001_modified"])

    def test_reported_outcome_and_direction_must_be_explicit_and_valid(self):
        with self.assertRaisesRegex(ValueError, "invalid_reported_outcome"):
            audit_ticket(placed([leg("nba:aaa", reported_outcome="guessed_win")]))
        with self.assertRaisesRegex(ValueError, "direction_must_be"):
            audit_ticket(placed([leg("nba:aaa", direction="maybe")]))
        missing = audit_ticket(placed([leg("nba:aaa", selection="Over 5+")]))
        self.assertIsNone(missing["reported_settled_hit_rate_descriptive_not_model_accuracy"])
        self.assertNotIn("all_overs_directional_concentration",
                         missing["structural_risk_flags"])
        self.assertIsNone(missing["parlay_settlement"])

    def test_private_cli_creates_only_local_readonly_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src = root / "private_ticket.json"
            out = root / "audit.json"
            src.write_text(json.dumps(placed([leg("nba:TOR-PHI")])) + "\n",
                           encoding="utf-8")
            main(["--ticket-file", str(src), "--output", str(out)])
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["decision"],
                             "HOLD_NO_INDEPENDENTLY_CERTIFIED_PROBABILITY_PRICE_AND_SETTLEMENT")
            self.assertNotIn("ticket_reference", result)
            with self.assertRaisesRegex(ValueError, "must_not_overwrite"):
                main(["--ticket-file", str(src), "--output", str(src)])


if __name__ == "__main__":
    unittest.main()
