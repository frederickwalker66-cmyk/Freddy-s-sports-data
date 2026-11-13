"""Always-on NBA sharp-edge research gate for every full NBA command.

SharpAPI archive movements are evidence of reported *bookmaker prices*,
not evidence of a professional sharp bettor, executable DraftKings quote,
native model probability, real closing-line value or positive expected value.
Preserve independent distinct buckets: full games, individual player props,
market repricings, season L5/L10 context, calibration and CLV.
No bet is promoted; Champion-001 never changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path


def _dictionary(value):
    if not isinstance(value, dict):
        raise ValueError("nba_sharp_edge_source_report_missing")
    if value.get("champion_001_modified") is not False:
        raise ValueError("nba_sharp_edge_source_cannot_modify_champion")
    if value.get("certified_positive_ev_bets", value.get("positive_ev_certified", 0)) != 0:
        raise ValueError("nba_sharp_edge_unverified_ev_promotion")
    return value


def _limited_nba(rows, limit=12):
    if not isinstance(rows, list):
        raise ValueError("nba_sharp_edge_research_watchlist_not_list")
    if len(rows) > 5000:
        raise ValueError("nba_sharp_edge_archive_watchlist_budget")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("nba_sharp_edge_invalid_watch_row")
        if row.get("league") == "nba":
            if row.get("certified_positive_ev", row.get("positive_ev_certified", False)) is not False:
                raise ValueError("nba_sharp_edge_archive_market_cannot_be_certified")
            result.append(row)
    return result[:limit]


def build_nba_sharp_edge(sharp, player_props, full_games, calibration, season=None):
    """Always emit the NBA-only data-quality/market-movement research section."""
    sharp = _dictionary(sharp)
    player_props = _dictionary(player_props)
    full_games = _dictionary(full_games)
    calibration = _dictionary(calibration)
    if (sharp.get("sharp_money_or_professional_action_inferred") is not False
            or player_props.get("sharp_flow_verified") is not False
            or player_props.get("player_active_verified") is not False
            or full_games.get("independently_verified_sportsbook_checkout_prices") != 0
            or calibration.get("native_calibration_applied_to_current_sharp_edge_quotes") is not False):
        raise ValueError("nba_sharp_edge_false_independent_verification")
    form = ((season or {}).get("by_league") or {}).get("nba", {})
    if not isinstance(form, dict):
        raise ValueError("nba_sharp_edge_season_form_not_object")
    game_watch = _limited_nba(full_games.get("today_recent_market_repricing_watchlist", []))
    player_watch = _limited_nba(player_props.get("ranked_prop_repricing_watchlist", []))
    money_watch = _limited_nba(sharp.get("ranked_market_movement_watchlist", []))
    board = _limited_nba(full_games.get("today_game_market_board", []), 40)
    props = _limited_nba((player_props.get("today_player_prop_market_probability_board") or {}).get("nba", []), 40)
    return {
        "report_type": "FREDDYS_PICKS_ALWAYS_NBA_SHARP_EDGE_RESEARCH",
        "requested_command": "run_nba_or_run_nba_best_bets",
        "sharp_edge_checked_every_nba_run": True,
        "source": "archived SharpAPI source-labeled odds and prior ESPN research; no current checkout access",
        "nba_moneyline_quote_observations": sharp.get("eligible_quotes_by_league", {}).get("nba", 0),
        "nba_exact_player_prop_quote_observations": player_props.get("valid_prop_quotes_by_league", {}).get("nba", 0),
        "nba_recent_two_sided_full_game_market_board_count": len(board),
        "nba_recent_two_sided_player_market_examples": len(props),
        "nba_recent_moneyline_price_movement_watch": money_watch,
        "nba_recent_spread_total_moneyline_price_movement_watch": game_watch,
        "nba_recent_player_prop_price_movement_watch": player_watch,
        "nba_recent_two_sided_full_game_reference_markets": board,
        "nba_recent_two_sided_player_prop_reference_markets": props,
        "nba_last5_complete_player_histories_source_only": form.get("player_last5_complete"),
        "nba_last10_complete_player_histories_source_only": form.get("player_last10_complete"),
        "nba_last5_complete_team_histories_source_only": form.get("team_last5_complete"),
        "nba_last10_complete_team_histories_source_only": form.get("team_last10_complete"),
        "calibration": calibration.get("persisted_nba_original_forward_calibration_status"),
        "nba_original_forecasts_graded": calibration.get("nba_original_graded_outcomes"),
        "verified_professional_sharp_betting_handle_or_ticket_flow": False,
        "verified_executable_draftkings_checkout_quotes": 0,
        "native_exact_market_model_probability": None,
        "qualified_independent_model_expected_value_percent": None,
        "matched_verified_entry_and_closing_lines": 0,
        "verified_clv_percent": None,
        "positive_ev_certified": 0,
        "certified_positive_ev_bets": 0,
        "independently_certified_parlay_legs": 0,
        "wagers_placed": 0,
        "champion_001_modified": False,
        "decision": "HOLD_NO_AUTHENTICATED_SHARP_FLOW_BOOK_PRICE_OR_CALIBRATED_MODEL",
        "next_verification": [
            "independently timestamped exact-book executable quote for each market",
            "official player ID/current roster and availability for prop",
            "independent chronological market-specific calibrated model p",
            "tracked original entry versus independently verified matching close for CLV",
            "verified actual professional bettor handle/ticket evidence for genuine sharp activity",
        ],
    }


def render(report):
    if (not isinstance(report, dict)
            or report.get("sharp_edge_checked_every_nba_run") is not True
            or report.get("certified_positive_ev_bets") != 0):
        raise ValueError("nba_sharp_edge_report_not_safe")
    lines = [
        "# Freddy's Picks AI V8 — NBA Sharp Edge (always included)",
        "**Decision: HOLD — research-only prices are not verified sharp money or positive EV.**",
        "",
        "| Category | Result |",
        "|---|---|",
        f"| NBA archived moneyline source quotes | {report['nba_moneyline_quote_observations']} |",
        f"| NBA archived exact player-prop source quotes | {report['nba_exact_player_prop_quote_observations']} |",
        f"| Recent full-game two-sided research markets | {report['nba_recent_two_sided_full_game_market_board_count']} |",
        f"| Recent player two-sided research examples | {report['nba_recent_two_sided_player_market_examples']} |",
        f"| Team last 5 / 10 complete research | {report['nba_last5_complete_team_histories_source_only']} / {report['nba_last10_complete_team_histories_source_only']} |",
        f"| Player last 5 / 10 complete research | {report['nba_last5_complete_player_histories_source_only']} / {report['nba_last10_complete_player_histories_source_only']} |",
        f"| Independently graded original NBA research forecasts | {report['nba_original_forecasts_graded']} |",
        f"| Verified professional sharp-money handle / tickets | N/A |",
        f"| Genuine closing-line value | N/A |",
        f"| Verified executable DraftKings checkout | 0 |",
        f"| Certified model-derived positive EV bets | 0 |",
        "",
        "### Recent NBA market repricing research — not certified sharp edges",
        "| Category | Market / source label | Quoted change | Status |",
        "|---|---|---|---|",
    ]
    buckets = (
        ("Moneyline", report["nba_recent_moneyline_price_movement_watch"]),
        ("Game line", report["nba_recent_spread_total_moneyline_price_movement_watch"]),
        ("Player prop", report["nba_recent_player_prop_price_movement_watch"]),
    )
    count=0
    for category, entries in buckets:
        for item in entries[:5]:
            label = str(item.get("player_name") or
                        (str(item.get("away_team", "?"))+" @ "+str(item.get("home_team", "?"))))
            market = str(item.get("prop_stat") or item.get("market") or "ML")
            change = item.get("same_line_no_vig_market_price_change_pp")
            if change is None:
                change = item.get("home_no_vig_change_percentage_points")
            if change is None:
                change = item.get("absolute_repricing_pp")
            c = "N/A" if change is None else str(change) + " pp (reported)"
            lines.append(f"| {category} | {(label+' — '+market).replace('|','/')[:92]} | {c} | HOLD |")
            count+=1
    if not count:
        lines.append("| All NBA markets | No fresh supported same-line movement | N/A | PASS |")
    lines.extend([
        "",
        "No market-implied percentage is represented as an independent model forecast.",
        "The system does not certify professional bettors, independently validate "
        "same-book checkout odds, or compute CLV without entry/close receipts.",
        "**Champion-001 frozen. Stakes $0. No automatic wagers.**",
    ])
    return "\n".join(lines)+"\n"


def save(report, root):
    path=Path(root)
    path.mkdir(parents=True, exist_ok=True)
    (path/"NBA_SHARP_EDGE_ALWAYS.json").write_text(
        json.dumps(report, sort_keys=True, indent=2)+"\n", encoding="utf-8")
    (path/"NBA_SHARP_EDGE_ALWAYS.md").write_text(render(report), encoding="utf-8")
