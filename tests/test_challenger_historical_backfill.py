"""Synthetic offline checks; no betting accuracy or official validation claims."""
from datetime import date, datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from challenger_historical_backfill import plan, run, build_report, MAX_DAYS, WINDOW_END


NOW = datetime(2026, 10, 29, 21, 0, tzinfo=timezone.utc)


def example():
    return {
        "record_type": "historical_completed_game_research",
        "outcome_source": "espn_public_scoreboard",
        "source_url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20260214",
        "retrieved_at_utc": "2026-10-28T22:00:00+00:00",
        "league": "nba", "espn_event_id": "401001",
        "event_start_utc": "2026-02-14T23:00:00+00:00",
        "home_team": "Home", "away_team": "Away",
        "home_team_espn_id": "1", "away_team_espn_id": "2",
        "home_score": 95, "away_score": 90, "result": "home",
        "official_league_result_verified": False,
        "provider_event_id_crosswalk_verified": False,
        "champion_001_modified": False,
    }


def collector(leagues, days, end_date):
    league = leagues[0]
    rows = [example()] if league == "nba" else []
    coverage = {
        "leagues": [league], "total_completed_results": len(rows),
        "by_league": {league: {
            "days_attempted": days, "days_ok": days - 1,
            "days_failed": 1, "completed_games": len(rows)}},
    }
    return rows, coverage


class BoundedHistoryTests(unittest.TestCase):
    def test_six_leagues_with_capped_budget(self):
        self.assertEqual(len(WINDOW_END), 6)
        for league in WINDOW_END:
            p = plan(league, MAX_DAYS, now=NOW)
            self.assertEqual(p["maximum_public_scoreboard_requests"], 35)
            self.assertEqual(p["sportsbook_api_requests"], 0)

    def test_future_and_unbounded_requests_blocked(self):
        for days in (0, 36, -1, True):
            with self.assertRaises(ValueError):
                plan("nba", days, now=NOW)
        with self.assertRaises(ValueError):
            plan("nba", end_date=date(2026, 10, 30), now=NOW)
        with self.assertRaises(ValueError):
            plan("mls", now=NOW)

    def test_writes_research_only_and_flags_incomplete_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run("nba", 2, date(2026, 2, 15), tmp,
                         collector=collector, clock=NOW)
            self.assertEqual(report["published_completed_game_results"], 1)
            self.assertEqual(report["quarantined_research_candidates"], 0)
            self.assertEqual(report["scoreboard_days_failed"], 1)
            self.assertFalse(report["coverage_complete"])
            self.assertEqual(report["sportsbook_api_requests"], 0)
            self.assertEqual(report["qualified_training_examples"], 0)
            self.assertEqual(report["certified_champion_001_predictions"], 0)
            self.assertEqual(report["bet_ready_selections"], 0)
            self.assertFalse(report["champion_001_modified"])
            written = json.loads((Path(tmp) / "backfill_coverage.json").read_text())
            self.assertEqual(written["stage"], "challenger_historical_backfill_research_only")
            self.assertEqual(len((Path(tmp) / "published_results.jsonl").read_text().splitlines()), 1)

    def test_rejects_incorrect_collection_count(self):
        rows = [example()]
        coverage = collector(("nba",), 2, date(2026, 2, 15))[1]
        coverage["total_completed_results"] = 0
        with self.assertRaises(ValueError):
            build_report("nba", 2, date(2026, 2, 15), rows, coverage,
                         [], {"research_candidates": 0})

    def test_nonzero_candidate_training_promotion_rejected(self):
        coverage = collector(("nba",), 2, date(2026, 2, 15))[1]
        with self.assertRaises(ValueError):
            build_report("nba", 2, date(2026, 2, 15), [example()],
                         coverage, [{"qualified_for_challenger_backtest": True,
                                     "bet_ready": False}], {"research_candidates": 1})


if __name__ == "__main__":
    unittest.main()
