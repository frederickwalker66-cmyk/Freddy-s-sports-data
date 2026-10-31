"""Consolidate genuine archived eight-league score windows into SQLite.

Only published ESPN game scores. NEVER certify bookmaker settlement,
independent source receipts, point-in-time pregame features, odds, props,
model performance or bets. Does not call SportsGameOdds or any network API.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

from challenger_research_features import validated
from historical_outcomes import LEAGUES, parse_time

EASTERN = ZoneInfo("America/New_York")
CROSS_YEAR = frozenset(("nba", "nfl", "nhl", "ncaaf", "ncaab", "uefa_champions_league"))
SOCCER = frozenset(("mls", "uefa_champions_league"))
RESULT_FILES = "published_results.jsonl"


def season_for(league, start):
    if league not in LEAGUES:
        raise ValueError("unsupported league")
    d = start.astimezone(EASTERN).date()
    if league not in CROSS_YEAR:
        return str(d.year)
    start_year = d.year if d.month >= 7 else d.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(obj):
    return hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


def _check_record(row, league, window):
    start = validated(row)
    if row.get("league") != league:
        raise ValueError("league mismatch")
    if (row.get("bookmaker_market_settlement_verified") is not False
            or row.get("regulation_90_min_result_verified") is not False
            or row.get("published_score_research_only") is not True
            or row.get("provider_event_id_crosswalk_verified") is not False
            or row.get("official_league_result_verified") is not False):
        raise ValueError("record must remain unverified published-score research")
    d = start.astimezone(EASTERN).date().isoformat()
    if not window["window_start_et"] <= d <= window["window_end_et"]:
        raise ValueError("game outside archived window")
    url = urlparse(row["source_url"])
    expected_sport, expected_comp = LEAGUES[league]
    if (url.path != f"/apis/site/v2/sports/{expected_sport}/{expected_comp}/scoreboard"
            or parse_qs(url.query).get("dates") != [d.replace("-", "")]):
        raise ValueError("source endpoint or requested game-day mismatch")
    if row["home_team_espn_id"] == row["away_team_espn_id"]:
        raise ValueError("duplicate participants")
    fingerprint = {
        "league": league, "event": row["espn_event_id"],
        "start": start.isoformat(), "home_id": row["home_team_espn_id"],
        "away_id": row["away_team_espn_id"],
        "home": row["home_team"], "away": row["away_team"],
        "home_score": row["home_score"], "away_score": row["away_score"],
        "result": row["result"], "season_type": row.get("season_type"),
    }
    return {**fingerprint, "season": season_for(league, start),
            "event_day_et": d, "fingerprint": _digest(fingerprint),
            "retrieved_at_utc": parse_time(row["retrieved_at_utc"]).isoformat(),
            "source_url": row["source_url"], "row_digest": _digest(row)}


def _read_window(path, root):
    parts = path.relative_to(root).parts
    if len(parts) < 3 or not parts[0].isdigit():
        raise ValueError("expected artifact in RUN_ID/ARTIFACT_NAME/published_results.jsonl")
    run_id, artifact_name = parts[0], parts[1]
    if not artifact_name.startswith("challenger-backfill-") or not artifact_name.endswith("-" + run_id):
        raise ValueError("invalid archived artifact identity")
    league = artifact_name[len("challenger-backfill-"):-len("-" + run_id)]
    if league not in LEAGUES:
        raise ValueError("unknown archived league")
    folder = path.parent
    report = json.loads((folder / "backfill_coverage.json").read_text(encoding="utf8"))
    coverage = json.loads((folder / "scoreboard_collection.json").read_text(encoding="utf8"))
    raw = path.read_bytes()
    rows = [json.loads(s) for s in raw.decode("utf8").splitlines() if s.strip()]
    if (report.get("league") != league or
            report.get("published_completed_game_results") != len(rows) or
            report.get("qualified_training_examples") != 0 or
            report.get("officially_adjudicated_results") != 0 or
            report.get("sportsbook_api_requests") != 0 or
            report.get("sportsgameodds_requests") != 0 or
            report.get("certified_champion_001_predictions") != 0 or
            report.get("certified_challenger_001_predictions") != 0 or
            report.get("automated_bets_placed") != 0 or
            report.get("champion_001_modified") is not False):
        raise ValueError("unsafe or mismatched window manifest")
    days = report.get("days_requested")
    good, bad = report.get("scoreboard_days_successful"), report.get("scoreboard_days_failed")
    if (type(days) is not int or not 1 <= days <= 35 or
            type(good) is not int or type(bad) is not int or
            good < 0 or bad < 0 or good + bad != days or
            report.get("public_scoreboard_requests_maximum") != days or
            report.get("coverage_complete") is not (bad == 0)):
        raise ValueError("invalid/misreported day coverage")
    start_day, end_day = (datetime.strptime(report[k], "%Y-%m-%d").date()
                          for k in ("window_start_et", "window_end_et"))
    if (end_day - start_day).days + 1 != days:
        raise ValueError("window duration mismatch")
    if (coverage.get("leagues") != [league] or
            coverage.get("total_completed_results") != len(rows) or
            coverage.get("by_league", {}).get(league, {}).get("days_failed") != bad):
        raise ValueError("scoreboard source coverage inconsistent")
    if league in SOCCER and (report.get("quarantined_research_candidates") != 0
                            or report.get("soccer_90_minute_result_verified") is not False):
        raise ValueError("soccer three-way evidence was incorrectly promoted")
    games = [_check_record(row, league, report) for row in rows]
    keys = [(game["league"], game["event"]) for game in games]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate event within a window")
    return {
        "run_id": run_id, "league": league, "start": str(start_day),
        "end": str(end_day), "days": days, "days_ok": good, "days_failed": bad,
        "result_count": len(rows), "sha256": hashlib.sha256(raw).hexdigest(),
        "games": games,
    }


def _db(dest, windows, winners, observations, conflicts):
    connection = sqlite3.connect(dest)
    try:
        with connection:
            connection.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE archive_windows(
                  run_id TEXT NOT NULL, league TEXT NOT NULL,
                  start_et TEXT NOT NULL, end_et TEXT NOT NULL,
                  days_requested INTEGER NOT NULL, days_fetched INTEGER NOT NULL,
                  days_failed INTEGER NOT NULL, published_games INTEGER NOT NULL,
                  file_sha256 TEXT NOT NULL,
                  PRIMARY KEY(run_id, league)
                );
                CREATE TABLE published_games(
                  league TEXT NOT NULL, season TEXT NOT NULL,
                  espn_event_id TEXT NOT NULL, start_utc TEXT NOT NULL,
                  event_date_et TEXT NOT NULL, home_team_id TEXT NOT NULL,
                  away_team_id TEXT NOT NULL, home_team TEXT NOT NULL,
                  away_team TEXT NOT NULL, home_score INTEGER NOT NULL,
                  away_score INTEGER NOT NULL, published_result TEXT NOT NULL,
                  season_type INTEGER, fingerprint_sha256 TEXT NOT NULL,
                  bookmaker_settlement_verified INTEGER NOT NULL DEFAULT 0,
                  independent_outcome_adjudication INTEGER NOT NULL DEFAULT 0,
                  historically_qualified_training INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY(league, espn_event_id)
                );
                CREATE TABLE source_observations(
                  league TEXT NOT NULL, espn_event_id TEXT NOT NULL,
                  run_id TEXT NOT NULL, source_url TEXT NOT NULL,
                  retrieved_at_utc TEXT NOT NULL, record_sha256 TEXT NOT NULL,
                  eligible_for_training INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY(league, espn_event_id, run_id)
                );
                CREATE TABLE conflicting_events(
                  league TEXT NOT NULL, espn_event_id TEXT NOT NULL,
                  distinct_versions INTEGER NOT NULL, disposition TEXT NOT NULL
                );
                CREATE INDEX ix_games_league_season_date
                  ON published_games(league, season, event_date_et);
                CREATE INDEX ix_games_team_home
                  ON published_games(league, home_team_id, event_date_et);
                CREATE INDEX ix_games_team_away
                  ON published_games(league, away_team_id, event_date_et);
            """)
            connection.executemany("INSERT INTO archive_windows VALUES (?,?,?,?,?,?,?,?,?)", (
                (w["run_id"], w["league"], w["start"], w["end"],
                 w["days"], w["days_ok"], w["days_failed"], w["result_count"], w["sha256"])
                for w in windows
            ))
            connection.executemany(
                "INSERT INTO published_games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,0)", (
                    (r["league"], r["season"], r["event"], r["start"],
                     r["event_day_et"], r["home_id"], r["away_id"], r["home"],
                     r["away"], r["home_score"], r["away_score"], r["result"],
                     r["season_type"], r["fingerprint"])
                    for r in winners
                )
            )
            connection.executemany(
                "INSERT INTO source_observations VALUES (?,?,?,?,?,?,0)",
                ((g["league"], g["event"], run, g["source_url"],
                  g["retrieved_at_utc"], g["row_digest"]) for run, g in observations)
            )
            connection.executemany(
                "INSERT INTO conflicting_events VALUES (?,?,?,?)",
                ((league, event_id, versions, "quarantined_all_versions")
                 for (league, event_id), versions in conflicts.items())
            )
    finally:
        connection.close()


