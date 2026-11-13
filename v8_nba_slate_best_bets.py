"""One NBA command: today's *full scheduled slate*, every available market, and research.

The ESPN schedule is requested on every invocation. SportsGameOdds and SharpAPI
prices come ONLY from saved artifacts, never an API call. The source-labeled
sportsbook quotes and fixed-Elo forecasts are research, not authenticated
DraftKings checkout prices or independently calibrated Champion probabilities.
No fabricated odds, player availability, handle splits, EV, or bet certification.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from independent_schedule_review import download_json_original
from v8_nba_forward_research import BASE, capture as capture_nba_forward
from v8_sgo_research import aware as aware_time
from v8_nba_player_prop_dashboard import create_player_props_board, render_player_props
from v8_nba_player_form_pipeline import run_player_form_research

NY = ZoneInfo("America/New_York")
MAX_FILES = 8
MAX_ROWS = 25000
MAX_SOURCE_BYTES = 30_000_000
FRESH_QUOTE_SECONDS = 120
MAX_START_MISMATCH_SECONDS = 300


def _clock(value=None):
    at = value or datetime.now(timezone.utc)
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("aware_clock_required")
    return at.astimezone(timezone.utc)


def _canonical(name):
    if not isinstance(name, str):
        return None
    out = " ".join(name.casefold().replace(".", "").split())
    # Provider naming differs for the same LA franchise; no fuzzy matching.
    return {"la clippers": "los angeles clippers"}.get(out, out)


def _teams(event):
    competitions = event.get("competitions")
    if not isinstance(competitions, list) or len(competitions) != 1:
        return None
    pair = competitions[0].get("competitors")
    if not isinstance(pair, list) or len(pair) != 2:
        return None
    found = {}
    for c in pair:
        if not isinstance(c, dict) or c.get("homeAway") not in ("home", "away"):
            return None
        team = c.get("team")
        if not isinstance(team, dict) or not str(team.get("id") or "").isdigit():
            return None
        name = team.get("displayName")
        if not isinstance(name, str) or not name.strip():
            return None
        found[c["homeAway"]] = {"id": str(team["id"]), "name": name.strip()}
    if set(found) != {"home", "away"} or found["home"]["id"] == found["away"]["id"]:
        return None
    return found


def read_today_schedule(original_bytes, day, *, received_at, url):
    """Parse the original date-scoped ESPN response, including live/final games.

    A schedule source is a schedule, NOT an independent odds or injury source.
    Fail closed rather than saying that an unreadable source has zero games.
    """
    if not isinstance(original_bytes, bytes) or not 0 < len(original_bytes) <= 5_000_000:
        raise ValueError("invalid_original_schedule_bytes")
    data = json.loads(original_bytes)
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise ValueError("invalid_espn_schedule")
    if len(data["events"]) >= 500:
        raise ValueError("possibly_truncated_espn_schedule")
    seen, schedule = set(), []
    sha = hashlib.sha256(original_bytes).hexdigest()
    for event in data["events"]:
        if not isinstance(event, dict):
            continue
        season = event.get("season")
        if not isinstance(season, dict) or season.get("type") not in (2, 3):
            continue
        event_id = str(event.get("id") or "")
        pair = _teams(event)
        if not event_id.isdigit() or pair is None:
            continue
        try:
            start = aware_time(event.get("date") or event["competitions"][0].get("date"))
        except (ValueError, TypeError, KeyError):
            continue
        if start.astimezone(NY).date() != day:
            continue
        if event_id in seen:
            raise ValueError("duplicated_espn_scheduled_game")
        seen.add(event_id)
        status = event.get("status", {})
        state = status.get("type", {}).get("state") if isinstance(status, dict) else None
        schedule.append({
            "espn_event_id": event_id,
            "away_team": pair["away"]["name"], "home_team": pair["home"]["name"],
            "away_team_id": pair["away"]["id"], "home_team_id": pair["home"]["id"],
            "start_utc": start.isoformat(),
            "start_et": start.astimezone(NY).isoformat(),
            "source_event_state": state if state in ("pre", "in", "post") else "unknown",
            "season_type": season["type"],
            "schedule_original_sha256": sha,
            "schedule_source_url": url,
            "schedule_received_or_read_utc": received_at.isoformat(),
        })
    schedule.sort(key=lambda r: (r["start_utc"], r["espn_event_id"]))
    return schedule


def _valid_price(v):
    return type(v) in (int, float) and math.isfinite(v) and (v <= -100 or v >= 100)


def _implied(american):
    return (-american / (100.0 - american)) if american < 0 else (100.0 / (100.0 + american))


def _payout(american):
    return (100.0 / -american) if american < 0 else (american / 100.0)


def _match_event(row, schedule, start):
    away, home = _canonical(row.get("away_team")), _canonical(row.get("home_team"))
    matches = [g for g in schedule
               if away == _canonical(g["away_team"])
               and home == _canonical(g["home_team"])
               and abs((aware_time(g["start_utc"]) - start).total_seconds())
               <= MAX_START_MISMATCH_SECONDS]
    return matches[0] if len(matches) == 1 else None


def load_sgo_slate_rows(directory, schedule, *, now):
    """Conservative, bounded original provider records; no crossbook identity join."""
    counter = Counter()
    roots = sorted(Path(directory).rglob("sportsgameodds_dk_*.jsonl")) if (
        directory and Path(directory).is_dir()) else []
    if len(roots) > MAX_FILES:
        raise ValueError("too_many_sgo_files")
    latest = {}
    for file in roots:
        if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("unsafe_sgo_archive_file")
        for line in file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            counter["seen"] += 1
            if counter["seen"] > MAX_ROWS:
                raise ValueError("too_many_sgo_archive_rows")
            try:
                row = json.loads(line)
                if not isinstance(row, dict) or row.get("source") != "sportsgameodds_v2":
                    raise ValueError("wrong_provider")
                if (row.get("league") != "nba" or row.get("record_type") != "pregame_odds_observation"
                        or row.get("sportsbook") != "draftkings"
                        or row.get("certified_prediction") is not False
                        or row.get("model_probability") is not None
                        or row.get("is_main_line") is not False
                        or row.get("cross_provider_identity_verified") is not False
                        or row.get("draftkings_price_independently_verified") is not False):
                    raise ValueError("untrusted_source_or_promotion")
                kind = row.get("market_type")
                if kind not in ("moneyline", "point_spread", "total_points") and not (
                        isinstance(kind, str) and kind.startswith("player_")
                        and 7 < len(kind) <= 80):
                    raise ValueError("unsupported_market")
                side = row.get("selection_type")
                if side not in (("home", "away") if kind in ("moneyline", "point_spread")
                                else ("over", "under")):
                    raise ValueError("invalid_side")
                odds = row.get("odds_american")
                if not _valid_price(odds):
                    raise ValueError("invalid_american_odds")
                timestamp, receipt, start = (aware_time(row.get(k)) for k in
                                             ("timestamp", "recorded_at", "event_start_time"))
                if not timestamp <= receipt < start or receipt > now:
                    raise ValueError("not_pregame_original_quote")
                game = _match_event(row, schedule, start)
                if game is None:
                    counter["unmatched_source_event"] += 1
                    continue
                market_line = row.get("line")
                if kind != "moneyline" and (type(market_line) not in (int, float)
                        or not math.isfinite(market_line)):
                    raise ValueError("missing_or_bad_line")
                # SGO's total_points includes full-game AND individual-team totals.
                # Use its exact selection label to prevent settlement scope leakage.
                selection_label = row.get("selection")
                scope = "full_game"
                if kind == "total_points":
                    scopes = {side.title(): "full_game",
                              "Home " + side.title(): "home_team",
                              "Away " + side.title(): "away_team"}
                    scope = scopes.get(selection_label)
                    if scope is None:
                        raise ValueError("unverified_total_settlement_scope")
                elif kind in ("moneyline", "point_spread"):
                    expected = game["home_team"] if side == "home" else game["away_team"]
                    if _canonical(selection_label) != _canonical(expected):
                        raise ValueError("unverified_team_market_selection")
                elif kind.startswith("player_"):
                    scope = "player_prop_unverified"
                player_id = row.get("player_id")
                player_name = row.get("player_name")
                if kind.startswith("player_") and (not isinstance(player_id, str)
                        or not player_id or not isinstance(player_name, str)
                        or not player_name.strip()):
                    raise ValueError("unverified_prop_identity_missing")
                if kind in ("moneyline", "point_spread", "total_points") and player_id is not None:
                    raise ValueError("player_attached_to_game_market")
                # A record for an already-started game is historical reference,
                # never "currently available".
                age = (now - timestamp).total_seconds()
                current = (game["source_event_state"] == "pre"
                           and aware_time(game["start_utc"]) > now
                           and 0 <= age <= FRESH_QUOTE_SECONDS)
                normalized = {
                    "espn_event_id_research_name_time_match": game["espn_event_id"],
                    "sgo_event_id_unverified": row.get("event_id"),
                    "player_id_unverified": player_id,
                    "player_name_unverified": player_name if kind.startswith("player_") else None,
                    "market": kind, "market_scope": scope,
                    "player_team_assignment_verified": False if kind.startswith("player_") else None,
                    "selection_side": side,
                    "line": market_line if kind != "moneyline" else None,
                    "american_odds": odds,
                    "quoted_utc": timestamp.isoformat(),
                    "recorded_utc": receipt.isoformat(),
                    "source_age_seconds": round(age, 1),
                    "fresh_provider_quote_not_checkout": current,
                    "source_label": "SGO_draftkings_provider_unverified",
                    "primary_or_alt_line_independently_verified": False,
                    "athlete_identity_independently_verified": False,
                    "actual_sportsbook_checkout_verified": False,
                }
                key = (game["espn_event_id"], row.get("event_id"),
                       kind, scope, player_id, market_line if kind != "moneyline" else None, side)
                prev = latest.get(key)
                if prev is None or timestamp >= aware_time(prev["quoted_utc"]):
                    latest[key] = normalized
                counter["matched_rows"] += 1
            except (ValueError, KeyError, TypeError, OverflowError, json.JSONDecodeError):
                counter["excluded_invalid_rows"] += 1
    ordered = sorted(latest.values(), key=lambda r: (
        r["espn_event_id_research_name_time_match"], r["market"],
        r["player_name_unverified"] or "", r["line"] if r["line"] is not None else 0,
        r["selection_side"], r["quoted_utc"]))
    return ordered, dict(sorted(counter.items()))


def _pair_key(row):
    market, line = row["market"], row["line"]
    if market == "moneyline":
        threshold = None
    elif market == "point_spread":
        threshold = round(abs(line), 3)
    else:
        threshold = round(line, 3)
    return (row["espn_event_id_research_name_time_match"],
            row["sgo_event_id_unverified"], market, row["market_scope"],
            row["player_id_unverified"], threshold)


def pair_sgo_prices(quotes, forecasts):
    """Only exact opposite sides of the SAME provider event and line are paired."""
    by_key = defaultdict(dict)
    for q in quotes:
        key, side = _pair_key(q), q["selection_side"]
        if side in by_key[key]:
            # Ambiguous source snapshots cannot be promoted to a two-sided price.
            continue
        by_key[key][side] = q
    forecasts_by_id = {x["espn_event_id"]: x for x in forecasts
                       if x.get("certified_prediction") is False
                       and x.get("model_probability_independently_calibrated") is False
                       and isinstance(x.get("espn_event_id"), str)}
    markets = []
    for key, sides in sorted(by_key.items(), key=lambda t: str(t[0])):
        event_id, provider_id, kind, scope, player_id, level = key
        names = ("home", "away") if kind in ("moneyline", "point_spread") else ("over", "under")
        left, right = (sides.get(x) for x in names)
        if left is None or right is None:
            continue
        if (kind == "point_spread" and abs(left["line"] + right["line"]) > .001) or (
                abs((aware_time(left["quoted_utc"]) - aware_time(right["quoted_utc"])).total_seconds())
                > FRESH_QUOTE_SECONDS):
            continue
        p1, p2 = _implied(left["american_odds"]), _implied(right["american_odds"])
        research = forecasts_by_id.get(event_id) if kind == "moneyline" else None
        model = (research.get("model_probability_home_win_research_only")
                 if research else None)
        if type(model) not in (int, float) or not 0 < model < 1:
            model = None
        # Research-only gap is deliberately NOT a certified model edge.
        gap = round((model - p1) * 100, 2) if model is not None else None
        payout_roi = round((model * (1 + _payout(left["american_odds"])) - 1) * 100, 2) if model is not None else None
        paired = {
            "espn_event_id_research_match": event_id,
            "sgo_event_id_unverified": provider_id,
            "market": kind, "market_scope": scope,
            "player_team_assignment_verified": False if kind.startswith("player_") else None,
            "player_id_unverified": player_id,
            "player_name_unverified": left.get("player_name_unverified"),
            "line_or_absolute_spread": level,
            "sides": [{**s, "break_even_percent": round(p * 100, 2),
                       "no_vig_market_percent": round(p / (p1 + p2) * 100, 2)}
                      for s, p in ((left, p1), (right, p2))],
            "model_home_win_probability_research_percent": round(model * 100, 2) if model is not None else None,
            "uncalibrated_model_minus_archived_break_even_pp": gap,
            "uncalibrated_archived_price_roi_percent_not_bet_edge": payout_roi,
            "independently_calibrated_model_probability_percent": None,
            "certified_sharp_edge_pp": None,
            "certified_expected_roi_percent": None,
            "source_pair_quote_fresh": (left["fresh_provider_quote_not_checkout"] and
                                        right["fresh_provider_quote_not_checkout"]),
            "source_quote_not_executable": True,
            "professional_handle_percent": None,
            "decision": "HOLD_NOT_VERIFIED_MODEL_AND_SPORTSBOOK",
        }
        markets.append(paired)
    return markets


def assemble(slate, forecasts, odds_rows, source_counts, *, now, calibration):
    by_game = {g["espn_event_id"]: g for g in slate}
    research = {r["espn_event_id"]: r for r in forecasts
                if r.get("certified_prediction") is False
                and r.get("model_probability_independently_calibrated") is False
                and r.get("espn_event_id") in by_game
                and aware_time(r["forecast_recorded_utc"]) < aware_time(by_game[r["espn_event_id"]]["start_utc"])}
    pairs = pair_sgo_prices(odds_rows, list(research.values()))
    grouped = defaultdict(list)
    for q in pairs:
        grouped[q["espn_event_id_research_match"]].append(q)
    games = []
    for g in slate:
        forecast = research.get(g["espn_event_id"])
        context = (forecast.get("nba_rest_and_recent_form_features")
                   if isinstance(forecast, dict) else None)
        if context is not None and (
                not isinstance(context, dict)
                or context.get("champion_001_modified") is not False
                or context.get("applied_as_probability_weight") is not False):
            raise ValueError("untrusted_NBA_rest_form_probability_promotion")
        game_pairs = grouped[g["espn_event_id"]]
        def coverage_key(quote):
            if quote["market"].startswith("player_"):
                return "player_prop_QUARANTINED_UNVERIFIED"
            if quote["market"] == "total_points" and quote["market_scope"] != "full_game":
                return "team_total_points_research"
            return quote["market"]
        counts = Counter(coverage_key(q) for q in game_pairs)
        games.append({
            **g,
            "model_home_win_research_percent": (round(
                100 * forecast["model_probability_home_win_research_only"], 2)
                if forecast else None),
            "model_away_win_research_percent": (round(
                100 * forecast["estimated_away_win_probability_research_only"], 2)
                if forecast else None),
            "forecast_recorded_utc": forecast.get("forecast_recorded_utc") if forecast else None,
            "forecast_model": forecast.get("model_version") if forecast else None,
            "nba_rest_back_to_back_last5_last10": context,
            "nba_recent_form_used_as_probability_weight": False,
            "forecast_independently_calibrated": False,
            "available_paired_archive_markets": dict(sorted(counts.items())),
            "paired_archived_market_count": len(game_pairs),
            "market_data_not_sportsbook_checkout": True,
            "decision": "PASS_HOLD_NO_VERIFIED_EDGE",
        })
    prop_board = create_player_props_board(games, pairs)
    prop_summary = {k: v for k, v in prop_board.items()
                    if k != "source_provider_player_prop_pairs"}
    return {
        "report_type": "FREDDYS_NBA_ALL_GAMES_SINGLE_COMMAND_RESEARCH_ONLY",
        "as_of_utc": now.isoformat(), "date_et": now.astimezone(NY).date().isoformat(),
        "slate_game_count_from_original_source": len(slate),
        "games": games,
        "games_with_rest_b2b_last5_last10_context": sum(
            g["nba_rest_back_to_back_last5_last10"] is not None for g in games),
        "rest_form_features_calibrated_or_weighted": False,
        "market_categories": ["moneyline", "point_spread", "total_points", "player_prop"],
        "all_archive_observations_deduplicated": len(odds_rows),
        "all_paired_archived_markets": pairs,
        "nba_player_props": prop_summary,
        "paired_archive_market_count": len(pairs),
        "quarantined_unverified_player_prop_pairs": sum(
            1 for q in pairs if q["market"].startswith("player_")),
        "player_props_with_independently_verified_team_roster_assignment": 0,
        "full_game_total_points_pairs": sum(
            1 for q in pairs if q["market"] == "total_points"
            and q["market_scope"] == "full_game"),
        "team_total_points_pairs": sum(
            1 for q in pairs if q["market"] == "total_points"
            and q["market_scope"] in ("home_team", "away_team")),
        "fresh_provider_reference_quote_rows_not_checkout": sum(
            1 for q in odds_rows if q["fresh_provider_quote_not_checkout"]),
        "latest_archived_quote_utc": max(
            (r["quoted_utc"] for r in odds_rows), default=None),
        "sgo_source_validation_counts": source_counts,
        "calibration": calibration,
        "independently_certified_positive_ev_bets": 0,
        "verified_native_exact_market_model_probabilities": 0,
        "draftkings_checkout_receipts_verified": 0,
        "live_professional_sharp_handle_percent": None,
        "five_leg_joint_probability": None,
        "best_bets_ranked_by_certified_ev": [],
        "model_research_price_disagreements_not_bets": sorted(
            [{"event_id": q["espn_event_id_research_match"],
              "side": q["sides"][0]["selection_side"],
              "market": q["market"],
              "indicative_uncalibrated_gap_pp": q["uncalibrated_model_minus_archived_break_even_pp"],
              "source_quote_fresh": q["source_pair_quote_fresh"],
              "sportsbook_checkout_verified": False,
              "decision": "HOLD_RESEARCH_NOT_BET"}
             for q in pairs if q["uncalibrated_model_minus_archived_break_even_pp"] is not None],
            key=lambda x: -x["indicative_uncalibrated_gap_pp"]),
        "betting_decision": "PASS_NO_CERTIFIED_POSITIVE_EV",
        "stake_usd": 0, "champion_001_modified": False,
        "warnings": [
            "Every listed game comes from an original current-date ESPN schedule response.",
            "SportsGameOdds rows are stored source labels, NOT live DraftKings checkouts.",
            "All alt/primary-line status is unverified; all available paired lines are reference-only.",
            "Moneyline research Elo forecasts are not independently calibrated or Champion-001.",
            "Back-to-back, rest, last-five and last-ten are research model inputs only, never unvalidated probability adjustments.",
            "There is NO separate exact-line spread, total or player-prop prediction model.",
            "Team totals cannot be represented as full-game totals; market scope is retained.",
            "Unverified player/team assignments are quarantined from display and betting.",
            "Do not infer professional sharp money from price movement or bet-count splits.",
            "A five-leg probability cannot be certified without marginal probabilities and dependence estimates.",
        ],
    }


def _c(value):
    if value is None:
        return "N/A"
    return str(value).replace("|", "/").replace("\n", " ")[:95]


def render_slate(report):
    lines = [
        "# Freddy's Picks AI — NBA tonight, ALL games + ALL market families",
        f"**Eastern date:** {report['date_et']} · **Captured UTC:** {report['as_of_utc']}",
        f"**Published NBA games:** {report['slate_game_count_from_original_source']} · "
        f"**Paired archived market references:** {report['paired_archive_market_count']}",
        "**Betting decision: PASS/HOLD — independently certified +EV selections: 0; wagers $0.**",
        f"**Latest stored price quote UTC:** {_c(report.get('latest_archived_quote_utc'))}"
        " (NOT an authenticated current sportsbook line).",
        f"**Fresh provider reference rows (not checkout):** "
        f"{report.get('fresh_provider_reference_quote_rows_not_checkout', 0)}.",
        f"**Unverified player-prop pairs QUARANTINED:** "
        f"{report.get('quarantined_unverified_player_prop_pairs', 0)}"
        " — roster/team assignment unverified; never a recommended prop.",
        "Full paired archive prices, including every retained line, appear in NBA_ALL_MARKET_PAIRS.json.",
        "Prices are provider-labeled historical observations, not sportsbook checkout receipts.",
        "",
        "## Complete published NBA slate",
        "| Start ET | Matchup | State | V8 Elo home % | V8 Elo away % | Archived ML / spreads / game totals / team totals / quarantined props |",
        "|---|---|---|---:|---:|---|",
    ]
    for g in report["games"]:
        counts = g["available_paired_archive_markets"]
        coverage = " / ".join(str(counts.get(k, 0)) for k in
                              ("moneyline", "point_spread", "total_points", "team_total_points_research", "player_prop_QUARANTINED_UNVERIFIED"))
        lines.append(f"| {_c(g['start_et'])} | {_c(g['away_team'])} @ {_c(g['home_team'])} "
                     f"| {_c(g['source_event_state'])} | {_c(g['model_home_win_research_percent'])} "
                     f"| {_c(g['model_away_win_research_percent'])} | {coverage} |")
    if not report["games"]:
        lines.append("| N/A | No games returned by the available NBA schedule source | N/A | N/A | N/A | N/A |")
    lines.extend([
        "",
        "## Rest, back-to-back, and last 5/10 games — point-in-time model features",
        "**Rest:** calendar dates between games minus one. B2B = the second night on consecutive Eastern dates.",
        "**Last-5/10 win rates:** only ESPN published final scores matured under the 48h research embargo.",
        "**Feature values are NOT yet fitted or weighted into the Elo probabilities. N/A means insufficient history.**",
        "| Matchup | Home rest days | Away rest days | Home B2B | Away B2B | Home last 5 / 10 win % | Away last 5 / 10 win % |",
        "|---|---:|---:|---|---|---|---|",
    ])
    def form_cell(side):
        if not isinstance(side, dict):
            return "N/A"
        return " / ".join(
            f"{round(100 * side[w]['win_rate'], 1)}% (n={side[w]['available_matured_games']})"
            if isinstance(side.get(w), dict) and side[w].get('win_rate') is not None
            else "N/A" for w in ('last5', 'last10'))
    for g in report["games"]:
        ctx = g.get("nba_rest_back_to_back_last5_last10")
        h = ctx.get("home") if isinstance(ctx, dict) else None
        a = ctx.get("away") if isinstance(ctx, dict) else None
        def val(side, key):
            return _c(side.get(key)) if isinstance(side, dict) else "N/A"
        lines.append(
            f"| {_c(g['away_team'])} @ {_c(g['home_team'])} "
            f"| {val(h, 'rest_days')} | {val(a, 'rest_days')} "
            f"| {val(h, 'back_to_back_second_night')} | {val(a, 'back_to_back_second_night')} "
            f"| {form_cell(h)} | {form_cell(a)} |")
    lines.extend([
        "", "## NBA markets — all recorded two-sided lines (research, not checkout)",
        "| Matchup | Market | Line | First odds / no-vig % | Other odds / no-vig % | Research Elo home % | Decision |",
        "|---|---|---:|---|---|---:|---|",
    ])
    lookup = {g["espn_event_id"]: g for g in report["games"]}
    for market in report["all_paired_archived_markets"]:
        game = lookup[market["espn_event_id_research_match"]]
        if market["market"].startswith("player_"):
            continue
        first, second = market["sides"]
        lines.append(f"| {_c(game['away_team'])} @ {_c(game['home_team'])} | {_c(market['market'])} ({_c(market['market_scope'])}) "
                     f"| {_c(market['line_or_absolute_spread'])} "
                     f"| {_c(first['american_odds'])} / {_c(first['no_vig_market_percent'])}% "
                     f"| {_c(second['american_odds'])} / {_c(second['no_vig_market_percent'])}% "
                     f"| {_c(market['model_home_win_probability_research_percent'])} | HOLD |")
    # Display paired archived props explicitly with prominent identity/price
    # holds. The full 441+ per-side references remain separate audit files.
    lines.extend(["", render_player_props(report["nba_player_props"], preview=True)])
    lines.extend([
        "", "## Player last five / last ten — new research snapshot",
        f"**Player research status:** {_c((report.get('nba_player_last5_last10_research') or {}).get('status'))}",
        f"**Historical player summary games requested / valid:** "
        f"{_c((report.get('nba_player_last5_last10_research') or {}).get('historical_summaries_attempted'))} / "
        f"{_c((report.get('nba_player_last5_last10_research') or {}).get('historical_summaries_validated'))}",
        f"**Historically linked candidates (not current-roster verified):** "
        f"{_c((report.get('nba_player_last5_last10_research') or {}).get('future_player_targets_staged_unverified_roster'))}",
        f"**Full last-5 / last-10 player windows:** "
        f"{_c((report.get('nba_player_last5_last10_research') or {}).get('players_with_complete_last5'))} / "
        f"{_c((report.get('nba_player_last5_last10_research') or {}).get('players_with_complete_last10'))}",
        "**Player statistics are separate from Elo probability, sportsbook identity and player-prop value.**",
        "See nba_player_form/NBA_PLAYER_LAST5_LAST10.md and .json for individual evidence.",
        "", "## Sharp Edge / Calibration / Best Bets",
        f"**Independently calibrated model available:** NO",
        f"**Persisted original NBA forward forecasts / graded / pending:** "
        f"{_c((report.get('calibration') or {}).get('nba_original_archived_forecasts'))} / "
        f"{_c((report.get('calibration') or {}).get('nba_original_graded_outcomes'))} / "
        f"{_c((report.get('calibration') or {}).get('nba_original_pending_grading'))}.",
        "**Brier / ECE:** N/A until mature original outcome samples meet thresholds.",
        "**Sharp-money handle/ticket verification:** N/A",
        "**Certified exact-market edge pp / expected ROI%:** N/A / N/A",
        "**Ranked verified positive-EV bets:** none. PASS.",
        "**Same-game/parlay joint probability:** N/A. No validated dependence model.",
        "**Missing market is N/A, never a 0% probability.**",
    ])
    return "\n".join(lines) + "\n"


def run(output_dir, *, days=35, now=None, sgo_archive_dir=None, calibration=None,
        forward_runner=None, schedule_fetcher=None, player_form_fetcher=None):
    """Save complete current-day schedule and evidence; fail closed on missing feeds."""
    at = _clock(now)
    today = at.astimezone(NY).date()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    runner = forward_runner or capture_nba_forward
    kwargs = {"history_days": days}
    if now is not None:
        kwargs["clock"] = lambda: at
    forecasts, forward_status = [], {}
    try:
        forecasts, forward_status = runner(output / "nba_forward", **kwargs)
    except (ValueError, ConnectionError, TimeoutError, OSError, RuntimeError, TypeError) as exc:
        forward_status = {"status": "source_failure", "error_class": type(exc).__name__,
                          "original_forecasts": 0, "champion_001_modified": False}
    url = BASE + urlencode({"dates": today.strftime("%Y%m%d"), "limit": 500})
    original = output / "nba_forward" / f"nba_original_future_schedule_{today:%Y%m%d}.json"
    slate, state = [], "source_unavailable"
    try:
        if original.is_file():
            raw = original.read_bytes()
            state = "original_future_capture"
        else:
            fetch = schedule_fetcher or download_json_original
            result = fetch(url)
            if not isinstance(result, tuple) or len(result) != 2:
                raise ValueError("source_original_tuple_required")
            payload, raw = result
            if json.loads(raw) != payload:
                raise ValueError("source_original_bytes_mismatch")
            state = "fresh_independent_schedule_request"
        slate = read_today_schedule(raw, today, received_at=at, url=url)
    except (ValueError, ConnectionError, TimeoutError, OSError, TypeError, KeyError,
            json.JSONDecodeError) as exc:
        state = f"unavailable_{type(exc).__name__}"
    odds, counts = load_sgo_slate_rows(sgo_archive_dir, slate, now=at)
    report = assemble(slate, forecasts, odds, counts, now=at, calibration=calibration)
    report["schedule_capture_status"] = state
    report["nba_forward_research_status"] = forward_status
    # New, later-observed player snapshot. Never overwrite the earlier Elo
    # forecast, infer current-roster truth or join provider prop identities.
    try:
        player_kwargs = {}
        if player_form_fetcher is not None:
            player_kwargs["fetcher"] = player_form_fetcher
        if now is not None:
            player_kwargs["clock"] = lambda: at
        player_report = run_player_form_research(
            output / "nba_forward" / "NBA_HISTORICAL_PUBLISHED_RESULTS_RESEARCH.jsonl",
            slate, output / "nba_player_form", coverage=forward_status,
            max_summaries=24, **player_kwargs)
    except (ValueError, TypeError, KeyError, OSError, TimeoutError) as exc:
        player_report = {
            "report_type": "V8_NBA_PREGAME_LAST5_LAST10_PLAYER_FORM",
            "status": "HOLD_PLAYER_SOURCE_VALIDATION_ERROR",
            "source_failure_class": type(exc).__name__,
            "certified_positive_ev_bets": 0, "wagers_placed": 0,
            "champion_001_modified": False,
        }
    report["nba_player_last5_last10_research"] = player_report
    report["source_coverage_complete_for_all_nba_games"] = state in (
        "original_future_capture", "fresh_independent_schedule_request")
    report["all_market_quote_rows"] = odds
    report["archived_provider_prices_not_verified_checkout"] = True
    (output / "NBA_TONIGHTS_FULL_SLATE.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # One-command outputs include BOTH the full player-prop table and an
    # exhaustive machine-readable provider-reference board.
    full_player_board = create_player_props_board(
        report["games"], report["all_paired_archived_markets"])
    (output / "NBA_PLAYER_PROPS_ALL_MARKETS.json").write_text(
        json.dumps(full_player_board, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    (output / "NBA_PLAYER_PROPS_ALL_MARKETS.md").write_text(
        render_player_props(full_player_board), encoding="utf-8")
    (output / "NBA_ALL_MARKET_PAIRS.json").write_text(
        json.dumps(report["all_paired_archived_markets"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    (output / "NBA_ALL_MARKET_QUOTES.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in odds), encoding="utf-8")
    (output / "NBA_BEST_BETS_LEADERBOARD.json").write_text(
        json.dumps({"best_bets": [], "certified_positive_ev_bets": 0,
                    "decision": report["betting_decision"],
                    "research_disagreements_not_bets":
                        report["model_research_price_disagreements_not_bets"]},
                   indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "NBA_TONIGHTS_FULL_SLATE.md").write_text(render_slate(report), encoding="utf-8")
    return report, forecasts

# User-requested Nov 13, 2026 NBA Sharp Edge best-bets archive-only rerun; no betting/model logic changed.

# User requested next NBA Sharp Edge best-bets scan for Nov 13, 2026. Research-only, archived-price inputs; full-game plus player props; no paid requests, no wagers, no Champion-001 changes.
