"""#79: same-run ESPN/NBA/MLB/NHL research market reconciliation.

A provider-labeled DraftKings quote is not a directly observed DraftKings
checkout receipt. This audit preserves exact market fields, timestamps and
all missing provenance while forbidding certification/positive EV. No network.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from challenger_prospective_outcome_validation import instant
from independent_schedule_review import SOURCES

MAX_AGE_SECONDS = 120
LEAGUES = tuple(SOURCES)
IDENTITIES = {
    "nba": ("nba_exact_pregame_game_identity_agrees_research_only", "nba_official_game_id"),
    "mlb": ("mlb_exact_pregame_game_identity_agrees_research_only", "mlb_official_game_pk"),
    "nhl": ("nhl_exact_pregame_game_identity_agrees_research_only", "nhl_official_game_id"),
}


def price_ok(price):
    return (type(price) is int and (price <= -100 or price >= 100))


def exact_market(q, league, home, away):
    """Require explicit provider market semantics; never fill missing fields."""
    market = q.get("market_type")
    selection = q.get("selection")
    side = q.get("selection_type")
    line = q.get("line")
    if not isinstance(market, str) or not market or not isinstance(selection, str) or not selection.strip():
        return "missing_exact_market_or_selection"
    if market == "moneyline":
        if league in ("mls", "uefa_champions_league"):
            return "soccer_three_way_settlement_unverified"
        if side not in ("home", "away") or line is not None:
            return "moneyline_side_or_scope_unverified"
        expected = home if side == "home" else away
        if selection.strip().casefold() != expected.strip().casefold():
            return "moneyline_selection_team_identity_mismatch"
        return None
    if market.startswith("player_"):
        if not q.get("player_id_research_only") or side not in ("over", "under", "yes", "no"):
            return "player_prop_id_or_side_unverified"
        if type(line) not in (int, float) or not math.isfinite(line):
            return "player_prop_line_missing"
        return "player_prop_active_status_and_market_unverified"
    return "market_type_or_settlement_scope_not_verified"


def audit(snapshots, identity_rows, identity_report):
    if (not isinstance(snapshots, list) or not isinstance(identity_rows, list)
            or not isinstance(identity_report, dict)):
        raise ValueError("market_audit_requires_same_run_research_inputs")
    if (identity_report.get("archived_espn_events_reviewed") != len(snapshots)
            or identity_report.get("champion_001_modified") is not False
            or identity_report.get("certified_positive_ev_bets") != 0
            or identity_report.get("direct_draftkings_checkout_markets_verified") != 0):
        raise ValueError("unreconciled_or_promoted_independent_identity_report")
    source_by_id = {}
    for entry in identity_rows:
        if not isinstance(entry, dict):
            raise ValueError("invalid_identity_review_row")
        key = (entry.get("league"), entry.get("espn_event_id"))
        if key in source_by_id or key[0] not in LEAGUES:
            raise ValueError("duplicate_or_unknown_identity_review_row")
        if (entry.get("champion_001_modified") is not False
                or entry.get("certified_prediction") is not False
                or entry.get("bet_ready") is not False
                or entry.get("draftkings_checkout_price_verified") is not False
                or entry.get("native_model_probability_verified") is not False):
            raise ValueError("identity_review_already_promoted")
        source_by_id[key] = entry
    if len(source_by_id) != len(snapshots):
        raise ValueError("source_identity_row_count_mismatch")
    observed = []
    classifications = Counter()
    by_league = {l: Counter() for l in LEAGUES}
    seen_events = set()
    seen_quotes = set()
    for snapshot in snapshots:
        if (not isinstance(snapshot, dict)
                or snapshot.get("record_type") != "prospective_evidence_snapshot_research_only"
                or snapshot.get("league") not in LEAGUES
                or snapshot.get("qualified_for_challenger_backtest") is not False
                or snapshot.get("model_probability") is not None
                or snapshot.get("certified_prediction") is not False
                or snapshot.get("bet_ready") is not False
                or snapshot.get("champion_001_modified") is not False):
            raise ValueError("unsafe_source_market_archive")
        league = snapshot["league"]
        eid = snapshot.get("espn_schedule_event_id")
        key = (league, eid)
        if not isinstance(eid, str) or not eid.isdecimal() or key in seen_events:
            raise ValueError("duplicate_or_missing_espn_game_in_market_audit")
        seen_events.add(key)
        review = source_by_id.get(key)
        if review is None:
            raise ValueError("no_same_run_independent_identity_row")
        start = instant(snapshot["event_start_utc"])
        completed = instant(snapshot["snapshot_completed_at_utc"])
        if (review.get("home_team") != snapshot.get("home_team")
                or review.get("away_team") != snapshot.get("away_team")
                or instant(review.get("event_start_utc")) != start
                or instant(review.get("espn_archive_completed_utc")) != completed
                or completed >= start):
            raise ValueError("identity_and_quote_game_receipts_do_not_match")
        quotes = snapshot.get("odds_observations")
        if (not isinstance(quotes, list)
                or review.get("aggregator_quote_rows_not_checkout_verified") != len(quotes)):
            raise ValueError("review_quote_count_does_not_match_original_archive")
        status, source_id_field = IDENTITIES.get(league, (None, None))
        matched = (review.get("identity_status") == status and
                   review.get("official_league_pregame_identity_matched_research_only") is True and
                   isinstance(review.get(source_id_field), str) and bool(review.get(source_id_field))) if status else False
        by_league[league]["games_reviewed"] += 1
        by_league[league]["league_identity_matched_research_only"] += int(matched)
        for q in quotes:
            if not isinstance(q, dict):
                raise ValueError("invalid_archived_quote")
            if (q.get("direct_draftkings_checkout_verified") is not False
                    or q.get("market_primary_line_verified") is not False
                    or q.get("player_available_verified") is not False
                    or q.get("model_probability") is not None
                    or q.get("certified_prediction") is True
                    or q.get("bet_ready") is True):
                raise ValueError("archived_provider_quote_attempted_certification")
            source = q.get("odds_provider")
            source_event = q.get("odds_provider_event_id")
            quote_id = (
                key, source, source_event, q.get("market_type"),
                q.get("selection_type"), q.get("selection"), str(q.get("line")),
                q.get("player_id_research_only"),
            )
            if quote_id in seen_quotes:
                raise ValueError("duplicate_exact_provider_market_in_same_run")
            seen_quotes.add(quote_id)
            reason = None
            try:
                update = instant(q.get("provider_updated_at_utc"))
                receipt = instant(q.get("received_at_utc"))
                if (not update <= receipt <= completed < start
                        or (receipt - update).total_seconds() > MAX_AGE_SECONDS
                        or (completed - receipt).total_seconds() > MAX_AGE_SECONDS):
                    reason = "quote_stale_or_not_actually_pregame"
            except (TypeError, ValueError, OverflowError):
                reason = "invalid_quote_timestamps"
            if not reason and (source not in ("sharpapi_rest", "sportsgameodds_v2")
                               or not isinstance(source_event, str) or not source_event):
                reason = "unknown_provider_or_event_id"
            if not reason and not price_ok(q.get("odds_american")):
                reason = "invalid_exact_american_price"
            if not reason:
                reason = exact_market(q, league, snapshot["home_team"], snapshot["away_team"])
            if not reason and not matched:
                reason = "league_game_identity_not_independently_matched"
            state = (reason or
                     "research_only_exact_aggregator_market_fields_not_direct_bookmaker_quote")
            classifications[state] += 1
            by_league[league]["research_aggregator_quote_rows_reviewed"] += 1
            by_league[league]["market_fields_reconciled_without_bookmaker_proof"] += int(reason is None)
            observed.append({
                "league": league, "espn_event_id": eid,
                "league_game_identity_matched_research_only": matched,
                "provider": source, "provider_event_id": source_event,
                "market_type": q.get("market_type"),
                "selection": q.get("selection"), "selection_type": q.get("selection_type"),
                "line": q.get("line"), "player_id_research_only": q.get("player_id_research_only"),
                "odds_american": q.get("odds_american"),
                "provider_updated_at_utc": q.get("provider_updated_at_utc"),
                "received_at_utc": q.get("received_at_utc"),
                "research_status": state,
                "direct_draftkings_checkout_verified": False,
                "exact_bookmaker_market_verified": False,
                "native_model_probability_verified": False,
                "qualified_for_training": False,
                "certified_prediction": False, "positive_ev_certified": False,
                "bet_ready": False, "shadow_stake_usd": 0,
                "champion_001_modified": False,
            })
    if seen_events != set(source_by_id):
        raise ValueError("unreconciled_identity_rows")
    report = {
        "stage": "challenger_79_exact_aggregator_market_research_quarantine",
        "archived_pregame_events": len(snapshots),
        "provider_quote_rows_reviewed": len(observed),
        "research_market_fields_reconciled": sum(
            v["market_fields_reconciled_without_bookmaker_proof"] for v in by_league.values()),
        "by_league": {l: dict(sorted(c.items())) for l, c in by_league.items()},
        "classifications": dict(sorted(classifications.items())),
        "direct_draftkings_checkout_quotes_verified": 0,
        "exact_direct_bookmaker_market_ids_verified": 0,
        "independently_verified_native_probabilities": 0,
        "qualified_chronological_training_games": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0,
        "automated_wagers": 0,
        "champion_001_modified": False,
        "warning": "Exact provider fields do not establish DraftKings checkout identity, market scope, executable quotes, settlement, model probability or positive EV.",
    }
    return observed, report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshots", required=True)
    p.add_argument("--identity-rows", required=True)
    p.add_argument("--identity-report", required=True)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args(argv)
    snapshots = [json.loads(line) for line in Path(args.snapshots).read_text().splitlines() if line.strip()]
    identities = [json.loads(line) for line in Path(args.identity_rows).read_text().splitlines() if line.strip()]
    report = json.loads(Path(args.identity_report).read_text())
    rows, result = audit(snapshots, identities, report)
    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "exact_market_research_rows.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf8")
    (root / "exact_market_research_report.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps({"stage": result["stage"], "provider_quote_rows_reviewed": len(rows),
                      "certified_positive_ev_bets": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
