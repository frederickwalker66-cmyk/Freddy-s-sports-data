"""Fictional fixtures for the fail-closed Challenger research intake gate."""
import unittest
from challenger_audit import validate, audit, market_family, load_schedule

EVENTS = {"fixture-001": {
    "event_id": "fixture-001", "league": "nba", "home_team": "Home",
    "away_team": "Away", "start_utc": "2026-10-28T21:00:00Z",
    "source_url": "https://example.org/schedule"
}}

def observation(**overrides):
    row = {
        "record_type": "pregame_odds_observation", "sportsbook": "draftkings",
        "certified_prediction": False, "model_probability": None,
        "event_id": "fixture-001", "league": "nba",
        "home_team": "Home", "away_team": "Away",
        "market_type": "moneyline", "selection": "Home",
        "selection_type": "home", "is_main_line": True,
        "is_alternate_line": False, "is_player_prop": False,
        "odds_american": -110, "odds_decimal": 1.909,
        "timestamp": "2026-10-28T19:59:00Z",
        "recorded_at": "2026-10-28T20:00:00Z",
        "event_start_time": "2026-10-28T21:00:00Z",
    }
    row.update(overrides)
    return row

class ChallengerGateTests(unittest.TestCase):
    def test_valid_main_moneyline_is_research_only(self):
        self.assertEqual(validate(observation(), EVENTS), [])
        staged, quarantined, report = audit([observation()], EVENTS)
        self.assertEqual((len(staged), len(quarantined)), (1, 0))
        self.assertEqual(report["bet_ready_selections"], 0)
        self.assertEqual(report["independently_reverified_sportsbook_prices"], 0)
        self.assertEqual(report["certified_champion_001_predictions"], 0)

    def test_missing_independent_schedule_quarantines(self):
        self.assertEqual(load_schedule(None), {})
        self.assertIn("independent_schedule_unknown", validate(observation(), {}))
        staged, quarantined, report = audit([observation()], {})
        self.assertEqual(len(staged), 0)
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(report["independent_schedule_events_available"], 0)

    def test_stale_quote_rejected(self):
        self.assertIn("quote_too_old_or_future", validate(
            observation(timestamp="2026-10-28T19:55:00Z"), EVENTS))

    def test_future_quote_rejected(self):
        self.assertIn("quote_too_old_or_future", validate(
            observation(timestamp="2026-10-28T20:00:30Z"), EVENTS))

    def test_event_start_disagreement_rejected(self):
        self.assertIn("event_start_mismatch", validate(
            observation(event_start_time="2026-10-28T21:10:00Z"), EVENTS))

    def test_reversed_teams_rejected(self):
        self.assertIn("event_identity_mismatch", validate(
            observation(home_team="Away", away_team="Home"), EVENTS))

    def test_prop_missing_stable_player_id_rejected(self):
        reasons = validate(observation(market_type="player_points",
            selection="Over", selection_type="over", is_player_prop=True,
            player_name="Example Player", player_id=None, line=24.5), EVENTS)
        self.assertIn("unresolved_player_identity", reasons)

    def test_spread_without_line_rejected(self):
        reasons = validate(observation(market_type="point_spread", line=None), EVENTS)
        self.assertIn("invalid_spread_line", reasons)

    def test_inconsistent_odds_rejected(self):
        self.assertIn("inconsistent_decimal_odds", validate(
            observation(odds_decimal=1.35), EVENTS))

    def test_market_probabilities_not_accepted_as_model(self):
        self.assertIn("unexpected_prediction_field", validate(
            observation(model_probability=0.6), EVENTS))

    def test_invalid_market_is_quarantined(self):
        self.assertIn("unsupported_market_family", validate(
            observation(market_type="unknown_market"), EVENTS))

    def test_report_accounting(self):
        staged, quarantined, r = audit([observation(), observation(player_id=None,
            market_type="player_points", is_player_prop=True,
            selection_type="over", line=21.5)], EVENTS)
        self.assertEqual(r["observations"], r["staged_for_research_only"] + r["quarantined"])
        self.assertEqual(r["automated_bets_placed"], 0)
        self.assertFalse(r["champion_001_modified"])

if __name__ == "__main__":
    unittest.main()
