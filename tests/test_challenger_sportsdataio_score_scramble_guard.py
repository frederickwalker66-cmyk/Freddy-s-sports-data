"""Synthetic-only assertions for score scrambling pattern and no correction."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_sportsdataio_score_scramble_guard import report,main

DATE="2026-10-31"
HASH="a"*64


def evidence(n=5, factor=1.66, day=DATE, flip=False):
    rows=[]
    for i in range(n):
        h,a=90+i,112+i
        p_h=round(h*factor)
        p_a=round(a*factor)
        if flip and i==0:
            p_h,p_a=p_a,p_h
        rows.append({
            "record_type":"sportsdataio_nba_final_result_comparison_research_only",
            "source_type":"licensed_third_party_nba_result_not_league_operated",
            "espn_research_event_id":str(401000000+i),
            "espn_published_score":{"home":h,"away":a},
            "sportsdataio_published_score":{"home":p_h,"away":p_a},
            "source_date_et":day,
            "source_original_bytes_sha256_self_attested":HASH,
            "crosscheck_status":"sportsdataio_disagrees_with_espn_score_quarantined",
            "qualified_for_challenger_backtest":False,
            "independently_verified_original_pregame_features":False,
            "independently_adjudicated_market_outcome":False,
            "bookmaker_moneyline_settlement_verified":False,
            "certified_prediction":False,
            "bet_ready":False,
            "champion_001_modified":False,
        })
    return rows


def provider(rows):
    return {
        "review_candidates":len(rows),
        "native_training_qualified_games":0,
        "certified_challenger_001_predictions":0,
        "champion_001_modified":False,
        "source_days_succeeded":1,
        "source_original_bytes_sha256_by_day":{DATE:HASH},
        "third_party_published_final_score_agreements_research_only":0,
    }


class SuspectedScrambledScoresTests(unittest.TestCase):
    def test_consistent_daily_ratio_quarantined_and_never_repaired(self):
        rows=evidence(7,1.66)
        r=report(rows,provider(rows))
        self.assertEqual(r["suspected_scrambled_score_pattern_days"],1)
        self.assertEqual(r["dates_with_strong_suspected_transformed_score_pattern"],[DATE])
        self.assertAlmostEqual(r["by_date"][DATE]["provider_to_espn_point_ratio_median_research_only"],1.66,delta=.02)
        self.assertEqual(r["by_date"][DATE]["same_winner_in_conflicted_scores"],7)
        self.assertEqual(r["untrusted_provider_scores_auto_corrected"],0)
        self.assertEqual(r["licensed_provider_scores_accepted_for_training"],0)
        self.assertEqual(r["licensed_provider_odds_accepted_for_positive_ev"],0)
        self.assertFalse(r["sportsdataio_api_key_tier_independently_verified"])
        self.assertFalse(r["champion_001_modified"])

    def test_small_sample_never_claims_systematic_scramble(self):
        rows=evidence(3,1.66)
        self.assertEqual(report(rows,provider(rows))["suspected_scrambled_score_pattern_days"],0)

    def test_inconsistent_ratio_not_a_daily_scaling_signal(self):
        rows=evidence(6,1.66)
        rows[-1]["sportsdataio_published_score"]["home"]=50
        self.assertEqual(report(rows,provider(rows))["suspected_scrambled_score_pattern_days"],0)

    def test_winner_disagreement_is_not_accepted_as_suspected_clean_scramble(self):
        rows=evidence(5,1.3,flip=True)
        self.assertEqual(report(rows,provider(rows))["suspected_scrambled_score_pattern_days"],0)

    def test_self_attested_source_hash_cannot_differ_from_original_report(self):
        rows=evidence()
        rows[0]["source_original_bytes_sha256_self_attested"]="b"*64
        with self.assertRaisesRegex(ValueError,"fingerprint_mismatch"):
            report(rows,provider(rows))

    def test_attempted_training_promotion_rejected(self):
        rows=evidence()
        rows[0]["qualified_for_challenger_backtest"]=True
        with self.assertRaisesRegex(ValueError,"unsafe_sportsdataio_score_archive"):
            report(rows,provider(rows))

    def test_duplicate_original_event_id_rejected(self):
        rows=evidence()
        rows[1]["espn_research_event_id"]=rows[0]["espn_research_event_id"]
        with self.assertRaisesRegex(ValueError,"duplicate_original_espn"):
            report(rows,provider(rows))

    def test_lacking_provider_response_is_not_clean_source(self):
        rows=evidence(0)
        r=report(rows,provider(rows))
        self.assertEqual(r["suspected_scrambled_score_pattern_days"],0)
        self.assertEqual(r["licensed_provider_scores_accepted_for_training"],0)

    def test_licensing_claims_and_original_fingerprint_are_not_enough_to_certify(self):
        rows=evidence(5,0.71)
        r=report(rows,provider(rows))
        self.assertEqual(r["suspected_scrambled_score_pattern_days"],1)
        self.assertEqual(r["qualified_challenger_training_games"],0)
        self.assertEqual(r["certified_challenger_001_predictions"],0)

    def test_cli_emits_standalone_research_only_report(self):
        rows=evidence(6,1.66)
        with TemporaryDirectory() as td:
            root=Path(td)
            (root/"provider.json").write_text(json.dumps(provider(rows)))
            (root/"review.jsonl").write_text("".join(
                json.dumps(x)+"\n" for x in rows))
            main(["--review",str(root/"review.jsonl"),
                  "--provider-report",str(root/"provider.json"),
                  "--output",str(root/"safe_report.json")])
            r=json.loads((root/"safe_report.json").read_text())
            self.assertEqual(r["suspected_scrambled_score_pattern_days"],1)
            self.assertFalse((root/"historical_results.jsonl").exists())
            with self.assertRaises(FileExistsError):
                main(["--review",str(root/"review.jsonl"),
                      "--provider-report",str(root/"provider.json"),
                      "--output",str(root/"safe_report.json")])


if __name__=="__main__":
    unittest.main()
