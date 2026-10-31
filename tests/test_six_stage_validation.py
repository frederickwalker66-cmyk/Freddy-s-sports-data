"""Six-stage safety-gate fixture tests. Synthetic only; no odds APIs or wagers."""
import json
from pathlib import Path
import tempfile
import unittest

from champion_001_authentication import inspect
from challenger_nba_history_qualification import audit
from challenger_nba_player_boxes import parse_summary
from challenger_oos_calibration import score, implied
from challenger_artifact_manifest import build, verify


def nba_box():
    labels=["MIN","PTS","REB","AST","STL","BLK"]
    def athlete(pid, stats, dnp=False):
        return {"athlete":{"id":pid,"displayName":"Player "+pid},
                "stats":stats,"didNotPlay":dnp,"starter":not dnp}
    return {"header":{"id":"1234567","competitions":[{
         "id":"1234567","status":{"type":{"completed":True}},
         "competitors":[{"team":{"id":"12"}},{"team":{"id":"34"}}]}]},
      "boxscore":{"players":[
          {"team":{"id":"12"},"statistics":[{"labels":labels,
             "athletes":[athlete("101",["32:15","18","9","7","1","0"]),
                         athlete("102",["0","0","0","0","0","0"],True)]}]},
          {"team":{"id":"34"},"statistics":[{"labels":labels,
             "athletes":[athlete("301",["28","16","3","8","0","2"])]}]}
      ]}}


class SixStageTests(unittest.TestCase):
    def test_stage_one_exact_completed_provider_trigger(self):
        text=Path(".github/workflows/challenger-prospective-pregame.yml").read_text()
        self.assertIn("workflow_run:",text)
        self.assertIn("Collect SharpAPI DraftKings pregame odds",text)
        self.assertIn("github.event.workflow_run.conclusion == 'success'",text)
        self.assertIn("TRIGGERED_SHARPAPI_RUN_ID",text)
        from challenger_prospective_pregame import validated_odds
        from datetime import datetime,timezone
        now=datetime(2026,10,31,12,tzinfo=timezone.utc)
        bad={"source":"sharpapi_rest","sportsbook":"draftkings",
            "certified_prediction":False,"model_probability":None,
            "event_start_time":"2026-10-31T19:00:00Z",
            "timestamp":"2026-10-31T11:30:00Z","recorded_at":"2026-10-31T11:31:00Z",
            "odds_american":-110,"event_id":"1","selection":"home","market_type":"moneyline"}
        self.assertEqual(validated_odds(bad,now)[1],"archive_quote_stale_at_snapshot")

    def test_stage_two_self_manifest_not_proof(self):
        self.assertFalse(inspect()["original_executable_verified"])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"model.bin";p.write_bytes(b"research fixture")
            import hashlib
            q=Path(d)/"manifest.json"
            q.write_text(json.dumps({"model_sha256":hashlib.sha256(p.read_bytes()).hexdigest()}))
            r=inspect(p,q)
            self.assertTrue(r["sha256_matches_supplied_manifest"])
            self.assertFalse(r["original_executable_verified"])
            self.assertFalse(r["reproducible_reference_outputs_verified"])
            self.assertFalse(r["champion_001_modified"])

    def test_stage_three_published_score_matches_still_not_training(self):
        candidate={"record_type":"challenger_nba_history_candidate_review_only",
                   "event_id":"12345","outcome":1,"published_score_only":{"home":100,"away":90}}
        second={"espn_research_event_id":"12345",
                "crosscheck_status":"nba_second_source_final_score_agrees_research_only",
                "official_nba_score":{"home":100,"away":90},
                "training_row_qualified":False}
        rows,report=audit([candidate],[second])
        self.assertEqual(report["second_source_result_agreements"],1)
        self.assertEqual(report["qualified_training_games"],0)
        self.assertFalse(rows[0]["independent_qualification"])
        self.assertEqual(len(rows[0]["missing"]),4)

    def test_stage_four_valid_minutes_dnp_and_source_only(self):
        rows=parse_summary(nba_box(),"1234567","2026-10-31T12:00:00Z")
        self.assertEqual(len(rows),3)
        self.assertAlmostEqual(rows[0]["minutes"],32.25)
        self.assertEqual(rows[0]["points"],18)
        self.assertTrue(rows[1]["did_not_play"])
        self.assertFalse(any(x["qualified_for_player_prop_training"] for x in rows))
        self.assertFalse(any(x["qualified_for_game_winner_training"] for x in rows))
        data=nba_box();data["header"]["id"]="notgame"
        with self.assertRaises(ValueError):
            parse_summary(data,"1234567","2026-10-31T12:00:00Z")
        data=nba_box();data["boxscore"]["players"][0]["statistics"][0]["athletes"][0]["stats"][0]="-"
        with self.assertRaises(ValueError):
            parse_summary(data,"1234567","2026-10-31T12:00:00Z")

    def test_stage_four_names_and_true_dnp_missing_stat_array(self):
        data=nba_box()
        first=data["boxscore"]["players"][0]["statistics"][0]
        first["names"]=first.pop("labels")
        first["athletes"][1]["stats"]=[]
        rows=parse_summary(data,"1234567","2026-10-31T12:00:00Z")
        self.assertEqual(len(rows),3)
        self.assertTrue(rows[1]["did_not_play"])
        self.assertIsNone(rows[1]["minutes"])
        self.assertIsNone(rows[1]["points"])
        self.assertFalse(rows[1]["qualified_for_player_prop_training"])

    def test_stage_five_empty_and_unverified_never_fake_metrics(self):
        self.assertEqual(score([])["certified_groups"],0)
        r=score([{"league":"nba","market_type":"moneyline",
                  "model_probability":0.6,"settlement":"WIN"}])
        self.assertEqual(r["qualified_groups_with_50plus"],0)
        self.assertEqual(r["exclusions"]["unverified_or_in_sample"],1)
        self.assertAlmostEqual(implied(-110),110/210)

    def test_stage_five_qualified_synthetic_holdout_not_bet_ready_without_receipts(self):
        rows=[{"league":"nba","market_type":"moneyline","model_version":"fixture-only",
               "settlement":"WIN" if i%2 else "LOSS",
               "model_probability":.6,"independent_outcome_verified":True,
               "historical_pregame_features_verified":True,
               "model_output_before_event_verified":True,
               "chronological_holdout":True,"model_training_excludes_holdout":True,
               "champion_001_modified":False,
               "event_start_utc":f"2026-10-{1+i//3:02d}T12:00:00Z",
               "event_id":str(i)} for i in range(50)]
        r=score(rows)
        a=r["league_market_reports"][0]
        self.assertEqual(a["holdout_samples"],50)
        self.assertIsNotNone(a["brier"])
        self.assertIsNotNone(a["log_loss"])
        self.assertIsNotNone(a["expected_calibration_error"])
        self.assertIsNone(a["closing_line_value_avg_prob_points"])
        self.assertIsNone(a["actual_settled_roi"])
        self.assertFalse(a["certified"])

    def test_stage_six_checksum_detects_mutation_and_not_durable(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"test.sqlite";p.write_bytes(b"example")
            m=build([str(p)])
            self.assertTrue(verify([str(p)],m))
            self.assertFalse(m["durable_storage_verified"])
            self.assertFalse(m["externally_signed"])
            p.write_bytes(b"changed")
            self.assertFalse(verify([str(p)],m))


if __name__=="__main__":
    unittest.main()
