"""Quality-of-grading runway: retrospective maturity and source gaps only."""
import unittest
from datetime import datetime, timezone
from v8_forward_grading_runway import (
    GRADE, PENDING, DUE, QUARANTINED, grade_runway,
)

NOW = datetime(2026, 11, 14, 20, 0, tzinfo=timezone.utc)


def row(eid, state, *, started="2026-11-10T20:00:00Z",
        captured="2026-11-10T19:00:00Z", won=None,
        published=None):
    return {
        "sport": "nba", "espn_event_id": eid, "model_version": "test-fixed",
        "original_forecast_utc": captured, "original_tipoff_utc": started,
        "grade_status": state, "home_won_published_final_research_only": won,
        "published_final_observed_utc": published,
        "certified_prediction": False, "certified_champion_001_shadow": False,
        "positive_ev_certified": False, "wager_stake_usd": 0,
    }


class GradeRunwayTests(unittest.TestCase):
    def test_empty_is_unavailable_not_zero_success(self):
        r = grade_runway([], now=NOW)
        self.assertIsNone(r["grade_completeness_of_mature_nonquarantined_pct"])
        self.assertIsNone(r["grade_coverage_of_all_archived_pct"])
        self.assertEqual(r["mature_eligible_nonquarantined"], 0)
        self.assertEqual(r["certified_positive_ev_bets"], 0)

    def test_mature_due_pending_and_quarantine_partition(self):
        rows = [
            row("100", GRADE, won=1, published="2026-11-13T20:00:00Z"),
            row("101", DUE),
            row("102", PENDING, started="2026-11-13T20:00:00Z",
                captured="2026-11-13T19:00:00Z"),
            # A quarantined forecast can have an older published result:
            # the history must preserve the original grade but exclude it
            # from reliable model metrics.
            row("103", QUARANTINED, won=0,
                published="2026-11-13T20:00:00Z"),
        ]
        r = grade_runway(
            rows, now=NOW, source_days_checked=1, forecasts_deferred=2)
        self.assertEqual(r["total_saved_original_forecasts"], 4)
        self.assertEqual(r["genuinely_forward_grades"], 1)
        self.assertEqual(r["awaiting_48h_maturity"], 1)
        self.assertEqual(r["mature_due_without_accepted_final"], 1)
        self.assertEqual(r["quarantined_conflicting_forecasts"], 1)
        self.assertEqual(r["grade_completeness_of_mature_nonquarantined_pct"],50.0)
        self.assertEqual(r["grade_coverage_of_all_archived_pct"],25.0)
        self.assertEqual(r["median_original_pregame_lead_minutes"],60.0)
        self.assertEqual(r["median_published_final_observation_delay_hours_after_tipoff"],72.0)
        self.assertEqual(r["oldest_mature_ungraded_hours_after_48h_gate"],48.0)
        self.assertEqual(r["forecasts_deferred_due_to_source_day_budget"],2)
        self.assertEqual(r["additional_graded_to_50"],49)
        self.assertEqual(r["additional_graded_to_100"],99)
        self.assertEqual(r["next_priority"],"REVIEW_STALE_MATURED_UNGRADED_RESULTS")
        self.assertFalse(r["predictive_accuracy_or_roi_computed"])
        self.assertFalse(r["calibrated_betting_model_created"])

    def test_blocks_false_premature_grades_and_outcome_leak(self):
        with self.assertRaisesRegex(ValueError,"grade_missing_final_or_not_mature"):
            grade_runway([row("100", GRADE, won=1,
                started="2026-11-14T19:00:00Z",
                captured="2026-11-14T18:00:00Z",
                published="2026-11-14T19:30:00Z")],now=NOW)
        with self.assertRaisesRegex(ValueError,"ungraded_forecast_has_outcome_label"):
            grade_runway([row("100", DUE, won=1)],now=NOW)
        with self.assertRaisesRegex(ValueError,"stale_maturity_state"):
            grade_runway([row("100", PENDING)],now=NOW)
        with self.assertRaisesRegex(ValueError,"cannot_promote_grade_health_to_a_bet"):
            grade_runway([dict(row("100",DUE), certified_prediction=True)],now=NOW)

    def test_rejects_duplicate_events_and_future_forecast_receipts(self):
        x=row("100", DUE)
        with self.assertRaisesRegex(ValueError,"duplicate_or_invalid_forward_event"):
            grade_runway([x,x],now=NOW)
        with self.assertRaisesRegex(ValueError,"future_original_forecast_receipt"):
            grade_runway([row("100",PENDING,
                started="2026-11-16T20:00:00Z",
                captured="2026-11-16T19:00:00Z")],now=NOW)
        with self.assertRaisesRegex(ValueError,"source_day_counters_must_be_nonnegative"):
            grade_runway([],now=NOW,source_days_checked=-1)


if __name__ == "__main__":
    unittest.main()
