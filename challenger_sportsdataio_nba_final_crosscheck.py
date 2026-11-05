"""#101-103: licensed SportsDataIO NBA published-final corroboration, research only.

Uses the existing SportsDataIO subscription via bounded, canonical
GamesByDate requests; accepts no bookmaker data and does not train a model.
A 3rd-party historical final agreement is NOT NBA-operated official
adjudication, original pregame publication evidence or betting settlement.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from challenger_backtest import timestamp
from challenger_nba_schedule_clock import nba_team_name
from challenger_sportsdataio_nba_schedule import (
    NBA_TEAM_NAMES, parse_games_with_diagnostics, schedule_url,
)

ET = ZoneInfo("America/New_York")
MAX_DAYS = 4
MAX_BYTES = 6_000_000
MAX_ROWS = 100
CLOCK_TOLERANCE_SECONDS = 30 * 60
AGREEMENT = "sportsdataio_published_final_agrees_with_espn_research_only"


def fetch_original(day, key):
    """One bounded call per canonical Eastern game date; no retries on 401/429."""
    if not isinstance(key, str) or not key.strip():
        raise ValueError("missing_sportsdataio_subscription")
    req = Request(schedule_url(day), headers={
        "Ocp-Apim-Subscription-Key": key.strip(),
        "Accept": "application/json",
        "User-Agent": "FreddysPicksAI-Research/1.0",
    })
    with urlopen(req, timeout=14) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("oversized_sportsdataio_source")
    return raw


def failure(exc):
    if isinstance(exc, HTTPError):
        return "HTTP_" + str(exc.code)
    if isinstance(exc, (URLError, TimeoutError)):
        return type(exc).__name__
    return type(exc).__name__


def parse_published_finals(raw, day):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("bounded_original_bytes_required")
    if schedule_url(day) is None:
        raise ValueError("noncanonical_date")
    items = json.loads(raw)
    if not isinstance(items, list) or len(items) > MAX_ROWS or any(
            not isinstance(x, dict) for x in items):
        raise ValueError("unexpected_original_provider_response")
    parsed, diag = parse_games_with_diagnostics(items)
    originals = {str(x.get("GameID")): x for x in items
                 if type(x.get("GameID")) is int}
    results = []
    for g in parsed:
        start = g["start"]
        if start.astimezone(ET).date().isoformat() != day:
            continue
        payload = originals[g["id"]]
        status = payload.get("Status")
        if status not in ("Final", "F/OT", "F/2OT", "F/3OT"):
            state = "provider_not_final"
        elif payload.get("IsClosed") is False:
            state = "provider_final_but_not_closed"
        else:
            home = payload.get("HomeTeamScore")
            away = payload.get("AwayTeamScore")
            if (type(home) is not int or type(away) is not int
                    or not 0 <= home <= 999 or not 0 <= away <= 999
                    or home == away):
                state = "provider_final_score_invalid"
            else:
                state = "provider_final_score_available"
        results.append({
            "sportsdataio_game_id":g["id"],
            "start_utc": start,
            "home":nba_team_name(NBA_TEAM_NAMES[g["home"]]),
            "away":nba_team_name(NBA_TEAM_NAMES[g["away"]]),
            "home_score":payload.get("HomeTeamScore") if state ==
                         "provider_final_score_available" else None,
            "away_score":payload.get("AwayTeamScore") if state ==
                         "provider_final_score_available" else None,
            "status":state,
        })
    return results, diag


def corroborate(candidates, now, key=None, fetcher=None, max_days=MAX_DAYS,
                official_comparisons=None):
    if (not isinstance(candidates, list)
            or not isinstance(now, datetime) or now.tzinfo is None
            or type(max_days) is not int or not 1 <= max_days <= 6):
        raise ValueError("invalid_original_nba_research_request")
    now = now.astimezone(timezone.utc)
    if fetcher is None:
        fetcher = fetch_original
    originals = {}
    errors, by_date, parsed_by_day = {}, defaultdict(list), {}
    ids = set()
    for c in candidates:
        if (not isinstance(c, dict)
                or c.get("record_type") !=
                        "challenger_nba_history_candidate_review_only"
                or c.get("league") != "nba"
                or c.get("market_type") != "moneyline"
                or c.get("selection_type") != "home"
                or c.get("qualified_for_challenger_backtest") is not False
                or c.get("eligible_to_train_probability_model") is not False
                or c.get("independent_asof_review") is not False
                or c.get("independent_outcome_review") is not False
                or c.get("certified_prediction") is not False
                or c.get("bet_ready") is not False
                or c.get("champion_001_modified") is not False
                or c.get("model_probability") is not None
                or not isinstance(c.get("event_id"),str)
                or not c["event_id"].isdigit()
                or c["event_id"] in ids):
            raise ValueError("invalid_or_duplicate_unqualified_nba_candidate")
        ids.add(c["event_id"])
        start = timestamp(c["start_utc"])
        snapshot = timestamp(c["snapshot_utc"])
        posted = timestamp(c["outcome_verified_at_utc"])
        if not snapshot < start < posted <= now:
            raise ValueError("missing_true_historical_timestamp_order")
        by_date[start.astimezone(ET).date().isoformat()].append(c)
    official = {}
    for c in (official_comparisons or []):
        if (not isinstance(c,dict) or not isinstance(
                c.get("espn_research_event_id"),str)
                or c["espn_research_event_id"] in official
                or c.get("training_row_qualified") is not False
                or c.get("champion_001_modified") is not False):
            raise ValueError("untrusted_official_nba_result_record")
        official[c["espn_research_event_id"]] = c
    if official and set(official) != ids:
        raise ValueError("official_nba_result_crosswalk_incomplete")

    requested = sorted(by_date,reverse=True)[:max_days]
    for day in requested:
        if not isinstance(key,str) or not key.strip():
            errors[day] = "sportsdataio_secret_not_configured"
            parsed_by_day[day] = []
            continue
        try:
            raw = fetcher(day,key)
            games,diag = parse_published_finals(raw,day)
            captured = datetime.now(timezone.utc)
            # Original bytes contain licensed data; archive only in user-owned
            # workflow artifacts, never echo payload or subscription key.
            originals[day] = {
                "raw":raw, "source_url":schedule_url(day),
                "received_at_utc":captured.isoformat(),
                "sha256":hashlib.sha256(raw).hexdigest(),
                "parser_diagnostics":diag,
            }
            parsed_by_day[day] = games
        except (HTTPError,URLError,OSError,ValueError,TypeError,TimeoutError,
                KeyError,OverflowError,json.JSONDecodeError) as exc:
            errors[day] = failure(exc)
            parsed_by_day[day] = []
    counts = Counter()
    review = []
    for day in sorted(by_date):
        for c in by_date[day]:
            start=timestamp(c["start_utc"])
            espn_home=nba_team_name(c["home_team"])
            espn_away=nba_team_name(c["away_team"])
            matched=[x for x in parsed_by_day.get(day, [])
                     if x["home"]==espn_home and x["away"]==espn_away
                     and abs((x["start_utc"]-start).total_seconds()) <=
                         CLOCK_TOLERANCE_SECONDS]
            row={
                "record_type":"sportsdataio_nba_final_result_comparison_research_only",
                "espn_research_event_id":c["event_id"],
                "home_team":c["home_team"],"away_team":c["away_team"],
                "start_utc":start.isoformat(),
                "espn_published_score":c["published_score_only"],
                "source_type":"licensed_third_party_nba_result_not_league_operated",
                "source_date_et":day,
                "source_url":schedule_url(day) if day in requested else None,
                "source_original_bytes_sha256_self_attested":
                    originals[day]["sha256"] if day in originals else None,
                "source_received_at_utc":
                    originals[day]["received_at_utc"] if day in originals else None,
                "sportsdataio_game_id":None,
                "sportsdataio_published_score":None,
                "independently_verified_original_pregame_features":False,
                "independently_adjudicated_market_outcome":False,
                "bookmaker_moneyline_settlement_verified":False,
                "qualified_for_challenger_backtest":False,
                "certified_prediction":False,
                "bet_ready":False,"champion_001_modified":False,
            }
            if day not in requested:
                state="unrequested_date_bounded_api_budget"
            elif day in errors:
                state="sportsdataio_source_unavailable"
            elif len(matched)>1:
                state="ambiguous_sportsdataio_final_event_identity"
            elif not matched:
                state="sportsdataio_no_exact_final_game_identity"
            else:
                g=matched[0]
                row["sportsdataio_game_id"]=g["sportsdataio_game_id"]
                if g["status"]!="provider_final_score_available":
                    state=g["status"]
                else:
                    scores={"home":g["home_score"],"away":g["away_score"]}
                    row["sportsdataio_published_score"]=scores
                    league_cmp=official.get(c["event_id"])
                    if (league_cmp is not None
                            and league_cmp.get("crosscheck_status") ==
                                "nba_second_source_final_score_agrees_research_only"
                            and league_cmp.get("official_nba_score") != scores):
                        state="nba_operated_vs_sportsdataio_result_conflict"
                    elif scores != c["published_score_only"]:
                        state="sportsdataio_disagrees_with_espn_score_quarantined"
                    else:
                        state=AGREEMENT
            row["crosscheck_status"]=state
            counts[state]+=1
            review.append(row)
    report={
        "stage":"challenger_101_licensed_sportsdataio_nba_final_research_only",
        "review_candidates":len(candidates),
        "unique_eastern_result_dates":len(by_date),
        "source_days_attempted":len(requested),
        "source_days_succeeded":len(originals),
        "source_failures_by_day":dict(sorted(errors.items())),
        "source_days_not_requested_due_to_limit":max(0,len(by_date)-len(requested)),
        "source_original_bytes_sha256_by_day":{
            k:v["sha256"] for k,v in sorted(originals.items())},
        "source_parser_diagnostics_by_day":{
            k:v["parser_diagnostics"] for k,v in sorted(originals.items())},
        "third_party_published_final_score_agreements_research_only":
            counts[AGREEMENT],
        "by_status":dict(sorted(counts.items())),
        "native_training_qualified_games":0,
        "qualified_holdout_games":0,
        "official_league_outcomes_authenticated":0,
        "direct_draftkings_checkout_quotes_verified":0,
        "certified_champion_001_predictions":0,
        "certified_challenger_001_predictions":0,
        "certified_positive_ev_selections":0,
        "automated_bets_placed":0,
        "champion_001_modified":False,
        "warning":("SportsDataIO is a licensed third-party publisher. Agreeing "
                   "with ESPN score is research corroboration only, not original "
                   "NBA league adjudication, independent pregame feature source "
                   "authentication or bookmaker market settlement. Never train "
                   "or bet from these source records alone."),
    }
    return review,report,originals


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates",required=True)
    p.add_argument("--official-comparisons")
    p.add_argument("--output-dir",default="prospective_validation")
    p.add_argument("--max-days",type=int,default=MAX_DAYS)
    a=p.parse_args(argv)
    def lines(path):
        file=Path(path)
        if not file.is_file():
            raise FileNotFoundError(file)
        return [json.loads(s) for s in file.read_text(encoding="utf8").splitlines()
                if s.strip()]
    key=os.getenv("SPORTSDATAIO_API_KEY")
    rows,report,originals=corroborate(
        lines(a.candidates),datetime.now(timezone.utc),key,
        max_days=a.max_days,
        official_comparisons=lines(a.official_comparisons)
        if a.official_comparisons else None)
    dest=Path(a.output_dir)
    dest.mkdir(parents=True,exist_ok=True)
    raw_dir=dest/"sportsdataio_nba_original_final_source"
    raw_dir.mkdir(parents=True,exist_ok=True)
    for day,entry in originals.items():
        file=raw_dir/(day+".json")
        file.write_bytes(entry["raw"])
        if hashlib.sha256(file.read_bytes()).hexdigest()!=entry["sha256"]:
            raise ValueError("original_source_bytes_changed_on_archive")
    (dest/"nba_sportsdataio_published_final_review.jsonl").write_text(
        "".join(json.dumps(row,sort_keys=True)+"\n" for row in rows),
        encoding="utf8")
    (dest/"nba_sportsdataio_published_final_report.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps({
        "research_rows":len(rows),
        "games_agreeing_two_publishers_uncertified":
            report["third_party_published_final_score_agreements_research_only"],
        "source_failures":report["source_failures_by_day"],
        "certified_predictions":0,"champion_001_modified":False},sort_keys=True))


if __name__=="__main__":
    main()
