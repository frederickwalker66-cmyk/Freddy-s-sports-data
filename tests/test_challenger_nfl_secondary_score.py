"""Synthetic NFL secondary-score tests; no source data is treated as training."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_nfl_secondary_score import parse_nflverse, review, run, main

NOW = datetime(2026, 11, 5, 13, 0, tzinfo=timezone.utc)

HEADER = "game_id,season,game_type,gameday,gametime,home_team,away_team,home_score,away_score,espn\n"


def csv_bytes(scores=("24", "17"), away="NYG", game_time="16:25", espn="4019001"):
    return (HEADER + f"2026_09_NYG_DAL,2026,REG,2026-11-01,{game_time},"
            + f"DAL,{away},{scores[0]},{scores[1]},{espn}\n"
            + "2026_10_NYG_DAL,2026,REG,2026-11-08,16:25,DAL,NYG,,,\n").encode()


def packet(event_id="4019001", published=True):
    return {
        "record_type": "challenger_original_bytes_feature_lineage_review_only",
        "league": "nfl", "event_id": event_id,
        "home_team": "Dallas Cowboys", "away_team": "New York Giants",
        "event_start_utc": "2026-11-01T21:25:00Z",
        "snapshot_completed_at_utc": "2026-11-01T17:25:00Z",
        "original_bytes_match_same_run_receipt": True,
        "same_run_receipt_independently_authenticated": False,
        "published_final_only": {
            "home_score": 24, "away_score": 17, "published_result": "home",
            "published_at_observation_utc": "2026-11-02T02:00:00Z",
            "source_url": "https://site.api.espn.com/scoreboard",
        } if published else None,
        "qualified_for_challenger_training": False,
        "independent_outcome_review": False,
        "market_settlement_rules_verified": False,
        "model_probability": None, "certified_prediction": False,
        "bet_ready": False, "champion_001_modified": False,
    }


class NFLSecondaryScoreTests(unittest.TestCase):
    def test_matches_exact_team_start_espn_id_and_final_score(self):
        rows, report = review([packet()], csv_bytes(), NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "nflverse_second_source_final_score_agrees_research_only")
        self.assertEqual(rows[0]["nflverse_game_id"], "2026_09_NYG_DAL")
        self.assertEqual(rows[0]["nflverse_source_sha256"],
                         hashlib.sha256(csv_bytes()).hexdigest())
        self.assertEqual(report["second_source_final_score_agreements"], 1)
        self.assertEqual(report["certified_positive_ev_bets"], 0)
        self.assertFalse(report["champion_001_modified"])

    def test_future_unplayed_games_not_scored(self):
        rows = parse_nflverse(csv_bytes())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["home_score"], 24)

    def test_nflverse_score_disagreement_is_reported(self):
        rows, _ = review([packet()], csv_bytes(("21", "17")), NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "nflverse_published_score_disagrees_with_espn")
        self.assertFalse(rows[0]["qualified_for_challenger_training"])

    def test_nflverse_espn_id_disagreement_blocks_false_game_match(self):
        rows, _ = review([packet()], csv_bytes(espn="4019999"), NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "nflverse_unmatched_identity_or_clock")

    def test_wrong_full_team_is_not_fuzzy_matched(self):
        p = packet()
        p["home_team"] = "Dallas"
        with self.assertRaisesRegex(ValueError, "unknown_full"):
            review([p], csv_bytes(), NOW)

    def test_reversed_or_different_away_team_never_matches(self):
        rows, _ = review([packet()], csv_bytes(away="PHI"), NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "nflverse_unmatched_identity_or_clock")

    def test_wrong_kickoff_excluded(self):
        rows, _ = review([packet()], csv_bytes(game_time="12:00"), NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "nflverse_unmatched_identity_or_clock")

    def test_nfl_tie_requires_separate_market_settlement(self):
        p=packet()
        p["published_final_only"]["home_score"] = 17
        p["published_final_only"]["published_result"] = "draw"
        rows, report = review([p], csv_bytes(("17", "17")), NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "tie_requires_book_specific_settlement_review")
        self.assertEqual(report["second_source_final_score_agreements"], 0)

    def test_missing_secondary_scores_but_primary_exists_blocks(self):
        rows, report = review([packet()], None, NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "nflverse_source_unavailable")
        self.assertFalse(report["nflverse_source_valid"])

    def test_missing_espn_published_final_skips_external_fetch(self):
        calls=[]
        rows, report, raw=run([packet(published=False)],
                              fetcher=lambda: calls.append("called"), observed=NOW)
        self.assertEqual(calls, [])
        self.assertIsNone(raw)
        self.assertEqual(rows[0]["crosscheck_status"], "awaiting_espn_published_final")

    def test_duplicate_nflverse_ids_invalidate_whole_source(self):
        x=csv_bytes()
        x += b"2026_09_NYG_DAL,2026,REG,2026-11-01,16:25,DAL,NYG,24,17,4019001\n"
        rows, report = review([packet()], x, NOW)
        self.assertTrue(rows[0]["crosscheck_status"].startswith("invalid_nflverse_source_"))
        self.assertEqual(report["second_source_final_score_agreements"],0)

    def test_missing_nflverse_header_fails_closed(self):
        rows, report = review([packet()], b"game_id,season\n2026_09_NYG_DAL,2026\n", NOW)
        self.assertFalse(report["nflverse_source_valid"])
        self.assertFalse(rows[0]["qualified_for_challenger_training"])

    def test_unqualified_packet_rejected_before_network(self):
        p=packet()
        p["qualified_for_challenger_training"]=True
        calls=[]
        with self.assertRaisesRegex(ValueError,"unquarantined"):
            run([p],fetcher=lambda: calls.append("called"),observed=NOW)
        self.assertFalse(calls)

    def test_network_failure_reports_blocker(self):
        def fail():
            raise OSError("offline")
        rows, report, raw = run([packet()], fetcher=fail, observed=NOW)
        self.assertIsNone(raw)
        self.assertEqual(report["network_source_failure"], "OSError")
        self.assertEqual(rows[0]["crosscheck_status"], "nflverse_source_unavailable")

    def test_cli_without_nfl_games_writes_no_model_or_source(self):
        with TemporaryDirectory() as tmp:
            input_file=Path(tmp)/"lineage.jsonl"
            input_file.write_text("")
            self.assertEqual(main(["--lineage",str(input_file),
                                   "--output-dir",str(Path(tmp)/"output")]),0)
            files=sorted(x.name for x in (Path(tmp)/"output").iterdir())
            self.assertEqual(files,["nfl_second_source_score_report.json",
                                    "nfl_second_source_score_review.jsonl"])
            report=json.loads((Path(tmp)/"output"/files[0]).read_text())
            self.assertEqual(report["independently_qualified_training_games"],0)


if __name__=="__main__":
    unittest.main()
