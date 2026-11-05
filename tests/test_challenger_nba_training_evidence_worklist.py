"""Offline NBA independent-evidence worklist, never model training."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from challenger_nba_history_qualification import audit as qualify
from challenger_nba_official_final_crosscheck import (
    review_candidates, RESEARCH_STATUS,
)
from challenger_nba_training_evidence_worklist import audit, main
from test_challenger_nba_official_final_crosscheck import case, official, NOW


def fixed_shadow(c, side="home"):
    return {
        "record_type":"nba_moneyline_prospective_untrained_shadow_research_only",
        "league":"nba","espn_event_id":c["event_id"],
        "home_team":c["home_team"],"away_team":c["away_team"],
        "event_start_utc":c["start_utc"],
        "snapshot_completed_at_utc":c["snapshot_utc"],
        "forecast_created_at_utc":"2026-10-30T22:00:00+00:00",
        "research_selection":side,
        "trained_challenger_001_model":False,
        "champion_001_prediction":False,
        "counts_toward_champion_001_certified_shadow_target":False,
        "certified_prediction":False,
        "bet_ready":False,"shadow_stake_usd":0,
        "champion_001_modified":False,
        "sportsbook_price":None,
        "independently_authenticated_source_publication":False,
    }


def inputs(crosscheck=None):
    c=case()
    comparisons,_=review_candidates([c],crosscheck,NOW)
    review,_=qualify([c],comparisons)
    return [c],comparisons,review


class TrainingEvidenceWorklistTests(unittest.TestCase):
    def test_unavailable_official_source_and_no_shadow_stay_blocked(self):
        c,p,q=inputs()
        rows,r=audit(c,p,q,[])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["nba_score_second_source_status"],
                         "nba_official_source_unavailable")
        self.assertEqual(len(rows[0]["missing_qualification_evidence"]),5)
        self.assertEqual(r["nba_missing_second_source_original_final"],1)
        self.assertEqual(r["structurally_missing_research_candidates_to_250"],249)
        self.assertEqual(r["independently_qualified_training_games"],0)
        self.assertEqual(r["certified_champion_001_predictions"],0)
        self.assertFalse(rows[0]["training_eligible"])

    def test_genuine_two_publisher_agreement_is_not_training_proof(self):
        c,p,q=inputs(official())
        rows,r=audit(c,p,q,[fixed_shadow(c[0])])
        self.assertEqual(rows[0]["nba_score_second_source_status"],RESEARCH_STATUS)
        self.assertEqual(rows[0]["research_side_if_exact_capture"],"home")
        self.assertEqual(r["nba_two_source_published_final_score_agreements_research_only"],1)
        self.assertEqual(r["nba_exact_original_pregame_heuristic_forecast_reconciled"],1)
        self.assertEqual(len(rows[0]["missing_qualification_evidence"]),4)
        self.assertEqual(r["independently_qualified_shortfall_to_250"],250)
        self.assertTrue(r["no_model_training_authorized"])

    def test_out_of_sync_result_source_never_used_as_training(self):
        c,p,q=inputs(official())
        p[0]["official_nba_score"]={"home":111,"away":97}
        with self.assertRaisesRegex(ValueError,"unsafe_or_unreconciled"):
            audit(c,p,q,[])

    def test_false_independent_claim_cannot_be_promoted(self):
        c,p,q=inputs(official())
        q[0]["independent_qualification"]=True
        with self.assertRaisesRegex(ValueError,"unsafe_or_unreconciled"):
            audit(c,p,q,[])

    def test_wrong_source_status_claim_blocked(self):
        c,p,q=inputs()
        q[0]["evidence"]["published_score_second_source_agreement"]=True
        q[0]["missing"]=list(q[0]["missing"])[1:]
        with self.assertRaisesRegex(ValueError,"unsafe_or_unreconciled"):
            audit(c,p,q,[])

    def test_missing_official_crosscheck_never_silently_dropped(self):
        c,p,q=inputs()
        with self.assertRaisesRegex(ValueError,"identity_missing"):
            audit(c,[],q,[])

    def test_duplicated_shadow_event_not_double_counted(self):
        c,p,q=inputs()
        row=fixed_shadow(c[0])
        with self.assertRaisesRegex(ValueError,"duplicate_research_shadow_ledger"):
            audit(c,p,q,[row,deepcopy(row)])

    def test_fake_trained_challenger_shadow_is_rejected(self):
        c,p,q=inputs()
        row=fixed_shadow(c[0])
        row["trained_challenger_001_model"]=True
        with self.assertRaisesRegex(ValueError,"shadow_claim_cannot"):
            audit(c,p,q,[row])

    def test_after_tipoff_shadow_rejected(self):
        c,p,q=inputs()
        row=fixed_shadow(c[0])
        row["forecast_created_at_utc"]="2026-10-31T00:01:00Z"
        with self.assertRaisesRegex(ValueError,"shadow_claim_cannot"):
            audit(c,p,q,[row])

    def test_different_original_capture_never_declares_one_to_one_join(self):
        c,p,q=inputs()
        row=fixed_shadow(c[0])
        row["snapshot_completed_at_utc"]="2026-10-30T21:05:00Z"
        rows,r=audit(c,p,q,[row])
        self.assertEqual(rows[0]["research_shadow_status"],
                         "different_valid_pregame_capture_no_one_to_one_join")
        self.assertIsNone(rows[0]["research_side_if_exact_capture"])
        self.assertEqual(r["nba_exact_original_pregame_heuristic_forecast_reconciled"],0)

    def test_orphan_shadow_fails_closed(self):
        c,p,q=inputs()
        row=fixed_shadow(c[0])
        row["espn_event_id"]="88888888"
        with self.assertRaisesRegex(ValueError,"orphan_shadow"):
            audit(c,p,q,[row])

    def test_cli_creates_a_review_queue_not_a_trained_model(self):
        c,p,q=inputs()
        with TemporaryDirectory() as folder:
            root=Path(folder)
            for name,rows in (("c.jsonl",c),("p.jsonl",p),("q.jsonl",q),
                              ("ledger.jsonl",[fixed_shadow(c[0])])):
                (root/name).write_text("".join(json.dumps(x)+"\n" for x in rows))
            main(["--candidates",str(root/"c.jsonl"),
                  "--comparisons",str(root/"p.jsonl"),
                  "--qualification",str(root/"q.jsonl"),
                  "--shadow-ledger",str(root/"ledger.jsonl"),
                  "--output-dir",str(root)])
            report=json.loads((root/"nba_independent_evidence_training_worklist_report.json").read_text())
            self.assertEqual(report["independently_qualified_training_games"],0)
            self.assertFalse((root/"research_model.json").exists())
            self.assertFalse((root/"historical_results.jsonl").exists())


if __name__=="__main__":
    unittest.main()
