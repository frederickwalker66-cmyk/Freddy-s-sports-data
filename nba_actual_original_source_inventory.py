"""Audit genuine archived NBA forward pregame research against original bytes.

Inputs: a READ-ONLY copy of the persistent research/forward-ledger branch and
optional separately fetched authenticated GitHub Actions run metadata.

Source-byte checks, run-clock crosschecks and ESPN pregame identity are
RESEARCH provenance only. A GitHub run or hash cannot establish ESPN original
publisher publication time, independent features, final settlement or
externally authenticated 200+50 NBA training data. No betting/EV output.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

VERSION = "nba-original-source-review-inventory-v1"
FORECAST_FILE = "nba_forward/NBA_FORWARD_FORECASTS.jsonl"
MAX_RUNS = 100
MAX_FORECASTS_PER_RUN = 1000
MAX_ORIGINAL_FILE_BYTES = 5_000_000
SHA_LENGTH = 64

def utc(value):
    if not isinstance(value, str):
        raise ValueError("missing_timestamp")
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("naive_timestamp")
    return t.astimezone(timezone.utc)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read_original(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing_or_linked_original")
    size = path.stat().st_size
    if size < 1 or size > MAX_ORIGINAL_FILE_BYTES:
        raise ValueError("unsafe_original_size")
    return path.read_bytes()

def expected_nba_schedule_event(event, forecast):
    if (not isinstance(event, dict)
            or str(event.get("id")) != forecast["espn_event_id"]
            or utc(event["date"]) != utc(forecast["start_utc"])):
        raise ValueError("original_nba_schedule_identity_or_tipoff_mismatch")
    comps = event.get("competitions")
    if not isinstance(comps, list) or len(comps) != 1:
        raise ValueError("unexpected_original_competitions")
    teams = comps[0].get("competitors")
    if not isinstance(teams, list) or len(teams) != 2:
        raise ValueError("unexpected_original_team_count")
    by_side = {team.get("homeAway"): team for team in teams if isinstance(team, dict)}
    if set(by_side) != {"home", "away"}:
        raise ValueError("ambiguous_original_home_away")
    for side in ("home", "away"):
        entry = by_side[side]
        team = entry.get("team")
        if (str(entry.get("id")) != forecast[side + "_team_espn_id"]
                or not isinstance(team, dict)
                or team.get("displayName") != forecast[side + "_team"]):
            raise ValueError("original_team_id_or_name_mismatch")
    if event.get("status", {}).get("type", {}).get("state") != "pre":
        raise ValueError("original_schedule_not_pregame_state")

def run_metadata(root, run_id, live_dir):
    saved = json.loads(read_original(root / "github_run.json"))
    if (type(saved) is not dict or type(saved.get("id")) is not int
            or saved["id"] != run_id
            or saved.get("conclusion") != "success"
            or saved.get("head_branch") != "main"):
        raise ValueError("invalid_archived_github_run_metadata")
    live = None
    if live_dir is not None:
        location = Path(live_dir) / (str(run_id) + ".json")
        if location.is_file():
            live = json.loads(read_original(location))
            if (type(live) is not dict or live.get("id") != run_id
                    or live.get("head_sha") != saved.get("head_sha")
                    or live.get("created_at") != saved.get("created_at")
                    or live.get("run_started_at") != saved.get("run_started_at")
                    or live.get("conclusion") != "success"):
                raise ValueError("github_live_run_metadata_conflict")
    return saved, live

def audit_forecast(run_root, run_id, row, saved, live, schedule_cache):
    if not isinstance(row, dict):
        raise ValueError("non_object_original_forecast")
    if (row.get("record_type") != "v8_genuine_forward_clocktime_NBA_Elo_research_only"
            or row.get("league") != "nba"
            or row.get("champion_001_modified") is not False
            or row.get("certified_prediction") is not False
            or row.get("bet_ready") is not False
            or row.get("verified_positive_ev") is not False
            or row.get("source_original_publisher_signed") is not False
            or row.get("forecast_reconstructed_after_game") is not False
            or row.get("model_probability_independently_calibrated") is not False
            or row.get("official_result_verified") is not False
            or row.get("stake_usd") != 0):
        raise ValueError("original_forecast_claims_unearned_certification")
    eid = row.get("espn_event_id")
    if not isinstance(eid, str) or not eid.isdigit():
        raise ValueError("invalid_original_espn_event_id")
    p = row.get("model_probability_home_win_research_only")
    if type(p) not in (float, int) or not math.isfinite(p) or not 0 < p < 1:
        raise ValueError("invalid_research_model_probability")
    start = utc(row.get("start_utc"))
    forecast = utc(row.get("forecast_recorded_utc"))
    schedule_seen = utc(row.get("schedule_original_received_at_utc"))
    if not (utc(saved["created_at"]) <= utc(saved["run_started_at"])
            <= schedule_seen <= forecast < start
            and forecast <= utc(saved["updated_at"])):
        raise ValueError("archived_run_or_pregame_clock_conflict")
    if live is not None and not (utc(live["run_started_at"]) <= schedule_seen
                                 <= forecast <= utc(live["updated_at"])):
        raise ValueError("live_github_run_time_mismatch")
    sha = row.get("schedule_original_sha256_local_receipt")
    if not isinstance(sha, str) or len(sha) != SHA_LENGTH or any(ch not in "0123456789abcdef" for ch in sha):
        raise ValueError("missing_original_schedule_digest")
    if not isinstance(row.get("model_version"), str) or not row["model_version"].startswith("v8-nba-elo-forward-research-"):
        raise ValueError("unknown_original_research_model")
    if not isinstance(row.get("schedule_source_url"), str) or not row["schedule_source_url"].startswith(
            "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?"):
        raise ValueError("unknown_nba_original_schedule_publisher")
    matches = []
    for path, (data_hash, event_map) in schedule_cache.items():
        if data_hash != sha:
            continue
        event = event_map.get(eid)
        if event is None:
            continue
        expected_nba_schedule_event(event, row)
        matches.append(path.name)
    if len(matches) != 1:
        raise ValueError("original_source_digest_missing_or_ambiguous_event")
    return {
        "record_type": VERSION,
        "league": "nba", "espn_event_id": eid,
        "event_start_utc": row["start_utc"],
        "first_observed_forecast_utc": row["forecast_recorded_utc"],
        "model_version": row["model_version"],
        "source_publisher": "ESPN",
        "original_schedule_sha256": sha,
        "original_schedule_path": str(matches[0]),
        "original_github_run_id": run_id,
        "github_run_started_utc": saved["run_started_at"],
        "github_live_metadata_crosscheck": live is not None,
        "research_only_first_pregame_capture_timing_plausible": True,
        "original_publisher_publication_time_independently_authenticated": False,
        "independent_pregame_feature_custodian_verified": False,
        "external_holdout_write_once_archive_verified": False,
        "nba_original_final_settlement_independently_verified": False,
        "independently_qualified_training_game": False,
        "independently_qualified_holdout_game": False,
        "draftkings_checkout_price_verified": False,
        "certified_positive_ev": False,
        "bet_ready": False,
        "champion_001_modified": False,
        "source_review_blockers": [
            "original_espn_publisher_asof_publication_not_independently_authenticated",
            "original_features_have_no_independent_pregame_witness",
            "final_nba_full_game_outcome_not_independently_adjudicated",
            "holdout_external_write_once_custody_unverified",
            "no_actual_direct_bookmaker_checkout_proof",
        ],
    }

def audit_archives(root, live_metadata_dir=None):
    root = Path(root)
    runs = sorted(
        (p for p in root.iterdir() if p.is_dir() and p.name.isdigit() and not p.is_symlink()),
        key=lambda x: int(x.name)
    ) if root.is_dir() and not root.is_symlink() else []
    if len(runs) > MAX_RUNS:
        raise ValueError("too_many_archived_original_runs")
    selected, excluded, quarantined = {}, Counter(), set()
    run_reports = []
    for run in runs:
        rid = int(run.name)
        try:
            saved, live = run_metadata(run, rid, live_metadata_dir)
            text = read_original(run / FORECAST_FILE).decode("utf-8")
            lines = [s for s in text.splitlines() if s.strip()]
            if len(lines) > MAX_FORECASTS_PER_RUN:
                raise ValueError("too_many_forecasts_per_original_run")
            schedule_cache = {}
            for path in sorted((run / "nba_forward").glob("nba_original_future_schedule_*.json")):
                raw = read_original(path)
                obj = json.loads(raw)
                if not isinstance(obj, dict) or not isinstance(obj.get("events"), list):
                    raise ValueError("invalid_original_schedule_bytes")
                ids = [str(e["id"]) for e in obj["events"] if isinstance(e, dict) and "id" in e]
                if len(ids) != len(set(ids)):
                    raise ValueError("duplicate_espn_schedule_events")
                schedule_cache[path] = (digest(raw), {str(e["id"]):e for e in obj["events"]})
            accepted = 0
            for line in lines:
                try:
                    row = json.loads(line)
                    item = audit_forecast(run, rid, row, saved, live, schedule_cache)
                    key = item["espn_event_id"]
                    if key in quarantined:
                        # A conflicting first original is never readmitted by
                        # subsequent repeated or later archived receipts.
                        excluded["already_quarantined_first_original_ignored"] += 1
                    elif key in selected:
                        prior = selected[key]
                        if item["first_observed_forecast_utc"] < prior["first_observed_forecast_utc"]:
                            selected[key] = item
                            excluded["later_forecast_superseded_by_original"] += 1
                        elif item["first_observed_forecast_utc"] == prior["first_observed_forecast_utc"] \
                                and item["original_schedule_sha256"] != prior["original_schedule_sha256"]:
                            selected.pop(key)
                            quarantined.add(key)
                            excluded["conflicting_first_original_quarantined"] += 1
                        else:
                            excluded["later_or_equal_original_ignored"] += 1
                    else:
                        selected[key] = item
                    accepted += 1
                except (ValueError, TypeError, KeyError, OverflowError, json.JSONDecodeError) as exc:
                    excluded[str(exc)] += 1
            run_reports.append({"run_id": rid, "original_forecast_rows": len(lines),
                                "source_identity_checked_rows": accepted,
                                "live_run_metadata_checked": live is not None})
        except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
            excluded["run_rejected_" + str(exc)] += 1
            run_reports.append({"run_id": rid, "status": "quarantined", "reason": str(exc)})
    result = sorted(selected.values(), key=lambda r:(r["event_start_utc"],r["espn_event_id"]))
    report = {
        "version": VERSION,
        "status": "RESEARCH_SOURCE_ORIGINAL_BYTES_INVENTORIED_NOT_AUTHENTICATED",
        "archived_run_directories_seen": len(runs),
        "original_run_statuses": run_reports,
        "unique_nba_first_original_research_forecasts_reviewable": len(result),
        "rejected_or_redundant": dict(sorted(excluded.items())),
        "qualified_chronological_training_games": 0,
        "qualified_untouched_holdout_games": 0,
        "shortfall_to_200_training": 200,
        "shortfall_to_50_holdout": 50,
        "source_publication_time_externally_authenticated": False,
        "independent_pregame_source_witnesses_supplied": 0,
        "external_holdout_custody_verified": False,
        "independently_verified_draftkings_checkout_prices": 0,
        "certified_positive_ev_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "bet_ready": False,
        "warning": "Repo archive + GitHub API timing cannot authenticate ESPN original publication or pregame feature provenance. This is NOT a training dataset.",
    }
    return result, report

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", default="research_original_runs_missing")
    parser.add_argument("--live-run-metadata-dir")
    parser.add_argument("--outdir", default="challenger_results/nba_actual_original_source_inventory")
    args = parser.parse_args(argv)
    rows, report = audit_archives(args.archive_root, args.live_run_metadata_dir)
    dest = Path(args.outdir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest/"nba_reviewable_original_source_candidates.jsonl").write_bytes(
        b"".join(json.dumps(r,sort_keys=True,separators=(",",":")).encode()+b"\n" for r in rows))
    (dest/"nba_actual_original_source_inventory.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,sort_keys=True))

if __name__ == "__main__":
    main()
