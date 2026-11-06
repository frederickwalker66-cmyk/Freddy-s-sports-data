"""Upgrades #76-78: NHL, MLB and NBA independent pregame identity; research only.

Distinct NHL-, MLB- and NBA-operated original HTTP responses can corroborate
an archived ESPN event's exact home/away identity and kickoff. No ESPN/league schedule receipt is an
independent DraftKings checkout quote or a native model prediction.
The remaining five leagues are explicitly unverified without an adapter.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from challenger_nhl_official_score_crosscheck import (
    FULL_TO_ABBREV, day_url, fetch_scoreboard, normalized_name, parse_scoreboard,
)
from challenger_nba_official_pregame_schedule import (
    fetch_original as fetch_nba_original,
    parse_original as parse_nba_original,
)
from challenger_nba_schedule_clock import (
    NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL, stats_scoreboard_url,
    nba_team_name, source_failure_label,
)
from challenger_mlb_official_pregame_schedule import (
    day_url as mlb_day_url, fetch_schedule as fetch_mlb_schedule,
    normalized_name as mlb_normalized_name, parse_schedule as parse_mlb_schedule,
)
from challenger_prospective_outcome_validation import instant
from independent_schedule_review import SOURCES

EASTERN = ZoneInfo("America/New_York")
MAX_KICKOFF_SKEW_SECONDS = 60


def audit(records, nhl_receipts, mlb_receipts=None, nba_receipts=None):
    """Fail closed on game identity, clocks, duplication, and source custody.

    nhl_receipts[yyyy-mm-dd] is {raw: bytes, observed_at_utc: aware ISO datetime,
    source_url: exact official NHL endpoint}. Missing/late/invalid responses
    stay unverified. This function never promotes prices or probabilities.
    """
    if mlb_receipts is None:
        mlb_receipts = {}
    if nba_receipts is None:
        nba_receipts = {}
    if (not isinstance(records, list) or not isinstance(nhl_receipts, dict)
            or not isinstance(mlb_receipts, dict) or not isinstance(nba_receipts, dict)):
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
    parsed_mlb = {}
    mlb_errors = {}
    for day, receipt in mlb_receipts.items():
        try:
            if not isinstance(receipt, dict) or receipt.get("source_url") != mlb_day_url(day):
                raise ValueError("official_mlb_source_url_invalid")
            observed = instant(receipt["observed_at_utc"])
            raw = receipt["raw"]
            games = parse_mlb_schedule(raw, day)
            parsed_mlb[day] = (games, observed, hashlib.sha256(raw).hexdigest())
        except (KeyError, TypeError, ValueError, UnicodeError, OverflowError) as exc:
            mlb_errors[day] = str(exc)[:120]
    parsed_nba = {}
    nba_errors = {}
    for url, receipt in nba_receipts.items():
        try:
            if not isinstance(receipt, dict) or receipt.get("source_url") != url:
                raise ValueError("nba_official_source_url_invalid")
            observed = instant(receipt["observed_at_utc"])
            rows_nba, digest, kind = parse_nba_original(
                receipt["raw"], url, observed)
            parsed_nba[url] = (rows_nba, observed, digest, kind)
        except (KeyError, TypeError, ValueError, UnicodeError, OverflowError) as exc:
            nba_errors[url] = str(exc)[:120]
    seen_espn = set()
    used_nba = set()
    used_mlb = set()
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
            "mlb_official_game_pk": None,
            "nba_official_game_id": None,
            "nba_official_home_team_id": None,
            "nba_official_away_team_id": None,
            "nba_official_source_url": None,
            "nba_original_response_sha256": None,
            "nba_response_observed_utc": None,
            "mlb_official_home_team_id": None,
            "mlb_official_away_team_id": None,
            "mlb_official_source_url": None,
            "mlb_original_response_sha256": None,
            "mlb_response_observed_utc": None,
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
        elif league == "nba":
            if not parsed_nba:
                status = ("invalid_nba_original_response" if nba_errors else
                          "nba_official_response_not_captured")
            else:
                candidates = []
                for url, (games, observed, digest, kind) in parsed_nba.items():
                    if not captured <= observed < start:
                        continue
                    for game in games:
                        if (nba_team_name(r["home_team"]) == game["home_name"]
                            and nba_team_name(r["away_team"]) == game["away_name"]):
                            candidates.append((game, url, observed, digest))
                if not any(captured <= observed < start
                           for games, observed, digest, kind in parsed_nba.values()):
                    status = "nba_response_not_observed_pregame"
                elif not candidates:
                    status = "nba_match_missing_or_ambiguous"
                else:
                    # Multiple official NBA CDN/Stats receipts may describe
                    # one game, but a contradictory revision blocks the ID.
                    unique = {}
                    conflicts = set()
                    for game, url, observed, digest in candidates:
                        gid = game["nba_game_id"]
                        signature = (game["start"], game["home_id"], game["away_id"])
                        if gid in unique and unique[gid][0] != signature:
                            conflicts.add(gid)
                        else:
                            unique[gid] = (signature, url, observed, digest)
                    if conflicts:
                        status = "nba_conflicting_official_game_revisions"
                    else:
                        matching = [(gid, info) for gid, info in unique.items()
                                    if abs((info[0][0] - start).total_seconds())
                                    <= MAX_KICKOFF_SKEW_SECONDS]
                        if len(matching) != 1:
                            status = ("nba_kickoff_disagrees" if unique and not matching
                                      else "nba_match_missing_or_ambiguous")
                        else:
                            gid, (signature, url, observed, digest) = matching[0]
                            if gid in used_nba:
                                raise ValueError("nba_official_game_reused_by_multiple_espn_ids")
                            used_nba.add(gid)
                            result["nba_official_game_id"] = gid
                            result["nba_official_home_team_id"] = signature[1]
                            result["nba_official_away_team_id"] = signature[2]
                            result["nba_official_source_url"] = url
                            result["nba_original_response_sha256"] = digest
                            result["nba_response_observed_utc"] = observed.isoformat()
                            result["official_league_pregame_identity_matched_research_only"] = True
                            status = "nba_exact_pregame_game_identity_agrees_research_only"
        elif league == "mlb":
            eastern_start = start.astimezone(EASTERN)
            day = eastern_start.date().isoformat()
            requested = [day]
            # Stadium-local "officialDate" may precede Eastern date when a
            # game starts between midnight and 04:59 Eastern.
            if eastern_start.hour < 5:
                requested.insert(0, (eastern_start.date() - timedelta(days=1)).isoformat())
            available = [(d, *parsed_mlb[d]) for d in requested if d in parsed_mlb]
            result["mlb_official_source_url"] = mlb_day_url(day)
            if not available:
                status = ("invalid_mlb_original_response" if
                          any(d in mlb_errors for d in requested) else
                          "mlb_official_response_not_captured")
            else:
                prospective = [(d, games, observed, digest)
                               for d, games, observed, digest in available
                               if captured <= observed < start]
                if not prospective:
                    status = "mlb_response_not_observed_pregame"
                elif not home or not away:
                    status = "unsupported_mlb_exact_team_identity"
                else:
                    # Repeated gamePks with same fields are ordinary; changed
                    # official start/identity across source days is ambiguous.
                    possible = {}
                    conflicts = set()
                    for d, games, observed, digest in prospective:
                        for game in games:
                            if (mlb_normalized_name(game["home_name"]) !=
                                    mlb_normalized_name(r["home_team"]) or
                                mlb_normalized_name(game["away_name"]) !=
                                    mlb_normalized_name(r["away_team"])):
                                continue
                            pk = game["mlb_game_pk"]
                            signature = (game["start"], game["home_id"], game["away_id"])
                            if pk in possible and possible[pk][0] != signature:
                                conflicts.add(pk)
                            else:
                                possible[pk] = (signature, d, observed, digest)
                    if conflicts:
                        status = "mlb_conflicting_official_game_revisions"
                    elif not possible:
                        status = "mlb_match_missing_or_ambiguous"
                    else:
                        aligned = [(pk, record) for pk, record in possible.items()
                                   if abs((record[0][0] - start).total_seconds())
                                   <= MAX_KICKOFF_SKEW_SECONDS]
                        if len(aligned) != 1:
                            status = ("mlb_kickoff_disagrees" if possible and not aligned
                                      else "mlb_match_missing_or_ambiguous")
                        else:
                            pk, (sig, chosen_day, observed, digest) = aligned[0]
                            if pk in used_mlb:
                                raise ValueError("mlb_official_game_reused_by_multiple_espn_ids")
                            used_mlb.add(pk)
                            result["mlb_official_game_pk"] = pk
                            result["mlb_official_home_team_id"] = sig[1]
                            result["mlb_official_away_team_id"] = sig[2]
                            result["mlb_official_source_url"] = mlb_day_url(chosen_day)
                            result["mlb_original_response_sha256"] = digest
                            result["mlb_response_observed_utc"] = observed.isoformat()
                            result["official_league_pregame_identity_matched_research_only"] = True
                            status = "mlb_exact_pregame_game_identity_agrees_research_only"
        result["identity_status"] = status
        reasons[status] += 1
        rows.append(result)
    matched = sum(x["official_league_pregame_identity_matched_research_only"] for x in rows)
    summary = {
        "stage": "challenger_78_independent_league_identity_research_only",
        "archived_espn_events_reviewed": len(rows),
        "independently_observed_nhl_pregame_identity_matches_research_only":
            sum(x["identity_status"] == "nhl_exact_pregame_game_identity_agrees_research_only" for x in rows),
        "independently_observed_nba_pregame_identity_matches_research_only":
            sum(x["identity_status"] == "nba_exact_pregame_game_identity_agrees_research_only" for x in rows),
        "independently_observed_mlb_pregame_identity_matches_research_only":
            sum(x["identity_status"] == "mlb_exact_pregame_game_identity_agrees_research_only" for x in rows),
        "independent_identity_unverified": len(rows) - matched,
        "by_status": dict(sorted(reasons.items())),
        "nhl_source_errors": dict(sorted(errors.items())),
        "mlb_source_errors": dict(sorted(mlb_errors.items())),
        "nba_source_errors": dict(sorted(nba_errors.items())),
        "direct_draftkings_checkout_markets_verified": 0,
        "verified_native_model_probabilities": 0,
        "qualified_chronological_training_games": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": "NHL, MLB and NBA game records originate from distinct league-operated "
                   "schedules observed at fetch time, not independently authenticated "
                   "publication timestamps, active player status, executable "
                   "DraftKings markets, native forecasts, or positive EV.",
    }
    return rows, summary


def run(capture_dir, output_dir, fetcher=fetch_scoreboard, clock=None,
        mlb_fetcher=fetch_mlb_schedule, nba_fetcher=fetch_nba_original):
    """Capture bounded NHL, MLB and NBA original responses for archived future games."""
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
        started = instant(clock().isoformat())
        try:
            raw = fetcher(day)
            observed = instant(clock().isoformat())
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
    # An offseason/no-game MLB scan makes no official MLB requests.
    mlb_receipts, mlb_failures = {}, {}
    mlb_dates = set()
    for r in records:
        if r.get("league") != "mlb":
            continue
        eastern_start = instant(r["event_start_utc"]).astimezone(EASTERN)
        mlb_dates.add(eastern_start.date().isoformat())
        if eastern_start.hour < 5:
            mlb_dates.add((eastern_start.date() - timedelta(days=1)).isoformat())
    for day in sorted(mlb_dates):
        started = instant(clock().isoformat())
        try:
            raw = mlb_fetcher(day)
            observed = instant(clock().isoformat())
            if observed < started:
                raise ValueError("official_mlb_source_clock_regressed")
            if not isinstance(raw, bytes) or not 1 <= len(raw) <= 3_000_000:
                raise ValueError("invalid_official_mlb_original_wire_bytes")
            name = "mlb_official_" + day.replace("-", "") + ".json"
            (output / name).open("xb").write(raw)
            mlb_receipts[day] = {"raw": raw, "source_url": mlb_day_url(day),
                                 "observed_at_utc": observed.isoformat()}
        except (OSError, ValueError, TimeoutError, UnicodeError, OverflowError) as exc:
            mlb_failures[day] = type(exc).__name__
    nba_receipts, nba_failures = {}, {}
    nba_dates = sorted({instant(r["event_start_utc"]).astimezone(EASTERN)
                        .date().isoformat() for r in records if r.get("league") == "nba"})
    if nba_dates:
        # When the full season schedule is denied, NBA Stats ScoreboardV3
        # can be requested separately for each actual *archived future*
        # NBA game date (at most seven calendar days). The NBA daily CDN
        # remains usable only on the observation's actual Eastern date.
        nba_clock = instant(clock().isoformat())
        today_date = nba_clock.astimezone(EASTERN).date()
        today_et = today_date.isoformat()
        eligible_dates = [day for day in nba_dates
                          if today_et <= day <= (today_date + timedelta(days=7)).isoformat()]
        urls = [NBA_SCHEDULE_URL]
        if today_et in eligible_dates:
            urls.append(NBA_TODAY_SCOREBOARD_URL)
        urls.extend(stats_scoreboard_url(day) for day in eligible_dates)
        filenames = {
            NBA_SCHEDULE_URL: "nba_official_season_schedule.json",
            NBA_TODAY_SCOREBOARD_URL: "nba_official_today_scoreboard.json",
            **{stats_scoreboard_url(day): (
                "nba_official_stats_v3_scoreboard.json" if day == today_et
                else "nba_official_stats_v3_" + day.replace("-", "") + ".json")
               for day in eligible_dates},
        }
        for url in urls:
            started = instant(clock().isoformat())
            try:
                raw = nba_fetcher(url)
                observed = instant(clock().isoformat())
                if observed < started:
                    raise ValueError("official_nba_source_clock_regressed")
                if not isinstance(raw, bytes) or not 1 <= len(raw) <= 18_000_000:
                    raise ValueError("invalid_official_nba_original_wire_bytes")
                # Retain original bytes even when parsing detects an invalid
                # league, date or team; never promote a failed response.
                (output / filenames[url]).open("xb").write(raw)
                future, _, kind = parse_nba_original(raw, url, observed)
                nba_receipts[url] = {"raw": raw, "source_url": url,
                                     "observed_at_utc": observed.isoformat()}
                # Full NBA schedule covers the slate; otherwise separately
                # gather bounded per-day fallbacks instead of stopping on
                # the first date with a partial/empty scoreboard.
                if url == NBA_SCHEDULE_URL and future:
                    break
            except (OSError, ValueError, TimeoutError, UnicodeError,
                    OverflowError, TypeError, KeyError) as exc:
                # A GitHub-runner HTTP 403/429 is a distinct access blocker,
                # not a generic "HTTPError" or fabricated schedule.
                nba_failures[url] = source_failure_label(exc)
    rows, report = audit(records, receipts, mlb_receipts, nba_receipts)
    report["official_nba_source_urls_attempted"] = (
        list(nba_failures) + list(nba_receipts))
    report["official_nba_scheduled_dates_reviewed"] = nba_dates
    report["network_nba_source_failures_by_url"] = nba_failures
    report["official_mlb_dates_requested"] = sorted(mlb_dates)
    report["network_mlb_source_failures_by_day"] = mlb_failures
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
