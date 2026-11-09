"""Certification-readiness audit tests: evidence receipts never self-certify."""
import json
import tempfile
import unittest
from pathlib import Path

from v8_certification_audit import inspect_archives, LEAGUES


def fixture(base):
    source = Path(base) / "source"
    sharp = Path(base) / "sharp"
    (source / "model_completion/native_training").mkdir(parents=True)
    (source / "independent_identity").mkdir(parents=True)
    (sharp / "validation_output").mkdir(parents=True)

    def write(root, rel, value):
        path = root / rel
        path.write_text(json.dumps(value) + "\n", encoding="utf-8")

    by_league = {lg: {
        "future_games_archived": 1 if lg == "nba" else 0,
        "source_days_failed": 0,
    } for lg in LEAGUES}
    write(source, "preflight_summary.json", {
        "stage": "challenger_eight_sport_original_schedule_live_preflight_research_only",
        "by_league": by_league,
        "totals": {"pregame_events_archived": 1},
        "champion_001_modified": False,
    })
    write(source, "model_completion/release_readiness.json", {
        "stage": "challenger_82_full_sequence_release_readiness",
        "archived_pregame_games": 1,
        "league_operated_identity_matches_research_only": {
            lg: 0 for lg in LEAGUES},
        "champion_001_modified": False,
    })
    write(source, "model_completion/native_training/research_training_report.json", {
        "stage": "challenger_multisport_native_research_training",
        "review_attested_records_received": 0,
        "trained_research_models": [],
        "champion_001_modified": False,
    })
    write(source, "model_completion/champion_authentication.json", {
        "stage": "champion_001_artifact_authentication",
        "original_executable_verified": False,
        "immutable_model_version_authenticated": False,
        "reproducible_reference_outputs_verified": False,
        "champion_001_modified": False,
    })
    write(source, "independent_identity/independent_game_identity_report.json", {
        "stage": "challenger_78_independent_league_identity_research_only",
        "archived_espn_events_reviewed": 1,
        "champion_001_modified": False,
    })
    write(sharp, "validation_output/moneyline_market_baseline_report.json", {
        "report_type": "challenger_full_game_two_way_market_baseline_research_only",
        "two_way_research_market_pairs": 10,
        "champion_001_modified": False,
    })
    return source, sharp


class CertificationAuditTests(unittest.TestCase):
    def test_without_any_artifact_no_proof_and_explicit_missing(self):
        r = inspect_archives()
        self.assertEqual(r["certified_v8_predictions"], 0)
        self.assertEqual(r["certified_positive_ev_bets"], 0)
        self.assertEqual(r["source_games_archived"], None)
        self.assertFalse(r["reports_found"]["release"])
        self.assertIn("source_archive_missing", r["by_league"]["nba"]["blockers"])

    def test_reconcile_real_report_shapes_without_fabricated_certification(self):
        with tempfile.TemporaryDirectory() as folder:
            source, sharp = fixture(folder)
            r = inspect_archives(source, sharp, 12345, 67890)
            self.assertEqual(r["source_games_archived"], 1)
            self.assertEqual(r["research_moneyline_price_pairs_from_aggregator"], 10)
            self.assertEqual(r["source_run_id"], 12345)
            self.assertEqual(r["sharp_run_id"], 67890)
            self.assertEqual(len(r["by_league"]), 8)
            self.assertEqual(r["by_league"]["nba"]["archived_source_games_latest_run"], 1)
            self.assertEqual(r["certified_positive_ev_bets"], 0)
            self.assertFalse(r["bet_ready"])

    def test_self_claimed_champion_success_is_not_external_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            source, sharp = fixture(folder)
            path = source / "model_completion/champion_authentication.json"
            value = json.loads(path.read_text())
            value["original_executable_verified"] = True
            value["immutable_model_version_authenticated"] = True
            value["reproducible_reference_outputs_verified"] = True
            path.write_text(json.dumps(value))
            r = inspect_archives(source, sharp)
            self.assertTrue(r["prior_artifact_report_claims_champion_verified_untrusted"])
            self.assertFalse(r["original_champion_001_authenticated_by_external_review"])
            self.assertEqual(r["certified_champion_001_predictions"], 0)

    def test_same_run_event_count_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source, sharp = fixture(folder)
            path = source / "model_completion/release_readiness.json"
            value = json.loads(path.read_text())
            value["archived_pregame_games"] = 3
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "counts_disagree"):
                inspect_archives(source, sharp)

    def test_orphan_release_or_wrong_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source, sharp = fixture(folder)
            (source / "preflight_summary.json").unlink()
            with self.assertRaisesRegex(ValueError, "orphan_release"):
                inspect_archives(source, sharp)

    def test_unsafe_pricing_report_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source, sharp = fixture(folder)
            path = sharp / "validation_output/moneyline_market_baseline_report.json"
            value = json.loads(path.read_text())
            value["champion_001_modified"] = True
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "unsafe_sharp_price_report"):
                inspect_archives(source, sharp)


if __name__ == "__main__":
    unittest.main()
