"""Freddy's Picks AI V8 — ONE command, full research stack for every sport.

Entry points: run_nba, run_nfl, run_nhl, run_mlb, run_ncaaf, run_ncaab,
run_mls, run_uefa, run_nba_nfl, run_sports / run_all.
One invocation yields: available pregame predictions, source probabilities,
team/player season L5/L10, game/prop quotes, repricing/Sharp Edge, exact
market calibration readiness, source/price integrity, CLV evidence status,
parlay preflight and best-bet eligibility.

CORE SAFETY: archived bookmaker implied percentages are NEVER substituted
for native model p. Previous market repricings are NOT evidence of a sharp
wager or real CLV. NBA/NFL historical-price source coverage is NOT eight-
sport live-book coverage. Unavailable sports/models are N/A and HOLD.
Champion-001 remains untouched; stakes $0 and no trades.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from v8_sharp_archive import summarize_sharp_archive
from v8_sharp_player_props import summarize_player_props
from v8_sharp_game_markets import summarize_full_game_markets
from v8_sharp_calibration_dashboard import dashboard as sharp_calibration_dashboard
from v8_forward_calibration_view import read_calibration
from v8_forward_leaderboard_view import read_leaderboard
from v8_betting_readiness import audit_betting_readiness
from v8_season_artifact_view import review as review_season_artifacts
from v8_sgo_research import audit_source_archive
from v8_clv_reconciliation import reconcile as reconcile_local_clv

ALL = ("nba","nfl","mlb","nhl","ncaaf","ncaab","mls","uefa_champions_league")
COMMAND_TO_SPORT = {
    "run_nba": ("nba",), "run_nba_best_bets": ("nba",),
    "run_nfl": ("nfl",), "run_nhl": ("nhl",), "run_mlb": ("mlb",),
    "run_ncaaf": ("ncaaf",), "run_ncaab": ("ncaab",),
    "run_mls": ("mls",), "run_uefa": ("uefa_champions_league",),
    "run_nba_nfl": ("nba","nfl"),
    "run_sports": ALL, "run_all": ALL,
}
PRIMARY = {
    "nba":"run_nba_best_bets", "nfl":"run_nfl_forward",
    "nhl":"run_nhl_forward", "mlb":"run_mlb", "ncaaf":"run_ncaaf",
    "ncaab":"run_ncaab", "mls":"run_mls", "uefa_champions_league":"run_uefa",
}
PRICE_SPORTS = frozenset(("nba","nfl"))


def _check_report(data, *, requires_explicit_champion_flag=False):
    if (not isinstance(data,dict)
            or (requires_explicit_champion_flag and
                data.get("champion_001_modified") is not False)
            or data.get("champion_001_modified", False) is not False
            or data.get("certified_positive_ev_bets") != 0
            or data.get("money_wagered_usd", 0) != 0):
        raise ValueError("full_stack_component_report_unsafe")
    return data


def _project_research(reports, scope, limit=60):
    result=[]
    for league in scope:
        source=reports.get(league)
        if source is None:
            continue
        rows=source.get("research_forward_probability_rows") or []
        if not isinstance(rows,list) or len(rows)>10000:
            raise ValueError("full_stack_forward_record_budget")
        for row in rows:
            if not isinstance(row,dict):
                raise ValueError("full_stack_invalid_forward_row")
            if league not in ("nba","nfl","nhl"):
                raise ValueError("unexpected_model_p_for_untrained_sport")
            p=row.get("model_probability_home_win_research_only")
            if type(p) not in (float,int) or not 0<p<1:
                raise ValueError("invalid_forward_research_probability")
            game=row.get("espn_event_id")
            if not isinstance(game,str) or not game:
                raise ValueError("missing_forecast_game_identity")
            result.append({
                "league":league, "espn_event_id":game,
                "home_team":row.get("home_team"),
                "away_team":row.get("away_team"),
                "start_utc":row.get("start_utc"),
                "original_forecast_recorded_utc":row.get("forecast_recorded_utc"),
                "home_win_research_rule_probability":round(p,8),
                "away_win_research_rule_probability":round(1-p,8),
                "confidence_is_uncalibrated_rule_output":True,
                "NFL_conditional_on_no_tie_not_DK_moneyline_probability":league=="nfl",
                "NHL_market_regulation_and_OT_settlement_unverified":league=="nhl",
                "native_Champion_001_model_probability":None,
                "market_specific_verified_expected_value":None,
                "verified_live_sportsbook_quote":False,
                "certified_positive_ev_bets":0,
            })
    result.sort(key=lambda x:(x["league"],x["start_utc"] or "",x["espn_event_id"]))
    return result[:limit]


def _watched_games(sharp_games, scope):
    data=sharp_games.get("today_game_market_board",[])
    if not isinstance(data,list):
        raise ValueError("invalid_archived_full_game_watchlist")
    return [x for x in data if isinstance(x,dict) and x.get("league") in scope
            and x.get("league") in PRICE_SPORTS][:30]


def _watched_props(sharp_props, scope):
    data=sharp_props.get("today_player_prop_market_probability_board") or {}
    if not isinstance(data,dict):
        raise ValueError("invalid_archived_prop_watchlist")
    rows=[]
    for lg in scope:
        if lg not in PRICE_SPORTS:
            continue
        a=data.get(lg,[])
        if not isinstance(a,list):
            raise ValueError("invalid_archived_player_market_board")
        rows += [x for x in a if isinstance(x,dict)][:30]
    return rows[:60]


def _watchlist(predictions):
    """Rank research strength, not EV, so no false 'best bets' rankings."""
    output=[]
    for x in predictions:
        p=x["home_win_research_rule_probability"]
        if x["league"]=="nfl":
            # Conditional probability on no tie must not be offered as ML bet.
            candidate_side="HOME (conditional non-tie)" if p>=.5 else "AWAY (conditional non-tie)"
        else:
            candidate_side="home" if p>=.5 else "away"
        output.append({
            "league":x["league"], "espn_event_id":x["espn_event_id"],
            "start_utc":x["start_utc"],"research_direction_only":candidate_side,
            "elo_rule_max_binary_p_not_calibrated":round(max(p,1-p),8),
            "value_or_betting_edge":None,
            "professional_sharp_signal_certified":False,
            "qualified_bet":False, "decision":"HOLD_NO_EXACT_MARKET_EV",
        })
    return sorted(output,key=lambda y:-y["elo_rule_max_binary_p_not_calibrated"])[:15]


def _save(root, bundle):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    targets={
        "FULL_STACK_ALL_IN_ONE_REPORT.json":bundle,
        "FULL_STACK_PREDICTIONS.json":bundle["research_only_pregame_predictions"],
        "FULL_STACK_SHARP_EDGE.json":bundle["sharp_edge_research"],
        "FULL_STACK_BEST_BETS.json":bundle["best_bets_and_edge_leaderboard"],
        "FULL_STACK_MARKET_PROBABILITIES.json":bundle["quoted_market_probability_research"],
        "FULL_STACK_CALIBRATION.json":bundle["recalibration_and_oos_readiness"],
        "FULL_STACK_CLV.json":bundle["closing_line_value"],
        "FULL_STACK_L5_L10.json":bundle["season_to_date_game_and_player_form"],
        "FULL_STACK_PARLAY_PREFLIGHT.json":bundle["parlay_preflight"],
        "FULL_STACK_BETTING_READINESS.json":bundle["betting_readiness"],
    }
    for name,obj in targets.items():
        dest=root/name
        if dest.is_symlink():
            raise ValueError("unsafe_full_stack_report_destination")
        dest.write_text(json.dumps(obj,indent=2,sort_keys=True,default=str)+"\n",
                        encoding="utf-8")
    (root/"FULL_STACK_ALL_IN_ONE_REPORT.md").write_text(
        render(bundle),encoding="utf-8")


def render(r):
    lines=[
        "# Freddy's Picks AI V8 — ONE COMMAND / FULL STACK",
        f"**Command:** {r['user_command']} · **Executed at UTC:** {r['checked_at_utc']}",
        f"**Sports:** {', '.join(x.upper() for x in r['requested_leagues'])}",
        "**Betting decision: HOLD — independently certified +EV picks: 0; Champion-001 unchanged, stake $0.**",
        "",
        "## Research coverage by sport (unverified is N/A, not zero skill)",
        "| League | Core scan | Preface forecasts | Team L5/L10 | Player L5/L10 | Source markets |",
        "|---|---|---:|---|---|---|",
    ]
    watch=r["by_league"]
    for lg in r["requested_leagues"]:
        x=watch[lg]
        lines.append(
            f"| {lg.upper()} | {x['execution_status']} | "
            f"{x['uncalibrated_pregame_forecast_rows']} | "
            f"{x['complete_team_last5']}/{x['complete_team_last10']} | "
            f"{x['complete_player_last5']}/{x['complete_player_last10']} | "
            f"{x['archived_sportsbook_market_support']} |")
    lines.extend([
        "",
        "## Sharp Edge / game and player prop markets",
        f"**NBA/NFL research quote rows:** {r['sharp_edge_research']['archived_quote_rows_read']}",
        f"**Recent two-sided full-game boards:** "
        f"{r['sharp_edge_research']['today_full_game_markets_in_selected_leagues']}",
        f"**Recent two-sided player-prop examples:** "
        f"{r['sharp_edge_research']['today_player_prop_markets_in_selected_leagues']}",
        "**Market movements are bookmaker-reprice research, NOT verified professional sharp action.**",
        "",
        "## Probability, forecasts and predicted directions",
        f"**Original, uncalibrated NBA/NFL/NHL forward-rule forecasts:** "
        f"{len(r['research_only_pregame_predictions'])}",
        "**These are NOT frozen Champion-001 predictions, independently validated accuracy "
        "or actionable sportsbook probabilities. NFL rule forecasts condition on no tie.**",
        "",
        "## Best bets, EV, CLV and recalibration",
        "**Qualified model-derived positive-EV bets: 0. Multi-sport EV leaderboard: EMPTY / HOLD.**",
        "**Archived no-vig/market-implied percentages are never substituted for native model probabilities.**",
        f"**CLV:** {r['closing_line_value']['status']} "
        "(no independently matched entry and closing receipts).",
        f"**NBA saved calibration:** {r['recalibration_and_oos_readiness']['nba_research_calibration_status']}",
        "**No automatic fitting, wagering, or parlay creation.**",
        "",
        "## Research-only prediction directions (NOT bets)",
        "| League | ESPN game | Direction | Uncalibrated binary rule p | Decision |",
        "|---|---|---|---:|---|",
    ])
    for x in r["best_bets_and_edge_leaderboard"]["research_direction_watchlist_unranked_by_ev"][:15]:
        lines.append(
            f"| {x['league'].upper()} | {x['espn_event_id']} | "
            f"{x['research_direction_only']} | "
            f"{100*x['elo_rule_max_binary_p_not_calibrated']:.1f}% | HOLD |")
    if not r["research_only_pregame_predictions"]:
        lines.append("| All | N/A (no qualified future research receipt) | N/A | N/A | HOLD |")
    lines.extend([
        "",
        "### Source and verification limitations",
        "- SharpAPI current archived market parser supports NBA and NFL, not all eight leagues.",
        "- Historical season ESPN statistics are not independently authenticated live odds, player identities, or official market settlements.",
        "- Readiness checks require independently captured exact prices, model forecasts, "
        "market-specific holdout calibration, source custody and matched CLV receipts.",
        "- Component failures are marked HOLD rather than replaced with synthetic predictions.",
    ])
    return "\n".join(lines)+"\n"


def run_full_stack(*, command, execute_fn, days=35, end_date=None, now=None,
                   output_dir="v8_results/one_command",sharp_rows=None,
                   sharp_run_ids=(), sgo_archive_dir=None, season_archive_dir=None,
                   leaderboard_file=None, calibration_file=None,
                   recent_core=None):
    """One command: compose existing real research lanes, fail closed per sport.

    execute_fn is injected for testability; normally v8_one_command.execute.
    No paid API calls, bet placement, Champion mutation or fabricated p.
    """
    if command not in COMMAND_TO_SPORT:
        raise ValueError("unsupported_full_stack_command")
    if type(days) is not int or not 1<=days<=35:
        raise ValueError("full_stack_days_1_to_35")
    clock=now or datetime.now(timezone.utc)
    if not isinstance(clock,datetime) or clock.tzinfo is None:
        raise ValueError("aware_full_stack_clock_required")
    clock=clock.astimezone(timezone.utc)
    scope=COMMAND_TO_SPORT[command]
    out=Path(output_dir)
    out.mkdir(parents=True,exist_ok=True)
    reports={}
    failures={}
    # Execute one existing distinct research lane for EACH selected league.
    # NBA runs the comprehensive slate; NFL/NHL emit genuine before-start Elo
    # research; inactive/remainder leagues capture bounded published scores.
    for league in scope:
        core=PRIMARY[league]
        try:
            if recent_core is not None and league in recent_core:
                report=recent_core[league]
            else:
                report=execute_fn(
                    core,days=days,end_date=(end_date if league not in
                         ("nba","nfl","nhl") else None),now=clock,
                    output_dir=str(out/"components"/league),
                    sharp_rows=sharp_rows or [], sharp_run_ids=sharp_run_ids,
                    sgo_archive_dir=sgo_archive_dir,
                    season_archive_dir=season_archive_dir,
                    leaderboard_file=leaderboard_file,
                    calibration_file=calibration_file,
                )
            reports[league]=_check_report(report,requires_explicit_champion_flag=True)
        except (ValueError,OSError,TimeoutError,RuntimeError,ConnectionError,
                KeyError,TypeError) as exc:
            failures[league]={"status":"HOLD_SOURCE_OR_VALIDATION_FAILED",
                              "exception_class":type(exc).__name__,
                              "native_model_probability":None,
                              "certified_positive_ev_bets":0}
    sharp, _=summarize_sharp_archive(sharp_rows or [],now=clock,archive_run_ids=sharp_run_ids)
    props, _=summarize_player_props(sharp_rows or [],now=clock,archive_run_ids=sharp_run_ids)
    games, _=summarize_full_game_markets(sharp_rows or [],now=clock,archive_run_ids=sharp_run_ids)
    for v in (sharp,props,games):
        _check_report(v)
    quotes=_watched_games(games,scope)
    player_quotes=_watched_props(props,scope)
    season=review_season_artifacts(season_archive_dir or out/"no_saved_season")
    _check_report(season)
    clv=reconcile_local_clv([],[])
    if clv["verified_realized_clv_percent"] is not None:
        raise ValueError("unexpected_unverified_CLV")
    calibration=sharp_calibration_dashboard(calibration_file)
    _check_report(calibration)
    persisted=read_calibration(calibration_file)
    _check_report(persisted)
    leaderboard=read_leaderboard(leaderboard_file)
    _check_report(leaderboard)
    readiness=audit_betting_readiness(calibration_file=calibration_file,
                                     sharp_rows=sharp_rows,sharp_run_ids=sharp_run_ids,
                                     now=clock)
    _check_report(readiness)
    if sgo_archive_dir is None:
        sgo={"status":"NO_ARCHIVED_SGO_SOURCE_PROVIDED",
             "certified_positive_ev_bets":0}
    else:
        sgo=audit_source_archive(sgo_archive_dir,now=clock)
        _check_report(sgo)
    rows=_project_research(reports,scope)
    research_watch=_watchlist(rows)
    by_league={}
    for league in scope:
        form=season.get("by_league",{}).get(league,{})
        support=("archived_research_only_not_live_checkout"
                 if league in PRICE_SPORTS else
                 "not_supported_by_existing_SharpAPI_NBA_NFL_parser")
        core=reports.get(league)
        by_league[league]={
            "source_command":PRIMARY[league],
            "execution_status":(
                "SUCCESS_RESEARCH_ONLY" if core is not None else
                failures.get(league,{}).get("status","HOLD_NO_SOURCE")),
            "exception_class_if_failed":failures.get(league,{}).get("exception_class"),
            "uncalibrated_pregame_forecast_rows":sum(x["league"]==league for x in rows),
            "independently_certified_model_forecasts":0,
            "complete_team_last5":form.get("team_last5_complete"),
            "complete_team_last10":form.get("team_last10_complete"),
            "complete_player_last5":form.get("player_last5_complete"),
            "complete_player_last10":form.get("player_last10_complete"),
            "season_scoreboard_status":form.get("status","NOT_YET_COLLECTED"),
            "archived_sportsbook_market_support":support,
            "qualified_exact_market_model_p":None,
            "market_specific_expected_roi_percent":None,
            "verified_CLV_percent":None,
            "certified_positive_ev_bets":0,
            "decision":"HOLD_NO_AUTHENTICATED_MODEL_PRICE_PAIR",
        }
    bundle={
        "report_type":"FREDDYS_PICKS_V8_ONE_COMMAND_ALL_IN_ONE_V1",
        "checked_at_utc":clock.isoformat(),
        "user_command":command,"requested_leagues":list(scope),
        "executed_core_research_lanes":{lg:PRIMARY[lg] for lg in scope},
        "by_league":by_league,
        "research_only_pregame_predictions":rows,
        "best_bets_and_edge_leaderboard":{
            "certified_positive_ev_ranked_bets":[],
            "research_direction_watchlist_unranked_by_ev":research_watch,
            "qualified_independent_model_probability_market_pairs":0,
            "verified_executable_checkout_prices":0,
            "certified_positive_ev_bets":0,
            "do_not_force_selections_or_five_leg_parlays":True,
            "decision":"HOLD_NO_CERTIFIED_EDGE",
        },
        "sharp_edge_research":{
            "status":"NBA_NFL_ARCHIVED_MARKET_RESEARCH_ONLY",
            "archived_quote_rows_read":len(sharp_rows or []),
            "source_run_ids":list(sharp_run_ids),
            "supported_archive_leagues":sorted(PRICE_SPORTS),
            "today_full_game_markets_in_selected_leagues":len(quotes),
            "today_player_prop_markets_in_selected_leagues":len(player_quotes),
            "market_movement_count_by_sport":{
                lg:sum(x.get("league")==lg for x in
                       games.get("today_recent_market_repricing_watchlist",[]))+
                    sum(x.get("league")==lg for x in
                        props.get("ranked_prop_repricing_watchlist",[]))
                for lg in scope},
            "source_verified_professional_bet_handle":False,
            "research_only_game_line_examples":quotes,
            "research_only_player_market_examples":player_quotes,
            "all_8_sports_sharp_flow_verified":False,
            "certified_positive_ev_bets":0,
        },
        "quoted_market_probability_research":{
            "method":"source_american_odds_implied_and_two_sided_no_vig",
            "source_name":"SharpAPI DraftKings-labeled aggregator, NOT sportsbook checkout",
            "nba_nfl_only_price_parser":True,
            "archived_full_game_snapshots":quotes,
            "archived_two_sided_player_prop_snapshots":player_quotes,
            "independent_same_market_model_p":None,
            "calibrated_sport_specific_market_p":None,
            "certified_positive_ev_bets":0,
        },
        "season_to_date_game_and_player_form":season,
        "recalibration_and_oos_readiness":{
            "nba_research_calibration_status":
                calibration.get("persisted_nba_original_forward_calibration_status"),
            "nba_research_graded_games":calibration.get("nba_original_graded_outcomes"),
            "persisted_nba_calibration_read_only":persisted,
            "persisted_nba_leaderboard_read_only":leaderboard,
            "non_nba_market_calibration_independently_verified":False,
            "automatic_retraining_or_fitting_per_command":False,
            "status":"READ_ONLY_DIAGNOSTIC_HOLD_NOT_A_MODEL_RETRAIN",
            "certified_positive_ev_bets":0,
        },
        "closing_line_value":{
            "status":"UNAVAILABLE_NO_INDEPENDENT_SAME_LINE_ENTRY_CLOSE",
            "reported_archive_price_movements_are_real_CLV":False,
            "same_book_market_entry_close_authenticated_pairs":0,
            "verified_realized_clv_percent":None,
            "local_private_receipt_tool_available":True,
            "research_local_receipt_readiness":clv,
            "certified_positive_ev_bets":0,
        },
        "parlay_preflight":{
            "five_leg_verified_qualified_selections":0,
            "independent_correlated_joint_probability":None,
            "five_leg_expected_roi":None,
            "approved_parlay":None,"decision":"HOLD",
            "certified_positive_ev_bets":0,
        },
        "betting_readiness":readiness,
        "separate_SGO_market_archive_research":sgo,
        "component_failures_by_league":failures,
        "champion_001_modified":False,
        "certified_positive_ev_bets":0,
        "money_wagered_usd":0,
        "status":"RESEARCH_ONLY_HOLD_ALL_EIGHT_LEAGUES_READY_FOR_EVIDENCE_UPGRADES",
    }
    _save(out,bundle)
    return bundle
