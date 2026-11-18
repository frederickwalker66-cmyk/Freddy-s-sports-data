"""Read-only six-role pregame review based on archived GitHub evidence.
No provider calls, generated model probabilities, wagering, or model changes.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo
from v9_sharp_edge_evidence_board import ROLE_NAMES, stamped, text_safe

EASTERN = ZoneInfo("America/New_York")
LEAGUES = frozenset(("nba","nfl","nhl","mlb","ncaaf","ncaab","mls","uefa_champions_league"))
MARKETS = ("moneyline","spread","over_under","player_props","player_combos","four_six_eight_leg_parlays")


def source_age(source, clock):
    if not isinstance(source, dict) or source.get("status") != "READ_EXISTING_ARCHIVE_ONLY":
        return None, "NO_SOURCE_ARCHIVE"
    stamp = stamped(source.get("run_created_at_utc"))
    if stamp is None:
        return None, "SOURCE_TIMESTAMP_MISSING"
    minutes = round((clock-stamp).total_seconds()/60, 1)
    if minutes < -5:
        return minutes, "SOURCE_TIMESTAMP_IN_FUTURE"
    if minutes > 120:
        return minutes, "STALE_SOURCE_ARCHIVE"
    return minutes, "RECENT_ARCHIVED_RESEARCH_ONLY"


def analyze(board, schedule=None, *, clock=None, lookahead_minutes=90):
    if not isinstance(board, dict):
        raise ValueError("sharp_evidence_board_required")
    if type(lookahead_minutes) is not int or not 1 <= lookahead_minutes <= 720:
        raise ValueError("invalid_window")
    clock = clock or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("clock_must_be_aware")
    clock = clock.astimezone(timezone.utc)
    source = board.get("source_manifest", {}).get("schedule")
    age, state = source_age(source, clock)
    valid_schedule = isinstance(schedule, dict) and isinstance(schedule.get("events"), list)
    can_review = valid_schedule and state == "RECENT_ARCHIVED_RESEARCH_ONLY"
    games, rejected, seen = [], 0, set()
    if can_review:
        for e in schedule["events"][:15000]:
            if not isinstance(e, dict) or e.get("status") != "scheduled":
                rejected += 1
                continue
            start = stamped(e.get("start_utc"))
            observed = stamped(e.get("observed_at_utc"))
            eid = e.get("provider_game_id")
            league, away, home = e.get("league"), e.get("away_team"), e.get("home_team")
            if (league not in LEAGUES or not isinstance(away,str) or not away.strip()
                or not isinstance(home,str) or not home.strip() or away==home
                or not isinstance(eid,(str,int)) or not str(eid).isdigit()
                or not start or not observed or observed>=start
                or observed > clock+timedelta(minutes=5)):
                rejected += 1
                continue
            mins=(start-clock).total_seconds()/60
            if not 0 < mins <= lookahead_minutes:
                continue
            key=(league,str(eid))
            if key in seen:
                rejected+=1
                continue
            seen.add(key)
            games.append({
                "league":league.upper(),"event_id":str(eid),
                "game":f"{away} @ {home}",
                "start_eastern":start.astimezone(EASTERN).isoformat(),
                "start_utc":start.isoformat(),"source_observed_utc":observed.isoformat(),
                "minutes_to_start":round(mins,1),
                "source_run_id":source.get("run_id"),
                "source_run_url":source.get("run_url"),
                "markets_reviewed":list(MARKETS),
                "proposed_prediction":None,"model_probability":None,
                "verified_odds":None,"certified_ev":None,
                "decision":"HOLD_UNVERIFIED"
            })
    games.sort(key=lambda g:(g["start_utc"],g["league"],g["event_id"]))
    gates={
        "native_champion_probabilities":board.get("certified_native_model_probability_count_by_this_board") or 0,
        "executable_draftkings_quotes":board.get("verified_executable_draftkings_quote_count_by_this_board") or 0,
        "independently_certified_ev":board.get("certified_positive_ev_count_by_this_board") or 0,
        "qualified_correlated_parlays":board.get("qualified_parlays_by_this_board") or 0,
        "verified_sharp_money":board.get("independently_verified_sharp_handle_count_by_this_board") or 0,
        "verified_clv":board.get("verified_entry_close_clv_by_this_board") or 0,
    }
    notes=(
        f"Meeting collected {len(games)} source-listed games starting within {lookahead_minutes} minutes.",
        f"Eight-sport source archive status: {state}; capture age: {age} minutes.",
        "Research moneylines, totals, props and combos are not certified Champion predictions.",
        "No 4/6/8-leg parlay is qualified without separately verified legs and joint probability.",
        "Veto release if exact quote, lineup, native forecast or calibration is unverified.",
        "Retain source workflow run ID, archived timestamps and explicit zero-certification audit.",
    )
    roles=[{"employee":name,"decision":"HOLD_RESEARCH_ONLY","finding":notes[i]}
           for i,name in enumerate(ROLE_NAMES)]
    status=("SOURCE_UNAVAILABLE_OR_STALE_HOLD" if not can_review else
            "NO_UPCOMING_GAME_HOLD" if not games else "PREGAME_MEETING_RESEARCH_HOLD")
    return {
        "title":"Freddy's Picks AI V9 — Six Staff Pregame Meeting",
        "meeting_utc":clock.isoformat(),
        "meeting_eastern":clock.astimezone(EASTERN).isoformat(),
        "window_minutes":lookahead_minutes,"status":status,
        "source_status":state,"source_age_minutes":age,
        "source_run_id":source.get("run_id") if isinstance(source,dict) else None,
        "source_run_url":source.get("run_url") if isinstance(source,dict) else None,
        "rejected_source_rows":rejected,"six_staff":roles,"markets":list(MARKETS),
        "pregame_games":games,"final_prediction":None,
        "nba_full_slate_games_displayed":sum(g["league"] == "NBA" for g in games),
        "nba_requested_markets":["moneyline","spread","game_total","player_points",
                                 "player_rebounds","player_assists","three_pointers",
                                 "player_PR","player_PA","player_RA","player_PRA"],
        "nba_injuries_and_final_lineups_verified_here":False,
        "eight_leg_required_certified_legs":8,
        "eight_leg_certified_legs":0,
        "eight_leg_lock_decision":"NO_LOCK_HOLD",
        "ceo_take_or_pass":"PASS_UNTIL_INDEPENDENT_PROOF",
        "final_team_decision":"HOLD","certified_bets_or_parlays":0,
        "evidence_gate_counts_board_level_only":gates,
        "automated_bets":0,"paid_api_calls":0,"shadow_stake_usd":0,
        "champion_001_modified":False,
        "warning":"Best-effort GitHub scheduling. Archived ESPN source is not independent official lineup, certified model output or executable sportsbook quote."
    }


def markdown(r):
    lines=["# Freddy's Picks AI V9 — Pregame Staff Meeting","",
        f"Meeting Eastern: **{text_safe(r['meeting_eastern'])}**",
        f"Status: **{r['status']}**; next **{r['window_minutes']} minutes**",
        f"Source: **{r['source_status']}**; age {r['source_age_minutes']} minutes",
        "","## Final decision: HOLD — no certified prediction released","",
        "| Employee | Decision | Finding |","|---|---|---|"]
    for s in r["six_staff"]:
        lines.append(f"| {text_safe(s['employee'])} | HOLD | {text_safe(s['finding'])} |")
    lines.extend(["",
                  "## CEO pregame eight-leg verdict: NO LOCK / DO NOT PLACE",
                  "Required: eight exact-market certified positive-EV legs, final injury/lineup checks, "
                  "joint parlay probability and correlation, authenticated six-specialist votes, "
                  "and separate CEO signoff. None of those can be assumed from a successful workflow.",
                  "",
                  f"NBA games in upcoming window: **{r['nba_full_slate_games_displayed']}**. "
                  "Eight-leg certified legs: **0 / 8**.",
                  "Injuries and expected lineups: **not independently matched to players in this run**; "
                  "review official updates before any decision.",
                  "Exact DraftKings quotes, frozen Champion-001 market probabilities, "
                  "model-derived EV, and qualified parlay joint probability: **N/A / HOLD**.",
                  "",
                  "## Upcoming games — researched, not approved","",
                  "| League | Matchup | Start Eastern | Minutes away | Decision |",
                  "|---|---|---|---:|---|"])
    for g in r["pregame_games"]:
        lines.append(f"| {text_safe(g['league'])} | {text_safe(g['game'])} | "
                     f"{text_safe(g['start_eastern'])} | {g['minutes_to_start']} | HOLD |")
    if not r["pregame_games"]:
        lines.append("| — | None verified in the window | — | — | HOLD |")
    lines.extend(["", "## NBA complete market scope — verification dashboard",
                  "For every NBA game above: moneyline, spread, game total; points, rebounds, "
                  "assists, three-pointers, PR, PA, RA, and PRA are requested research markets. "
                  "Individual prices or model predictions appear only when independently sourced "
                  "and attributable to that exact event and market. Missing information is N/A, "
                  "not a 0% probability or an Under/Over recommendation.",
                  "", "## Evidence gate counts — global only, not game certifications"])
    lines.extend(f"- {text_safe(k)}: {v}" for k,v in r["evidence_gate_counts_board_level_only"].items())
    if r["source_run_url"]:
        lines.append("Archived source run: "+text_safe(r["source_run_url"],240))
    lines.extend(["","Champion-001 unchanged; no paid API calls or wagers; zero-dollar research stake.",
                  r["warning"],""])
    return "\n".join(lines)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board-json",required=True)
    parser.add_argument("--schedule-json")
    parser.add_argument("--cache-root",default="v9_results/_cached_source/schedule")
    parser.add_argument("--output-dir",default="v9_results")
    parser.add_argument("--lookahead-minutes",type=int,default=90)
    args=parser.parse_args(argv)
    board=json.loads(Path(args.board_json).read_text(encoding="utf-8"))
    path=Path(args.schedule_json) if args.schedule_json else None
    if path is None:
        s=board.get("source_manifest",{}).get("schedule",{})
        run_id=s.get("run_id") if isinstance(s,dict) else None
        if type(run_id) is int and run_id>0:
            path=Path(args.cache_root)/str(run_id)/"espn_schedule_capture.json"
    schedule=None
    if path and path.is_file() and path.stat().st_size<15000000:
        try:
            schedule=json.loads(path.read_text(encoding="utf-8"))
        except (ValueError,UnicodeDecodeError,OSError):
            schedule=None
    report=analyze(board,schedule,lookahead_minutes=args.lookahead_minutes)
    root=Path(args.output_dir)
    root.mkdir(parents=True,exist_ok=True)
    (root/"V9_PREGAME_MEETING.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    page=markdown(report)
    (root/"V9_PREGAME_MEETING.md").write_text(page,encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a",encoding="utf-8") as f:
            f.write(page+"\n")
    print(json.dumps({"status":report["status"],"games":len(report["pregame_games"]),
                      "final_decision":report["final_team_decision"],"wagers":0}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
