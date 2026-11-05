"""#93–96 NBA prospective $0 research shadow selections and source-replay ledger.

Consumes ORIGINAL already-archived pregame ESPN snapshots + fixed-rule baseline
forecasts; never creates retrospective forecasts, qualifies native model
probabilities, or reads/infers betting odds. A same-event source revision is
quarantined. Published ESPN finals only provide descriptive research grades.

Research selections NEVER count as certified Champion-001 25–50 shadows.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from challenger_prospective_outcome_validation import instant, validate_snapshot
from challenger_research_shadow_baseline import _form, VERSION
from challenger_research_shadow_scorecard import valid_forecast

METHOD = "fixed_0.5_plus_0.3_times_difference_in_previously_observed_5game_win_rate"


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(x):
    return hashlib.sha256(canonical(x).encode("utf8")).hexdigest()


def _loaded(root, filename):
    path = Path(root)
    if path.is_file() and path.name == filename:
        files = [path]
    elif path.is_dir():
        files = sorted(path.rglob(filename))
    else:
        raise FileNotFoundError(path)
    result = []
    for file in files:
        for line in file.read_text(encoding="utf8").splitlines():
            if line.strip():
                if len(result) >= 250000:
                    raise ValueError("research_capture_archive_too_large")
                result.append(json.loads(line))
    return result


def _grade(record, outcome, clock):
    if not isinstance(outcome, dict):
        return "awaiting_published_result", None
    if (outcome.get("status") != "linked_to_espn_published_final_only"
            or outcome.get("league") != "nba"
            or str(outcome.get("espn_event_id")) != record["espn_event_id"]
            or outcome.get("home_team") != record["home_team"]
            or outcome.get("away_team") != record["away_team"]
            or outcome.get("independent_league_outcome_verified") is not False
            or outcome.get("qualified_for_challenger_backtest") is not False
            or outcome.get("bet_ready") is not False
            or outcome.get("champion_001_modified") is not False):
        return "unverified_or_mismatched_result_quarantined", None
    final = outcome.get("published_outcome")
    if not isinstance(final, dict) or final.get("result") not in ("home", "away"):
        return "invalid_or_tied_published_result_quarantined", None
    try:
        start = instant(record["event_start_utc"])
        final_seen = instant(final["published_retrieved_at_utc"])
        linked_start = instant(outcome["event_start_utc"])
    except (ValueError, KeyError, TypeError, OverflowError):
        return "invalid_published_outcome_timing", None
    if linked_start != start or not start < final_seen <= clock:
        return "invalid_published_outcome_timing", None
    return "linked_to_espn_published_final_research_only", final["result"]


def build_ledger(snapshots, forecasts, linked=None, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("utc_aware_clock_required")
    now = now.astimezone(timezone.utc)
    if not isinstance(snapshots, list) or not isinstance(forecasts, list):
        raise ValueError("original_snapshots_and_forecasts_required")
    linked = [] if linked is None else linked
    if not isinstance(linked, list):
        raise ValueError("linked_outcomes_must_be_list")

    captures = defaultdict(dict)
    failures = Counter()
    for row in snapshots:
        if not isinstance(row, dict) or row.get("league") != "nba":
            continue
        try:
            key, captured = validate_snapshot(row, now)
        except (ValueError, KeyError, TypeError, OverflowError):
            failures["invalid_original_nba_snapshot"] += 1
            continue
        k = (key[1], captured.isoformat())
        captures[k][sha(row)] = row

    candidates = defaultdict(list)
    for forecast in forecasts:
        if not isinstance(forecast, dict) or forecast.get("league") != "nba":
            continue
        proof = valid_forecast(forecast, now)
        if proof is None or forecast.get("forecast_method") != METHOD:
            failures["invalid_or_after_start_baseline_forecast"] += 1
            continue
        key, generated = proof
        eid = key[1]
        try:
            captured = instant(forecast["snapshot_completed_at_utc"])
        except (ValueError, KeyError, TypeError, OverflowError):
            failures["missing_snapshot_timestamp"] += 1
            continue
        group = captures.get((eid, captured.isoformat()))
        if group is None or len(group) != 1:
            failures["missing_or_conflicting_exact_capture_source"] += 1
            continue
        snapshot = next(iter(group.values()))
        if (snapshot.get("home_team") != forecast.get("home_team")
                or snapshot.get("away_team") != forecast.get("away_team")
                or instant(snapshot["event_start_utc"]) !=
                    instant(forecast["event_start_utc"])):
            failures["snapshot_fixture_identity_mismatch"] += 1
            continue
        h = _form(snapshot.get("home_team_form"), captured)
        a = _form(snapshot.get("away_team_form"), captured)
        if h is None or a is None:
            failures["missing_asof_original_team_form"] += 1
            continue
        p_home = round(0.5 + 0.3 * (h - a), 6)
        if (type(forecast.get("baseline_home_win_probability")) not in (int, float)
                or forecast["baseline_home_win_probability"] != p_home):
            failures["baseline_probability_not_reproducible_from_snapshot"] += 1
            continue
        candidates[eid].append((generated, forecast, snapshot))

    valid = {}
    for eid, rows in candidates.items():
        signatures = {(x["home_team"], x["away_team"],
                       instant(x["event_start_utc"])) for _, x, _ in rows}
        first_time = min(t for t, _, _ in rows)
        first = [(f, snap) for t, f, snap in rows if t == first_time]
        if len(signatures) != 1 or len({sha(f) for f, _ in first}) != 1:
            failures["revised_or_conflicting_nba_forecast_quarantined"] += 1
            continue
        valid[eid] = (first_time, *first[0])
    linked_by_event = defaultdict(list)
    for row in linked:
        if isinstance(row, dict) and row.get("league") == "nba":
            linked_by_event[str(row.get("espn_event_id"))].append(row)

    ledger = []
    grades = Counter()
    for eid, (forecast_time, forecast, snap) in sorted(
            valid.items(), key=lambda item: (item[1][0], item[0])):
        p = forecast["baseline_home_win_probability"]
        side = "home" if p > 0.5 else "away" if p < 0.5 else None
        side_probability = round(max(p, 1-p), 6) if side else None
        row = {
            "record_type": "nba_moneyline_prospective_untrained_shadow_research_only",
            "league": "nba",
            "espn_event_id": eid,
            "market_reference": "full_game_home_away_research_only_no_bookmaker_settlement",
            "home_team": forecast["home_team"],
            "away_team": forecast["away_team"],
            "event_start_utc": instant(forecast["event_start_utc"]).isoformat(),
            "snapshot_completed_at_utc": instant(
                forecast["snapshot_completed_at_utc"]).isoformat(),
            "forecast_created_at_utc": forecast_time.isoformat(),
            "research_selection": side,
            "research_selection_win_probability": side_probability,
            "research_home_win_probability": p,
            "research_away_win_probability": round(1-p, 6),
            "research_method": VERSION,
            "baseline_formula": METHOD,
            "original_snapshot_sha256_self_attested": sha(snap),
            "original_forecast_sha256_self_attested": sha(forecast),
            "trained_challenger_001_model": False,
            "champion_001_prediction": False,
            "counts_toward_champion_001_certified_shadow_target": False,
            "independently_authenticated_source_publication": False,
            "independently_verified_draftkings_checkout_price": False,
            "sportsbook": None,
            "sportsbook_price": None,
            "expected_value_verified": False,
            "certified_prediction": False,
            "bet_ready": False,
            "shadow_stake_usd": 0,
            "champion_001_modified": False,
        }
        row["research_ledger_receipt_sha256_self_attested"] = sha(row)
        outcomes = linked_by_event.get(eid, [])
        status, winner = _grade(row, outcomes[0] if len(outcomes) == 1 else None, now)
        if len(outcomes) > 1:
            status = "duplicate_result_records_quarantined"
        row["published_result_status"] = status
        row["espn_published_winner_research_only"] = winner
        row["directional_research_pick_correct_vs_published_final"] = (
            side == winner if side is not None and winner is not None else None)
        grades[status] += 1
        ledger.append(row)
    report = {
        "stage": "challenger_93_nba_earliest_genuine_pregame_research_selection_ledger",
        "generated_at_utc": now.isoformat(),
        "original_archived_nba_snapshot_records": sum(
            1 for x in snapshots if isinstance(x, dict) and x.get("league")=="nba"),
        "original_untrained_nba_forecast_rows": sum(
            1 for x in forecasts if isinstance(x,dict) and x.get("league")=="nba"),
        "research_unique_events_with_reproduced_original_formula": len(ledger),
        "directional_nba_research_selections": sum(
            r["research_selection"] is not None for r in ledger),
        "neutral_no_selection_events": sum(
            r["research_selection"] is None for r in ledger),
        "linked_to_published_espn_finals_descriptive_only": grades[
            "linked_to_espn_published_final_research_only"],
        "quarantine_reasons": dict(sorted(failures.items())),
        "published_result_statuses": dict(sorted(grades.items())),
        "independently_verified_native_model_training_records": 0,
        "native_challenger_001_predictions": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_selections": 0,
        "verified_direct_draftkings_checkout_prices": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "release_decision": "RESEARCH_ONLY_NOT_CERTIFIED_MODEL_NO_BETTING",
        "warning": "This is a replay-validated, previously recorded UNTRAINED "
                   "NBA form heuristic, not original Champion-001, native trained "
                   "Challenger-001, independent as-of authentication or sportsbook edge. "
                   "Only actual pre-tipoff forecast rows count as research selections. "
                   "Research pick counts DO NOT count toward certified 25-50 shadows.",
    }
    return ledger, report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot-root", required=True)
    p.add_argument("--forecast-root", required=True)
    p.add_argument("--linked-results")
    p.add_argument("--output-dir", required=True)
    args = p.parse_args(argv)
    snaps = _loaded(args.snapshot_root, "prospective_event_evidence.jsonl")
    forecasts = _loaded(args.forecast_root, "research_shadow_forecasts.jsonl")
    linked = _loaded(args.linked_results,"linked_pregame_outcomes.jsonl") if args.linked_results else []
    ledger, report = build_ledger(snaps, forecasts, linked)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out/"nba_untrained_moneyline_shadow_ledger.jsonl").write_text(
        "".join(canonical(row)+"\n" for row in ledger), encoding="utf8")
    (out/"nba_untrained_moneyline_shadow_ledger_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2)+"\n", encoding="utf8")
    print(json.dumps({
        "research_only_nba_selections": report["directional_nba_research_selections"],
        "linked_espn_final_games_uncertified":
            report["linked_to_published_espn_finals_descriptive_only"],
        "native_model_predictions": 0, "certified_model_predictions": 0,
        "champion_001_modified": False}, sort_keys=True))


if __name__ == "__main__":
    main()
