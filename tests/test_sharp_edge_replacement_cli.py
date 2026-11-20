from datetime import datetime, timedelta, timezone
import unittest
from research.sharp_edge_replacement_cli import run, candidate_from_json

NOW = datetime(2026, 11, 20, 19, 0, tzinfo=timezone.utc)


def fixture_candidate(**changes):
    base = dict(selection_id="assists-a", market="assists_over", american_odds=-110,
                model_probability=.60, model_id="Champion-001", model_verified=True,
                odds_verified=True, odds_timestamp=(NOW-timedelta(minutes=1)).isoformat(),
                evaluation_timestamp=NOW.isoformat(), injury_verified=True,
                matchup_verified=True, minutes_verified=True, calibrated=True)
    base.update(changes)
    return base


def test_adapter_take_only_and_report_hold():
    report = run({"original": [{"selection_id": "bad", "decision": "PASS"}],
                  "candidates": [fixture_candidate()]})
    assert report["replacements"][0]["decision"] == "TAKE"
    assert report["betting_status"] == "HOLD_UNTIL_FULL_TICKET_VERIFIED"
    assert "NOT_LIVE" in report["source_status"]


def test_unverified_snapshot_cannot_replace():
    report = run({"original": [{"selection_id": "bad", "decision": "PASS"}],
                  "candidates": [fixture_candidate(model_verified=False)]})
    assert report["replacements"][0]["replacement"] is None
    assert report["candidate_audit"][0]["decision"] == "HOLD"


def test_missing_verification_field_fails_closed():
    item = fixture_candidate()
    del item["calibrated"]
    with unittest.TestCase().assertRaises(ValueError):
        candidate_from_json(item)


def test_string_verified_flag_rejected():
    with unittest.TestCase().assertRaises(ValueError):
        candidate_from_json(fixture_candidate(model_verified="true"))


def test_no_snapshot_candidates_means_no_replacement():
    report = run({"original": [{"selection_id": "bad", "decision": "PASS"}], "candidates": []})
    assert report["board"][0]["decision"] == "HOLD"
