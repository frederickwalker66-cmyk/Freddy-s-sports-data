"""Offline fixtures for multi-window, multi-season SQLite historical evidence.

Synthetic published-game records only. No bookmaker calls or model training.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from challenger_multiseason_history import assemble, season_for, main
from historical_outcomes import scoreboard_url, normalize_game


def published(league, event_id="40123455", dt="2026-02-14T22:00:00Z",
              home_score=104, away_score=99):
    start = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    local = start.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date()
    obj = {
        "id": event_id, "date": dt,
        "season": {"type": 2},
        "status": {"type": {"state": "post", "completed": True}},
        "competitions": [{"competitors": [
            {"homeAway": "home", "team": {"id": "101", "displayName": "Sample Home"}, "score": home_score},
            {"homeAway": "away", "team": {"id": "102", "displayName": "Sample Away"}, "score": away_score},
        ]}],
    }
    return normalize_game(obj, league, scoreboard_url(league, local),
                          datetime(2026, 10, 31, 12, tzinfo=timezone.utc))


def archive(root, run_id, league, records, end="2026-02-15", days=3,
            days_failed=0, alter=None):
    folder = root / str(run_id) / f"challenger-backfill-{league}-{run_id}"
    folder.mkdir(parents=True)
    start = datetime.fromisoformat(end).date() - __import__("datetime").timedelta(days=days - 1)
    report = {
        "league": league, "published_completed_game_results": len(records),
        "qualified_training_examples": 0,
        "officially_adjudicated_results": 0, "sportsbook_api_requests": 0,
        "sportsgameodds_requests": 0, "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "automated_bets_placed": 0, "champion_001_modified": False,
        "days_requested": days, "scoreboard_days_successful": days-days_failed,
        "scoreboard_days_failed": days_failed,
        "coverage_complete": days_failed == 0,
        "public_scoreboard_requests_maximum": days,
        "window_start_et": start.isoformat(), "window_end_et": end,
        "quarantined_research_candidates": 0,
        "soccer_90_minute_result_verified": False,
    }
    if alter:
        report.update(alter)
    coverage = {"leagues": [league], "total_completed_results": len(records),
                "by_league": {league: {"days_failed": days_failed}}}
    (folder / "published_results.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf8")
    (folder / "backfill_coverage.json").write_text(json.dumps(report), encoding="utf8")
    (folder / "scoreboard_collection.json").write_text(json.dumps(coverage), encoding="utf8")
    return folder


class MultiSeasonLedgerTests(unittest.TestCase):
    def test_season_identity_calendar_and_cross_year(self):
        before = datetime(2026, 2, 14, tzinfo=timezone.utc)
        after = datetime(2025, 11, 10, tzinfo=timezone.utc)
        self.assertEqual(season_for("nba", before), "2025-26")
        self.assertEqual(season_for("nhl", before), "2025-26")
        self.assertEqual(season_for("ncaaf", after), "2025-26")
        self.assertEqual(season_for("uefa_champions_league", before), "2025-26")
        self.assertEqual(season_for("mlb", before), "2026")
        self.assertEqual(season_for("mls", before), "2026")

    def test_deduplicate_identical_game_and_track_two_archive_runs(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            one=published("nba")
            two=dict(one, retrieved_at_utc="2026-10-31T14:00:00+00:00")
            archive(root, 11, "nba", [one])
            archive(root, 12, "nba", [two])
            report=assemble(root, root/"out.sqlite")
            self.assertEqual(report["published_games_deduplicated"],1)
            self.assertEqual(report["consistent_repeated_observations"],1)
            self.assertEqual(report["distinct_gitHub_run_ids"],2)
            self.assertEqual(report["conflicting_event_ids_quarantined"],0)
            with sqlite3.connect(root/"out.sqlite") as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM published_games").fetchone()[0],1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM source_observations").fetchone()[0],2)
                self.assertEqual(db.execute("SELECT historically_qualified_training FROM published_games").fetchone()[0],0)
                self.assertEqual(db.execute("SELECT season FROM published_games").fetchone()[0],"2025-26")

    def test_conflicting_score_quarantines_both_versions(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            archive(root, 11, "nba", [published("nba")])
            archive(root, 12, "nba", [published("nba",home_score=103)])
            r=assemble(root,root/"out.sqlite")
            self.assertEqual(r["conflicting_event_ids_quarantined"],1)
            self.assertEqual(r["published_games_deduplicated"],0)
            with sqlite3.connect(root/"out.sqlite") as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM published_games").fetchone()[0],0)
                self.assertEqual(db.execute("SELECT disposition FROM conflicting_events").fetchone()[0],
                                 "quarantined_all_versions")

    def test_two_sports_same_event_id_remain_separate(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            archive(root, 11, "nba", [published("nba")])
            archive(root, 11, "nhl", [published("nhl")])
            r=assemble(root, root/"out.sqlite")
            self.assertEqual(r["published_games_deduplicated"],2)
            self.assertEqual({x["league"] for x in r["by_league_season"]},{"nba","nhl"})

    def test_soccer_draw_never_promoted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            archive(root, 11, "uefa_champions_league",
                    [published("uefa_champions_league", home_score=2,away_score=2)])
            r=assemble(root, root/"out.sqlite")
            self.assertEqual(r["published_games_deduplicated"],1)
            self.assertEqual(r["verified_90_min_soccer_market_results"],0)
            self.assertEqual(r["independently_qualified_training_records"],0)
            with sqlite3.connect(root/"out.sqlite") as db:
                self.assertEqual(db.execute("SELECT published_result FROM published_games").fetchone()[0],"draw")

    def test_missing_or_unsafe_archive_cannot_create_trusted_game(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            archive(root, 11, "nba", [published("nba")], alter={"qualified_training_examples":1})
            with self.assertRaises(ValueError):
                assemble(root, root/"out.sqlite")
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            archive(root, 11, "nba", [published("nba")])
            archive(root, 12, "nhl", [published("nhl")],
                    alter={"officially_adjudicated_results":5})
            r=assemble(root,root/"out.sqlite")
            self.assertEqual(r["published_games_deduplicated"],1)
            self.assertEqual(r["archives_rejected"],1)
            self.assertEqual(r["quarantined_rejected_archives"][0]["relative_path"].split("/")[0],"12")

    def test_research_status_must_be_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            row=published("nba")
            row["bookmaker_market_settlement_verified"]=True
            archive(root, 11, "nba", [row])
            with self.assertRaises(ValueError):
                assemble(root,root/"out.sqlite")

    def test_source_day_mismatch_quarantined(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            row=published("nba")
            row["source_url"]=row["source_url"].replace("20260214","20260215")
            archive(root, 11, "nba", [row])
            with self.assertRaises(ValueError):
                assemble(root,root/"out.sqlite")

    def test_cli_outputs_database_and_report_without_training_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            archive(root, 11, "mlb", [published("mlb")])
            self.assertEqual(main(["--archive-root",str(root),
                                   "--output-dir",str(root/"results")]),0)
            out=root/"results"
            r=json.loads((out/"history_coverage.json").read_text())
            self.assertEqual(r["published_games_deduplicated"],1)
            self.assertTrue((out/"historical_published_scores.sqlite").is_file())
            self.assertEqual(r["certified_challenger_001_predictions"],0)
            self.assertEqual(r["historical_player_boxscores"],0)
            self.assertFalse((out/"historical_results.jsonl").exists())
            self.assertFalse((out/"research_model.json").exists())
            with self.assertRaises(FileExistsError):
                main(["--archive-root",str(root),"--output-dir",str(out)])


if __name__ == "__main__":
    unittest.main()
