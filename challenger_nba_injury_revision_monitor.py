"""Compare two NBA-owned injury-report PDF revisions, as actually retrieved.

The NEWER report has an original same-run capture receipt. The preceding PDF
is downloaded NOW from the original NBA index (not backdated to its filename).
Changes are publisher DESIGNATION signals, never confirmed active/inactive
lineups, DNP settlements, original pregame forecasts, or bets.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin

from challenger_nba_pregame_injury_pdf import (
    INDEX_URL, MAX_INDEX_BYTES, MAX_PDF_BYTES, LinkReader,
    fetch_bytes, pick_index_report, report_label_from_url,
)
from challenger_nba_injury_pdf_player_rows import (
    ET, STATUSES, TEAM_CODES, TEAMS, parse_pdf_bytes,
)
from challenger_nba_player_two_source_review import canonical
from challenger_nba_schedule_clock import nba_team_name
from challenger_prospective_outcome_validation import instant

MAX_PREVIOUS_GAP_SECONDS = 90 * 60
MAX_CURRENT_CAPTURE_AGE_SECONDS = 10 * 60
MAX_EVENTS = 100
MAX_ROWS = 800


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def now_utc(clock):
    result=clock()
    if not isinstance(result,datetime) or result.tzinfo is None:
        raise ValueError("nba_injury_revision_capture_clock_naive")
    return result.astimezone(timezone.utc)


def previous_report_link(index_raw, current_url, latest_at, at):
    """Select only exact prior NBA PDF link, never a future or third-party URL."""
    if not isinstance(index_raw,bytes) or not 1<=len(index_raw)<=MAX_INDEX_BYTES:
        raise ValueError("invalid_original_nba_injury_index_bytes")
    reader=LinkReader()
    reader.feed(index_raw.decode("utf8"))
    valid=set()
    for href in reader.hrefs:
        url=urljoin(INDEX_URL,href)
        try:
            label=report_label_from_url(url)
        except (ValueError,TypeError,OverflowError):
            continue
        if label<=at and 0<=(latest_at-label).total_seconds()<=MAX_PREVIOUS_GAP_SECONDS:
            valid.add((label,url))
    if (latest_at,current_url) not in valid:
        raise ValueError("original_nba_injury_current_report_not_in_original_index")
    older=[(label,url) for label,url in valid if label<latest_at]
    if not older:
        return None
    older.sort(reverse=True)
    if len({url for label,url in older if label==older[0][0]})!=1:
        raise ValueError("ambiguous_older_nba_pdf_revision")
    return older[0]


def original_capture(root, at):
    """Reverify actual source bytes: receipts are integrity, not external time proof."""
    root=Path(root)
    metadata=root/"nba_injury_original_report.json"
    if not metadata.is_file():
        raise FileNotFoundError("no_original_nba_injury_capture")
    r=json.loads(metadata.read_text(encoding="utf8"))
    if (not isinstance(r,dict)
        or r.get("stage")!="challenger_original_nba_pregame_injury_pdf_archive_research_only"):
        raise ValueError("wrong_original_nba_injury_archive_type")
    if r.get("source_status")!="captured_original_index_and_pdf":
        return None,r
    for field in ("nba_players_confirmed_active",
                  "qualified_player_prop_training_observations",
                  "certified_champion_001_predictions",
                  "certified_challenger_001_predictions",
                  "certified_positive_ev_bets","bet_ready_selections",
                  "automated_bets_placed"):
        if r.get(field)!=0:
            raise ValueError("unsafe_promoted_injury_capture")
    if (r.get("champion_001_modified") is not False
        or r.get("report_filename_label_externally_authenticated") is not False
        or r.get("original_pdf_authorship_cryptographically_verified") is not False):
        raise ValueError("unsafe_original_injury_source_authentication_claim")
    current_at=instant(r["capture_observed_at_utc"])
    if not current_at<=at or (at-current_at).total_seconds()>MAX_CURRENT_CAPTURE_AGE_SECONDS:
        raise ValueError("source_revision_comparison_not_same_capture_run")
    raw_pdf=(root/"nba_injury_original_report.pdf").read_bytes()
    raw_index=(root/"nba_injury_original_index.html").read_bytes()
    if (sha(raw_pdf)!=r["original_pdf_sha256"]
        or sha(raw_index)!=r["official_nba_index_sha256"]
        or r.get("official_nba_index_url")!=INDEX_URL):
        raise ValueError("original_pdf_or_index_bytes_changed")
    pdf_url=r["official_nba_report_url"]
    labeled=report_label_from_url(pdf_url)
    if (labeled!=instant(r["report_filename_labeled_at_utc_not_authenticated"])
        or pick_index_report(raw_index,current_at)!=(labeled,pdf_url)):
        raise ValueError("original_pdf_label_or_index_disagreement")
    return {
        "receipt":r,"pdf":raw_pdf,"index":raw_index,
        "current_at":current_at,"label":labeled,"url":pdf_url,
    },r


def validate_rows(rows,filings):
    if (not isinstance(rows,list) or len(rows)>MAX_ROWS
            or not isinstance(filings,list) or len(filings)>MAX_ROWS):
        raise ValueError("invalid_nba_report_parsed_rows_count")
    result, seen, missing = {},set(),set()
    for f in filings:
        if (not isinstance(f,dict)
            or f.get("record_type")!="nba_official_pdf_team_report_not_submitted_research_only"
            or f.get("filing_status")!="not_yet_submitted"
            or f.get("confirmed_all_players_available") is not False
            or f.get("bet_ready") is not False
            or f.get("champion_001_modified") is not False):
            raise ValueError("unsafe_nba_team_unsubmitted_row")
        k=(f.get("game_date_et"),f.get("matchup"),f.get("team_abbreviation"))
        if k in missing:
            raise ValueError("duplicate_unsubmitted_nba_team")
        missing.add(k)
    for row in rows:
        if (not isinstance(row,dict)
            or row.get("record_type")!="nba_official_pdf_player_status_extracted_for_review_only"
            or row.get("source_injury_designation") not in STATUSES
            or row.get("nba_person_id") is not None
            or row.get("espn_athlete_id") is not None
            or row.get("player_current_game_active_status_verified") is not False
            or row.get("roster_player_id_crosswalk_verified") is not False
            or row.get("qualified_for_prop_training") is not False
            or row.get("market_eligibility_verified") is not False
            or row.get("bet_ready") is not False
            or row.get("champion_001_modified") is not False):
            raise ValueError("unsafe_or_unknown_nba_injury_player_designation")
        code=row.get("nba_team_abbreviation")
        if code not in TEAM_CODES or row.get("team_name")!=TEAM_CODES[code]:
            raise ValueError("incorrect_original_pdf_nba_team")
        day, matchup=row.get("game_date_et"),row.get("matchup")
        if not isinstance(day,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",day):
            raise ValueError("unknown_pdf_game_day")
        if not isinstance(matchup,str) or not re.fullmatch(r"[A-Z]{2,3}@[A-Z]{2,3}",matchup):
            raise ValueError("unknown_pdf_matchup")
        away,home=matchup.split("@")
        if away not in TEAM_CODES or home not in TEAM_CODES or code not in (away,home) or away==home:
            raise ValueError("injury_pdf_team_not_in_game")
        if (day,matchup,code) in missing:
            raise ValueError("contradictory_unsubmitted_team_and_reported_player")
        player=canonical(row.get("source_player_name_display"))
        if not player:
            raise ValueError("unresolved_injury_player_name")
        key=(day,matchup,code,player)
        if key in seen:
            raise ValueError("duplicate_exact_nba_injury_player")
        seen.add(key)
        result[key]=row
    return result,missing


def eligible_future_events(events, current_at, reviewed_at):
    if events is None:
        return None
    if not isinstance(events,list) or len(events)>MAX_EVENTS:
        raise ValueError("invalid_prospective_nba_event_review")
    mapping=defaultdict(list)
    ids=set()
    for event in events:
        if not isinstance(event,dict) or event.get("league")!="nba":
            continue
        if (event.get("record_type")!="prospective_evidence_snapshot_research_only"
            or event.get("qualified_for_challenger_backtest") is not False
            or event.get("model_probability") is not None
            or event.get("certified_prediction") is not False
            or event.get("bet_ready") is not False
            or event.get("champion_001_modified") is not False):
            raise ValueError("promoted_nba_pregame_event_not_eligible")
        eid=event.get("espn_schedule_event_id")
        if not isinstance(eid,str) or not eid.isdecimal() or eid in ids:
            raise ValueError("duplicate_nba_event_in_source_revision_review")
        ids.add(eid)
        start=instant(event.get("event_start_utc"))
        snapshot=instant(event.get("snapshot_completed_at_utc"))
        if not snapshot<=current_at<=reviewed_at<start:
            continue
        home=nba_team_name(event.get("home_team"))
        away=nba_team_name(event.get("away_team"))
        if home not in TEAMS or away not in TEAMS or away==home:
            continue
        key=(start.astimezone(ET).date().isoformat(),TEAMS[away]+"@"+TEAMS[home])
        mapping[key].append(eid)
    return mapping


def compare_reports(new_rows,new_filings,old_rows,old_filings,current_at,
                    previous_at,reviewed_at,events=None):
    latest,missing_latest=validate_rows(new_rows,new_filings)
    prior,missing_prior=validate_rows(old_rows,old_filings)
    future=eligible_future_events(events,current_at,reviewed_at)
    changes,counts=[],Counter()
    keys=sorted(set(latest)|set(prior))
    for key in keys:
        day,matchup,team,player=key
        old, new=prior.get(key),latest.get(key)
        if old and new:
            if old["source_injury_designation"]==new["source_injury_designation"]:
                continue
            state="reported_status_changed"
            if new["source_injury_designation"]=="Out":
                state="reported_designation_changed_to_out"
            elif old["source_injury_designation"]=="Out":
                state="reported_designation_changed_from_out"
        elif new:
            state="newly_listed_in_later_pdf_not_prior_unavailability_proof"
        else:
            state="missing_from_later_pdf_not_availability_proof"
        filing_key=(day,matchup,team)
        if filing_key in missing_latest or filing_key in missing_prior:
            state="unsubmitted_team_report_prevents_individual_status_inference"
        candidates=future.get((day,matchup),[]) if future is not None else []
        if len(candidates)==1:
            relation="pregame_same_event_espn_schedule_research_only"
        elif len(candidates)>1:
            relation="ambiguous_pregame_event_identity"
        else:
            relation="pregame_matchup_not_authenticated"
        # This flag means we actually observed and linked the later source
        # BEFORE scheduled tipoff. It still does NOT verify active/inactive.
        alert=(state=="reported_designation_changed_to_out"
               and relation=="pregame_same_event_espn_schedule_research_only"
               and current_at<=reviewed_at)
        rec={
            "record_type":"challenger_nba_injury_designation_revision_review_only",
            "game_date_et":day,"matchup":matchup,
            "team_name":TEAM_CODES[team],
            "source_player_name":(new or old)["source_player_name_display"],
            "earlier_reported_status":old["source_injury_designation"] if old else None,
            "later_reported_status":new["source_injury_designation"] if new else None,
            "comparison_status":state,
            "source_observed_before_tipoff_match":relation,
            "espn_event_id_candidate":candidates[0] if len(candidates)==1 else None,
            "potential_out_designation_update_for_manual_review":alert,
            "earlier_original_pdf_retrieved_at_utc":reviewed_at.isoformat(),
            "later_original_pdf_captured_at_utc":current_at.isoformat(),
            "earlier_filename_labeled_at_utc_not_verified":previous_at.isoformat(),
            "actual_source_publication_time_independently_authenticated":False,
            "confirmed_late_scratch":False,
            "official_complete_active_list_verified":False,
            "player_participation_verified":False,
            "projected_minutes_verified":False,
            "bookmaker_prop_settlement_verified":False,
            "qualified_for_player_prop_training":False,
            "certified_prediction":False,"bet_ready":False,
            "champion_001_modified":False,
        }
        changes.append(rec)
        counts[state]+=1
    # Changes from an unsubmitted team to a submitted team cannot be inferred
    # solely from missing players. Preserve the explicit team filing status.
    for key in sorted(missing_latest ^ missing_prior):
        day,matchup,team=key
        label=("became_unsubmitted" if key in missing_latest else
               "prior_unsubmitted_filing_absent_from_later_pdf")
        counts[label]+=1
    return changes,dict(sorted(counts.items()))


def base_report(capture,now):
    return {
        "stage":"challenger_nba_original_injury_pdf_revision_monitor_research_only",
        "observed_at_utc":now.isoformat(),
        "current_original_pdf_sha256":capture.get("original_pdf_sha256"),
        "previous_original_pdf_sha256":None,
        "previous_pdf_source_url":None,
        "earlier_revision_retrieved_at_utc":None,
        "different_earlier_pdf_revisions_compared":0,
        "reported_player_status_changes":0,
        "possible_out_designation_transitions":0,
        "pregame_linked_out_transitions_for_review":0,
        "change_statuses":{},
        "source_status":"blocked_or_unavailable",
        "confirmed_active_players":0,
        "confirmed_late_scratches":0,
        "verified_player_participation":0,
        "verified_player_prop_training_examples":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_bets":0,
        "bet_ready_selections":0,
        "automated_bets_placed":0,
        "champion_001_modified":False,
        "warning":("Earlier PDF is retrieved NOW, not at its label time. "
                   "An official injury designation revision is not a confirmed "
                   "active/inactive roster decision, a late scratch settlement "
                   "or an authenticated original publication timestamp."),
    }


def run(capture_dir,events=None,fetcher=None,clock=None,parser=None):
    clock=clock or (lambda:datetime.now(timezone.utc))
    fetcher=fetcher or fetch_bytes
    parser=parser or parse_pdf_bytes
    now=now_utc(clock)
    current,receipt=original_capture(capture_dir,now)
    report=base_report(receipt,now)
    if current is None:
        report["source_status"]="current_nba_report_not_captured"
        return [],report,None
    selected=previous_report_link(current["index"],current["url"],current["label"],current["current_at"])
    if selected is None:
        report["source_status"]="no_prior_nba_report_link_within_90_minutes"
        return [],report,None
    previous_at,previous_url=selected
    try:
        older_pdf=fetcher(previous_url,MAX_PDF_BYTES)
        fetched=now_utc(clock)
        if fetched<now or (fetched-now).total_seconds()>90:
            raise ValueError("comparison_source_fetch_outside_same_run_clock_window")
        if not isinstance(older_pdf,bytes) or not 100<=len(older_pdf)<=MAX_PDF_BYTES:
            raise ValueError("empty_or_oversized_previous_injury_pdf")
        new_rows,new_filings,_=parser(current["pdf"],current["url"])
        old_rows,old_filings,_=parser(older_pdf,previous_url)
        changed,counts=compare_reports(new_rows,new_filings,old_rows,old_filings,
                                       current["current_at"],previous_at,fetched,events)
        report.update({
            "source_status":"two_official_report_revisions_parsed_research_only",
            "previous_original_pdf_sha256":sha(older_pdf),
            "previous_pdf_source_url":previous_url,
            "earlier_revision_retrieved_at_utc":fetched.isoformat(),
            "different_earlier_pdf_revisions_compared":1,
            "reported_player_status_changes":sum(
                k in ("reported_status_changed",
                      "reported_designation_changed_to_out",
                      "reported_designation_changed_from_out")
                for x in changed for k in [x["comparison_status"]]),
            "possible_out_designation_transitions":counts.get("reported_designation_changed_to_out",0),
            "pregame_linked_out_transitions_for_review":sum(
                x["potential_out_designation_update_for_manual_review"]
                for x in changed),
            "change_statuses":counts,
        })
        return changed,report,older_pdf
    except (OSError,ValueError,TypeError,UnicodeError,OverflowError,RuntimeError) as exc:
        report["source_status"]="revision_compare_blocked_"+type(exc).__name__
        return [],report,None


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture-dir",required=True)
    p.add_argument("--events")
    p.add_argument("--output-dir",default="nba_injury_revision_research")
    args=p.parse_args(argv)
    events=None
    if args.events:
        path=Path(args.events)
        if not path.is_file():
            raise FileNotFoundError("missing_prospective_nba_game_events")
        events=[json.loads(x) for x in path.read_text(encoding="utf8").splitlines()
                if x.strip()]
    rows,report,previous_raw=run(args.capture_dir,events)
    root=Path(args.output_dir)
    root.mkdir(parents=True,exist_ok=True)
    (root/"nba_injury_status_changes.jsonl").write_text(
        "".join(json.dumps(x,sort_keys=True)+"\n" for x in rows),encoding="utf8")
    (root/"nba_injury_revision_report.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf8")
    if previous_raw is not None:
        file=root/"nba_previous_original_injury_report.pdf"
        if file.exists():
            raise FileExistsError("refuse_to_overwrite_prior_original_pdf")
        file.write_bytes(previous_raw)
    print(json.dumps({
        "status":report["source_status"],
        "designation_changes":report["reported_player_status_changes"],
        "reported_to_out":report["possible_out_designation_transitions"],
        "confirmed_late_scratches":0,"certified_bets":0,
    }))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
