"""Season-isolated player prop/stat last-five and last-ten research for 8 leagues.

Inputs are *verified-shape original-source historical boxscore rows*,
never odds-provider player IDs. An eligible appearance needs an observed
final boxscore >=48h after event start, captured before the forecast,
inside the CURRENT LEAGUE season search anchor, and not DNP.
Historical line hit rates are descriptive, NOT model probabilities / EV.

Sport-specific coverage is strictly feature-by-feature: unknown or
unavailable data is NULL, never 0 or inferred from market prices.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import mean
from zoneinfo import ZoneInfo

from historical_outcomes import LEAGUES, parse_time
from v8_all_sports_season_form import season_anchor, MATURITY_HOURS

ESPN_SUMMARY_ROOT = "https://site.api.espn.com/apis/site/v2/sports/"
SPORT_PATH = {
    "nba":"basketball/nba",
    "ncaab":"basketball/mens-college-basketball",
    "nfl":"football/nfl",
    "ncaaf":"football/college-football",
    "mlb":"baseball/mlb",
    "nhl":"hockey/nhl",
    "mls":"soccer/usa.1",
    "uefa_champions_league":"soccer/uefa.champions",
}
STATS = {
    "nba": ("minutes","points","rebounds","assists","threes_made","steals","blocks","turnovers"),
    "ncaab": ("minutes","points","rebounds","assists","threes_made","steals","blocks","turnovers"),
    "nfl": ("passing_yards","passing_touchdowns","passing_interceptions","passing_completions",
             "passing_attempts","rushing_yards","rushing_attempts","rushing_touchdowns",
             "receiving_yards","receptions","receiving_targets","receiving_touchdowns"),
    "ncaaf": ("passing_yards","passing_touchdowns","passing_interceptions","passing_completions",
               "passing_attempts","rushing_yards","rushing_attempts","rushing_touchdowns",
               "receiving_yards","receptions","receiving_targets","receiving_touchdowns"),
    "mlb": ("hits","runs","rbis","home_runs","total_bases","stolen_bases",
            "batting_walks","batting_strikeouts","pitching_strikeouts","pitching_outs",
            "hits_allowed","earned_runs","walks_allowed"),
    "nhl": ("goals","assists","points","shots_on_goal","blocked_shots","saves"),
    "mls": ("goals","assists","shots","shots_on_target","saves","minutes"),
    "uefa_champions_league": ("goals","assists","shots","shots_on_target","saves","minutes"),
}
COMPOSITES = {
    "nba": {"pra":("points","rebounds","assists"),
            "points_rebounds":("points","rebounds"),
            "points_assists":("points","assists"),
            "rebounds_assists":("rebounds","assists")},
    "ncaab": {"pra":("points","rebounds","assists")},
}
MAX_ROWS = 300_000
MAX_TARGETS = 4_000


def _derived(row, league, stat):
    if stat in STATS[league]:
        return row["stats"].get(stat)
    parts = COMPOSITES.get(league, {}).get(stat)
    if parts:
        values = [row["stats"].get(x) for x in parts]
        if all(x is not None for x in values):
            return sum(values)
    return None


def _window(rows, league, n, coverage_complete):
    latest = rows[-n:]
    eligible = len(latest) == n and coverage_complete
    keys = STATS[league]+tuple(COMPOSITES.get(league, {}))
    avgs = {}
    for key in keys:
        vals = [_derived(r,league,key) for r in latest]
        avgs[key] = round(mean(vals),4) if eligible and all(
            type(v) in (int,float) for v in vals) else None
    return {
        "requested_appearances": n,
        "matured_observed_appearances": len(latest),
        "complete_season_scoreboard_source_days": coverage_complete,
        "complete_window_for_sport_stats": eligible,
        "season_to_date_stats_last_window_average": avgs,
        "actual_historical_espn_event_ids": [x["event_id"] for x in latest],
        "betting_model_probability": None,
        "calibrated_prop_odds": None,
    }


def build_all_player_form(rows, upcoming, as_of_utc, coverage_by_league=None):
    asof=parse_time(as_of_utc.isoformat() if isinstance(as_of_utc,datetime) else as_of_utc)
    if (not isinstance(rows,list) or not isinstance(upcoming,list)
            or len(rows)>MAX_ROWS or len(upcoming)>MAX_TARGETS):
        raise ValueError("multisport_player_history_or_targets_budget_invalid")
    coverage_by_league=coverage_by_league or {}
    by_player=defaultdict(list)
    seen=set()
    rejected=Counter()
    for row in rows:
        if (not isinstance(row,dict) or row.get("league") not in LEAGUES
                or row.get("published_boxscore_research_only") is not True
                or row.get("qualified_for_player_prop_training") is not False
                or row.get("independently_verified_player_stats") is not False
                or row.get("champion_001_modified") is not False):
            raise ValueError("untrusted_multisport_player_box")
        league=row["league"]
        eid,pid,tid=row.get("espn_event_id"),row.get("espn_player_id"),row.get("espn_team_id")
        if (not isinstance(eid,str) or not eid.isdecimal()
                or not isinstance(pid,str) or not pid.isdecimal()
                or not isinstance(tid,str) or not tid.isdecimal()
                or row.get("source_url")!=ESPN_SUMMARY_ROOT+SPORT_PATH[league]+"/summary?event="+eid):
            raise ValueError("invalid_ESPN_player_summary_identity")
        if (league,eid,pid) in seen:
            raise ValueError("duplicate_ESPN_player_box_for_event")
        seen.add((league,eid,pid))
        retrieved=parse_time(row["retrieved_at_utc"])
        started=parse_time(row["event_start_utc"])
        if not started < retrieved <= asof:
            raise ValueError("player_final_observed_out_of_order_or_future")
        anchor,_=season_anchor(league,asof)
        if started.astimezone(ZoneInfo("America/New_York")).date()<anchor:
            rejected["other_season"]+=1
            continue
        if row.get("season_type") != 2:
            rejected["not_regular_season"]+=1
            continue
        if row.get("did_not_play") is True:
            rejected["DNP_not_an_appearance"]+=1
            continue
        if row.get("did_not_play") is not False:
            raise ValueError("unknown_player_participation")
        if started+timedelta(hours=MATURITY_HOURS)>asof:
            rejected["result_not_matured_48h"]+=1
            continue
        stats=row.get("stats")
        if not isinstance(stats,dict) or set(stats)-set(STATS[league]):
            raise ValueError("player_stats_not_in_sport_schema")
        if not stats:
            rejected["no_parsed_sport_stats"]+=1
            continue
        for k,v in stats.items():
            if (v is not None and
                    (type(v) not in (int,float)
                     or not -200 <=v<=3000
                     or (v<0 and k not in (
                         "passing_yards","rushing_yards","receiving_yards")))):
                raise ValueError("player_sport_stat_value_invalid")
        if all(v is None for v in stats.values()):
            rejected["all_sport_stats_unavailable"]+=1
            continue
        by_player[(league,pid)].append({
            "event_id":eid,"start":started,"team_id":tid,
            "stats":dict(stats),
        })
    for v in by_player.values():
        v.sort(key=lambda q:(q["start"],q["event_id"]))
    results={}
    for q in upcoming:
        if not isinstance(q,dict) or q.get("league") not in LEAGUES:
            raise ValueError("invalid_upcoming_multisport_player")
        lg,eid,pid=q["league"],q.get("espn_event_id"),q.get("espn_player_id")
        if (not isinstance(eid,str) or not eid.isdecimal()
                or not isinstance(pid,str) or not pid.isdecimal()):
            raise ValueError("invalid_upcoming_ESPN_player_event")
        tip=parse_time(q["start_utc"])
        if tip<=asof:
            continue
        k=f"{lg}:{eid}:{pid}"
        if k in results:
            raise ValueError("duplicate_upcoming_player_event")
        anchor,_=season_anchor(lg,asof)
        league_coverage=coverage_by_league.get(lg,{})
        day_ids=league_coverage.get("source_days_confirmed_et",[])
        expected=(asof.astimezone(ZoneInfo("America/New_York")).date()-anchor).days
        full=(league_coverage.get("conservative_collection_anchor_et")==anchor.isoformat()
              and isinstance(day_ids,list) and len(set(day_ids))==len(day_ids)==expected
              and not league_coverage.get("conflicting_game_event_ids")
              and league_coverage.get("source_days_failed_in_latest_collection",0)==0)
        history=[x for x in by_player[(lg,pid)] if x["start"]<tip]
        results[k]={
            "league":lg,"scheduled_event_id":eid,"historical_espn_player_id":pid,
            "historical_team_ids_not_current_roster_validation":sorted({
                x["team_id"] for x in history}),
            "season_collection_anchor_not_official_opening_day_et":anchor.isoformat(),
            "last5":_window(history,lg,5,full),
            "last10":_window(history,lg,10,full),
            "as_of_utc":asof.isoformat(),
            "current_roster_status_verified":False,
            "bookmaker_player_ID_crosswalk_verified":False,
            "independent_prop_model_probabilities":None,
            "source_player_stats_independently_corrobated":False,
            "certified_positive_ev_bets":0,"champion_001_modified":False,
        }
    return {
        "report_type":"EIGHT_SPORT_PLAYER_LAST_5_AND_LAST_10_RESEARCH",
        "as_of_utc":asof.isoformat(),
        "historical_mature_player_appearance_rows":sum(map(len,by_player.values())),
        "player_targets":len(results),
        "players_by_event":results,
        "rejected_history_reasons":dict(sorted(rejected.items())),
        "all_leagues_stat_field_schemas_supported":list(LEAGUES),
        "all_leagues_stat_source_coverage_verified":False,
        "player_stat_source_is_not_sportsbook_odds":True,
        "calibrated_model_generated_player_prop_probabilities":0,
        "certified_positive_ev_bets":0,
        "champion_001_modified":False,
    }


def historical_line_hits(player_record,stat,line,side,n):
    """Descriptive result versus supplied line, never independently generated p.

    Accepts the original source-box history for one player; never aggregate
    bookmaker ID directly. Pushes are excluded from conditional win/loss %.
    """
    if type(line) not in (int,float) or side not in ("over","under") or n not in (5,10):
        raise ValueError("invalid_exact_player_prop_line")
    if len(player_record)<n:
        return {"sample_size":len(player_record),
                "complete_window":False,"wins":None,"losses":None,"pushes":None,
                "descriptive_hit_rate_not_model_probability":None}
    recent=player_record[-n:]
    values=[_derived(x["row"],x["league"],stat) for x in recent]
    if any(v is None for v in values):
        return {"sample_size":n,"complete_window":False,"wins":None,
                "losses":None,"pushes":None,
                "descriptive_hit_rate_not_model_probability":None}
    wins=sum((v>line if side=="over" else v<line) for v in values)
    pushes=sum(v==line for v in values)
    valid=n-pushes
    return {"sample_size":n,"complete_window":True,"wins":wins,
            "losses":valid-wins,"pushes":pushes,
            "descriptive_hit_rate_not_model_probability":
                round(wins/valid,6) if valid else None}
