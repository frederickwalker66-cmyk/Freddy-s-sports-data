import json
import tempfile
import unittest
from pathlib import Path
from mlb_nba_independent_source_gate import audit

class SourceGateTests(unittest.TestCase):
    def test_empty_archives_hold_both_leagues(self):
        with tempfile.TemporaryDirectory() as root:
            result = audit(root)
            self.assertEqual(result["status"], "HOLD")
            for league in ("mlb", "nba"):
                self.assertEqual(result["leagues"][league]["qualified_training_rows"], 0)
                self.assertIn("missing_historical_coverage_report", result["leagues"][league]["blocking_gates"])

    def test_self_reported_flags_do_not_certify(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root) / "nba"
            base.mkdir()
            record = {"league": "nba", "published_completed_game_results": 3,
                      "quarantined_research_candidates": 2,
                      "historical_pregame_feature_timestamps_verified": True,
                      "historical_odds_snapshots_verified": True,
                      "independent_result_adjudication_verified": True,
                      "bookmaker_market_settlement_verified": True}
            (base / "backfill_coverage.json").write_text(json.dumps(record))
            (base / "validation_report.json").write_text(json.dumps({"provider_scores_stats_odds_authenticated": True}))
            result = audit(root)
            self.assertEqual(result["leagues"]["nba"]["published_final_observations"], 3)
            self.assertIn("record_level_independent_attestations_not_evaluated", result["leagues"]["nba"]["blocking_gates"])
            self.assertEqual(result["qualified_training_rows_created"], 0)
            self.assertFalse(result["champion_001_modified"])
            self.assertFalse(result["nfl_collection_modified"])

if __name__ == "__main__":
    unittest.main()
