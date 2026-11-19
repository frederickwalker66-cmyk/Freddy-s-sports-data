"""Exact NBA ticket research audit: authentic match requirements and HOLD gates."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import unittest

from v8_nba_ticket_research import audit_named_ticket

TICKET_FILE = Path(__file__).resolve().parents[1] / "examples" / "nba_2026_11_17_eight_leg_research.json"
NOW = datetime(2026, 11, 17, 21, 0, tzinfo=timezone.utc)


def reports():
    return (
        {"certified_positive_ev_bets": 0, "champion_001_modified": False,
         "today_game_market_board": []},
        {"certified_positive_ev_bets": 0, "champion_001_modified": False,
         "today_player_prop_market_probability_board": {"nba": []}},
    )


class NamedEightLegTicketTests(unittest.TestCase):
    def setUp(self):
        self.ticket = json.loads(TICKET_FILE.read_text(encoding="utf-8"))
        self.games, self.props = reports()

    def test_no_new_prices_never_means_no_probability(self):
        r = audit_named_ticket(self.ticket, self.games, self.props, now=NOW)
        self.assertEqual(r["leg_count"], 8)
        self.assertEqual(r["current_qualified_two_sided_reference_count"], 0)
        self.assertEqual([x["action"] for x in r["legs"]], ["HOLD"] * 8)
        self.assertEqual(len(r["same_event_groups"]), 3)
        self.assertEqual(r["certified_positive_ev_bets"], 0)
        self.assertEqual(r["wagers_placed"], 0)
        self.assertIsNone(r["certified_joint_parlay_win_probability"])
        self.assertIsNone(r["legs"][0]["model_probability"])
        self.assertFalse(r["champion_001_modified"])

    def test_exact_moneyline_archived_price_cannot_certify_model(self):
        self.games["today_game_market_board"] = [{
            "league": "nba", "home_team": "Toronto Raptors",
            "away_team": "New York Knicks", "start_utc": "2026-11-18T00:30:00Z",
            "verified_sportsbook_checkout": False,
            "qualified_model_probability": False,
            "paired_primary_markets": {"moneyline": {
                "home_or_over_line": None, "away_or_under_line": None,
                "home_or_over_odds": 115, "away_or_under_odds": -135,
                "source_received_utc": "2026-11-17T20:55:00Z",
                "bookmaker_checkout_price_verified": False,
                "native_model_probability_verified": False,
            }},
        }]
        r = audit_named_ticket(self.ticket, self.games, self.props, now=NOW)
        self.assertEqual(r["current_qualified_two_sided_reference_count"], 1)
        self.assertEqual(r["legs"][0]["fresh_archived_price_not_executable"], -135)
        self.assertIsNone(r["legs"][0]["verified_checkout_price"])
        self.assertIsNone(r["legs"][0]["certified_expected_value"])
        self.assertEqual(r["certified_positive_ev_bets"], 0)

    def test_changed_total_line_must_not_match_original_eight_leg(self):
        self.games["today_game_market_board"] = [{
            "league": "nba", "home_team": "Minnesota Timberwolves",
            "away_team": "Portland Trail Blazers",
            "start_utc": "2026-11-18T01:00:00Z",
            "verified_sportsbook_checkout": False,
            "qualified_model_probability": False,
            "paired_primary_markets": {"total_points": {
                "home_or_over_line": 225.5, "away_or_under_line": 225.5,
                "home_or_over_odds": -110, "away_or_under_odds": -110,
                "source_received_utc": "2026-11-17T20:55:00Z",
                "bookmaker_checkout_price_verified": False,
                "native_model_probability_verified": False,
            }},
        }]
        r = audit_named_ticket(self.ticket, self.games, self.props, now=NOW)
        self.assertEqual(r["legs"][1]["source_market_status"],
                         "NO_RECENT_EXACT_TWO_SIDED_ARCHIVE_REFERENCE")

    def test_diacritics_and_strict_prop_stat_line_match_only_as_reference(self):
        self.props["today_player_prop_market_probability_board"]["nba"] = [{
            "league": "nba", "home_team": "Los Angeles Lakers",
            "away_team": "Charlotte Hornets", "start_utc": "2026-11-18T04:00:00Z",
            "player_name": "Luka Doncic", "prop_stat": "player_points",
            "line": 29.5, "over_american_odds": -200,
            "under_american_odds": 170,
            "last_capture_utc": "2026-11-17T20:55:00Z",
            "active_player_independently_verified": False,
            "player_identity_independently_verified": False,
            "bet_ready": False,
        }]
        r = audit_named_ticket(self.ticket, self.games, self.props, now=NOW)
        self.assertEqual(r["legs"][7]["fresh_archived_price_not_executable"], -200)
        self.assertEqual(r["legs"][7]["previously_reported_odds_not_current"], -364)
        self.assertIsNone(r["legs"][7]["model_probability"])

    def test_expired_ticket_is_not_published_as_current(self):
        after = NOW + timedelta(days=1)
        r = audit_named_ticket(self.ticket, self.games, self.props, now=after)
        self.assertTrue(all(x["source_market_status"] == "EXPIRED_REFERENCE_DATE"
                            for x in r["legs"]))
        self.assertEqual(r["current_qualified_two_sided_reference_count"], 0)

    def test_refuse_false_provider_checkout_or_fabricated_certification(self):
        self.games["certified_positive_ev_bets"] = 1
        with self.assertRaisesRegex(ValueError, "untrusted_game_report"):
            audit_named_ticket(self.ticket, self.games, self.props, now=NOW)
        self.games["certified_positive_ev_bets"] = 0
        self.props["champion_001_modified"] = True
        with self.assertRaisesRegex(ValueError, "untrusted_prop_report"):
            audit_named_ticket(self.ticket, self.games, self.props, now=NOW)

    def test_research_ticket_cannot_include_placed_wager(self):
        self.ticket["stake_usd"] = "10.00"
        with self.assertRaisesRegex(ValueError, "research_ticket_cannot_have_accepted_wager"):
            audit_named_ticket(self.ticket, self.games, self.props, now=NOW)


    def test_stale_future_missing_timestamp_and_unpaired_game_odds_are_not_recent(self):
        pair = {
            "home_or_over_line": None, "away_or_under_line": None,
            "home_or_over_odds": 115, "away_or_under_odds": -135,
            "source_received_utc": "2026-11-17T20:55:00Z",
            "bookmaker_checkout_price_verified": False,
            "native_model_probability_verified": False,
        }
        entry = {
            "league": "nba", "home_team": "Toronto Raptors",
            "away_team": "New York Knicks", "start_utc": "2026-11-18T00:30:00Z",
            "verified_sportsbook_checkout": False,
            "qualified_model_probability": False,
            "paired_primary_markets": {"moneyline": pair},
        }
        self.games["today_game_market_board"] = [entry]
        self.assertEqual(audit_named_ticket(self.ticket, self.games, self.props, now=NOW)
                         ["current_qualified_two_sided_reference_count"], 1)
        for stamp in ("2026-11-17T20:49:59Z", "2026-11-17T21:00:01Z",
                      "2026-11-18T00:30:00Z", "invalid", None):
            with self.subTest(stamp=stamp):
                pair["source_received_utc"] = stamp
                result = audit_named_ticket(self.ticket, self.games, self.props, now=NOW)
                self.assertEqual(result["current_qualified_two_sided_reference_count"], 0)
                self.assertIsNone(result["legs"][0]["fresh_archived_price_not_executable"])
        pair["source_received_utc"] = "2026-11-17T20:59:00Z"
        pair["away_or_under_odds"] = None
        self.assertEqual(audit_named_ticket(self.ticket, self.games, self.props, now=NOW)
                         ["current_qualified_two_sided_reference_count"], 0)

    def test_prop_reference_requires_recent_two_sided_pregame_price(self):
        prop = {
            "league": "nba", "home_team": "Los Angeles Lakers",
            "away_team": "Charlotte Hornets", "start_utc": "2026-11-18T04:00:00Z",
            "player_name": "Luka Doncic", "prop_stat": "player_points",
            "line": 29.5, "over_american_odds": -200, "under_american_odds": 170,
            "last_capture_utc": "2026-11-17T20:58:00Z",
            "active_player_independently_verified": False,
            "player_identity_independently_verified": False, "bet_ready": False,
        }
        self.props["today_player_prop_market_probability_board"]["nba"] = [prop]
        good = audit_named_ticket(self.ticket, self.games, self.props, now=NOW)
        self.assertEqual(good["legs"][7]["reference_quote_age_minutes"], 2.0)
        self.assertEqual(good["legs"][7]["action"], "HOLD")
        for key, value in (("last_capture_utc", "2026-11-17T20:30:00Z"),
                           ("under_american_odds", None)):
            with self.subTest(key=key):
                candidate = dict(prop)
                candidate[key] = value
                self.props["today_player_prop_market_probability_board"]["nba"] = [candidate]
                result = audit_named_ticket(self.ticket, self.games, self.props, now=NOW)
                self.assertIsNone(result["legs"][7]["fresh_archived_price_not_executable"])

    def test_previous_holds_are_visible_and_eight_leg_lock_remains_blocked(self):
        result = audit_named_ticket(self.ticket, self.games, self.props, now=NOW)
        self.assertEqual(result["previously_held_or_rejected_leg_numbers"],
                         list(range(1, 9)))
        self.assertEqual(result["certified_eight_leg_locks"], 0)
        self.assertIn("NO_LOCK", result["eight_leg_betting_verdict"])
        self.assertTrue(all(x["previously_held_or_rejected"] for x in result["legs"]))
        self.assertTrue(all(x["eligible_for_certified_parlay"] is False
                            for x in result["legs"]))
        self.assertEqual(result["max_archive_reference_age_seconds"], 600)


if __name__ == "__main__":
    unittest.main()
