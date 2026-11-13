"""Incremental, bounded season-to-date scoreboard evidence across eight leagues.

One league per job; collect at most 35 Eastern calendar days PER HTTP batch,
retain all previous valid published scores, and request only unconfirmed days.
Never silently present a partial season as full. ESPN scoreboard receipts are
published-score RESEARCH, not odds, independently confirmed settlements,
pregame historical backtests or player stats. User-facing PTS/total figures
are *scoreboard displayed* scores; sport market settlement can differ.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import argparse
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from challenger_research_features import validated
from historical_outcomes import LEAGUES, collect, parse_time, scoreboard_url
from v8_all_sports_season_form import (_team, _coverage, build_season_game_form,
                                       season_anchor, MATURITY_HOURS, NY)

MAX_DAYS_PER_REQUEST = 35
MAX_SEASON_DAYS = 366
MAX_HISTORICAL_ROWS = 10000


def _asof(clock):
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("aware_season_collection_clock_required")
    return value.astimezone(timezone.utc)


def _verify_history(rows, league, asof, anchor):
    if not isinstance(rows, list) or len(rows) > MAX_HISTORICAL_ROWS:
        raise ValueError("invalid_season_history_budget")
    found = {}
    for row in rows:
        validated(row)
        started = parse_time(row["event_start_utc"])
        observed = parse_time(row["retrieved_at_utc"])
        if (row["league"] != league or observed > asof
                or row["source_url"] != scoreboard_url(
                    league, started.astimezone(NY).date())
                or started.astimezone(NY).date() < anchor):
            raise ValueError("wrong_league_season_or_asof_result")
        eid = row["espn_event_id"]
        if eid in found:
            raise ValueError("duplicate_season_result_event")
        found[eid] = row
    return found


def _validated_previous(path, league, anchor, asof):
    if path is None:
        return {}, set()
    source = Path(path)
    meta = source / "SEASON_COVERAGE.json"
    results = source / "SEASON_RESULTS.jsonl"
    if not meta.is_file() or not results.is_file():
        raise ValueError("previous_season_artifact_incomplete")
    cfg = json.loads(meta.read_text(encoding="utf-8"))
    if cfg.get("league") != league or cfg.get("conservative_collection_anchor_et") != anchor.isoformat():
        raise ValueError("previous_season_artifact_wrong_league_or_anchor")
    if cfg.get("champion_001_modified") is not False:
        raise ValueError("untrusted_previous_season_model_mutation")
    raw = results.read_bytes()
    if len(raw) > 12_000_000:
        raise ValueError("oversized_previous_season_artifact")
    lines = [json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]
    found = _verify_history(lines, league, asof, anchor)
    dates = cfg.get("source_days_confirmed_et")
    if not isinstance(dates, list) or len(set(dates)) != len(dates):
        raise ValueError("invalid_previous_season_coverage")
    today_et = asof.astimezone(NY).date()
    for s in dates:
        d = date.fromisoformat(s)
        if not anchor <= d < today_et:
            raise ValueError("previous_source_day_in_future_or_wrong_season")
    return found, set(dates)


def _segments(days):
    """Group *consecutive missing days* in chronological max-35-day batches."""
    if not days:
        return []
    out = []
    first = last = days[0]
    for d in days[1:]:
        if (d-last).days == 1 and (d-first).days < MAX_DAYS_PER_REQUEST:
            last = d
        else:
            out.append((first, last, (last-first).days+1))
            first = last = d
    out.append((first, last, (last-first).days+1))
    return out


def _team_board(rows, league, asof, manifest):
    _, _, complete, _ = _coverage(league, manifest, asof)
    teams = defaultdict(list)
    for r in rows:
        if r["season_type"] != 2:
            continue
        start = parse_time(r["event_start_utc"])
        observed = parse_time(r["retrieved_at_utc"])
        home, away = r["home_team_espn_id"], r["away_team_espn_id"]
        score_home, score_away = r["home_score"], r["away_score"]
        for tid, scored, allowed, venue, name in (
                (home, score_home, score_away, "home", r["home_team"]),
                (away, score_away, score_home, "away", r["away_team"])):
            teams[tid].append({
                "start": start, "retrieved": observed,
                "event_id": r["espn_event_id"], "scored": scored,
                "allowed": allowed, "venue": venue, "team_name": name,
                "result": ("win" if scored > allowed else
                           "loss" if scored < allowed else "draw"),
            })
    output = {}
    snapshot = asof + timedelta(hours=1)
    for tid, games in sorted(teams.items()):
        info = _team(games, league, snapshot, asof, complete)
        output[tid] = {
            "team_name_from_most_recent_ESPN_result": sorted(
                games, key=lambda q:q["start"])[-1]["team_name"],
            "team_espn_id": tid, "league": league, **info,
        }
    return {
        "report_type": "SEASON_TO_DATE_TEAM_AND_GAME_LAST5_LAST10_RESEARCH",
        "league": league, "as_of_utc": asof.isoformat(),
        "teams_in_published_history": len(output),
        "regular_season_games": sum(r["season_type"] == 2 for r in rows),
        "complete_scoreboard_day_coverage": complete,
        "teams": output,
        "props_requiring_historical_line_and_settlement_not_computed": True,
        "all_source_stats_are_PUBLISHED_displayed_score_only": True,
        "model_coefficients_fitted": False,
        "champion_001_modified": False, "certified_positive_ev_bets": 0,
    }


def collect_season(league, out_dir, *, previous_dir=None, clock=None,
                   collector=collect, pause_seconds=0.08, max_days=MAX_SEASON_DAYS):
    if league not in LEAGUES:
        raise ValueError("only_eight_configured_leagues_supported")
    if type(max_days) is not int or not 1 <= max_days <= MAX_SEASON_DAYS:
        raise ValueError("season_collection_date_budget_exceeded")
    clock = clock or (lambda: datetime.now(timezone.utc))
    began = _asof(clock)
    anchor, season = season_anchor(league, began)
    end = began.astimezone(NY).date() - timedelta(days=1)
    days_total = max(0, (end-anchor).days+1)
    if days_total > max_days:
        raise ValueError("requested_season_longer_than_collection_day_budget")
    prior, complete_days = _validated_previous(previous_dir, league, anchor, began)
    missing = [anchor+timedelta(days=i) for i in range(days_total)
               if (anchor+timedelta(days=i)).isoformat() not in complete_days]
    batches = _segments(missing)
    conflicts, errors = set(), Counter()
    successful = 0
    attempts = 0
    for first, last, duration in batches:
        if duration > MAX_DAYS_PER_REQUEST:
            raise ValueError("season_chunk_over_35_days")
        # The caller's collector is the original capped 1-35-day scoreboard
        # function; it timestamps source responses AFTER receipt.
        rows, report = collector((league,), duration, last)
        stats = report.get("by_league", {}).get(league)
        if (not isinstance(rows, list) or not isinstance(stats, dict)
                or stats.get("days_attempted") != duration
                or stats.get("days_ok", -1)+stats.get("days_failed", -1) != duration
                or report.get("total_completed_results") != len(rows)
                or report.get("sportsgameodds_api_requests") != 0
                or report.get("champion_001_modified") is not False):
            raise ValueError("untrusted_or_incomplete_scoreboard_batch_receipt")
        attempts += duration
        if stats["days_failed"]:
            errors.update({"source_day_fetch_failures": stats["days_failed"]})
        else:
            successful += duration
            complete_days.update(
                (first+timedelta(days=i)).isoformat() for i in range(duration))
        batch = _verify_history(rows, league, _asof(clock), anchor)
        for eid, row in batch.items():
            if eid in prior:
                old = prior[eid]
                # A source correction or non-identical identity needs review;
                # never silently select the result most favorable to a bet.
                comparable = ("league", "espn_event_id", "event_start_utc",
                              "home_team_espn_id", "away_team_espn_id",
                              "home_score", "away_score", "season_type")
                if any(old.get(x) != row.get(x) for x in comparable):
                    conflicts.add(eid)
                    continue
            else:
                prior[eid] = row
    asof = _asof(clock)
    if asof.astimezone(NY).date() != began.astimezone(NY).date():
        raise ValueError("season_scan_crossed_local_date")
    # Do not report complete when source events are contradictory.
    manifest = {
        "report_type": "V8_ALL_EIGHT_LEAGUES_SEASON_COVERAGE",
        "league": league, "season_label_collection_not_official": season,
        "conservative_collection_anchor_et": anchor.isoformat(),
        "source_history_through_et": end.isoformat(),
        "source_days_expected": days_total,
        "source_days_confirmed_et": sorted(complete_days),
        "source_days_confirmed_total": len(complete_days),
        "source_days_failed_in_latest_collection": errors["source_day_fetch_failures"],
        "source_days_requested_in_latest_collection": attempts,
        "source_days_successful_in_latest_collection": successful,
        "source_batches_attempted_in_latest_collection": len(batches),
        "conflicting_game_event_ids": sorted(conflicts),
        "source_coverage_complete": (
            len(complete_days) == days_total and not conflicts),
        "retained_published_final_results": len(prior),
        "as_of_utc": asof.isoformat(),
        "source": "ESPN public scoreboard, per-request receipt timestamps",
        "coverage_claim_does_not_certify_independent_source_custody": True,
        "not_official_league_market_settlement": True,
        "historical_pregame_feature_timestamps_not_reconstructed": True,
        "all_sport_player_prop_histories_separately_collected": False,
        "champion_001_modified": False,
        "certified_positive_ev_bets": 0, "wagers_placed": 0,
    }
    history = sorted(prior.values(), key=lambda r:(
        r["event_start_utc"], r["espn_event_id"]))
    board = _team_board(history, league, asof, manifest)
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root/"SEASON_RESULTS.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True)+"\n" for r in history),
        encoding="utf-8")
    (root/"SEASON_COVERAGE.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    (root/"TEAM_LAST5_LAST10.json").write_text(
        json.dumps(board, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    lines = [
        f"# {league.upper()} — full season search since {anchor.isoformat()}",
        "**Conservative collection anchor, NOT verified official opening day.**",
        f"**As of:** {asof.isoformat()}",
        f"**ESPN source days:** {len(complete_days)}/{days_total}; "
        f"full coverage: {manifest['source_coverage_complete']}",
        f"**Published final games retained:** {len(history)}",
        "**All values are published score research, not calibrated +EV, "
        "market settlements or player prop probabilities.**",
        "| Team | L5 (W-D-L) | L10 (W-D-L) | L5 avg for/against | Last 10 avg total | Coverage |",
        "|---|---|---|---|---|---|",
    ]
    def wdl(x):
        return (f"{x['wins']}-{x['draws']}-{x['losses']}"
                if x["complete_window"] else "INCOMPLETE")
    for v in board["teams"].values():
        a, b = v["last5"], v["last10"]
        nm = str(v["team_name_from_most_recent_ESPN_result"]).replace("|", "/")
        lines.append(f"| {nm} | {wdl(a)} | {wdl(b)} "
                     f"| {a['avg_scored']} / {a['avg_allowed']} "
                     f"| {b['avg_game_total_display_score']} "
                     f"| {'complete' if board['complete_scoreboard_day_coverage'] else 'partial'} |")
    (root/"TEAM_LAST5_LAST10.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return manifest, board


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league", required=True, choices=sorted(LEAGUES))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--previous-dir")
    args=parser.parse_args(argv)
    manifest, board=collect_season(args.league,args.output_dir,
                                   previous_dir=args.previous_dir)
    print(json.dumps({
        "league":args.league,
        "days_complete":manifest["source_days_confirmed_total"],
        "days_expected":manifest["source_days_expected"],
        "published_games":manifest["retained_published_final_results"],
        "teams":board["teams_in_published_history"],
        "coverage_complete":manifest["source_coverage_complete"],
        "certified_positive_ev_bets":0,
    }, sort_keys=True))


if __name__=="__main__":
    main()
