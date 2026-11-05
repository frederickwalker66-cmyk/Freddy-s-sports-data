"""Eight-league original-pregame-to-second-score-source coverage ledger.

Read only research review artifacts previously produced by the existing
pipeline. Count actual event joins, missing stages and publisher disagreements;
do not turn corroborated scores into historically authenticated pregame
training rows, odds, certified predictions or player props.

Distinct source labels matter: NBA/NHL operate some sources, nflverse/college
proxy/API Ninjas are third-party, and MLB has no linked second result stage.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from challenger_multisport_evidence_bridge import LEAGUES
from challenger_multisport_original_bytes_lineage import REVIEW_RECORD
from challenger_prospective_outcome_validation import instant

SOURCE_SPECS = {
    "nba": ("nba_official_final_crosscheck.jsonl", "espn_research_event_id",
            "nba_second_source_final_score_agrees_research_only", "nba_league_operated_separate_score"),
    "nfl": ("nfl_second_source_score_review.jsonl", "espn_event_id",
            "nflverse_second_source_final_score_agrees_research_only", "nflverse_community_third_party_score"),
    "nhl": ("nhl_official_score_crosscheck.jsonl", "espn_event_id",
            "nhl_second_source_final_score_agrees_research_only", "nhl_league_operated_separate_score"),
    "ncaaf": ("college_ncaa_score_review.jsonl", "espn_event_id",
              "ncaa_derived_final_score_agrees_research_only", "ncaa_com_derived_third_party_proxy"),
    "ncaab": ("college_ncaa_score_review.jsonl", "espn_event_id",
              "ncaa_derived_final_score_agrees_research_only", "ncaa_com_derived_third_party_proxy"),
    "mls": ("soccer_90min_second_source_review.jsonl", "espn_event_id",
            "regulation_score_agrees_with_espn_published_score_research_only",
            "api_ninjas_unaffiliated_soccer_regulation"),
    "uefa_champions_league": ("soccer_90min_second_source_review.jsonl", "espn_event_id",
                             "regulation_score_agrees_with_espn_published_score_research_only",
                             "api_ninjas_unaffiliated_soccer_regulation"),
}
MAX_LINES = 100000
EXPECTED_SECOND_RECORD = {
    "nba":"", # NBA crosscheck predates the newer review-row type field.
    "nfl":"challenger_nfl_second_source_research_only",
    "nhl":"challenger_nhl_second_source_research_review_only",
    "ncaaf":"challenger_college_ncaa_proxy_score_crosscheck_research_only",
    "ncaab":"challenger_college_ncaa_proxy_score_crosscheck_research_only",
    "mls":"challenger_soccer_ninety_minute_second_source_review_only",
    "uefa_champions_league":"challenger_soccer_ninety_minute_second_source_review_only",
}
OUTCOME_MISMATCH = {
    "nba": ("nba_official_final_disagrees_with_espn",),
    "nfl": ("nflverse_published_score_disagrees_with_espn",),
    "nhl": ("nhl_official_final_disagrees_with_espn",),
    "ncaaf": ("ncaa_derived_score_disagrees_with_espn",),
    "ncaab": ("ncaa_derived_score_disagrees_with_espn",),
    "mls": ("regulation_score_disagrees_with_espn_published_score",),
    "uefa_champions_league": ("regulation_score_disagrees_with_espn_published_score",),
}


def jsonl(path):
    if not Path(path).is_file():
        return None
    lines=Path(path).read_text(encoding="utf8").splitlines()
    if len(lines)>MAX_LINES:
        raise ValueError("overlarge_all_sport_review_archive")
    return [json.loads(s) for s in lines if s.strip()]


def _audit_lineage(rows, now):
    if not isinstance(rows,list):
        raise ValueError("required_original_byte_lineage_missing")
    packets={}
    for item in rows:
        if (not isinstance(item,dict) or item.get("record_type")!=REVIEW_RECORD
                or item.get("league") not in LEAGUES
                or not isinstance(item.get("event_id"),str)
                or not item["event_id"].isdecimal()
                or item.get("original_bytes_match_same_run_receipt") is not True
                or item.get("same_run_receipt_independently_authenticated") is not False
                or item.get("independent_feature_asof_review") is not False
                or item.get("independent_outcome_review") is not False
                or item.get("market_settlement_rules_verified") is not False
                or item.get("qualified_for_challenger_training") is not False
                or item.get("model_probability") is not None
                or item.get("certified_prediction") is not False
                or item.get("bet_ready") is not False
                or item.get("champion_001_modified") is not False):
            raise ValueError("unsafe_or_unverified_original_sport_review_line")
        for field in ("source_event_line_sha256","source_archive_file_sha256",
                      "same_run_receipt_sha256"):
            value=item.get(field)
            if not isinstance(value,str) or re.fullmatch("[a-f0-9]{64}",value) is None:
                raise ValueError("missing_original_source_byte_receipt")
        at=instant(item.get("snapshot_completed_at_utc"))
        start=instant(item.get("event_start_utc"))
        if not at<start<=now:
            raise ValueError("future_or_after_game_original_sport_snapshot")
        if item.get("published_final_only") is not None:
            published=item["published_final_only"]
            if (not isinstance(published,dict)
                    or published.get("published_result") not in ("home","away","draw")
                    or type(published.get("home_score")) is not int
                    or type(published.get("away_score")) is not int
                    or instant(published.get("published_at_observation_utc")) < start
                    or instant(published.get("published_at_observation_utc")) > now):
                raise ValueError("unqualified_or_early_published_sport_result")
        key=(item["league"],item["event_id"])
        if key in packets:
            raise ValueError("duplicate_original_sport_event_key")
        packets[key]=item
    return packets


def _audit_second(rows, league, matches, source_name):
    """One and only one second-source review per original event, no promotion."""
    keyfield=SOURCE_SPECS[league][1]
    agreement=SOURCE_SPECS[league][2]
    statuses=Counter()
    output={}
    orphaned=0
    for item in rows:
        if not isinstance(item,dict):
            raise ValueError("invalid_second_source_review_record")
        if league in ("ncaaf","ncaab","mls","uefa_champions_league") and item.get("league")!=league:
            continue
        if (league in ("nfl","nhl") and item.get("league")!=league):
            raise ValueError("wrong_sport_second_source_review")
        expected=EXPECTED_SECOND_RECORD[league]
        if expected and item.get("record_type")!=expected:
            raise ValueError("wrong_second_source_review_type")
        eid=item.get(keyfield)
        if not isinstance(eid,str) or not eid.isdecimal():
            raise ValueError("invalid_second_source_event_id")
        if eid in output:
            raise ValueError("duplicate_second_source_event")
        # The source adapter must not have certified the downstream row.
        for name in ("bet_ready","champion_001_modified"):
            if item.get(name) is not False:
                raise ValueError("unsafe_second_source_promotion_flag")
        if item.get("qualified_for_challenger_training",False) is not False:
            raise ValueError("unqualified_second_source_training_promotion")
        if item.get("certified_prediction",False) is not False:
            raise ValueError("unqualified_second_source_prediction_promotion")
        status=item.get("crosscheck_status")
        if not isinstance(status,str) or not status:
            raise ValueError("missing_second_source_review_status")
        if (league,eid) not in matches:
            # NBA published-score research can originate from a broader
            # evidence review queue than the receipt-authenticated subset.
            # Quarantine it instead of counting or joining it by similarity.
            orphaned+=1
            continue
        if (status==agreement or status in OUTCOME_MISMATCH[league]):
            if matches[(league,eid)].get("published_final_only") is None:
                raise ValueError("second_source_agreement_without_published_final")
        output[eid]=item
        statuses[status]+=1
    return output,statuses,orphaned


def reconcile(root,now=None):
    now=now or datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None:
        raise ValueError("coverage_requires_aware_clock")
    now=now.astimezone(timezone.utc)
    root=Path(root)
    packets=_audit_lineage(jsonl(root/"original_bytes_lineage_review.jsonl"),now)
    source_cache={name:jsonl(root/name) for name,*_ in SOURCE_SPECS.values()}
    coverage={}
    overall=Counter()
    for league in LEAGUES:
        originals={eid:row for (lg,eid),row in packets.items() if lg==league}
        published={eid:row for eid,row in originals.items()
                   if row.get("published_final_only") is not None}
        with_features=sum(r.get("asof_features_for_manual_review_only") is not None
                          for r in originals.values())
        if league in SOURCE_SPECS:
            file,field,agree,provider=SOURCE_SPECS[league]
            data=source_cache[file]
            if data is None:
                matched,statuses,orphaned={},Counter(),0
                availability="source_review_artifact_missing"
            else:
                matched,statuses,orphaned=_audit_second(data,league,packets,file)
                availability="source_review_artifact_present"
            counts={
                "original_pregame_events_receipt_backed":len(originals),
                "pregame_feature_research_rows":with_features,
                "linked_published_results":len(published),
                "second_source_rows_reviewed":len(matched),
                "source_review_rows_quarantined_without_original_lineage":orphaned,
                "second_source_published_score_agreements_research_only":statuses[agree],
                "second_source_score_disagreements_for_review":
                    sum(statuses[k] for k in OUTCOME_MISMATCH[league]),
                "second_source_without_original_final":sum(
                    eid not in published for eid in matched),
                "published_results_without_second_source_review":
                    sum(eid not in matched for eid in published),
                "second_source_review_statuses":dict(sorted(statuses.items())),
                "source_class":provider,
                "source_availability":availability,
            }
            if counts["second_source_rows_reviewed"]>counts["original_pregame_events_receipt_backed"]:
                raise ValueError("second_source_rows_exceed_prospective_evidence")
        else:
            counts={
                "original_pregame_events_receipt_backed":len(originals),
                "pregame_feature_research_rows":with_features,
                "linked_published_results":len(published),
                "second_source_rows_reviewed":0,
                "source_review_rows_quarantined_without_original_lineage":0,
                "second_source_published_score_agreements_research_only":0,
                "second_source_score_disagreements_for_review":0,
                "second_source_without_original_final":0,
                "published_results_without_second_source_review":len(published),
                "second_source_review_statuses":{},
                "source_class":"second_source_stage_not_integrated",
                "source_availability":"no_matching_second_source_review_in_current_pipeline",
            }
        # Never let score corroboration, a same-run hash or a PDF/CSV
        # reverse-fill a valid original point-in-time prediction or odds.
        counts.update({
            "independently_authenticated_pregame_features":0,
            "independently_adjudicated_market_settlements":0,
            "qualified_chronological_training_records":0,
            "model_calibration_verified":False,
            "certified_positive_ev_bets":0,
        })
        if not originals:
            priority="collect_original_pregame_snapshots_and_receipts"
        elif len(published)<len(originals):
            priority="link_later_results_without_retroactive_feature_filling"
        elif counts["second_source_rows_reviewed"]<len(published):
            priority=("add_separate_publisher_score_crosscheck" if league=="mlb"
                      else "repair_or_extend_second_source_result_coverage")
        elif not counts["second_source_published_score_agreements_research_only"]:
            priority="resolve_nonagreement_or_unavailable_second_source"
        else:
            priority="authenticate_original_feature_publication_and_market_settlement"
        counts["next_evidence_priority"]=priority
        coverage[league]=counts
        for key in ("original_pregame_events_receipt_backed",
                    "linked_published_results",
                    "second_source_rows_reviewed",
                    "second_source_published_score_agreements_research_only",
                    "second_source_score_disagreements_for_review"):
            overall[key]+=counts[key]
    return {
        "stage":"challenger_eight_sport_cross_source_coverage_gate_research_only",
        "generated_at_utc":now.isoformat(),
        "leagues":list(LEAGUES),
        "by_league":coverage,
        "totals":dict(sorted(overall.items())),
        "source_publication_times_independently_authenticated":False,
        "bookmaker_market_settlement_rules_verified":False,
        "qualified_training_records":0,
        "trained_probability_models_created":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_bets":0,
        "bet_ready_selections":0,
        "automated_bets_placed":0,
        "champion_001_modified":False,
        "warning":("Cross-source score agreements are retrospective REVIEW ONLY. "
                   "Provider data, original hash receipts and linked ESPN finals "
                   "do not authenticate feature publication, settled odds, "
                   "historical pregame forecasts, calibration or EV. "
                   "NBA later history candidates and MLS/UEFA 90-minute market "
                   "rules need independent separately verified settlement."),
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir",required=True)
    p.add_argument("--output",default="prospective_validation/eight_sport_source_coverage.json")
    a=p.parse_args(argv)
    r=reconcile(a.input_dir)
    output=Path(a.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(r,sort_keys=True,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"stage":r["stage"],"totals":r["totals"],
                      "trained_probability_models_created":0,
                      "certified_positive_ev_bets":0}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
