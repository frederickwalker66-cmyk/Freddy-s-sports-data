"""Read-only independent public schedule corroboration for crossfeed research.
ESPN is distinct from either odds aggregator; this is NOT official league
player verification, a DraftKings checkout quote, or model certification.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
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

def ingest_schedule(date_et, fetch=download_json, now=None):
    now=now or datetime.now(timezone.utc)
    result={"collected_at_utc":now.isoformat(),"date_et":date_et,"events":[],"sources":{}}
    for league,(sport,competition) in SOURCES.items():
        url=BASE+"/"+sport+"/"+competition+"/scoreboard?"+urlencode({"dates":date_et.replace("-",""),"limit":500})
        try:
            payload=fetch(url)
            if not isinstance(payload,dict) or not isinstance(payload.get("events"),list):
                raise ValueError("invalid schedule payload")
            valid=0
            for game in payload["events"][:500]:
                if not isinstance(game,dict):continue
                comps=game.get("competitions")
                if not isinstance(comps,list) or not comps:continue
                obj=comps[0]
                if not isinstance(obj,dict):continue
                home,away=None,None
                for competitor in obj.get("competitors",[]):
                    if not isinstance(competitor,dict):continue
                    team=competitor.get("team")
                    name=team.get("displayName") if isinstance(team,dict) else None
                    if competitor.get("homeAway")=="home":home=name
                    elif competitor.get("homeAway")=="away":away=name
                try: start=parse_dt(game.get("date") or obj.get("date"))
                except (TypeError,ValueError,AttributeError):continue
                state=game.get("status",{}).get("type",{}).get("state")
                if not home or not away or state!="pre":continue
                if start<=now:continue
                result["events"].append({
                    "league":league,"home_team":home,"away_team":away,
                    "start_utc":start.isoformat(),"source_url":url,
                    "provider_game_id":str(game.get("id") or ""),
                    "observed_at_utc":now.isoformat(),"status":"scheduled"
                })
                valid+=1
            result["sources"][league]={"status":"retrieved","source_url":url,"scheduled_events":valid}
        except Exception as exc:
            result["sources"][league]={"status":"unavailable","reason":type(exc).__name__}
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
