"""Safety tests for source schedule watchdog and fail-closed recovery."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from v8_source_cadence_watchdog import (
    evaluate, dispatch, MAX_AGE_MINUTES,
    MAX_RECOVERY_ATTEMPTS_PER_DAY, TARGET,
)

NOW = datetime(2026, 11, 9, 17, 0, tzinfo=timezone.utc)


def run(index, *, minutes_ago, status="completed", conclusion="success",
        event="schedule", branch="main", created_minutes_ago=None):
    created = NOW - timedelta(minutes=created_minutes_ago if created_minutes_ago is not None else minutes_ago + 2)
    updated = NOW - timedelta(minutes=minutes_ago)
    return {
        "id": index, "head_branch": branch, "event": event,
        "created_at": created.isoformat(), "updated_at": updated.isoformat(),
        "status": status, "conclusion": conclusion,
    }


class SourceWatchdogTests(unittest.TestCase):
    def test_fresh_success_does_not_dispatch(self):
        r = evaluate({"workflow_runs": [run(1, minutes_ago=42)]}, now=NOW)
        self.assertEqual(r["recovery_decision"], "HOLD")
        self.assertEqual(r["reason"], "recent_successful_source_workflow")
        self.assertEqual(r["latest_successful_workflow_run_id"], 1)

    def test_stale_success_requests_one_source_only(self):
        r = evaluate({"workflow_runs": [run(1, minutes_ago=MAX_AGE_MINUTES + 1)]}, now=NOW)
        self.assertEqual(r["recovery_decision"], "REQUEST_ONE_PUBLIC_SOURCE_CAPTURE")
        self.assertEqual(r["source_workflow"], TARGET)
        self.assertFalse(r["dispatch_accepted"])
        self.assertFalse(r["source_data_independently_authenticated"])
        self.assertEqual(r["certified_positive_ev_bets"], 0)

    def test_queue_blocks_recovery(self):
        r = evaluate({"workflow_runs": [
            run(1, minutes_ago=250), run(2, minutes_ago=10,
                status="in_progress", conclusion=None)]}, now=NOW)
        self.assertEqual(r["reason"], "source_workflow_already_in_flight")

    def test_recovery_attempt_budget(self):
        rows = [run(1, minutes_ago=400)]
        rows += [run(i + 10, minutes_ago=180 + i * 20,
                    event="workflow_dispatch", status="completed",
                    conclusion="failure")
                 for i in range(MAX_RECOVERY_ATTEMPTS_PER_DAY)]
        r = evaluate({"workflow_runs": rows}, now=NOW)
        self.assertEqual(r["reason"], "recovery_attempt_budget_exhausted_24h")

    def test_missing_metadata_blocks_dispatch(self):
        for data in ({}, {"fetch_error": True}, {"workflow_runs": None}, None):
            r = evaluate(data, now=NOW)
            self.assertEqual(r["recovery_decision"], "HOLD")
            self.assertEqual(r["reason"], "metadata_unavailable")

    def test_untrusted_branch_not_evidence(self):
        r = evaluate({"workflow_runs": [run(1, minutes_ago=12, branch="feature/test")]}, now=NOW)
        self.assertEqual(r["recovery_decision"], "REQUEST_ONE_PUBLIC_SOURCE_CAPTURE")
        self.assertIsNone(r["latest_successful_workflow_run_id"])

    def test_execute_one_fixed_dispatch_is_not_completed_job(self):
        report = evaluate({"workflow_runs": [run(1, minutes_ago=300)]}, now=NOW)
        calls = []
        def runner(args):
            calls.append(args)
            return SimpleNamespace(returncode=0)
        updated = dispatch(report, execute=True, token="test-token", runner=runner)
        self.assertTrue(updated["dispatch_accepted"])
        self.assertEqual(updated["recovery_decision"], "DISPATCH_ACCEPTED_UNVERIFIED")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][-1], "ref=main")
        self.assertIn(TARGET, calls[0][4])
        self.assertFalse(updated["source_data_independently_authenticated"])
        self.assertEqual(updated["automated_wagers"], 0)

    def test_no_token_no_writes(self):
        report = evaluate({"workflow_runs": []}, now=NOW)
        updated = dispatch(report, execute=True, token=None)
        self.assertFalse(updated["dispatch_attempted"])
        self.assertEqual(updated["recovery_decision"], "HOLD")

    def test_never_dispatch_other_workflow(self):
        report = evaluate({"workflow_runs": []}, now=NOW)
        report["source_workflow"] = "collect-sharpapi.yml"
        def forbidden(_):
            raise AssertionError("must_not_call_any_other_workflow")
        updated = dispatch(report, execute=True, token="test-token", runner=forbidden)
        self.assertFalse(updated["dispatch_attempted"])


if __name__ == "__main__":
    unittest.main()
