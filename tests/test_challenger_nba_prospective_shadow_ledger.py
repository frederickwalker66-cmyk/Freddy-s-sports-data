"""Research-only NBA actual pregame selection ledger regression tests.

Synthetic outcomes demonstrate implementation only, never live accuracy.
"""
import unittest
from copy import deepcopy
from datetime import datetime, timezone

from challenger_research_shadow_baseline import build_forecasts
from challenger_nba_prospective_shadow_ledger import build_ledger, sha
from test_challenger_research_shadow_baseline import fixture, NOW
from test_challenger_research_shadow_scorecard import linked

AFTER = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


class NbaProspectiveLedgerTests(unittest.TestCase):
    def source(self, snapshot=None):
        snap = fixture() if snapshot is None else snapshot
        forecasts, report = build_forecasts([snap], NOW)
        self.assertEqual(report["shadow_forecasts_created"], 1)
        return snap, forecasts[0]

    def test_original_pregame_formula_makes_home_selection_with_immutable_id(self):
        snap, forecast = self.source()
        rows, r = build_ledger([snap], [forecast], [linked()], AFTER)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["research_selection"], "home")
        self.assertEqual(row["research_home_win_probability"], 0.62)
        self.assertEqual(row["research_away_win_probability"], 0.38)
        self.assertEqual(row["research_selection_win_probability"], 0.62)
        self.assertEqual(row["published_result_status"],
                         "linked_to_espn_published_final_research_only")
        self.assertIs(row["directional_research_pick_correct_vs_published_final"], True)
        self.assertEqual(r["directional_nba_research_selections"], 1)
        self.assertEqual(r["certified_champion_001_predictions"], 0)
        self.assertEqual(r["certified_challenger_001_predictions"], 0)
        self.assertEqual(r["certified_positive_ev_selections"], 0)
        self.assertFalse(row["counts_toward_champion_001_certified_shadow_target"])
        self.assertFalse(row["trained_challenger_001_model"])
        self.assertFalse(row["bet_ready"])
        self.assertEqual(row["research_ledger_receipt_sha256_self_attested"],sha({
            k:v for k,v in row.items()
            if k not in ("research_ledger_receipt_sha256_self_attested",
                         "published_result_status","espn_published_winner_research_only",
                         "directional_research_pick_correct_vs_published_final")
        }))

    def test_neutral_event_produces_no_directional_selection(self):
        snap = fixture()
        snap["away_team_form"]["win_rate"] = 0.8
        forecast = build_forecasts([snap], NOW)[0][0]
        rows, r = build_ledger([snap], [forecast], [linked()], AFTER)
        self.assertIsNone(rows[0]["research_selection"])
        self.assertIsNone(rows[0]["research_selection_win_probability"])
        self.assertIsNone(rows[0]["directional_research_pick_correct_vs_published_final"])
        self.assertEqual(r["neutral_no_selection_events"],1)
        self.assertEqual(r["directional_nba_research_selections"],0)

    def test_away_direction_is_not_mislabeled_home(self):
        snap = fixture()
        snap["home_team_form"]["win_rate"] = 0.2
        forecast = build_forecasts([snap], NOW)[0][0]
        rows,_ = build_ledger([snap],[forecast],[linked()],AFTER)
        self.assertEqual(rows[0]["research_selection"],"away")
        self.assertAlmostEqual(rows[0]["research_selection_win_probability"],0.56)
        self.assertIs(rows[0]["directional_research_pick_correct_vs_published_final"],False)

    def test_tampered_probability_cannot_be_reproduced_from_source(self):
        snap,forecast = self.source()
        forecast["baseline_home_win_probability"] = 0.75
        rows,r = build_ledger([snap],[forecast],[],AFTER)
        self.assertEqual(rows,[])
        self.assertEqual(r["quarantine_reasons"][
            "baseline_probability_not_reproducible_from_snapshot"],1)

    def test_duplicate_repeated_capture_and_forecast_counted_once(self):
        snap,f = self.source()
        later=deepcopy(f)
        later["forecast_created_at_utc"]="2026-10-29T22:00:00Z"
        rows,r=build_ledger([snap,deepcopy(snap)],[later,f,deepcopy(f)],[linked()],AFTER)
        self.assertEqual(r["research_unique_events_with_reproduced_original_formula"],1)
        self.assertEqual(rows[0]["forecast_created_at_utc"],NOW.isoformat())

    def test_event_identity_revision_quarantined_even_if_earliest_was_valid(self):
        snap,f=self.source()
        alternate=deepcopy(snap)
        alternate["away_team"]="Boston Celtics"
        alternate["snapshot_completed_at_utc"]="2026-10-29T21:46:00Z"
        other=build_forecasts([alternate],datetime(
            2026,10,29,21,51,tzinfo=timezone.utc))[0][0]
        rows,r=build_ledger([snap,alternate],[f,other],[],AFTER)
        self.assertEqual(rows,[])
        self.assertEqual(r["quarantine_reasons"][
            "revised_or_conflicting_nba_forecast_quarantined"],1)

    def test_conflicting_exact_snapshot_bytes_cannot_attach(self):
        snap,f=self.source()
        altered=deepcopy(snap)
        altered["away_team_form"]["win_rate"]=0.6
        rows,r=build_ledger([snap,altered],[f],[],AFTER)
        self.assertEqual(rows,[])
        self.assertEqual(r["quarantine_reasons"][
            "missing_or_conflicting_exact_capture_source"],1)

    def test_after_tipoff_or_future_forged_forecast_is_rejected(self):
        snap,f=self.source()
        f["forecast_created_at_utc"]="2026-10-30T00:01:00Z"
        rows,r=build_ledger([snap],[f],[],AFTER)
        self.assertEqual(rows,[])
        self.assertEqual(r["quarantine_reasons"][
            "invalid_or_after_start_baseline_forecast"],1)

    def test_duplicate_published_results_stay_ungraded(self):
        snap,f=self.source()
        rows,r=build_ledger([snap],[f],[linked(),deepcopy(linked())],AFTER)
        self.assertEqual(r["directional_nba_research_selections"],1)
        self.assertEqual(rows[0]["published_result_status"],
                         "duplicate_result_records_quarantined")
        self.assertIsNone(rows[0]["directional_research_pick_correct_vs_published_final"])

    def test_published_outcome_not_independently_adjudicated(self):
        snap,f=self.source()
        official_claim=linked()
        official_claim["independent_league_outcome_verified"]=True
        rows,r=build_ledger([snap],[f],[official_claim],AFTER)
        self.assertEqual(rows[0]["published_result_status"],
                         "unverified_or_mismatched_result_quarantined")
        self.assertEqual(r["certified_positive_ev_selections"],0)

    def test_missing_original_capture_is_not_rebuilt_from_forecast(self):
        _,f=self.source()
        rows,r=build_ledger([], [f], [], AFTER)
        self.assertEqual(rows,[])
        self.assertEqual(r["quarantine_reasons"][
            "missing_or_conflicting_exact_capture_source"],1)

    def test_no_outcome_does_not_trigger_a_fake_prediction_result(self):
        snap,f=self.source()
        rows,r=build_ledger([snap],[f],[],AFTER)
        self.assertEqual(rows[0]["published_result_status"],
                         "awaiting_published_result")
        self.assertIsNone(rows[0]["espn_published_winner_research_only"])
        self.assertEqual(r["linked_to_published_espn_finals_descriptive_only"],0)

    def test_future_result_publication_cannot_be_used(self):
        snap,f=self.source()
        result=linked()
        result["published_outcome"]["published_retrieved_at_utc"]="2026-11-09T00:00:00Z"
        rows,r=build_ledger([snap],[f],[result],AFTER)
        self.assertEqual(rows[0]["published_result_status"],
                         "invalid_published_outcome_timing")
        self.assertEqual(r["certified_challenger_001_predictions"],0)


if __name__ == "__main__":
    unittest.main()
