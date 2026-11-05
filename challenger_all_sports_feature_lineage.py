"""Same-run as-observed feature lineage for all eight Challenger research leagues.

Joins *already archived* prospective team-form snapshots to the exact parsed
ESPN final-score observations that supplied the rolling features. Source
response arrival time, NOT job startup, is used. A self-issued digest and ESPN
URL cannot establish historical publication or independently verify facts.
No models, odds, player props, Champion modifications, or wagers.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from challenger_prospective_pregame import LEAGUES, LAG_HOURS, MIN_PRIOR, WINDOW, name_key
from historical_outcomes import parse_time

SOURCE_HOST = "site.api.espn.com"


def checksum(obj):
    return hashlib.sha256(json.dumps(
        obj, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


def source_ok(url):
    u = urlparse(url) if isinstance(url, str) else None
    return bool(u and u.scheme == "https" and u.hostname == SOURCE_HOST)


def build_lineage(events, historical):
    """Fail closed on mismatched source inputs, never qualify training evidence."""
    if not isinstance(events, list) or not isinstance(historical, list):
        raise ValueError("invalid_source_rows")
    history = {}
    for row in historical:
        if not isinstance(row, dict) or row.get("league") not in LEAGUES:
            raise ValueError("invalid_history_league")
        league, event_id = row["league"], str(row.get("espn_event_id", ""))
        if not event_id.isdigit() or (league, event_id) in history:
            raise ValueError("duplicate_or_missing_historical_event_id")
        if (row.get("record_type") != "historical_completed_game_research"
                or row.get("outcome_source") != "espn_public_scoreboard"
                or row.get("champion_001_modified") is not False
                or not source_ok(row.get("source_url"))):
            raise ValueError("unusable_historical_source")
        history[(league, event_id)] = row

    output, seen = [], set()
    counter = Counter()
    for record in events:
        if not isinstance(record, dict):
            raise ValueError("invalid_event_row")
        league, eid = record.get("league"), str(record.get("espn_schedule_event_id", ""))
        if (league not in LEAGUES or not eid.isdigit() or (league, eid) in seen
                or record.get("record_type") != "prospective_evidence_snapshot_research_only"
                or record.get("champion_001_modified") is not False
                or record.get("bet_ready") is not False
                or record.get("model_probability") is not None
                or record.get("qualified_for_challenger_backtest") is not False):
            raise ValueError("invalid_or_promoted_pregame_event")
        seen.add((league, eid))
        started = parse_time(record["event_start_utc"])
        snapshot = parse_time(record["snapshot_completed_at_utc"])
        schedule_observed = parse_time(record["schedule_observed_at_utc"])
        if not schedule_observed <= snapshot < started or not source_ok(record.get("schedule_source_url")):
            raise ValueError("invalid_event_pregame_timing_or_source")
        scopes = {}
        for side in ("home", "away"):
            form = record.get(side + "_team_form")
            team = record.get(side + "_team")
            if not name_key(team):
                raise ValueError("missing_team_identity")
            if form is None:
                scopes[side] = {"status": "missing_reliable_prior_form", "source_rows": [],
                                "independently_published_asof": False}
                counter[(league, "missing_form_sides")] += 1
                continue
            ids = form.get("prior_espn_event_ids")
            urls = form.get("source_urls")
            if (not isinstance(ids, list) or not MIN_PRIOR <= len(ids) <= WINDOW
                    or len(set(ids)) != len(ids) or not isinstance(urls, list)
                    or len(ids) != len(urls) or form.get("last_games") != len(ids)
                    or form.get("historical_original_publication_times_verified") is not False
                    or parse_time(form.get("retrieval_asof_utc")) != snapshot
                    or form.get("result_start_embargo_hours") != LAG_HOURS):
                raise ValueError("invalid_team_form_receipt")
            prior = []
            for source_id, url in zip(ids, urls):
                g = history.get((league, source_id))
                if g is None or g.get("source_url") != url:
                    raise ValueError("team_form_prior_source_missing_or_mismatched")
                past = parse_time(g["event_start_utc"])
                retrieved = parse_time(g["retrieved_at_utc"])
                if not past < started - timedelta(hours=LAG_HOURS) or not past < retrieved <= snapshot:
                    raise ValueError("prior_score_not_observed_before_event")
                home, away = name_key(g.get("home_team")), name_key(g.get("away_team"))
                if name_key(team) not in (home, away) or home == away:
                    raise ValueError("prior_team_identity_mismatch")
                hs, aws = g.get("home_score"), g.get("away_score")
                if (type(hs) is not int or type(aws) is not int
                        or min(hs, aws) < 0 or max(hs, aws) > 999
                        or (league == "nba" and g.get("season_type") != 2)):
                    raise ValueError("invalid_score_or_season")
                diff = (hs - aws) if home == name_key(team) else (aws - hs)
                prior.append({
                    "espn_event_id": source_id,
                    "event_start_utc": past.isoformat(),
                    "source_observed_at_utc": retrieved.isoformat(),
                    "source_url": url,
                    "team_margin": diff,
                    "parsed_row_sha256_self_attested": checksum(g),
                })
            if (sorted(prior, key=lambda r: (r["event_start_utc"], r["espn_event_id"])) != prior
                    or round(sum(item["team_margin"] > 0 for item in prior) / len(prior), 6) != form.get("win_rate")
                    or round(sum(item["team_margin"] for item in prior) / len(prior), 6) != form.get("margin_average")):
                raise ValueError("team_form_does_not_reproduce_from_sources")
            scopes[side] = {
                "status": "same_run_parsed_source_lineage_unverified",
                "source_rows": prior,
                "form_values_reproduced": True,
                "independently_published_asof": False,
            }
            counter[(league, "linked_form_sides")] += 1
        linked = all(scopes[side]["form_values_reproduced"] for side in ("home", "away")
                     if "form_values_reproduced" in scopes[side]) and all(
                     scopes[side]["status"] == "same_run_parsed_source_lineage_unverified"
                     for side in ("home", "away"))
        counter[(league, "events")] += 1
        counter[(league, "both_forms_lineage_reproduced")] += int(linked)
        output.append({
            "record_type": "challenger_eight_sport_parsed_feature_lineage_research_only",
            "league": league,
            "event_id": eid,
            "event_start_utc": started.isoformat(),
            "observed_pregame_snapshot_utc": snapshot.isoformat(),
            "home": scopes["home"], "away": scopes["away"],
            "both_team_forms_reproduced": linked,
            "original_scoreboard_bytes_preserved_by_this_stage": False,
            "original_scoreboard_publication_independently_authenticated": False,
            "historical_features_independently_qualified": False,
            "certified_prediction": False,
            "bet_ready": False,
            "champion_001_modified": False,
        })
    by_league = {lg: {
        "prospective_games": counter[(lg, "events")],
        "both_team_forms_reproduced": counter[(lg, "both_forms_lineage_reproduced")],
        "side_forms_linked_research_only": counter[(lg, "linked_form_sides")],
        "side_forms_missing": counter[(lg, "missing_form_sides")],
        "qualified_training_rows": 0,
    } for lg in LEAGUES}
    report = {
        "stage": "challenger_eight_sport_parsed_feature_lineage_research_only",
        "by_league": by_league,
        "prospective_games_checked": len(output),
        "both_team_forms_reproduced": sum(v["both_team_forms_reproduced"] for v in by_league.values()),
        "historical_pregame_feature_provenance_independently_authenticated": False,
        "original_source_response_bytes_independently_authenticated": False,
        "qualified_training_rows": 0,
        "calibration_ready_models": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": "A source-observed timestamp and digest only record this run's research receipt. Original publisher as-of history, independently signed source bytes, native model probabilities and settled outcomes remain unverified.",
    }
    return output, report


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True)
    p.add_argument("--historical", required=True)
    p.add_argument("--output-dir", required=True)
    a = p.parse_args(argv)
    lineage, report = build_lineage(read_jsonl(a.events), read_jsonl(a.historical))
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "feature_lineage.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in lineage), encoding="utf-8")
    (out / "feature_lineage_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stage": report["stage"],
                      "games": report["prospective_games_checked"],
                      "linked_both": report["both_team_forms_reproduced"],
                      "qualified_training_rows": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
