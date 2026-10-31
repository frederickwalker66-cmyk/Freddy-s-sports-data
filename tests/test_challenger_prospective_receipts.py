"""Synthetic only: receipt integrity is not independent provenance."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_prospective_receipts import (
    LEAGUES, check_archive_root, make_receipt, main, verify_receipt,
)

AT = datetime(2026, 10, 29, 21, 40, tzinfo=timezone.utc)
LATE = datetime(2026, 10, 30, 1, 0, tzinfo=timezone.utc)


def row(league="nba", eid="401001"):
    return {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": league,
        "espn_schedule_event_id": eid,
        "home_team": "Fictional Home",
        "away_team": "Fictional Away",
        "event_start_utc": "2026-10-30T00:00:00Z",
        "snapshot_completed_at_utc": "2026-10-29T21:30:00Z",
        "schedule_observed_at_utc": "2026-10-29T21:29:00Z",
        "schedule_source_url": "https://site.api.espn.com/scoreboard",
        "odds_observations": [],
        "certified_prediction": False,
        "model_probability": None,
        "qualified_for_challenger_backtest": False,
        "bet_ready": False, "champion_001_modified": False,
    }


def original(*items):
    return "".join(json.dumps(x, sort_keys=True) + "\n" for x in items).encode("utf-8")


class OriginalByteReceiptTests(unittest.TestCase):
    def test_eight_leagues_have_timed_research_receipts_not_certification(self):
        source=original(*(row(league, str(401000+i)) for i,league in enumerate(LEAGUES)))
        manifest=make_receipt(source, "5312", AT)
        checked=verify_receipt(source, manifest, expected_run_id="5312", now=LATE)
        self.assertEqual(checked["timed_research_captures"],8)
        self.assertEqual(checked["independently_authenticated_captures"],0)
        self.assertEqual(sum(x.get("timed_capture_for_review_only",0)
                             for x in checked["by_league"].values()),8)
        self.assertEqual(manifest["certified_champion_001_predictions"],0)
        self.assertFalse(manifest["qualified_for_challenger_training"])

    def test_raw_byte_mutation_cannot_pass_same_original_receipt(self):
        a=original(row())
        manifest=make_receipt(a,"5312",AT)
        mutated=a.replace(b"Fictional Home",b"Fictional Other")
        with self.assertRaisesRegex(ValueError,"raw bytes"):
            verify_receipt(mutated,manifest,now=LATE)

    def test_modified_record_hash_cannot_pass(self):
        a=original(row())
        manifest=make_receipt(a,"5312",AT)
        manifest["records"][0]["raw_jsonl_line_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"identity/status"):
            verify_receipt(a,manifest,now=LATE)

    def test_receipt_generated_after_tipoff_not_accepted_for_pregame(self):
        a=original(row())
        receipt=make_receipt(a,"5312",LATE)
        r=verify_receipt(a,receipt,now=LATE)
        self.assertEqual(r["timed_research_captures"],0)
        self.assertEqual(r["status_counts"]["receipt_not_before_game"],1)

    def test_future_receipt_rejected(self):
        a=original(row())
        receipt=make_receipt(a,"5312",LATE)
        with self.assertRaisesRegex(ValueError,"future-dated"):
            verify_receipt(a,receipt,now=AT)

    def test_duplicate_same_event_in_snapshot_fails(self):
        with self.assertRaisesRegex(ValueError,"duplicate"):
            make_receipt(original(row(),row()),"5312",AT)

    def test_after_tipoff_capture_is_blocked(self):
        x=row()
        x["snapshot_completed_at_utc"]="2026-10-30T00:00:01Z"
        receipt=make_receipt(original(x),"5312",LATE)
        r=verify_receipt(original(x),receipt,now=LATE)
        self.assertEqual(r["status_counts"]["invalid_or_late_pregame_capture"],1)

    def test_unsupported_league_not_enabled(self):
        x=row("wnba")
        source=original(x)
        receipt=make_receipt(source,"5312",AT)
        result=verify_receipt(source,receipt,now=LATE)
        self.assertEqual(result["status_counts"]["unsupported_league"],1)

    def test_false_certification_flag_fails_hard(self):
        source=original(row())
        receipt=make_receipt(source,"5312",AT)
        receipt["qualified_for_challenger_training"]=True
        with self.assertRaisesRegex(ValueError,"certification"):
            verify_receipt(source,receipt,now=LATE)

    def test_mismatched_run_id_fails(self):
        source=original(row())
        receipt=make_receipt(source,"5312",AT)
        with self.assertRaisesRegex(ValueError,"run ID mismatch"):
            verify_receipt(source,receipt,expected_run_id="5313",now=LATE)

    def test_invalid_run_id_fails(self):
        with self.assertRaises(ValueError):
            make_receipt(original(row()),"fake-run",AT)

    def test_missing_historical_receipts_are_reported_as_missing(self):
        with TemporaryDirectory() as root:
            folder=Path(root)/"123"
            folder.mkdir()
            (folder/"prospective_event_evidence.jsonl").write_bytes(original(row()))
            r=check_archive_root(root,now=LATE)
            self.assertEqual(r["archive_coverage"]["archive_missing_receipt"],1)
            self.assertEqual(r["independently_verified_training_examples"],0)

    def test_archive_root_detects_tampered_or_claimed_run(self):
        with TemporaryDirectory() as root:
            folder=Path(root)/"999"
            folder.mkdir()
            raw=original(row())
            (folder/"prospective_event_evidence.jsonl").write_bytes(raw)
            receipt=make_receipt(raw,"5312",AT)
            (folder/"point_in_time_receipt.json").write_text(json.dumps(receipt))
            report=check_archive_root(root,now=LATE)
            self.assertEqual(report["archive_coverage"]["receipt_invalid_or_mismatch"],1)

    def test_valid_original_file_in_run_dir_integrity_only(self):
        with TemporaryDirectory() as root:
            folder=Path(root)/"5312"
            folder.mkdir()
            raw=original(row())
            (folder/"prospective_event_evidence.jsonl").write_bytes(raw)
            (folder/"point_in_time_receipt.json").write_text(
                json.dumps(make_receipt(raw,"5312",AT)))
            report=check_archive_root(root,now=LATE)
            self.assertEqual(report["archive_coverage"]["archive_bytes_checked"],1)
            self.assertEqual(report["independently_verified_training_examples"],0)
            self.assertTrue(report["original_raw_bytes_checked_against_self_issued_receipts_only"])
            self.assertFalse(report["github_actions_run_id_crosschecked_with_platform"])

    def test_cli_capture_and_inspect_keeps_zero_training(self):
        with TemporaryDirectory() as root:
            folder=Path(root)/"5312"
            folder.mkdir()
            path=folder/"prospective_event_evidence.jsonl"
            path.write_bytes(original(row()))
            receipt=folder/"point_in_time_receipt.json"
            # The CLI uses current time; its receipt can be after the
            # fictional game, and this must not be recast as pregame evidence.
            self.assertEqual(main(["--mode","capture","--snapshots",str(path),
                                   "--run-id","5312","--output",str(receipt)]),0)
            report=Path(root)/"report.json"
            self.assertEqual(main(["--mode","inspect","--snapshot-root",root,
                                   "--output",str(report)]),0)
            summary=json.loads(report.read_text())
            self.assertEqual(summary["trained_models_created"],0)
            self.assertEqual(summary["bet_ready_selections"],0)
            self.assertFalse(summary["champion_001_modified"])


if __name__=="__main__":
    unittest.main()
