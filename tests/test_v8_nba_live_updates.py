"""Offline guards for NBA as-observed game state and market freshness updates."""
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from v8_nba_live_updates import create_report, parse_scoreboard, render, run

NOW = datetime(2026, 11, 14, 23, 15, tzinfo=timezone.utc)


def event(event_id, *, state, start, score_home="0", score_away="0"):
    return {
        "id": str(event_id),
        "date": start,
        "season": {"type": 2},
        "status": {
            "type": {"state": state, "shortDetail": "source-reported"},
            "period": 3,
            "displayClock": "04:35",
        },
        "competitions": [{
            "date": start,
            "competitors": [
                {"homeAway": "home", "team": {"id": str(100+int(event_id)),
                 "displayName": "Home " + str(event_id)}, "score": score_home},
                {"homeAway": "away", "team": {"id": str(200+int(event_id)),
                 "displayName": "Away " + str(event_id)}, "score": score_away},
            ],
        }],
    }


def source(*events):
    return json.dumps({"events": list(events)}).encode("utf-8")


class NBALiveUpdateTests(unittest.TestCase):

    def test_pregame_game_cannot_show_predicted_scores_or_bets(self):
        game = event(1, state="pre", start="2026-11-15T00:00:00Z")
        board = parse_scoreboard(source(game), now=NOW)
        self.assertEqual(board["published_game_count"], 1)
        row = board["games"][0]
        self.assertTrue(row["pregame_research_eligible_by_clock_only"])
        self.assertIsNone(row["score_home"])
        self.assertIsNone(row["score_away"])
        self.assertIsNone(row["period"])
        self.assertIsNone(row["verified_sportsbook_price"])
        self.assertIsNone(row["verified_player_active_status"])
        self.assertEqual(row["bet_decision"], "HOLD_NO_CERTIFIED_EDGE")

    def test_in_play_has_reported_score_but_no_pregame_bet(self):
        game = event(2, state="in", start="2026-11-14T22:00:00Z",
                     score_home="88", score_away="79")
        board = create_report(scoreboard_bytes=source(game), now=NOW)
        self.assertEqual(board["source_reported_in_progress"], 1)
        self.assertEqual(board["games"][0]["score_home"], 88)
        self.assertEqual(board["games"][0]["score_away"], 79)
        self.assertEqual(board["games"][0]["period"], 3)
        self.assertEqual(board["games"][0]["clock"], "04:35")
        self.assertFalse(board["games"][0]["pregame_research_eligible_by_clock_only"])
        self.assertFalse(board["games"][0]["in_play_betting_covered"])
        self.assertEqual(board["certified_positive_ev_bets"], 0)

    def test_in_play_score_pace_extrapolation_is_not_win_probability(self):
        board = create_report(scoreboard_bytes=source(
            event(20, state="in", start="2026-11-14T22:00:00Z",
                  score_home="88", score_away="79")), now=NOW)
        game = board["games"][0]
        self.assertEqual(game["projection_status"], "IN_GAME_UNCALIBRATED_PACE_ESTIMATE")
        self.assertAlmostEqual(game["elapsed_regulation_minutes"], 31.42, places=2)
        self.assertAlmostEqual(game["pace_extrapolated_final_total_points"], 255.2, places=1)
        self.assertIsNone(game["live_win_probability"])
        self.assertFalse(game["qualified_for_in_play_betting"])
        self.assertFalse(game["in_play_market_odds_verified"])
        self.assertEqual(board["uncalibrated_pace_estimates_available"], 1)
        self.assertFalse(board["live_win_probabilities_certified"])
        self.assertIn("pace projections", render(board))
        self.assertIn("255.2", render(board))

    def test_first_quarter_pace_prediction_withheld(self):
        game = event(21, state="in", start="2026-11-14T22:00:00Z",
                     score_home="20", score_away="23")
        game["status"]["period"] = 1
        game["status"]["displayClock"] = "02:00"
        report = create_report(scoreboard_bytes=source(game), now=NOW)
        row = report["games"][0]
        self.assertEqual(row["projection_status"], "FIRST_QUARTER_NOT_COMPLETE")
        self.assertIsNone(row["pace_extrapolated_final_total_points"])
        self.assertIsNone(row["live_win_probability"])

    def test_overtime_does_not_claim_regulation_projected_total(self):
        game = event(22, state="in", start="2026-11-14T22:00:00Z",
                     score_home="112", score_away="112")
        game["status"]["period"] = 5
        game["status"]["displayClock"] = "04:35"
        report = create_report(scoreboard_bytes=source(game), now=NOW)
        row = report["games"][0]
        self.assertEqual(row["projection_status"], "OVERTIME_NOT_MODELED")
        self.assertIsNone(row["pace_extrapolated_final_total_points"])

    def test_clock_invalid_or_missing_score_blocks_projection(self):
        bad = event(23, state="in", start="2026-11-14T22:00:00Z",
                    score_home="88", score_away="79")
        bad["status"]["displayClock"] = "unknown"
        missing_score = event(24, state="in", start="2026-11-14T22:00:00Z",
                              score_home="88", score_away="unavailable")
        board = create_report(scoreboard_bytes=source(bad, missing_score), now=NOW)
        states = [g["projection_status"] for g in board["games"]]
        self.assertIn("IN_GAME_CLOCK_UNPARSABLE", states)
        self.assertIn("IN_GAME_SCORE_OR_CLOCK_UNAVAILABLE", states)
        self.assertEqual(board["uncalibrated_pace_estimates_available"], 0)

    def test_final_and_pregame_not_turned_into_live_pace_predictions(self):
        pre = event(25, state="pre", start="2026-11-15T00:00:00Z")
        post = event(26, state="post", start="2026-11-14T22:00:00Z",
                     score_home="102", score_away="96")
        board = create_report(scoreboard_bytes=source(pre, post), now=NOW)
        self.assertEqual(board["games"][0]["projection_status"], "PREGAME_NO_LIVE_PROJECTION")
        self.assertEqual(board["games"][1]["projection_status"], "FINAL_USE_ACTUAL_SCORE_NOT_PROJECTION")
        self.assertTrue(all(g["live_win_probability"] is None for g in board["games"]))
        self.assertEqual(board["certified_positive_ev_bets"], 0)

    def test_final_is_as_observed_not_upcoming(self):
        game = event(3, state="post", start="2026-11-14T20:30:00Z",
                     score_home="108", score_away="104")
        board = parse_scoreboard(source(game), now=NOW)
        self.assertEqual(board["source_reported_final"], 1)
        self.assertEqual(board["games"][0]["score_home"], 108)
        self.assertIsNone(board["games"][0]["clock"])
        self.assertFalse(board["games"][0]["pregame_research_eligible_by_clock_only"])

    def test_pregame_past_scheduled_tip_is_held_even_if_feed_lags(self):
        game = event(4, state="pre", start="2026-11-14T21:00:00Z")
        board = parse_scoreboard(source(game), now=NOW)
        self.assertFalse(board["games"][0]["pregame_research_eligible_by_clock_only"])

    def test_invalid_score_not_inferred(self):
        board = parse_scoreboard(
            source(event(5, state="in", start="2026-11-14T21:00:00Z",
                         score_home="9999", score_away="not reported")),
            now=NOW)
        self.assertIsNone(board["games"][0]["score_home"])
        self.assertIsNone(board["games"][0]["score_away"])

    def test_malformed_response_is_unavailable_not_zero_scheduled(self):
        board = create_report(scoreboard_bytes=b"garbage", now=NOW)
        self.assertIsNone(board["published_game_count"])
        self.assertEqual(board["source_status"], "UNREADABLE_ESPN_SOURCE_NOT_ZERO_GAMES")
        self.assertEqual(board["decision"], "HOLD_NO_CERTIFIED_EDGE")
        self.assertEqual(board["wagers_placed"], 0)

    def test_http_unavailable_is_not_marked_as_no_games(self):
        with TemporaryDirectory() as p:
            output = run(output_dir=p, now=NOW,
                         fetcher=lambda url: (_ for _ in ()).throw(OSError("503")))
            self.assertIsNone(output["published_game_count"])
            self.assertEqual(output["source_status"], "SOURCE_UNAVAILABLE_NOT_ZERO_GAMES")
            self.assertEqual(output["source_error"], "PUBLIC_SCOREBOARD_NETWORK_OR_HTTP_UNAVAILABLE")
            self.assertTrue((Path(p)/"NBA_LIVE_UPDATES.md").exists())

    def test_injury_metadata_is_only_workflow_not_player_clearance(self):
        with TemporaryDirectory() as p:
            meta = Path(p)/"injury.json"
            meta.write_text(json.dumps([{
                "databaseId": 23, "updatedAt": "2026-11-14T23:01:00Z"}]))
            board = create_report(scoreboard_bytes=source(), now=NOW,
                                  injury_metadata=meta)
            injury = board["injury_workflow_reference"]
            self.assertEqual(injury["workflow_run_id"], 23)
            self.assertEqual(injury["reference_age_minutes"], 14)
            self.assertFalse(injury["actual_player_injury_designations_retrieved_here"])
            self.assertFalse(injury["official_final_active_roster_confirmed"])

    def test_no_quote_archive_cannot_claim_live_odds_or_zero_percent(self):
        with TemporaryDirectory() as p:
            board = create_report(scoreboard_bytes=source(), now=NOW,
                                  sharp_archive_dir=p)
            self.assertEqual(board["market_quote_status"], "NO_ARCHIVED_PROVIDER_QUOTES")
            self.assertNotIn("NO_EXACT_PAIRED_MARKETS", board["market_quote_status"])
            self.assertIsNone(board["latest_archived_nba_quote_age_minutes"])
            self.assertFalse(board["live_draftkings_checkout_verified"])
            self.assertFalse(board["live_player_props_verified"])
            self.assertIn("HOLD", render(board))
            self.assertNotIn("100% win", render(board))

    def test_date_boundary_uses_eastern_and_removes_other_dates(self):
        board = parse_scoreboard(source(
            event(6, state="pre", start="2026-11-15T00:00:00Z"),
            event(7, state="pre", start="2026-11-16T02:00:00Z")
        ), now=NOW)
        self.assertEqual(board["date_et"], "2026-11-14")
        self.assertEqual(board["published_game_count"], 1)

    def test_read_bounded_original_bytes_not_arbitrary_large_payload(self):
        with self.assertRaises(ValueError):
            parse_scoreboard(b"x" * 5_000_001, now=NOW)

    def test_missing_clock_timezone_rejected(self):
        with self.assertRaises(ValueError):
            create_report(scoreboard_bytes=source(), now=datetime(2026, 11, 14))


if __name__ == "__main__":
    unittest.main()
