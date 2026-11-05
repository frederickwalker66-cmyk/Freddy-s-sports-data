"""Upgrade #76: strict league-operated game identity crosscheck; research only.

The independent NHL original HTTP response can corroborate an archived
ESPN event's team IDs and kickoff. No ESPN/league schedule receipt is an
independent DraftKings checkout quote or a native model prediction.
Every other league remains explicitly unverified until its own adapter exists.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from challenger_nhl_official_score_crosscheck import (
    FULL_TO_ABBREV, day_url, fetch_scoreboard, normalized_name, parse_scoreboard,
)
from challenger_prospective_outcome_validation import instant
from independent_schedule_review import SOURCES

EASTERN = ZoneInfo("America/New_York")
MAX_KICKOFF_SKEW_SECONDS = 60


def audit(records, nhl_receipts):
    """Fail closed on game identity, clocks, duplication, and source custody.

    nhl_receipts[yyyy-mm-dd] is {raw: bytes, observed_at_utc: aware ISO datetime,
    source_url: exact official NHL endpoint}. Missing/late/invalid responses
    stay unverified. This function never promotes prices or probabilities.
    """
    if not isinstance(records, list) or not isinstance(nhl_receipts, dict):
        raise ValueError("invalid_independent_identity_inputs")
    parsed = {}
    errors = {}
    for day, receipt in nhl_receipts.items():
        try:
            if not isinstance(receipt, dict) or receipt.get("source_url") != day_url(day):
                raise ValueError("official_nhl_source_url_invalid")
            fetched = instant(receipt["observed_at_utc"])
            raw = receipt["raw"]
            if not isinstance(raw, bytes) or not raw:
                raise ValueError("official_nhl_original_bytes_unavailable")
            parsed[day] = (parse_scoreboard(raw, day), fetched,
                           hashlib.sha256(raw).hexdigest())
        except (KeyError, TypeError, ValueError, UnicodeError, OverflowError) as exc:
            errors[day] = str(exc)[:120]
    seen_espn = set()
    used_nhl = set()
    rows = []
    reasons = Counter()
    for r in records:
        if (not isinstance(r, dict) or r.get("league") not in SOURCES
                or r.get("record_type") != "prospective_evidence_snapshot_research_only"
                or r.get("certified_prediction") is not False
                or r.get("model_probability") is not None
                or r.get("bet_ready") is not False
                or r.get("qualified_for_challenger_backtest") is not False
                or r.get("champion_001_modified") is not False):
            raise ValueError("unsafe_independent_identity_archive_row")
        league, eid = r["league"], r.get("espn_schedule_event_id")
        key = (league, eid)
        if not isinstance(eid, str) or not eid.isdecimal() or key in seen_espn:
            raise ValueError("missing_or_duplicate_espn_game_identity")
        seen_espn.add(key)
        start = instant(r["event_start_utc"])
        captured = instant(r["snapshot_completed_at_utc"])
        prior = instant(r["schedule_observed_at_utc"])
        if not prior <= captured < start:
            raise ValueError("game_archive_not_genuinely_pregame")
        home = normalized_name(r.get("home_team"))
        away = normalized_name(r.get("away_team"))
        if not home or not away or home == away:
            raise ValueError("malformed_espn_matchup")
        if not isinstance(r.get("odds_observations"), list):
            raise ValueError("missing_research_market_observation_list")
        result = {
            "league": league,
            "espn_event_id": eid,
            "home_team": r["home_team"], "away_team": r["away_team"],
            "event_start_utc": start.isoformat(),
            "espn_archive_completed_utc": captured.isoformat(),
            "nhl_official_game_id": None,
            "nhl_official_source_url": None,
            "nhl_original_response_sha256": None,
            "nhl_response_observed_utc": None,
            "aggregator_quote_rows_not_checkout_verified": len(r["odds_observations"]),
            "official_league_pregame_identity_matched_research_only": False,
            "exact_draftkings_market_identity_verified": False,
            "draftkings_checkout_price_verified": False,
            "native_model_probability_verified": False,
            "qualified_for_training": False, "certified_prediction": False,
            "bet_ready": False, "champion_001_modified": False,
        }
        status = "official_league_adapter_not_available"
        if league == "nhl":
            day = start.astimezone(EASTERN).date().isoformat()
            result["nhl_official_source_url"] = day_url(day)
            if day in errors:
                status = "invalid_nhl_original_response"
            elif day not in parsed:
                status = "nhl_official_response_not_captured"
            else:
                games, observed, digest = parsed[day]
                result["nhl_original_response_sha256"] = digest
                result["nhl_response_observed_utc"] = observed.isoformat()
                if not captured <= observed < start:
                    status = "nhl_response_not_observed_pregame"
                elif home not in FULL_TO_ABBREV or away not in FULL_TO_ABBREV:
                    status = "unsupported_nhl_exact_team_identity"
                else:
                    possibilities = [g for g in games
                        if g["home_abbrev"] == FULL_TO_ABBREV[home]
                        and g["away_abbrev"] == FULL_TO_ABBREV[away]]
                    matched = [g for g in possibilities if
                        abs((g["start"] - start).total_seconds())
                        <= MAX_KICKOFF_SKEW_SECONDS]
                    if len(matched) != 1:
                        status = ("nhl_kickoff_disagrees" if possibilities and not matched
                                  else "nhl_match_missing_or_ambiguous")
                    else:
                        nhl_id = matched[0]["nhl_game_id"]
                        if nhl_id in used_nhl:
                            raise ValueError("nhl_official_game_reused_by_multiple_espn_ids")
                        used_nhl.add(nhl_id)
                        result["nhl_official_game_id"] = nhl_id
                        result["official_league_pregame_identity_matched_research_only"] = True
                        status = "nhl_exact_pregame_game_identity_agrees_research_only"
        result["identity_status"] = status
        reasons[status] += 1
        rows.append(result)
    matched = sum(x["official_league_pregame_identity_matched_research_only"] for x in rows)
    summary = {
        "stage": "challenger_76_independent_league_identity_research_only",
        "archived_espn_events_reviewed": len(rows),
        "independently_observed_nhl_pregame_identity_matches_research_only": matched,
        "independent_identity_unverified": len(rows) - matched,
        "by_status": dict(sorted(reasons.items())),
        "nhl_source_errors": dict(sorted(errors.items())),
        "direct_draftkings_checkout_markets_verified": 0,
        "verified_native_model_probabilities": 0,
        "qualified_chronological_training_games": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": "NHL source is a distinct league-operated schedule observed at fetch time, "
                   "not an authenticated publisher timestamp, player status, independent "
                   "DraftKings market, native forecast, or positive EV.",
    }
    return rows, summary


def run(capture_dir, output_dir, fetcher=fetch_scoreboard, clock=None):
    """Bounded NHL schedule queries for dates containing archived future NHL games."""
    root = Path(capture_dir)
    preflight = json.loads((root / "eight_sport_schedule_coverage.json").read_text())
    records = [json.loads(s) for s in
        (root / "prospective_event_evidence.jsonl").read_text().splitlines() if s.strip()]
    if (preflight.get("archived_games_matching_exact_original_event_fields") != len(records)
            or preflight.get("original_espn_source_responses_verified", 0) < 1
            or preflight.get("champion_001_modified") is not False
            or preflight.get("certified_positive_ev_bets") != 0):
        raise ValueError("original_espn_evidence_not_reconciled_before_official_crosscheck")
    clock = (lambda: datetime.now(timezone.utc)) if clock is None else clock
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError("independent_source_output_directory_must_be_empty")
    output.mkdir(parents=True, exist_ok=True)
    receipts, failures = {}, {}
    nhl_dates = sorted(set(instant(r["event_start_utc"]).astimezone(EASTERN)
                           .date().isoformat() for r in records if r.get("league") == "nhl"))
    for day in nhl_dates:
        started = instant(clock())
        try:
            raw = fetcher(day)
            observed = instant(clock())
            if observed < started:
                raise ValueError("official_nhl_source_clock_regressed")
            if not isinstance(raw, bytes) or not 1 <= len(raw) <= 3_000_000:
                raise ValueError("invalid_official_nhl_original_wire_bytes")
            # Original bytes are retained even if the content fails parsing.
            name = "nhl_official_" + day.replace("-", "") + ".json"
            (output / name).open("xb").write(raw)
            receipts[day] = {"raw": raw, "source_url": day_url(day),
                             "observed_at_utc": observed.isoformat()}
        except (OSError, ValueError, TimeoutError, UnicodeError, OverflowError) as exc:
            failures[day] = type(exc).__name__
    rows, report = audit(records, receipts)
    report["network_source_failures_by_day"] = failures
    report["official_nhl_dates_requested"] = nhl_dates
    (output / "independent_game_identity.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in rows), encoding="utf8")
    (output / "independent_game_identity_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture-dir", required=True)
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()
    result = run(args.capture_dir, args.output_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
