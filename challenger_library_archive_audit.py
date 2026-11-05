"""Audit user-owned ChatGPT Library historical ZIPs without training or wagering.

No network, no source promotion, no Champion execution. ZIP SHA matches prove
local byte consistency, not independently authenticated pregame publication.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import zipfile

LEAGUES = ("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls",
           "uefa_champions_league")
EXPECTED = {"artifact_integrity_manifest.json", "champion_authentication.json",
            "historical_published_scores.sqlite", "history_coverage.json",
            "independently_qualified_holdout.jsonl", "oos_calibration_report.json"}
LEGACY_RESULTS = "01_historical_game_results.csv"
LEGACY_QUOTES = "03_archived_quotes_TIMESTAMP_BEFORE_START_UNCONFIRMED.csv"


def utc(t):
    if not isinstance(t, str):
        raise ValueError("missing_timestamp")
    d = datetime.fromisoformat(t.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("naive_timestamp")
    return d.astimezone(timezone.utc)


def checked_zip(path):
    z = zipfile.ZipFile(path)
    entries = z.infolist()
    if (len(entries) > 100 or
        sum(x.file_size for x in entries) > 25_000_000 or
        len(entries) != len({x.filename for x in entries}) or
        any(x.flag_bits & 1 or x.filename.startswith("/") or
            ".." in Path(x.filename).parts for x in entries)):
        z.close()
        raise ValueError("unsafe_historical_archive")
    return z


def audit_history(zip_path):
    with checked_zip(zip_path) as z:
        if set(z.namelist()) != EXPECTED:
            raise ValueError("historical_archive_schema_mismatch")
        manifest = json.loads(z.read("artifact_integrity_manifest.json"))
        records = manifest.get("artifacts")
        if (not isinstance(records, list) or len(records) != 4 or
            {x["name"] for x in records} !=
            EXPECTED - {"artifact_integrity_manifest.json",
                        "independently_qualified_holdout.jsonl"}):
            raise ValueError("incomplete_original_hash_manifest")
        for item in records:
            raw = z.read(item["name"])
            if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError("tampered_original_archive_bytes")
        coverage = json.loads(z.read("history_coverage.json"))
        champion = json.loads(z.read("champion_authentication.json"))
        calibration = json.loads(z.read("oos_calibration_report.json"))
        if (coverage.get("stage") !=
                "challenger_multiseason_published_score_sqlite_research_only"
            or coverage.get("independently_qualified_training_records") != 0
            or coverage.get("champion_001_modified") is not False
            or manifest.get("externally_signed") is not False
            or manifest.get("independently_authenticated") is not False
            or manifest.get("champion_001_modified") is not False
            or champion.get("original_executable_verified") is not False
            or champion.get("immutable_model_version_authenticated") is not False
            or champion.get("reproducible_reference_outputs_verified") is not False
            or champion.get("champion_001_modified") is not False
            or calibration.get("certified_groups") != 0
            or calibration.get("rows_received") != 0
            or z.getinfo("independently_qualified_holdout.jsonl").file_size != 0):
            raise ValueError("unsafe_training_or_authentication_promotion")
        raw = z.read("historical_published_scores.sqlite")
        if not raw.startswith(b"SQLite format 3\x00"):
            raise ValueError("invalid_sqlite_archive")
    with TemporaryDirectory() as folder:
        dbpath = Path(folder) / "archive.sqlite"
        dbpath.write_bytes(raw)
        con = sqlite3.connect("file:" + str(dbpath) + "?mode=ro&immutable=1", uri=True)
        try:
            con.execute("PRAGMA query_only=ON")
            con.execute("PRAGMA trusted_schema=OFF")
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("sqlite_integrity_failure")
            tables = {row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if tables != {"archive_windows", "published_games", "source_observations",
                          "conflicting_events"}:
                raise ValueError("unexpected_sqlite_schema")
            games = con.execute(
                "SELECT league,season,espn_event_id,start_utc,"
                "home_score,away_score,published_result,"
                "bookmaker_settlement_verified,independent_outcome_adjudication,"
                "historically_qualified_training FROM published_games").fetchall()
            observations = con.execute(
                "SELECT league,espn_event_id,run_id,retrieved_at_utc,"
                "eligible_for_training FROM source_observations").fetchall()
            windows = con.execute("SELECT run_id,league FROM archive_windows").fetchall()
            conflicts = con.execute("SELECT count(*) FROM conflicting_events").fetchone()[0]
        finally:
            con.close()
    if len(games) > 100_000 or len(observations) > 1_000_000:
        raise ValueError("unbounded_archive")
    by_league, by_season, starts = Counter(), {}, {}
    for row in games:
        league, season, event, at, home, away, winner, book, adjudicated, trained = row
        if (league not in LEAGUES or not str(event).isdigit() or
            type(home) is not int or type(away) is not int or
            home < 0 or away < 0 or
            winner != ("home" if home > away else "away" if away > home else "draw") or
            book != 0 or adjudicated != 0 or trained != 0):
            raise ValueError("unverified_historical_result_attempted_promotion")
        key = (league, event)
        if key in starts:
            raise ValueError("duplicate_historical_game")
        starts[key] = utc(at)
        by_league[league] += 1
        by_season.setdefault(league, set()).add(season)
    source_times, runs = Counter(), set()
    for league, event, run_id, when, qualified in observations:
        if (league, event) not in starts or qualified != 0:
            raise ValueError("orphan_or_promoted_source_observation")
        source_times["postgame" if utc(when) >= starts[league,event] else "pregame"] += 1
        runs.add(run_id)
    if (len(by_league) != len(LEAGUES)
        or len(games) != coverage.get("published_games_deduplicated")
        or len(observations)-len(games) != coverage.get("consistent_repeated_observations")
        or len(windows) != coverage.get("archive_windows_accepted")
        or len(runs) != coverage.get("distinct_gitHub_run_ids")
        or conflicts != coverage.get("conflicting_event_ids_quarantined")):
        raise ValueError("research_archive_coverage_reconciliation_failed")
    return {
        "stage": "challenger_88_chatgpt_library_history_research_only",
        "history_zip_sha256": hashlib.sha256(Path(zip_path).read_bytes()).hexdigest(),
        "four_local_hashes_match_bytes": True,
        "sqlite_integrity": "ok",
        "deduplicated_historical_games": len(games),
        "archived_source_observations": len(observations),
        "repeated_observations_not_new_games": len(observations)-len(games),
        "source_observations_retrieved_after_or_at_game_start": source_times["postgame"],
        "source_observations_retrieved_before_game_start": source_times["pregame"],
        "archive_windows_accepted": len(windows),
        "archive_windows_rejected": coverage["archives_rejected"],
        "run_count": len(runs),
        "by_league": {
            league: {"game_results": by_league[league],
                     "seasons": sorted(by_season[league]),
                     "qualified_training_games": 0}
            for league in LEAGUES},
        "original_hashes_independently_publisher_signed": False,
        "qualifying_pregame_features_in_archive": 0,
        "qualified_chronological_training_games": 0,
        "direct_draftkings_checkout_quotes_verified": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
    }


def audit_legacy(archive):
    with checked_zip(archive) as z:
        if not {LEGACY_RESULTS,LEGACY_QUOTES} <= set(z.namelist()):
            raise ValueError("missing_legacy_csv_evidence")
        scores = list(csv.DictReader(io.StringIO(
            z.read(LEGACY_RESULTS).decode("utf-8-sig"))))
        quotes = list(csv.DictReader(io.StringIO(
            z.read(LEGACY_QUOTES).decode("utf-8-sig"))))
    if any(row.get("status") != "FINAL" or
           row.get("start_time_is_actual_confirmed") != "NO"
           for row in scores):
        raise ValueError("legacy_scores_cannot_be_promoted")
    if any(row.get("pregame_confirmed") != "NO" or
           row.get("usable_for_model_backtest") != "NO" for row in quotes):
        raise ValueError("legacy_quotes_cannot_be_promoted")
    return {
        "legacy_result_rows_not_merged": len(scores),
        "old_provider_timestamp_quotes_unconfirmed": len(quotes),
        "draftkings_labeled_unconfirmed": sum(
            x.get("sportsbook") == "draftkings" for x in quotes),
        "direct_draftkings_checkout_quotes_verified": 0,
        "qualified_chronological_training_games": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--history-zip", required=True)
    p.add_argument("--legacy-zip")
    p.add_argument("--output", required=True)
    a = p.parse_args(argv)
    report = audit_history(a.history_zip)
    if a.legacy_zip:
        report["legacy_research_only"] = audit_legacy(a.legacy_zip)
    path = Path(a.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError("refusing_to_overwrite_existing_source_audit")
    path.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"historical_games":report["deduplicated_historical_games"],
                      "certified_training_games":0,"champion_001_modified":False}))


if __name__ == "__main__":
    main()
