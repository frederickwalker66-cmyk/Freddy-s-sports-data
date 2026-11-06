"""Synthetic GitHub schedule event tests, no HTTP, API key or sportsbook calls."""
from datetime import datetime, timezone
import unittest
from challenger_hourly_cadence_audit import evaluate

UTC = timezone.utc
ACTIVATED = datetime(2026, 11, 6, 10, 3, tzinfo=UTC)
NOW = datetime(2026, 11, 6, 17, 0, tzinfo=UTC)

def run(ident, created, conclusion="success", event="schedule", status="completed"):
    return {"id": ident, "created_at": created, "event": event,
            "status": status, "conclusion": conclusion}

class HourlyCadenceAuditTests(unittest.TestCase):
    def test_real_slots_count_only_actual_created_scheduled_runs(self):
        data = {"workflow_runs": [
            run(1, "2026-11-06T10:35:00Z"),
            run(2, "2026-11-06T11:34:00Z", conclusion="failure"),
            run(3, "2026-11-06T14:33:00Z"),
            run(4, "2026-11-06T15:02:00Z", event="workflow_run"),
        ]}
        r = evaluate(data, now=NOW, activated_at=ACTIVATED)
        self.assertEqual(r["eligible_scheduled_slots"], 6)
        self.assertEqual(r["observed_scheduled_slots"], 3)
        self.assertEqual(r["successful_scheduled_workflow_runs"], 2)
        self.assertEqual(r["unsuccessful_or_running_scheduled_workflow_runs"], 1)
        self.assertEqual(r["unobserved_scheduled_slots"], 3)
        self.assertEqual(r["certified_positive_ev_bets"], 0)
        self.assertFalse(r["champion_001_modified"])

    def test_delayed_run_cannot_fill_two_slots(self):
        data = {"workflow_runs": [run(42, "2026-11-06T12:35:00Z")]}
        r = evaluate(data, now=NOW, activated_at=ACTIVATED)
        self.assertEqual(r["observed_scheduled_slots"], 1)
        observed = [s for s in r["slots"] if "github_run_id" in s]
        self.assertEqual(observed[0]["scheduled_for_utc"], "2026-11-06T12:27:00+00:00")

    def test_recent_slot_not_prematurely_called_missing(self):
        early = datetime(2026, 11, 6, 11, 0, tzinfo=UTC)
        r = evaluate({"workflow_runs": []}, now=early, activated_at=ACTIVATED)
        self.assertEqual(r["eligible_scheduled_slots"], 0)
        self.assertEqual(r["unobserved_scheduled_slots"], 0)

    def test_unavailable_github_api_is_unknown_not_zero_success(self):
        r = evaluate({"fetch_error": True}, now=NOW, activated_at=ACTIVATED)
        self.assertFalse(r["metadata_available"])
        self.assertIsNone(r["unobserved_scheduled_slots"])
        self.assertEqual(r["successful_scheduled_workflow_runs"], 0)

    def test_metadata_does_not_relabel_workflow_run_as_scheduled(self):
        data = {"workflow_runs": [run(50, "2026-11-06T14:33:00Z",
                                       event="workflow_run")]}
        r = evaluate(data, now=NOW, activated_at=ACTIVATED)
        self.assertEqual(r["observed_scheduled_slots"], 0)

    def test_inprogress_schedule_run_never_reported_as_success(self):
        data = {"workflow_runs": [run(70, "2026-11-06T13:33:00Z",
                                       conclusion=None, status="in_progress")]}
        r = evaluate(data, now=NOW, activated_at=ACTIVATED)
        self.assertEqual(r["successful_scheduled_workflow_runs"], 0)
        self.assertEqual(r["unsuccessful_or_running_scheduled_workflow_runs"], 1)

    def test_invalid_clock_and_metadata_fail_closed(self):
        with self.assertRaises(ValueError):
            evaluate({"workflow_runs": []},
                     now=datetime(2026, 11, 6, 17, 0),
                     activated_at=ACTIVATED)
        with self.assertRaises(ValueError):
            evaluate({"workflow_runs": "no"},
                     now=NOW, activated_at=ACTIVATED)

if __name__ == "__main__":
    unittest.main()
