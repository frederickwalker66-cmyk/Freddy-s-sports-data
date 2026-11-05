"""Read-only eight-sport source-slate vs retained pregame event coverage.

Distinguishes: no ESPN games LISTED in checked dates, games that already
started, partial HTTP failures, discovered games rejected by the snapshot
collector, and actually archived future games. No predictions or wagers.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlparse
from independent_schedule_review import SOURCES, MAX_LOOKAHEAD_DAYS
from challenger_prospective_outcome_validation import instant

LEAGUES = tuple(SOURCES)


def audit(snapshot, report, records):
    if not isinstance(snapshot,dict) or not isinstance(report,dict) or not isinstance(records,list):
        raise ValueError("invalid_schedule_coverage_inputs")
    if (report.get("stage")!="challenger_prospective_eight_league_evidence_research_only"
        or set(report.get("by_league",{}))!=set(LEAGUES)
        or report.get("certified_champion_001_predictions")!=0
        or report.get("certified_challenger_001_predictions")!=0
        or report.get("verified_historical_training_examples")!=0
        or report.get("direct_draftkings_checkout_quotes_verified")!=0
        or report.get("verified_player_availability_entries")!=0
        or report.get("bet_ready_selections")!=0
        or report.get("automated_bets_placed")!=0
        or report.get("champion_001_modified") is not False):
        raise ValueError("schedule_diagnostic_input_promoted_to_bet_or_training")
    at=instant(snapshot.get("collected_at_utc"))
    end=instant(report.get("captured_at_utc"))
    if not at<=end:
        raise ValueError("schedule_source_observed_after_snapshot_end")
    span=snapshot.get("lookahead_days_requested")
    if type(span) is not int or not 0<=span<=MAX_LOOKAHEAD_DAYS:
        raise ValueError("invalid_eight_sport_outlook_window")
    if (not isinstance(snapshot.get("events"),list)
        or not isinstance(snapshot.get("sources"),dict)
        or set(snapshot["sources"])!=set(LEAGUES)):
        raise ValueError("missing_league_source_diagnostics")
    source_by=Counter()
    event_ids={}
    for entry in snapshot["events"]:
        if (not isinstance(entry,dict) or entry.get("league") not in LEAGUES
            or entry.get("status")!="scheduled"
            or not isinstance(entry.get("provider_game_id"),str)
            or not entry["provider_game_id"].isdecimal()):
            raise ValueError("unsafe_espn_discovered_future_event")
        start=instant(entry.get("start_utc"))
        observed=instant(entry.get("observed_at_utc"))
        if not (at<=observed<=end and observed<start):
            raise ValueError("schedule_event_not_observed_before_tipoff")
        link=urlparse(entry.get("source_url",""))
        if link.scheme!="https" or link.hostname!="site.api.espn.com":
            raise ValueError("unapproved_original_future_schedule_source")
        k=(entry["league"],entry["provider_game_id"])
        if k in event_ids:
            raise ValueError("duplicate_discovered_scheduled_event")
        event_ids[k]=entry
        source_by[entry["league"]]+=1
    archive_by=Counter()
    archived_ids=set()
    for entry in records:
        if (not isinstance(entry,dict)
            or entry.get("record_type")!="prospective_evidence_snapshot_research_only"
            or entry.get("league") not in LEAGUES
            or entry.get("model_probability") is not None
            or entry.get("qualified_for_challenger_backtest") is not False
            or entry.get("certified_prediction") is not False
            or entry.get("bet_ready") is not False
            or entry.get("champion_001_modified") is not False):
            raise ValueError("unsafe_archived_pregame_event")
        key=(entry["league"],entry.get("espn_schedule_event_id"))
        if key in archived_ids or key not in event_ids:
            raise ValueError("missing_or_duplicate_original_schedule_for_archive")
        archived_ids.add(key)
        if not (at<=instant(entry["schedule_observed_at_utc"])<=
                    instant(entry["snapshot_completed_at_utc"])<=end<
                    instant(entry["event_start_utc"])):
            raise ValueError("archive_record_timestamp_not_pregame")
        archive_by[entry["league"]]+=1
    coverage={}
    for lg in LEAGUES:
        src=snapshot["sources"][lg]
        if not isinstance(src,dict):
            raise ValueError("malformed_espn_league_source")
        q=src.get("lookahead")
        if not isinstance(q,list) or not 1<=len(q)<=span+1:
            raise ValueError("missing_bounded_source_query_receipts")
        good=sum(item.get("status")=="retrieved" for item in q)
        bad=sum(item.get("status")=="unavailable" for item in q)
        if (good+bad!=len(q) or good!=src.get("days_retrieved")
            or bad!=src.get("days_unavailable")
            or len(q)!=src.get("days_checked")
            or src.get("status")!=("retrieved" if good else "unavailable")
            or src.get("scheduled_events")!=source_by[lg]
            or report["by_league"][lg]["upcoming_events"]!=archive_by[lg]
            or source_by[lg]<archive_by[lg]):
            raise ValueError("schedule_source_and_archive_counts_disagree")
        # Do not infer a no-game day unless all source dates actually
        # returned a valid scoreboard. One missing day blocks that claim.
        raw_total=sum(item.get("raw_events_listed",0)
                      for item in q if item["status"]=="retrieved")
        if raw_total!=src.get("raw_game_listings_across_checked_dates"):
            raise ValueError("raw_source_slate_totals_do_not_reconcile")
        if source_by[lg] and archive_by[lg]==source_by[lg]:
            flag="all_discovered_future_games_archived_research_only"
        elif source_by[lg]:
            flag="some_discovered_future_games_missing_from_archive"
        elif bad:
            flag="partial_or_total_source_failure_not_proof_of_no_games"
        elif raw_total:
            flag="games_listed_but_none_future_valid_at_capture"
        elif good==span+1:
            flag="espn_no_listed_games_in_fully_checked_window"
        else:
            flag="no_listed_games_in_checked_dates_beyond_scan_not_checked"
        coverage[lg]={
            "requested_future_days":span,
            "source_days_attempted":len(q),
            "source_days_succeeded":good,
            "source_days_failed":bad,
            "source_game_listings":raw_total,
            "source_future_games_discovered":source_by[lg],
            "archived_pregame_games":archive_by[lg],
            "discovered_games_not_archived":source_by[lg]-archive_by[lg],
            "first_day_listed_games":src.get("first_day_raw_events"),
            "source_diagnosis":src.get("diagnosis"),
            "coverage_class":flag,
            "source_is_espn_third_party_not_official_league":True,
            "source_checks":q,
            "independently_verified_game_eligibility":False,
            "qualified_for_model_training":0,
            "certified_predictions":0,
        }
    totals={
        "espn_game_listings_retrieved":sum(x["source_game_listings"] for x in coverage.values()),
        "future_games_discovered":sum(source_by.values()),
        "pregame_events_archived":sum(archive_by.values()),
        "source_days_failed":sum(x["source_days_failed"] for x in coverage.values()),
        "missing_future_archive_events":sum(x["discovered_games_not_archived"] for x in coverage.values()),
    }
    return {
        "stage":"challenger_eight_sport_seven_day_schedule_coverage_research_only",
        "captured_at_utc":end.isoformat(),
        "leagues":list(LEAGUES),
        "by_league":coverage,"totals":totals,
        "independent_league_schedule_verified":False,
        "historical_feature_publication_authenticated":False,
        "qualified_chronological_training_games":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_bets":0,
        "bet_ready_selections":0,"automated_bets_placed":0,
        "champion_001_modified":False,
        "warning":("Empty ESPN game list over checked dates is not proof no league games "
                   "exist outside the observed window. Archived future schedules are "
                   "research observations, not pregame model forecasts, independently "
                   "authenticated league schedules, odds, or verified betting edges."),
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture-dir",required=True)
    p.add_argument("--output")
    args=p.parse_args(argv)
    root=Path(args.capture_dir)
    snapshot=json.loads((root/"espn_schedule_capture.json").read_text())
    report=json.loads((root/"prospective_report.json").read_text())
    records=[json.loads(s) for s in
             (root/"prospective_event_evidence.jsonl").read_text().splitlines()
             if s.strip()]
    summary=audit(snapshot,report,records)
    output=Path(args.output) if args.output else root/"eight_sport_schedule_coverage.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"stage":summary["stage"],"totals":summary["totals"],
                      "certified_positive_ev_bets":0}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
