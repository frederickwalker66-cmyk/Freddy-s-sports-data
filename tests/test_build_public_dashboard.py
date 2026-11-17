"""Offline tests: public dashboard never promotes unverified betting evidence."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.build_public_dashboard import build, read_report

NOW = datetime(2026, 11, 14, 21, 0, tzinfo=timezone.utc)


def live(at=NOW):
    return {
        "source_status": "ESPN_SCOREBOARD_OBSERVED",
        "observed_at_utc": at.isoformat(),
        "date_et": at.date().isoformat(),
        "champion_001_modified": False,
        "certified_positive_ev_bets": 0,
        "wagers_placed": 0,
        "pregame_rule_context_status": "EXACT_MATCHED_UNCALIBRATED_PREGAME_RESEARCH_ONLY",
        "games": [{
            "espn_event_id": "123",
            "away_team": "Chicago Bulls",
            "home_team": "Minnesota Timberwolves",
            "scheduled_start_et": "2026-11-14T20:00:00-05:00",
            "source_event_state": "pre",
            "score_away": None, "score_home": None,
            "pregame_rule_home_win_percent": 72.9,
            "pregame_rule_probability_source_time_utc": "2026-11-14T20:40:00Z",
            "pace_extrapolated_final_home_points": None,
            "pace_extrapolated_final_away_points": None,
            "pace_extrapolated_final_total_points": None,
            "projection_status": "PREGAME_NO_LIVE_PROJECTION",
        }],
        "today_unstarted_nba_price_rows_within_120m": 100,
    }


def model():
    return {
        "champion_001_modified": False,
        "certified_positive_ev_bets": 0,
        "checked_at_utc": NOW.isoformat(),
        "by_league": {
            "nba": {"execution_status": "SUCCESS_RESEARCH_ONLY",
                    "uncalibrated_pregame_forecast_rows": 1,
                    "complete_player_last5": 25, "complete_team_last10": 30}
        },
        "sharp_edge_research": {
            "per_sport_market_evidence": {
                "nba": {
                    "archived_provider_quote_rows": 1000,
                    "fresh_paired_game_boards": 5,
                    "fresh_paired_player_prop_markets": 8,
                    "primary_source_blocker": "UNVERIFIED_MODEL_PROBABILITY_AND_CHECKOUT",
                }
            }
        },
        "source_quote_freshness": {
            "by_league": {"nba": {
                "today_upcoming_quote_rows_within_120m": 100,
                "latest_valid_source_received_utc": "2026-11-14T20:50:00Z",
                "latest_valid_archive_receipt_age_minutes": 10,
            }}
        },
    }


class PublicDashboardTests(unittest.TestCase):
    def test_minimal_valid_current_score_and_exact_rule_baseline(self):
        board = build(live=live(), model=model(), at=NOW,
                      live_run=123, model_run=456)
        self.assertEqual(board["live_source_status"], "SOURCE_OBSERVED")
        self.assertEqual(board["games"][0]["pregame_home_probability_pct"], 72.9)
        self.assertEqual(board["games"][0]["status"], "pre")
        self.assertIsNone(board["games"][0]["home_score"])
        self.assertEqual(board["market"]["paired_game_markets"], 5)
        self.assertEqual(board["market"]["paired_prop_markets"], 8)
        self.assertEqual(board["market"]["verified_checkout_prices"], 0)
        self.assertEqual(board["market"]["certified_positive_ev"], 0)
        self.assertTrue(board["model"]["champion_frozen"])
        self.assertEqual(board["sources"]["run_nba"].split("/")[-1], "456")

    def test_stale_scoreboard_is_not_displayed_as_live(self):
        board = build(live=live(NOW - timedelta(hours=4)), model=model(), at=NOW)
        self.assertEqual(board["live_source_status"], "AWAITING_FRESH_PUBLIC_SCOREBOARD")
        self.assertEqual(board["games"], [])
        self.assertIsNone(board["live_observed_at_utc"])
        self.assertEqual(board["market"]["paired_game_markets"], 5)

    def test_model_must_be_frozen_and_zero_certified(self):
        unsafe = model()
        unsafe["champion_001_modified"] = True
        r = build(live=live(), model=unsafe, at=NOW)
        self.assertIsNone(r["market"]["paired_game_markets"])
        self.assertEqual(r["market"]["certified_positive_ev"], 0)
        unsafe = model()
        unsafe["certified_positive_ev_bets"] = 1
        r = build(live=live(), model=unsafe, at=NOW)
        self.assertEqual(r["model"]["betting_state"], "HOLD")

    def test_stale_model_report_cannot_supply_current_market_coverage(self):
        old = model()
        old["checked_at_utc"] = (NOW - timedelta(hours=4)).isoformat()
        board = build(model=old, at=NOW)
        self.assertEqual(board["leagues"]["nba"]["research_freshness"], "STALE_RESEARCH")
        self.assertEqual(board["market"]["price_evidence_state"], "STALE_OR_MISSING_MODEL_REPORT")
        self.assertFalse(board["market"]["paired_market_reference_current"])
        self.assertIsNone(board["market"]["paired_game_markets"])
        self.assertIsNone(board["market"]["paired_prop_markets"])
        # Historical archive evidence remains visible as ARCHIVED, not live.
        self.assertEqual(board["market"]["archived_quotes"], 1000)
        self.assertEqual(board["market"]["certified_positive_ev"], 0)

    def test_old_quote_with_recent_model_shows_missing_current_prices(self):
        recent_model = model()
        recent_model["source_quote_freshness"]["by_league"]["nba"][
            "latest_valid_source_received_utc"] = (NOW - timedelta(hours=3)).isoformat()
        board = build(model=recent_model, at=NOW)
        self.assertEqual(board["leagues"]["nba"]["research_freshness"], "RECENT_RESEARCH")
        self.assertEqual(board["market"]["price_evidence_state"], "STALE_OR_MISSING_PRICE_RECEIPT")
        self.assertIsNone(board["market"]["paired_game_markets"])
        self.assertIsNone(board["market"]["recent_raw_quotes"])
        self.assertEqual(board["market"]["verified_checkout_prices"], 0)

    def test_current_aggregator_stays_research_only(self):
        board = build(model=model(), at=NOW)
        self.assertTrue(board["market"]["paired_market_reference_current"])
        self.assertEqual(board["market"]["paired_game_markets"], 5)
        self.assertEqual(board["market"]["price_evidence_state"],
                         "RECENT_AGGREGATOR_REFERENCE_ONLY_NO_CHECKOUT")
        self.assertEqual(board["market"]["certified_positive_ev"], 0)

    def test_no_in_game_pace_when_pregame(self):
        row = live()
        game = row["games"][0]
        game["pace_extrapolated_final_total_points"] = 256.4
        game["pace_extrapolated_final_away_points"] = 120
        game["pace_extrapolated_final_home_points"] = 136.4
        game["projection_status"] = "IN_GAME_UNCALIBRATED_PACE_ESTIMATE"
        out = build(live=row, model=model(), at=NOW)
        self.assertIsNone(out["games"][0]["pace_total"])

    def test_explicit_score_and_pace_when_inplay(self):
        row = live()
        game = row["games"][0]
        game.update(source_event_state="in", score_away=79, score_home=88,
                    period=3, clock="04:35",
                    projection_status="IN_GAME_UNCALIBRATED_PACE_ESTIMATE",
                    pace_extrapolated_final_total_points=255.2,
                    pace_extrapolated_final_home_points=134.5,
                    pace_extrapolated_final_away_points=120.7)
        out = build(live=row, model=model(), at=NOW)
        self.assertEqual(out["games"][0]["pace_total"], 255.2)
        self.assertEqual(out["games"][0]["home_score"], 88)
        self.assertEqual(out["market"]["certified_positive_ev"], 0)

    def test_invalid_probability_and_missing_source_are_na(self):
        row = live()
        row["pregame_rule_context_status"] = "NO_QUALIFIED_EXACT_MATCH"
        row["games"][0]["pregame_rule_home_win_percent"] = 99.9
        r = build(live=row, at=NOW)
        self.assertIsNone(r["games"][0]["pregame_home_probability_pct"])
        self.assertIsNone(r["market"]["paired_game_markets"])
        self.assertEqual(r["leagues"]["ncaab"]["status"], "No synced research report")

    def test_missing_files_fail_closed(self):
        with TemporaryDirectory() as d:
            self.assertIsNone(read_report(Path(d)/"not-here.json"))
            out = build(at=NOW)
            self.assertEqual(out["games"], [])
            self.assertEqual(out["model"]["betting_state"], "HOLD")
            self.assertFalse(out["live_scoreboard_not_continuous"] is False)

    def test_all_sports_report_fills_missing_leagues_not_fabricated(self):
        r = model()
        r["by_league"]["nhl"] = {"execution_status":"SUCCESS_RESEARCH_ONLY",
                                  "uncalibrated_pregame_forecast_rows": 6}
        out = build(live=live(), model=model(), all_sports=r, at=NOW, all_run=90)
        self.assertEqual(out["leagues"]["nhl"]["forecasts"], 6)
        self.assertIsNone(out["leagues"]["ncaaf"]["forecasts"])
        self.assertEqual(out["sources"]["run_all"].split("/")[-1], "90")


if __name__ == "__main__":
    unittest.main()
