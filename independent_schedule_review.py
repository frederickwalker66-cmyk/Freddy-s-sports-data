"""Read-only independent public schedule corroboration for crossfeed research.
ESPN is distinct from either odds aggregator; this is NOT official league
player verification, a DraftKings checkout quote, or model certification.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from crossfeed_reconcile import event_key, parse_dt

SOURCES = {
    "nba": ("basketball", "nba"),
    "nfl": ("football", "nfl"),
    "mlb": ("baseball", "mlb"),
    "nhl": ("hockey", "nhl"),
    "ncaaf": ("football", "college-football"),
    "ncaab": ("basketball", "mens-college-basketball"),
    "mls": ("soccer", "usa.1"),
    "uefa_champions_league": ("soccer", "uefa.champions"),
}
BASE = "https://site.api.espn.com/apis/site/v2/sports"

def download_json(url):
    req = Request(url, headers={"User-Agent": "FreddysPicks-IndependentScheduleAudit/1.0",
                                "Accept": "application/json"})
    with urlopen(req, timeout=18) as stream:
        payload=stream.read(5_000_001)
    if len(payload)>5_000_000: raise ValueError("oversized schedule")
    result=json.loads(payload)
    if not isinstance(result,dict) or not isinstance(result.get("events"),list):
        raise ValueError("unexpected schedule data")
    return result


def download_json_original(url):
    """Return the parsed original ESPN response AND the untouched wire bytes."""
    req = Request(url, headers={"User-Agent": "FreddysPicks-IndependentScheduleAudit/1.0",
                                "Accept": "application/json"})
    with urlopen(req, timeout=18) as stream:
        raw = stream.read(5_000_001)
    if not 1 <= len(raw) <= 5_000_000:
        raise ValueError("invalid_or_oversized_original_espn_schedule")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ValueError("unexpected_original_espn_schedule")
    return payload, raw


MAX_LOOKAHEAD_DAYS = 7


def _parse_schedule_response(payload, league, url, requested_day, now):
    """Only future, uniquely identified ESPN games are pregame evidence."""
    if (not isinstance(payload, dict) or not isinstance(payload.get("events"), list)
            or len(payload["events"]) > 500):
        raise ValueError("invalid_or_oversized_espn_schedule_payload")
    eligible, identities = [], set()
    state_counts = Counter()
    invalid = 0
    wrong_eastern_date = 0
    started_before_response = 0
    for game in payload["events"]:
        if not isinstance(game, dict):
            invalid += 1
            continue
        raw_state = game.get("status")
        state = (raw_state.get("type", {}).get("state")
                 if isinstance(raw_state, dict)
                 and isinstance(raw_state.get("type"), dict) else None)
        state_counts[str(state or "unknown")[:24]] += 1
        comps = game.get("competitions")
        if not isinstance(comps, list) or not comps or not isinstance(comps[0], dict):
            invalid += 1
            continue
        obj = comps[0]
        home, away = None, None
        for competitor in obj.get("competitors", []):
            if not isinstance(competitor, dict):
                continue
            team = competitor.get("team")
            name = team.get("displayName") if isinstance(team, dict) else None
            if competitor.get("homeAway") == "home":
                home = name
            elif competitor.get("homeAway") == "away":
                away = name
        try:
            start = parse_dt(game.get("date") or obj.get("date"))
        except (TypeError, ValueError, AttributeError):
            invalid += 1
            continue
        if state != "pre":
            continue
        if start.astimezone(ZoneInfo("America/New_York")).date().isoformat() != requested_day:
            wrong_eastern_date += 1
            invalid += 1
            continue
        if start <= now:
            started_before_response += 1
            continue
        gid = str(game.get("id") or "")
        if (not gid.isdecimal() or not isinstance(home, str)
                or not isinstance(away, str) or not home.strip()
                or not away.strip() or home == away):
            invalid += 1
            continue
        if gid in identities:
            raise ValueError("duplicate_espn_future_game_identity_same_league_day")
        identities.add(gid)
        eligible.append({
            "league": league, "home_team": home, "away_team": away,
            "start_utc": start.isoformat(), "source_url": url,
            "provider_game_id": gid, "observed_at_utc": now.isoformat(),
            "status": "scheduled", "requested_date_et": requested_day,
        })
    return eligible, {
        "raw_events_listed": len(payload["events"]),
        "state_counts": dict(sorted(state_counts.items())),
        "invalid_or_unusable_listings": invalid,
        "wrong_requested_eastern_date_listings": wrong_eastern_date,
        "game_started_before_response_listings": started_before_response,
        "eligible_future_events": len(eligible),
    }


def ingest_schedule(date_et, fetch=download_json, now=None, lookahead_days=0,
                    clock=None, original_dir=None):
    """Source-only seven-day optional outlook, without probability or wager output.

    Default zero-day mode preserves older callers. With lookahead enabled,
    only leagues with NO valid pregame event today are searched on subsequent
    Eastern dates, stopping at the first date with future games. Explicitly
    preserve errors and negative-slate coverage rather than inventing games.
    """
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("schedule_capture_requires_aware_clock")
    now = now.astimezone(timezone.utc)
    if lookahead_days and clock is None:
        raise ValueError("prospective_multiday_scan_requires_actual_response_clock")
    clock = clock or (lambda: now)  # Legacy one-day diagnostic fixtures.
    def observed_now():
        response_at = clock()
        if not isinstance(response_at, datetime) or response_at.tzinfo is None:
            raise ValueError("schedule_response_clock_not_aware")
        response_at = response_at.astimezone(timezone.utc)
        if response_at < now:
            raise ValueError("schedule_response_clock_before_scan_started")
        return response_at
    if type(lookahead_days) is not int or not 0 <= lookahead_days <= MAX_LOOKAHEAD_DAYS:
        raise ValueError("schedule_lookahead_outside_bounded_window")
    day0 = date.fromisoformat(date_et)
    capture_eastern_day = now.astimezone(ZoneInfo("America/New_York")).date()
    if (lookahead_days and
            day0 != now.astimezone(ZoneInfo("America/New_York")).date()):
        raise ValueError("future_schedule_outlook_must_start_on_actual_eastern_today")
    original_root = Path(original_dir) if original_dir is not None else None
    if original_root is not None:
        original_root.mkdir(parents=True, exist_ok=True)
    result = {
        "collected_at_utc": now.isoformat(), "date_et": date_et,
        "lookahead_days_requested": lookahead_days,
        "original_source_bytes_capture_enabled": original_root is not None,
        "events": [], "sources": {},
    }
    for league, (sport, competition) in SOURCES.items():
        events, queries = [], []
        seen = set()
        for delta in range(lookahead_days + 1):
            requested_day = (day0 + timedelta(days=delta)).isoformat()
            url = (BASE + "/" + sport + "/" + competition + "/scoreboard?" +
                   urlencode({"dates": requested_day.replace("-", ""), "limit": 500}))
            request_started = None
            try:
                request_started = observed_now()
                response = fetch(url)
                response_observed = observed_now()
                raw = None
                if original_root is None:
                    payload = response
                else:
                    if (not isinstance(response, tuple) or len(response) != 2
                            or not isinstance(response[0], dict)
                            or not isinstance(response[1], bytes)
                            or not 1 <= len(response[1]) <= 5_000_000):
                        raise ValueError("original_espn_schedule_bytes_not_available")
                    payload, raw = response
                    if json.loads(raw) != payload:
                        raise ValueError("original_espn_schedule_bytes_differ_from_parsed_response")
                if response_observed < request_started:
                    raise ValueError("schedule_source_clock_regressed_during_request")
                # A single-day crosswalk may query a FUTURE Eastern fixture
                # date. Compare response-time to the actual capture day, not
                # to the requested fixture date: requiring those to match
                # incorrectly quarantines every tomorrow/Sunday schedule.
                if (response_observed.astimezone(ZoneInfo("America/New_York")).date()
                        != capture_eastern_day):
                    raise ValueError("prospective_scan_crossed_eastern_calendar_day")
                parsed, counts = _parse_schedule_response(
                    payload, league, url, requested_day, response_observed)
                for item in parsed:
                    key = item["provider_game_id"]
                    if key in seen:
                        raise ValueError("duplicate_future_game_across_checked_days")
                    seen.add(key)
                raw_receipt = {}
                if original_root is not None:
                    original_name = league + "_" + requested_day.replace("-", "") + ".json"
                    with (original_root / original_name).open("xb") as writer:
                        writer.write(raw)
                    checksum = hashlib.sha256(raw).hexdigest()
                    raw_receipt = {
                        "original_source_file": original_name,
                        "original_source_sha256": checksum,
                        "original_source_bytes": len(raw),
                    }
                    for event in parsed:
                        event["source_original_sha256"] = checksum
                events.extend(parsed)
                queries.append({
                    "date_et": requested_day, "status": "retrieved",
                    **raw_receipt,
                    "source_url": url,
                    "request_started_at_utc": request_started.isoformat(),
                    "response_observed_at_utc": response_observed.isoformat(),
                    **counts,
                })
                if parsed:
                    break
            except (OSError, ValueError, TypeError, KeyError,
                    UnicodeError, OverflowError, TimeoutError) as exc:
                queries.append({
                    "date_et": requested_day, "status": "unavailable",
                    "source_url": url, "reason": type(exc).__name__,
                    "request_started_at_utc": (
                        request_started.isoformat() if request_started else None),
                    "request_failed_at_utc": observed_now().isoformat(),
                })
        valid_days = sum(x["status"] == "retrieved" for x in queries)
        failed_days = len(queries) - valid_days
        raw_games = sum(x.get("raw_events_listed", 0) for x in queries)
        if events:
            diagnosis = "future_game_source_observed"
        elif not valid_days:
            diagnosis = "schedule_source_unavailable_for_all_checked_dates"
        elif failed_days:
            diagnosis = "future_game_unknown_due_to_partial_source_failures"
        elif raw_games == 0:
            diagnosis = "no_games_listed_on_all_checked_dates"
        else:
            diagnosis = "games_listed_but_none_future_eligible"
        status = "retrieved" if valid_days else "unavailable"
        result["sources"][league] = {
            "status": status,
            "source_url": queries[0]["source_url"],
            "scheduled_events": len(events),
            "first_day_status": queries[0]["status"],
            "first_day_raw_events": queries[0].get("raw_events_listed"),
            "days_checked": len(queries),
            "days_retrieved": valid_days,
            "days_unavailable": failed_days,
            "raw_game_listings_across_checked_dates": raw_games,
            "diagnosis": diagnosis,
            "lookahead": queries,
        }
        if not valid_days:
            result["sources"][league]["reason"] = queries[0]["reason"]
        result["events"].extend(events)
    return result


def corroborate(agree,disagree,schedule,now=None):
    now=now or datetime.now(timezone.utc)
    events=defaultdict(list)
    for e in schedule.get("events",[]):
        key=event_key(e)
        if key:
            try: start=parse_dt(e["start_utc"])
            except (KeyError,ValueError,TypeError):continue
            events[key].append((e,start))
    match_count=0
    checked_events=set()
    by_reason=Counter()
    output=[]
    for row in agree+disagree:
        current=dict(row)
        key=event_key(row)
        choices=[]
        try:
            sharp_time=parse_dt(row["event_time_sharpapi"])
            sgo_time=parse_dt(row["event_time_sgo"])
            for event,start in events.get(key,[]):
                if abs((start-sharp_time).total_seconds())<=3600 and abs((start-sgo_time).total_seconds())<=3600:
                    choices.append((event,start))
        except (KeyError,TypeError,ValueError):
            choices=[]
        matched=False
        reason="independent_schedule_missing_or_ambiguous"
        if len(choices)==1:
            event,start=choices[0]
            checked_events.add((event["league"],event["home_team"],event["away_team"],start))
            if abs((start-sharp_time).total_seconds())<=60 and abs((start-sgo_time).total_seconds())<=60:
                matched=True
                reason="schedule_corrobated" # neither direct sportsbook nor verified league identity
            else:
                reason="provider_start_disagrees_with_independent_schedule"
        current["independent_public_schedule_corrobated"]=matched
        current["independent_schedule_source"]="ESPN" if len(choices)==1 else None
        current["schedule_rejection_reason"]=None if matched else reason
        current["official_league_schedule_verified"]=False
        current["draftkings_direct_price_verified"]=False
        current["model_probability"]=None
        current["positive_ev_certified"]=False
        current["bet_ready"]=False
        output.append(current)
        match_count+=int(matched)
        by_reason[reason]+=1
    report={
        "generated_at_utc":now.isoformat(),
        "independent_public_scheduled_events_retrieved":len(schedule.get("events",[])),
        "independent_source_status":schedule.get("sources",{}),
        "crossfeed_price_pairs_reviewed":len(output),
        "public_schedule_corrobated_price_pairs":match_count,
        "schedule_unverified_price_pairs":len(output)-match_count,
        "schedule_failure_reasons":dict(by_reason),
        "independent_price_verifications":0,
        "verified_model_probabilities":0,
        "certified_champion_001_predictions":0,
        "certified_positive_ev_bets":0,
        "bet_ready_selections":0,
        "champion_001_modified":False,
        "warning":"Public ESPN schedule corroboration is not official source IDs, actual lineup clearance, direct DraftKings checkout, or a probability model."
    }
    return output,report

def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf8").splitlines() if x.strip()]

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--crossfeed-dir",required=True)
    p.add_argument("--output-dir",default="schedule_review")
    p.add_argument("--date-et",default=None)
    args=p.parse_args(argv)
    now=datetime.now(timezone.utc)
    day=args.date_et or now.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    schedule=ingest_schedule(day,now=now)
    parent=Path(args.crossfeed_dir)
    agree=read_jsonl(parent/"matching_prices.jsonl")
    disagree=read_jsonl(parent/"different_prices.jsonl")
    rows,report=corroborate(agree,disagree,schedule,now)
    dest=Path(args.output_dir);dest.mkdir(parents=True,exist_ok=True)
    (dest/"public_schedule_evidence.json").write_text(json.dumps(schedule,indent=2)+"\n",encoding="utf8")
    (dest/"schedule_review.jsonl").write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in rows),encoding="utf8")
    (dest/"report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
