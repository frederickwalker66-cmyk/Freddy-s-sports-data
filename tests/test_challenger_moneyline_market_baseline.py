"""Synthetic paired-market audit; no-vig market odds are NOT model forecasts."""
import unittest
from copy import deepcopy

from challenger_moneyline_market_baseline import compare_pairs, inspect_quote, implied


def quote(side="home", source="sportsgameodds_v2", **changes):
    odds = -120 if side == "home" else 110
    row = {
        "record_type": "pregame_odds_observation",
        "source": source, "sportsbook": "draftkings",
        "league": "nba", "event_id": "sgo:game1",
        "provider_odd_id": f"points-{side}-game-ml-{side}",
        "home_team": "Atlanta Hawks", "away_team": "Cleveland Cavaliers",
        "selection": "Atlanta Hawks" if side == "home" else "Cleveland Cavaliers",
        "selection_type": side, "market_type": "moneyline", "line": None,
        "is_main_line": False if source == "sportsgameodds_v2" else True,
        "is_alternate_line": False, "is_player_prop": False,
        "odds_american": odds, "odds_decimal": (1.833333 if side == "home" else 2.1),
        "timestamp": "2026-10-30T19:00:00Z",
        "recorded_at": "2026-10-30T19:08:00Z",
        "event_start_time": "2026-10-30T23:30:00Z",
        "certified_prediction": False, "model_probability": None,
    }
    row.update(changes)
    return row


def validation(n):
    return {"observations": n, "champion_001_modified": False,
            "certified_champion_001_predictions": 0,
            "certified_challenger_predictions": 0,
            "independently_reverified_sportsbook_prices": 0,
            "bet_ready_selections": 0, "automated_bets_placed": 0}


class MoneylineBaselineTests(unittest.TestCase):
    def test_market_two_way_overround_and_no_vig(self):
        pairs, report = compare_pairs([quote(), quote("away")], validation(2))
        self.assertEqual(len(pairs), 1)
        x = pairs[0]
        p_home = 120 / 220
        p_away = 100 / 210
        self.assertAlmostEqual(x["market_no_vig_home_probability_research_only"],
                               p_home / (p_home + p_away), places=6)
        self.assertAlmostEqual(x["market_overround"], p_home + p_away, places=6)
        self.assertFalse(x["provider_main_line_flag_for_both"])
        self.assertFalse(x["draftkings_checkout_verified"])
        self.assertFalse(x["certified_prediction"])
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertEqual(report["positive_ev_candidates_certified"], 0)
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_archived_ten_minute_price_is_not_bet_ready(self):
        r = quote(recorded_at="2026-10-30T19:10:00Z")
        pairs, report = compare_pairs([r, quote("away",
                                     recorded_at="2026-10-30T19:10:00Z")],validation(2))
        self.assertEqual(len(pairs), 1)
        self.assertFalse(pairs[0]["draftkings_checkout_verified"])
        self.assertEqual(report["automated_bets_placed"], 0)

    def test_older_first_to_score_moneyline_is_excluded(self):
        h = quote(provider_odd_id="firstToScore-home-game-ml-home")
        a = quote("away",provider_odd_id="firstToScore-away-game-ml-away")
        pairs, report=compare_pairs([h,a],validation(2))
        self.assertEqual(pairs, [])
        self.assertEqual(report["excluded_rows_or_event_groups"]
                         ["untrusted_sgo_full_game_winner_stat"],2)

    def test_older_last_to_score_is_excluded(self):
        h = quote(provider_odd_id="lastToScore-home-game-ml-home")
        self.assertEqual(inspect_quote(h)[1],"untrusted_sgo_full_game_winner_stat")

    def test_missing_side_never_reconstructed(self):
        pairs, report = compare_pairs([quote()], validation(1))
        self.assertEqual(pairs, [])
        self.assertEqual(report["excluded_rows_or_event_groups"]["missing_or_duplicate_two_sides"],1)

    def test_multiple_prices_per_side_are_ambiguous(self):
        rows=[quote(),quote(),quote("away")]
        pairs,report=compare_pairs(rows,validation(3))
        self.assertEqual(pairs, [])
        self.assertEqual(report["excluded_rows_or_event_groups"]["missing_or_duplicate_two_sides"],1)

    def test_unequal_timestamps_reject_pair(self):
        away=quote("away",timestamp="2026-10-30T19:03:00Z")
        pairs,report=compare_pairs([quote(),away],validation(2))
        self.assertEqual(pairs, [])
        self.assertEqual(report["excluded_rows_or_event_groups"]["inconsistent_event_or_price_times"],1)

    def test_wrong_team_selection_rejects_side(self):
        rows=[quote(selection="Cleveland Cavaliers"),quote("away")]
        pairs,r=compare_pairs(rows,validation(2))
        self.assertEqual(pairs, [])
        self.assertEqual(r["excluded_rows_or_event_groups"]["selection_contradicts_side"],1)

    def test_too_old_or_after_start_rejected(self):
        self.assertEqual(inspect_quote(quote(recorded_at="2026-10-30T20:00:00Z"))[1],
                         "not_timestamped_pregame_archive")
        self.assertEqual(inspect_quote(quote(timestamp="2026-10-30T23:31:00Z"))[1],
                         "not_timestamped_pregame_archive")

    def test_player_props_and_three_way_soccer_do_not_enter_binary_market(self):
        for invalid in [quote(league="mls"),quote(is_player_prop=True),
                        quote(market_type="player_points")]:
            self.assertEqual(inspect_quote(invalid)[1],"unsupported_or_untrusted_market")

    def test_provider_book_not_combined(self):
        h=quote()
        a=quote("away",source="sharpapi_rest",event_id="sgo:game1")
        pairs,report=compare_pairs([h,a],validation(2))
        self.assertEqual(pairs, [])
        self.assertEqual(report["moneyline_event_groups_seen"],2)

    def test_negative_or_implausible_vig_quarantined(self):
        h=quote(odds_american=200,odds_decimal=3.0)
        a=quote("away",odds_american=200,odds_decimal=3.0)
        pairs,r=compare_pairs([h,a],validation(2))
        self.assertEqual(pairs,[])
        self.assertEqual(r["excluded_rows_or_event_groups"]["implausible_market_overround"],1)

    def test_inconsistent_decimal_rejected(self):
        self.assertEqual(inspect_quote(quote(odds_decimal=4.0))[1],
                         "inconsistent_decimal_price")

    def test_forged_model_probability_and_modified_champion_blocked(self):
        h=quote(model_probability=0.7)
        self.assertEqual(inspect_quote(h)[1], "unsupported_or_untrusted_market")
        report=validation(2)
        report["champion_001_modified"]=True
        with self.assertRaisesRegex(ValueError,"cannot analyze certified"):
            compare_pairs([quote(),quote("away")],report)

    def test_sharp_provider_assertion_still_not_checkout_verification(self):
        h=quote(source="sharpapi_rest",selection="ATL Hawks")
        a=quote("away",source="sharpapi_rest")
        pairs,_=compare_pairs([h,a],validation(2))
        self.assertEqual(len(pairs),1)
        self.assertTrue(pairs[0]["provider_main_line_flag_for_both"])
        self.assertFalse(pairs[0]["independently_verified_primary_line"])
        self.assertFalse(pairs[0]["draftkings_checkout_verified"])


if __name__=="__main__":
    unittest.main()
