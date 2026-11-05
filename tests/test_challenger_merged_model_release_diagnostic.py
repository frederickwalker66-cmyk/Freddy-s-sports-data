"""Synthetic tests of consolidated research and no-release decision."""
import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_merged_model_release_diagnostic import assess, main
from challenger_nba_probability import BLOCKED


def reports():
    intake={
        "nba_review_candidates":53,
        "result":"blocked_independent_source_review_and_chronological_validation",
        "qualified_for_challenger_backtest":0,
        "independently_verified_training_records":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "automated_bets_placed":0,"champion_001_modified":False,
    }
    official={
        "review_candidates":53,
        "combined_second_source_score_agreements_research_only":0,
        "qualified_training_games":0,"qualified_holdout_games":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "automated_bets_placed":0,"champion_001_modified":False,
    }
    licensed={
        "review_candidates":53,"source_days_succeeded":2,
        "source_failures_by_day":{"2026-11-01":"HTTP_429"},
        "third_party_published_final_score_agreements_research_only":4,
        "native_training_qualified_games":0,"qualified_holdout_games":0,
        "official_league_outcomes_authenticated":0,
        "direct_draftkings_checkout_quotes_verified":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_selections":0,
        "automated_bets_placed":0,"champion_001_modified":False,
    }
    qualified={
        "candidate_games":53,
        "model_training_authorized":False,"calibration_ready":False,
        "qualified_training_games":0,"qualified_holdout_games":0,
        "independently_authenticated_pregame_features":0,
        "independently_adjudicated_game_outcomes":0,
        "champion_001_modified":False,
    }
    ledger={
        "research_unique_events_with_reproduced_original_formula":53,
        "directional_nba_research_selections":47,
        "neutral_no_selection_events":6,
        "native_challenger_001_predictions":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_selections":0,
        "verified_direct_draftkings_checkout_prices":0,
        "automated_bets_placed":0,"champion_001_modified":False,
    }
    worklist={
        "nba_research_candidates_reconciled":53,
        "nba_two_source_published_final_score_agreements_research_only":0,
        "sportsdataio_third_party_agreements_not_official":4,
        "independently_qualified_training_games":0,
        "independently_qualified_holdout_games":0,
        "no_model_training_authorized":True,
        "research_baseline_is_not_trained_challenger_001":True,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_selections":0,
        "direct_draftkings_checkout_quotes_verified":0,
        "automated_bets_placed":0,"champion_001_modified":False,
    }
    native={
        "result":BLOCKED,"rows_review_attested_and_settled":0,
        "independently_certified_training_records":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "bet_ready_selections":0,
        "automated_bets_placed":0,"champion_001_modified":False,
    }
    return intake,official,licensed,qualified,ledger,worklist,native


class CombinedModelReleaseGateTests(unittest.TestCase):
    def test_all_sources_integrated_without_false_native_model(self):
        out=assess(*reports())
        self.assertEqual(out["nba_structurally_valid_research_candidates"],53)
        self.assertEqual(out["nba_directional_untrained_heuristic_research_picks"],47)
        self.assertEqual(out["nba_third_party_published_score_research_agreements"],4)
        self.assertEqual(out["nba_official_published_score_research_agreements"],0)
        self.assertEqual(out["nba_research_candidate_shortfall_to_250"],197)
        self.assertEqual(out["native_trained_probability_models_created"],0)
        self.assertFalse(out["out_of_sample_native_model_accuracy_verified"])
        self.assertEqual(out["release_decision"],"HOLD_NO_CERTIFIED_MODEL_NO_WAGERS")
        self.assertFalse(out["champion_001_modified"])
        self.assertEqual(out["certified_challenger_001_predictions"],0)
        self.assertEqual(len(out["prioritized_remaining_external_evidence_and_release_actions"]),6)

    def test_provider_agreement_cannot_be_counted_as_nba_official_agreement(self):
        things=list(reports())
        things[5]["nba_two_source_published_final_score_agreements_research_only"]=4
        with self.assertRaisesRegex(ValueError,"publisher_research_scores"):
            assess(*things)

    def test_ledger_forecasts_cannot_exceed_original_game_candidates(self):
        things=list(reports())
        things[4]["research_unique_events_with_reproduced_original_formula"]=54
        things[4]["neutral_no_selection_events"]=7
        with self.assertRaisesRegex(ValueError,"research_shadow_count"):
            assess(*things)

    def test_unqualified_positive_training_flag_rejected(self):
        things=list(reports())
        things[3]["qualified_training_games"]=1
        with self.assertRaisesRegex(ValueError,"promoted_qualified_training_games"):
            assess(*things)

    def test_trained_model_claim_without_evidence_rejected(self):
        things=list(reports())
        things[6]["result"]="fitted_unverified_research_model"
        with self.assertRaisesRegex(ValueError,"native_model_gate"):
            assess(*things)

    def test_unverified_bookmaker_price_claim_is_rejected(self):
        things=list(reports())
        things[5]["direct_draftkings_checkout_quotes_verified"]=1
        with self.assertRaisesRegex(ValueError,"promoted_direct_draftkings"):
            assess(*things)

    def test_source_count_must_reconcile_exactly(self):
        things=list(reports())
        things[2]["review_candidates"]=52
        with self.assertRaisesRegex(ValueError,"inconsistent_nba_candidate"):
            assess(*things)

    def test_champion_modified_claim_rejected(self):
        things=list(reports())
        things[0]["champion_001_modified"]=True
        with self.assertRaisesRegex(ValueError,"frozen_champion"):
            assess(*things)

    def test_no_certified_model_cannot_be_inferred_from_50_sample_heuristic(self):
        things=list(reports())
        things[4]["directional_nba_research_selections"]=53
        things[4]["neutral_no_selection_events"]=0
        out=assess(*things)
        self.assertEqual(out["certified_challenger_001_predictions"],0)

    def test_cli_writes_read_only_release_summary(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            params=[]
            for name,report in zip((
                    "intake","official","licensed","qualified","ledger",
                    "worklist","native"),reports()):
                file=root/(name+".json")
                file.write_text(json.dumps(report))
                params.extend(["--"+name,str(file)])
            params.extend(["--output",str(root/"release.json")])
            main(params)
            out=json.loads((root/"release.json").read_text())
            self.assertEqual(out["release_decision"],"HOLD_NO_CERTIFIED_MODEL_NO_WAGERS")
            with self.assertRaises(FileExistsError):
                main(params)


if __name__=="__main__":
    unittest.main()