def assemble(root, dest):
    root, dest = Path(root), Path(dest)
    files = sorted(root.rglob(RESULT_FILES))
    if not files:
        raise FileNotFoundError("no real archived historical-score JSONL files")
    windows = []
    sources = defaultdict(list)
    rejected = []
    run_league = set()
    for path in files:
        try:
            w = _read_window(path, root)
            key = (w["run_id"], w["league"])
            if key in run_league:
                raise ValueError("duplicate window from same run/league")
            run_league.add(key)
            windows.append(w)
            for g in w["games"]:
                sources[(g["league"], g["event"])].append((w["run_id"], g))
        except (ValueError, KeyError, TypeError, UnicodeError,
                json.JSONDecodeError, OSError) as exc:
            rejected.append({"relative_path": str(path.relative_to(root)),
                             "reason": type(exc).__name__ + ": " + str(exc)[:180]})
    if not windows:
        raise ValueError("all archives rejected; no database may be published")
    conflicts = {}
    winners = []
    observations = []
    for key, versions in sorted(sources.items()):
        fingerprints = {g["fingerprint"] for _, g in versions}
        if len(fingerprints) != 1:
            conflicts[key] = len(fingerprints)
            continue
        # Same score and event identity across archived windows is one game.
        representative = min((g for _, g in versions),
                             key=lambda x: (x["retrieved_at_utc"], x["row_digest"]))
        winners.append(representative)
        observations.extend(versions)
    winners.sort(key=lambda x: (x["start"], x["league"], x["event"]))
    windows.sort(key=lambda x: (x["run_id"], x["league"]))
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError("refusing to overwrite existing historical database")
    _db(dest, windows, winners, observations, conflicts)
    by_season = defaultdict(lambda: {"games": 0, "source_days": set(), "archive_windows": set()})
    for row in winners:
        key = (row["league"], row["season"])
        by_season[key]["games"] += 1
        by_season[key]["source_days"].add(row["event_day_et"])
    for w in windows:
        # A successful window confirms the provider responded for its days,
        # not that every historical game of the league or season was captured.
        if w["days_failed"] == 0:
            day = datetime.fromisoformat(w["start"]).date()
            end = datetime.fromisoformat(w["end"]).date()
            while day <= end:
                season = season_for(w["league"], datetime(
                    day.year, day.month, day.day, 12, tzinfo=EASTERN))
                by_season[(w["league"], season)]["source_days"].add(day.isoformat())
                by_season[(w["league"], season)]["archive_windows"].add(w["run_id"])
                day += timedelta(days=1)
    coverage = [{
        "league": league, "season": season, "published_games": data["games"],
        "source_days_successful_in_archived_windows": len(data["source_days"]),
        "source_archive_run_ids": sorted(data["archive_windows"]),
        "entire_season_completeness_verified": False,
        "official_results_adjudicated": False,
    } for (league, season), data in sorted(by_season.items())]
    report = {
        "stage": "challenger_multiseason_published_score_sqlite_research_only",
        "archive_windows_accepted": len(windows),
        "archives_rejected": len(rejected),
        "distinct_gitHub_run_ids": len({w["run_id"] for w in windows}),
        "published_games_deduplicated": len(winners),
        "consistent_repeated_observations": len(observations) - len(winners),
        "conflicting_event_ids_quarantined": len(conflicts),
        "quarantined_rejected_archives": rejected,
        "by_league_season": coverage,
        "source_retention": "Actions artifacts are temporary, not durable archival storage",
        "historical_player_boxscores": 0,
        "independently_qualified_training_records": 0,
        "verified_90_min_soccer_market_results": 0,
        "verified_bookmaker_settlement_results": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "sportsgameodds_api_requests": 0,
        "warning": (
            "SQLite stores research-only ESPN-published scores and source provenance. "
            "This is NOT verified pregame data, an entire historical season, "
            "independently adjudicated results, player box scores or a betting model."
        ),
    }
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive-root", required=True)
    p.add_argument("--output-dir", default="challenger_multiseason")
    args = p.parse_args(argv)
    out = Path(args.output_dir)
    report = assemble(args.archive_root, out / "historical_published_scores.sqlite")
    (out / "history_coverage.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
