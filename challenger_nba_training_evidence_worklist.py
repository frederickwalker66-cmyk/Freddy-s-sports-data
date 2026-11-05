"""#100: NBA per-event outside-evidence qualification worklist, NOT training.

Joins strictly unqualified NBA capture candidates, first/alternate official
score checks, original-source qualification audit, and prior prospective $0
research selection ledger. Never turns reviews into historical_results.jsonl.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from challenger_backtest import timestamp
from challenger_nba_history_qualification import REQUIRED
from challenger_nba_official_final_crosscheck import RESEARCH_STATUS


def canonical(row):
    return json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(row):
    return hashlib.sha256(canonical(row).encode()).hexdigest()


def validated_map(rows, id_field, what):
    if not isinstance(rows, list):
        raise ValueError("expected_"+what+"_list")
    found = {}
    for row in rows:
        key=row.get(id_field) if isinstance(row,dict) else None
        if not isinstance(key,str) or not key.isdigit() or key in found:
            raise ValueError("invalid_or_duplicate_"+what+"_event")
        found[key] = row
    return found


def audit(candidates, comparisons, qualification, ledger):
    original = validated_map(candidates,"event_id","original_candidate")
    official = validated_map(comparisons,"espn_research_event_id","official_comparison")
    claims = validated_map(qualification,"event_id","qualification_audit")
    shadows = validated_map(ledger,"espn_event_id","research_shadow_ledger")
    if set(original) != set(official) or set(original) != set(claims):
        raise ValueError("qualification_candidate_or_official_source_identity_missing")
    if not set(shadows).issubset(original):
        raise ValueError("orphan_shadow_forecast_not_a_review_candidate")
    per_state = Counter()
    output = []
    for eid,c in original.items():
        o = official[eid]
        q = claims[eid]
        if (c.get("record_type") != "challenger_nba_history_candidate_review_only"
                or c.get("league") != "nba" or c.get("market_type") != "moneyline"
                or c.get("selection_type") != "home"
                or c.get("qualified_for_challenger_backtest") is not False
                or c.get("eligible_to_train_probability_model") is not False
                or c.get("independent_asof_review") is not False
                or c.get("independent_outcome_review") is not False
                or c.get("certified_prediction") is not False
                or c.get("bet_ready") is not False
                or c.get("champion_001_modified") is not False
                or c.get("model_probability") is not None
                or o.get("home_team") != c.get("home_team")
                or o.get("away_team") != c.get("away_team")
                or o.get("espn_published_score") != c.get("published_score_only")
                or any(o.get(k) is not False for k in (
                    "training_row_qualified","independent_feature_asof_verified",
                    "independent_source_receipt_authenticated",
                    "independent_bookmaker_settlement_verified",
                    "certified_prediction","bet_ready","champion_001_modified"))
                or q.get("independent_qualification") is not False
                or q.get("bet_ready") is not False
                or q.get("champion_001_modified") is not False
                or q.get("evidence") is None
                or set(q["evidence"]) != set(REQUIRED)
                or any(type(v) is not bool for v in q["evidence"].values())
                or any(q["evidence"][k] is not False for k in REQUIRED
                       if k != "published_score_second_source_agreement")
                or q["evidence"]["published_score_second_source_agreement"] != (
                    o.get("crosscheck_status") == RESEARCH_STATUS
                    and o.get("official_nba_score") == c.get("published_score_only"))
                or q.get("missing") != [
                    k for k in REQUIRED if q["evidence"][k] is False]):
            raise ValueError("unsafe_or_unreconciled_nba_evidence_attestation")

        start=timestamp(c["start_utc"])
        capture=timestamp(c["snapshot_utc"])
        final=timestamp(c["outcome_verified_at_utc"])
        if not capture < start < final:
            raise ValueError("untrustworthy_chronological_nba_evidence")
        linked=shadows.get(eid)
        shadow_status="no_original_pregame_research_forecast"
        research_pick=None
        if linked:
            if (linked.get("record_type") !=
                        "nba_moneyline_prospective_untrained_shadow_research_only"
                    or linked.get("home_team") != c["home_team"]
                    or linked.get("away_team") != c["away_team"]
                    or timestamp(linked["event_start_utc"]) != start
                    or linked.get("trained_challenger_001_model") is not False
                    or linked.get("champion_001_prediction") is not False
                    or linked.get("counts_toward_champion_001_certified_shadow_target") is not False
                    or linked.get("certified_prediction") is not False
                    or linked.get("bet_ready") is not False
                    or linked.get("shadow_stake_usd") != 0
                    or linked.get("champion_001_modified") is not False
                    or linked.get("sportsbook_price") is not None
                    or linked.get("independently_authenticated_source_publication") is not False
                    or not timestamp(linked["snapshot_completed_at_utc"]) <=
                           timestamp(linked["forecast_created_at_utc"]) < start):
                raise ValueError("shadow_claim_cannot_be_used_as_native_training_proof")
            if timestamp(linked["snapshot_completed_at_utc"]) != capture:
                shadow_status="different_valid_pregame_capture_no_one_to_one_join"
            else:
                shadow_status="exact_original_pregame_research_shadow_found_uncertified"
                research_pick=linked.get("research_selection")
                if research_pick not in ("home","away",None):
                    raise ValueError("invalid_research_side")
        second_source = q["evidence"]["published_score_second_source_agreement"]
        obstacles = [key for key in REQUIRED if not q["evidence"][key]]
        if not second_source:
            per_state["needs_official_nba_original_final_recovery"] += 1
        else:
            per_state["nba_second_source_published_score_agrees"] += 1
        per_state[shadow_status] += 1
        output.append({
            "record_type":"challenger_nba_independent_review_worklist_only",
            "league":"nba",
            "espn_event_id":eid,
            "home_team":c["home_team"],
            "away_team":c["away_team"],
            "start_utc":start.isoformat(),
            "original_snapshot_utc":capture.isoformat(),
            "espn_published_final_seen_utc":final.isoformat(),
            "published_score_only":c["published_score_only"],
            "independently_adjudicated_market_outcome":False,
            "nba_score_second_source_status":o.get("crosscheck_status"),
            "review_priority":(
                "authenticate_original_pregame_and_independent_adjudication"
                if second_source else
                "recover_official_final_then_authenticate_original_pregame"),
            "missing_qualification_evidence":obstacles,
            "source_self_hash_not_independent_attestation":
                c.get("source_receipt_sha256_not_independently_verified"),
            "research_shadow_status":shadow_status,
            "research_side_if_exact_capture":research_pick,
            "research_shadow_is_trained_model":False,
            "qualified_for_challenger_backtest":False,
            "training_eligible":False,
            "certified_prediction":False,
            "bet_ready":False,
            "champion_001_modified":False,
        })
    output.sort(key=lambda item: (
        item["nba_score_second_source_status"]!=RESEARCH_STATUS,
        item["start_utc"],item["espn_event_id"]))
    return output, {
        "stage":"challenger_100_nba_evidence_to_training_qualification_worklist",
        "nba_research_candidates_reconciled":len(output),
        "nba_two_source_published_final_score_agreements_research_only":
            per_state["nba_second_source_published_score_agrees"],
        "nba_missing_second_source_original_final":
            per_state["needs_official_nba_original_final_recovery"],
        "nba_exact_original_pregame_heuristic_forecast_reconciled":
            per_state["exact_original_pregame_research_shadow_found_uncertified"],
        "nba_pregame_heuristic_missing_or_different_snapshot":
            len(output)-per_state["exact_original_pregame_research_shadow_found_uncertified"],
        "target_chronological_training_games":200,
        "target_later_holdout_games":50,
        "structurally_missing_research_candidates_to_250":
            max(0,250-len(output)),
        "independently_qualified_training_games":0,
        "independently_qualified_holdout_games":0,
        "independently_qualified_shortfall_to_250":250,
        "no_model_training_authorized":True,
        "research_baseline_is_not_trained_challenger_001":True,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_selections":0,
        "direct_draftkings_checkout_quotes_verified":0,
        "automated_bets_placed":0,
        "champion_001_modified":False,
        "warning":("Per-event score and pregame research receipts are not "
                   "independently authenticated historical feature publication, "
                   "original trained model weights, independently adjudicated "
                   "market settlement, or sportsbook price evidence. Worklist "
                   "must never be read as historical_results.jsonl for training."),
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates",required=True)
    p.add_argument("--comparisons",required=True)
    p.add_argument("--qualification",required=True)
    p.add_argument("--shadow-ledger",required=True)
    p.add_argument("--output-dir",default="prospective_validation")
    args=p.parse_args(argv)
    def lines(path):
        f=Path(path)
        if not f.is_file():
            raise FileNotFoundError(f)
        return [json.loads(x) for x in f.read_text(encoding="utf8").splitlines()
                if x.strip()]
    rows,report=audit(lines(args.candidates),lines(args.comparisons),
                      lines(args.qualification),lines(args.shadow_ledger))
    dest=Path(args.output_dir)
    dest.mkdir(parents=True,exist_ok=True)
    (dest/"nba_independent_evidence_training_worklist.jsonl").write_text(
        "".join(canonical(x)+"\n" for x in rows),encoding="utf8")
    (dest/"nba_independent_evidence_training_worklist_report.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps({
        "research_candidates":report["nba_research_candidates_reconciled"],
        "official_original_final_research_agreements":
           report["nba_two_source_published_final_score_agreements_research_only"],
        "qualified_training_games":0,"certified_predictions":0,
        "champion_001_modified":False},sort_keys=True))


if __name__=="__main__":
    main()
