"""Offline provenance and fail-closed tests for V9 evidence aggregation."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import unittest

from v9_sharp_edge_evidence_board import build_board, markdown, load_file, text_safe


FIXED = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


class V9EvidenceTests(unittest.TestCase):
    def test_unverified_probability_and_ev_claims_never_promoted(self):
        with TemporaryDirectory() as t:
            root = Path(t) / "one_display"
            root.mkdir()
            content = {
                "certified_positive_ev_bets": 99,
                "rows": [{
                    "league": "nba", "game": "Example A @ Example B",
                    "market": "home/away win", "category": "RESEARCH FORECAST",
                    "selection": "HOME", "line": None, "american_odds": -110,
                    "break_even_probability_percent": 52.38,
                    "no_vig_market_probability_percent": 50.0,
                    "research_model_probability_percent": 63.0,
                    "verified_champion_001_probability_percent": 99.0,
                    "expected_roi_percent": 100.0, "source_timestamp_utc": "2026-11-18T09:00:00Z",
                }],
            }
            (root / "ONE_DISPLAY_SHARP_EDGE.json").write_text(json.dumps(content))
            meta = {"scope": "one_display", "run_id": 123,
                    "run_url": "https://github.com/test/repo/actions/runs/123",
                    "artifact_name": "v8-one-command-123"}
            report = build_board({"one_display": (root, meta)}, clock=FIXED)
            row = report["game_and_prop_display_rows"][0]
            self.assertEqual(row["action"], "HOLD_RESEARCH_ONLY")
            self.assertEqual(row["time_status"], "HISTORICAL_OR_STALE_GT_120_MIN")
            self.assertEqual(row["uncalibrated_research_rule_percent_not_champion"], 63.0)
            self.assertIsNone(row["certified_native_model_probability_percent"])
            self.assertIsNone(row["certified_ev_percent"])
            self.assertEqual(report["certified_positive_ev_count_by_this_board"], 0)
            self.assertEqual(report["automated_wagers"], 0)
            self.assertEqual(report["paid_api_requests"], 0)
            self.assertEqual(report["qualified_parlays_by_this_board"], 0)
            self.assertIn("UNAUTHENTICATED_UPSTREAM_POSITIVE_EV_CLAIM",
                          " ".join(report["warnings"]))
            self.assertEqual(row["evidence"]["json_array_pointer"], "/rows/0")
            self.assertEqual(len(row["evidence"]["sha256_of_downloaded_file"]), 64)
            self.assertEqual(row["evidence"]["run_id"], 123)

    def test_archived_movement_cannot_be_called_clv_or_sharp_flow(self):
        with TemporaryDirectory() as t:
            root = Path(t) / "sharp_edge"
            root.mkdir()
            (root / "NFL_PLAYER_PROP_SHARP_EDGE_RESEARCH.json").write_text(json.dumps({
                "nba_exact_prop_archive_observations": 25,
                "nfl_exact_prop_archive_observations": 80,
            }))
            (root / "sharp_prop_line_movements.jsonl").write_text(json.dumps({
                "league": "nfl", "player_name": "Test Player",
                "line": 3.5, "stat": "player_receptions",
                "last_capture_utc": "2026-11-17T01:00:00Z",
                "away_team": "Team A", "home_team": "Team B",
                "verified_sharp_money": True, "bet_ready": True,
            }) + "\n")
            meta = {"scope": "sharp_edge", "run_id": 456,
                    "run_url": "https://github.com/test/repo/actions/runs/456",
                    "artifact_name": "v8-nfl-props-edge-456"}
            board = build_board({"sharp_edge": (root, meta)}, clock=FIXED)
            self.assertEqual(len(board["market_repricing_research_rows"]), 1)
            move = board["market_repricing_research_rows"][0]
            self.assertFalse(move["verified_clv"])
            self.assertFalse(move["verified_sharp_money"])
            self.assertIn("HISTORICAL", move["status"])
            self.assertEqual(move["evidence"]["jsonl_line"], 1)
            self.assertEqual(board["reported_quote_coverage_context_only"]["archived_nfl_prop_observations"], 80)

    def test_schedule_source_scope_and_missing_files(self):
        with TemporaryDirectory() as t:
            root = Path(t) / "schedule"
            root.mkdir()
            (root / "eight_sport_schedule_coverage.json").write_text(json.dumps({
                "by_league": {"nba": {"coverage_class": "example_only", "source_checks": [{}]}}
            }))
            board = build_board({"schedule": (root, {"scope": "schedule"})}, clock=FIXED)
            self.assertEqual(board["eight_league_schedule_source_snapshot"]["nba"]["research_source_day_checks"], 1)
            self.assertEqual(board["eight_league_schedule_source_snapshot"]["mlb"]["scope"], "UNAVAILABLE")
            self.assertEqual(len(board["six_virtual_staff"]), 6)
            self.assertEqual(board["source_manifest"]["sharp_edge"]["status"], "UNAVAILABLE")
            self.assertEqual(board["source_manifest"]["one_display"]["status"], "UNAVAILABLE")
            self.assertIn("Eight-league schedule-source evidence", markdown(board))

    def test_file_hash_does_not_claim_authenticity(self):
        with TemporaryDirectory() as t:
            p = Path(t)
            raw = b'{"rows":[]}'
            (p / "ONE_DISPLAY_SHARP_EDGE.json").write_bytes(raw)
            doc, ref = load_file(p, "ONE_DISPLAY_SHARP_EDGE.json",
                                 {"scope": "one_display", "run_id": 2})
            self.assertEqual(doc, {"rows": []})
            self.assertEqual(ref["sha256_of_downloaded_file"], hashlib.sha256(raw).hexdigest())
            self.assertFalse(ref["original_provider_or_checkout_signature_verified"])
            with self.assertRaises(ValueError):
                load_file(p, "../../etc/passwd", {"scope": "one_display"})

    def test_markdown_untrusted_content_sanitized(self):
        self.assertNotIn("|", text_safe("NBA|NEW\nLINE<script>"))
        self.assertNotIn("<", text_safe("NBA|NEW\nLINE<script>"))


if __name__ == "__main__":
    unittest.main()
