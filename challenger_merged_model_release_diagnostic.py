"""#104-106: composite NBA operations and model release decision, read-only.

All input reports must be derived from genuine upstream pipeline steps.
Separate exploratory research selections, provider result agreements, training
evidence, actual model fitting and bookmaker checkout confirmation. A working
API and a good research hit rate cannot promote Challenger or Champion.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from challenger_nba_probability import BLOCKED


def clean_zero(report, keys):
    if not isinstance(report,dict):
        raise ValueError("missing_pipeline_report")
    for key in keys:
        if report.get(key) != 0:
            raise ValueError("upstream_still_not_proven_or_promoted_" + key)
    if report.get("champion_001_modified") is not False:
        raise ValueError("frozen_champion_integrity_not_confirmed")


def assess(intake, official, licensed, qualified, ledger, worklist, native, score_integrity=None):
    if not all(isinstance(r,dict) for r in (
            intake,official,licensed,qualified,ledger,worklist,native)):
        raise ValueError("seven_required_provenance_reports_missing")
    clean_zero(intake,(
        "independently_verified_training_records",
        "certified_champion_001_predictions",
        "certified_challenger_001_predictions",
        "automated_bets_placed"))
    clean_zero(official,(
        "qualified_training_games","qualified_holdout_games",
        "certified_champion_001_predictions",
        "certified_challenger_001_predictions","automated_bets_placed"))
    clean_zero(licensed,(
        "native_training_qualified_games","qualified_holdout_games",
        "official_league_outcomes_authenticated",
        "direct_draftkings_checkout_quotes_verified",
        "certified_champion_001_predictions",
        "certified_challenger_001_predictions",
        "certified_positive_ev_selections","automated_bets_placed"))
    clean_zero(qualified,(
        "qualified_training_games","qualified_holdout_games",
        "independently_authenticated_pregame_features",
        "independently_adjudicated_game_outcomes"))
    clean_zero(ledger,(
        "native_challenger_001_predictions",
        "certified_champion_001_predictions",
        "certified_challenger_001_predictions",
        "certified_positive_ev_selections",
        "verified_direct_draftkings_checkout_prices",
        "automated_bets_placed"))
    clean_zero(worklist,(
        "independently_qualified_training_games",
        "independently_qualified_holdout_games",
        "certified_champion_001_predictions",
        "certified_challenger_001_predictions",
        "certified_positive_ev_selections",
        "direct_draftkings_checkout_quotes_verified",
        "automated_bets_placed"))
    clean_zero(native,(
        "independently_certified_training_records",
        "certified_champion_001_predictions",
        "certified_challenger_001_predictions",
        "bet_ready_selections","automated_bets_placed"))

    candidate_count=intake.get("nba_review_candidates")
    if (type(candidate_count) is not int or candidate_count<0
            or any(r.get(k)!=candidate_count for r,k in [
                (official,"review_candidates"),
                (licensed,"review_candidates"),
                (qualified,"candidate_games"),
                (worklist,"nba_research_candidates_reconciled")])):
        raise ValueError("inconsistent_nba_candidate_count_or_incomplete_join")
    if (intake.get("result") !=
            "blocked_independent_source_review_and_chronological_validation"
            or intake.get("qualified_for_challenger_backtest") != 0
            or qualified.get("model_training_authorized") is not False
            or qualified.get("calibration_ready") is not False
            or worklist.get("no_model_training_authorized") is not True
            or worklist.get("research_baseline_is_not_trained_challenger_001") is not True
            or native.get("result") != BLOCKED
            or native.get("rows_review_attested_and_settled") != 0):
        raise ValueError("unexpected_training_or_native_model_gate_state")
    if (licensed.get("third_party_published_final_score_agreements_research_only") !=
            worklist.get("sportsdataio_third_party_agreements_not_official")
            or official.get("combined_second_source_score_agreements_research_only") !=
            worklist.get("nba_two_source_published_final_score_agreements_research_only")):
        raise ValueError("publisher_research_scores_cannot_be_reconciled")
    n_research=ledger.get("research_unique_events_with_reproduced_original_formula")
    n_selections=ledger.get("directional_nba_research_selections")
    if (type(n_research) is not int or n_research<0
            or type(n_selections) is not int
            or not 0 <= n_selections <= n_research
            or n_research > candidate_count
            or ledger.get("neutral_no_selection_events") !=
                n_research-n_selections):
        raise ValueError("research_shadow_count_missing_or_promoted")
    third=licensed["third_party_published_final_score_agreements_research_only"]
    official_count=official["combined_second_source_score_agreements_research_only"]
    if not (0 <= third <= candidate_count and 0 <= official_count<=candidate_count):
        raise ValueError("invalid_original_score_corroboration_counts")
    suspicious_dates=0
    if score_integrity is not None:
        if not isinstance(score_integrity,dict):
            raise ValueError("missing_licensed_provider_integrity_report")
        clean_zero(score_integrity,(
            "licensed_provider_scores_accepted_for_training",
            "licensed_provider_player_stats_accepted_for_training",
            "licensed_provider_odds_accepted_for_positive_ev",
            "untrusted_provider_scores_auto_corrected",
            "qualified_challenger_training_games",
            "certified_champion_001_predictions",
            "certified_challenger_001_predictions",
            "certified_positive_ev_bets",
            "automated_bets_placed",
        ))
        if (score_integrity.get("records_seen")!=candidate_count
                or score_integrity.get("source_successful_dates") !=
                    licensed.get("source_days_succeeded")
                or score_integrity.get("by_status")!=licensed.get("by_status")
                or score_integrity.get(
                    "sportsdataio_api_key_tier_independently_verified") is not False):
            raise ValueError("untrusted_provider_integrity_not_reconciled")
        suspicious_dates=score_integrity.get("suspected_scrambled_score_pattern_days")
        if type(suspicious_dates) is not int or suspicious_dates<0:
            raise ValueError("suspected_score_pattern_count_invalid")
    train=qualified["qualified_training_games"]
    holdout=qualified["qualified_holdout_games"]
    thresholds={"train":200,"later_holdout":50}
    blockers=[
        {"priority":1,"code":"ORIGINAL_PREGAME_PUBLICATION_CUSTODY",
         "status":"missing_independent_authentication",
         "qualified_records":0,"next_action":
         "Independently authenticate contemporaneous original pregame feature bytes, timestamps and chain of custody"},
        {"priority":2,"code":"OFFICIAL_NBA_GAME_RESULT_AND_SETTLEMENT",
         "status":"not_independently_adjudicated",
         "research_agreements_nba_operated":official_count,
         "research_agreements_sportsdataio_third_party":third,
         "next_action":
         "Resolve NBA source access, retain original league-operated outcome records and separately validate market settlement"},
        {"priority":3,"code":"NBA_CHRONOLOGICAL_TRAIN_AND_HOLDOUT",
         "status":"blocked",
         "training_games_qualified":train,
         "holdout_games_qualified":holdout,
         "train_deficit":max(0,200-train),
         "holdout_deficit":max(0,50-holdout),
         "next_action":
         "Collect sufficient disjoint independently verified as-of examples; never train from published-score research alone"},
        {"priority":4,"code":"NATIVE_CHALLENGER_PROBABILITY_AND_CALIBRATION",
         "status":"blocked_no_qualified_training_data",
         "next_action":
         "Only after evidence validation fit distinct NBA moneyline model, score untouched later holdout and run calibration"},
        {"priority":5,"code":"EXACT_DRAFTKINGS_EXECUTABLE_PRICE_AND_EV",
         "status":"not_verified",
         "next_action":
         "Verify exact event, market, line, side, time and executable sportsbook quote before calculating a real edge"},
        {"priority":6,"code":"AUTHENTICATE_FROZEN_CHAMPION_ORIGINAL_AND_RELEASE",
         "status":"frozen_original_not_authenticated",
         "next_action":
         "Recover immutable Champion executable and independent reference-output checks; preserve original unmodified"},
    ]
    if score_integrity is not None:
        for block in blockers:
            block["priority"] += 1
        blockers.insert(0,{
            "priority":1,
            "code":"VERIFY_SPORTSDATAIO_REAL_UNSCRAMBLED_DATA_ENTITLEMENT",
            "status":"provider_score_field_integrity_not_authenticated",
            "suspected_transformed_score_pattern_days":suspicious_dates,
            "next_action":("Check account entitlement for real, non-scrambled "
                           "game scores, player stats and odds; compare exact "
                           "final scores with league-operated independent source "
                           "before any data training. Do not rescale altered scores."),
        })
    return {
        "stage":"challenger_106_combined_operational_training_release_diagnostic",
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "nba_structurally_valid_research_candidates":candidate_count,
        "nba_research_captures_with_exact_reproducible_baseline":n_research,
        "nba_directional_untrained_heuristic_research_picks":n_selections,
        "nba_neutral_untrained_heuristic_research_events":n_research-n_selections,
        "nba_official_published_score_research_agreements":official_count,
        "nba_third_party_published_score_research_agreements":third,
        "nba_third_party_source_days_succeeded":licensed.get("source_days_succeeded"),
        "nba_third_party_source_failures_by_day":licensed.get("source_failures_by_day"),
        "suspected_provider_scrambled_score_pattern_days":suspicious_dates,
        "sportsdataio_subscription_tier_independently_confirmed":False,
        "sportsdataio_score_fields_authenticated_for_training":False,
        "nba_research_candidate_shortfall_to_250":max(0,250-candidate_count),
        "nba_independently_qualified_training_games":train,
        "nba_independently_qualified_later_holdout_games":holdout,
        "native_trained_probability_models_created":0,
        "out_of_sample_native_model_accuracy_verified":False,
        "independently_verified_draftkings_checkout_prices":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_selections":0,
        "automatic_wagers_placed":0,
        "champion_001_modified":False,
        "release_decision":"HOLD_NO_CERTIFIED_MODEL_NO_WAGERS",
        "prioritized_remaining_external_evidence_and_release_actions":blockers,
        "warning":("Successful data collection and real untrained research "
                   "picks do not qualify a native predictive model or sportsbook "
                   "edge. SportsDataIO agreement is third-party corroboration only. "
                   "No source flag or self-issued timestamp can substitute for "
                   "independent original-source audit."),
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("intake","official","licensed","qualified","ledger",
                 "worklist","native"):
        p.add_argument("--"+name,required=True)
    p.add_argument("--score-integrity")
    p.add_argument("--output",required=True)
    args=p.parse_args(argv)
    def read(filename):
        f=Path(filename)
        if not f.is_file():
            raise FileNotFoundError(f)
        return json.loads(f.read_text(encoding="utf8"))
    reports=[read(getattr(args,x)) for x in (
        "intake","official","licensed","qualified","ledger","worklist","native")]
    report=assess(*reports,
        score_integrity=read(args.score_integrity) if args.score_integrity else None)
    out=Path(args.output)
    if out.exists():
        raise FileExistsError("refuse_unsafe_release_report_overwrite")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps({
        "nba_research_candidates":report["nba_structurally_valid_research_candidates"],
        "nba_research_directional_picks":
            report["nba_directional_untrained_heuristic_research_picks"],
        "qualified_training_games":0,
        "certified_model_predictions":0,
        "release":report["release_decision"]},sort_keys=True))


if __name__=="__main__":
    main()
