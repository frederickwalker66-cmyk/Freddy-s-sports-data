"""#84: original-byte rolling prospective archive and leakage/duplicate tests."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_rolling_pregame_archive import (
    inspect_capture, aggregate, run,
)
from independent_schedule_review import SOURCES

ORIGINAL = b'{"original":"verified ESPN schedule bytes"}'
DIGEST = hashlib.sha256(ORIGINAL).hexdigest()


def event(start="2026-11-08T18:00:00Z", eid="401873200", **changes):
    r = {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": "nfl", "espn_schedule_event_id": eid,
        "home_team": "New England Patriots", "away_team": "New York Jets",
        "event_start_utc": start,
        "schedule_observed_at_utc": "2026-11-05T18:44:00Z",
        "snapshot_completed_at_utc": "2026-11-05T18:46:00Z",
        "espn_original_schedule_sha256_research_only": DIGEST,
        "model_probability": None, "qualified_for_challenger_backtest": False,
        "certified_prediction": False, "bet_ready": False,
        "champion_001_modified": False,
    }
    return dict(r, **changes)


def build(root, records=None, raw=ORIGINAL):
    root.mkdir(parents=True, exist_ok=True)
    d = root/"espn_original_schedule_bytes"
    d.mkdir()
    (d/"original.json").write_bytes(raw)
    rs = [event()] if records is None else records
    (root/"prospective_event_evidence.jsonl").write_text(
        "".join(json.dumps(r)+"\n" for r in rs))
    (root/"eight_sport_schedule_coverage.json").write_text(json.dumps({
        "by_league": {lg: {} for lg in SOURCES},
        "archived_games_matching_exact_original_event_fields": len(rs),
        "certified_positive_ev_bets": 0,
        "champion_001_modified": False,
    }))


class RollingArchiveTests(unittest.TestCase):
    def test_prospective_original_hash_and_observation_verified(self):
        with TemporaryDirectory() as t:
            p = Path(t)/"scan"
            build(p)
            checked = inspect_capture(p)
            self.assertEqual(checked[0]["original_espn_sha256"], DIGEST)

    def test_hash_tamper_late_archive_or_fake_forecast_rejected(self):
        with TemporaryDirectory() as t:
            p = Path(t)/"scan"
            build(p,raw=b"changed")
            with self.assertRaisesRegex(ValueError, "source_sha"):
                inspect_capture(p)
        for change, phrase in (
            ({"snapshot_completed_at_utc": "2026-11-08T18:01:00Z"}, "not_captured_before"),
            ({"model_probability": 0.65}, "unsafe"),
            ({"certified_prediction": True}, "unsafe"),
        ):
            with TemporaryDirectory() as t:
                p = Path(t)/"scan"
                build(p,[event(**change)])
                with self.assertRaisesRegex(ValueError, phrase):
                    inspect_capture(p)

    def test_same_event_multiple_runs_is_one_unique_identity(self):
        with TemporaryDirectory() as t:
            p = Path(t)/"scan"
            build(p)
            a = inspect_capture(p)
            rows, report = aggregate({"first":a,"second":a})
            self.assertEqual(report["observations_checked"], 2)
            self.assertEqual(report["distinct_future_espn_game_ids"], 1)
            self.assertEqual(report["duplicates_counted_as_independent_training_games"], 0)
            self.assertEqual(rows[0]["capture_count"], 2)
            self.assertEqual(report["qualified_training_games"], 0)

    def test_kickoff_revision_quarantines_both_time_observations(self):
        with TemporaryDirectory() as t:
            p = Path(t)/"scan"
            build(p,[event()])
            a = inspect_capture(p)
            q = Path(t)/"scan2"
            build(q,[event(start="2026-11-08T18:05:00Z")])
            b = inspect_capture(q)
            rows, report = aggregate({"first":a,"second":b})
            self.assertEqual(rows[0]["research_status"],
                             "kickoff_revision_observed_research_quarantined")
            self.assertEqual(report["by_league"]["nfl"]["events_with_conflicts_or_revisions"],1)

    def test_reversed_home_away_is_never_accepted(self):
        with TemporaryDirectory() as t:
            p=Path(t)/"a"
            build(p)
            q=Path(t)/"b"
            build(q,[event(home_team="New York Jets",away_team="New England Patriots")])
            rows, report = aggregate({"a":inspect_capture(p),"b":inspect_capture(q)})
            self.assertEqual(rows[0]["research_status"],
                             "team_or_orientation_conflict_research_quarantined")

    def test_same_run_duplicate_event_fails_closed(self):
        with TemporaryDirectory() as t:
            p=Path(t)/"scan"
            build(p,[event(),event()])
            with self.assertRaisesRegex(ValueError,"source_sha_or_event_identity"):
                inspect_capture(p)

    def test_full_run_optional_previous_missing_or_invalid_skipped(self):
        with TemporaryDirectory() as t:
            root=Path(t)
            build(root/"current")
            invalid=root/"old"/"111"
            invalid.mkdir(parents=True)
            result=run(root/"current",root/"old",root/"output")
            self.assertEqual(result["capture_runs_checked"],1)
            self.assertIn("111",result["previous_capture_artifact_failures"])
            self.assertFalse(result["durable_external_archive_verified"])
            self.assertEqual(result["certified_positive_ev_bets"],0)


if __name__=="__main__":
    unittest.main()
