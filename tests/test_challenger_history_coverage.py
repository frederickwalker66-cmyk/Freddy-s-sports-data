"""Synthetic source-coverage tests; not real-world model results."""
import unittest
from datetime import date, datetime, timezone, timedelta
from challenger_prospective_pregame import LEAGUES, planned_history

NOW = datetime(2026, 10, 29, 19, 0, tzinfo=timezone.utc)
END = date(2026, 10, 28)


def event(league, hours=6, status="scheduled"):
    return {"league": league, "status": status,
            "start_utc": (NOW + timedelta(hours=hours)).isoformat()}


def schedule(*items):
    return {"events": list(items)}


def fake_collector(log):
    def collect(leagues, days, end_date):
        log.append((tuple(leagues), days, end_date))
        return ([{"league": league, "espn_event_id": str(i+1),
                  "event_start_utc": "2026-10-10T00:00:00Z"}
                 for i, league in enumerate(leagues)],
                {"by_league": {league:
                  {"days_attempted": days, "days_ok": days,
                   "days_failed": 0, "completed_games": 1,
                   "draws": 0, "error_types": {}}
                 for league in leagues}})
    return collect


class PlannedHistoryTests(unittest.TestCase):
    def test_only_upcoming_leagues_and_35_day_football_window(self):
        called = []
        rows, report = planned_history(
            schedule(event("nba"), event("nfl"), event("ncaaf"),
                     event("nhl", hours=-1)),
            NOW, END, collector=fake_collector(called))
        self.assertEqual(called, [
            (("nba",), 14, END),
            (("nfl", "ncaaf"), 35, END),
        ])
        self.assertEqual(len(rows), 3)
        self.assertEqual(report["days_by_league"]["nba"], 14)
        self.assertEqual(report["days_by_league"]["nfl"], 35)
        self.assertEqual(report["days_by_league"]["ncaaf"], 35)
        self.assertEqual(report["days_by_league"]["nhl"], 0)
        self.assertEqual(report["daily_requests_maximum"], 84)
        self.assertEqual(report["bet_ready_selections"], 0)
        self.assertFalse(report["champion_001_modified"])

    def test_empty_schedule_makes_zero_requests(self):
        called = []
        rows, report = planned_history(
            schedule(), NOW, END, collector=fake_collector(called))
        self.assertEqual(called, [])
        self.assertEqual(rows, [])
        self.assertEqual(report["total_completed_results"], 0)
        self.assertTrue(all(x["days_attempted"] == 0
                            for x in report["by_league"].values()))

    def test_past_or_cancelled_events_do_not_trigger_requests(self):
        called = []
        planned_history(schedule(event("nfl", hours=-1),
                                 event("nba", status="canceled"),
                                 event("nhl", status="post"),
                                 event("wnba")),
                        NOW, END, collector=fake_collector(called))
        self.assertEqual(called, [])

    def test_partial_source_failure_preserved_in_report(self):
        def partially_failed(leagues, days, end_date):
            return [], {"by_league": {league: {
                "days_attempted": days, "days_ok": days-2,
                "days_failed": 2, "completed_games": 0, "draws": 0,
                "error_types": {"TimeoutError": 2}
            } for league in leagues}}
        rows, report = planned_history(
            schedule(event("nfl")), NOW, END, collector=partially_failed)
        self.assertEqual(rows, [])
        self.assertEqual(report["by_league"]["nfl"]["days_failed"], 2)
        self.assertEqual(report["by_league"]["nfl"]["error_types"]["TimeoutError"], 2)

    def test_misreported_source_counters_fail_closed(self):
        def bad(leagues, days, end_date):
            return [], {"by_league": {league: {
                "days_attempted": days, "days_ok": days-1,
                "days_failed": 0} for league in leagues}}
        with self.assertRaises(ValueError):
            planned_history(schedule(event("nfl")), NOW, END, collector=bad)

    def test_repeated_game_ids_fail_closed(self):
        def dup(leagues, days, end_date):
            return ([{"league": "nba", "espn_event_id": "123",
                      "event_start_utc": "2026-10-01T00:00:00Z"}] * 2,
                    {"by_league": {"nba": {
                     "days_attempted": days, "days_ok": days,
                     "days_failed": 0}}})
        with self.assertRaises(ValueError):
            planned_history(schedule(event("nba")), NOW, END, collector=dup)

    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            planned_history(schedule(), NOW, END, regular_days=36)
        with self.assertRaises(ValueError):
            planned_history(schedule(), NOW, END,
                            regular_days=25, football_days=14)

    def test_league_inventory_stays_eight_for_reporting(self):
        called = []
        _, report = planned_history(schedule(event("nfl")), NOW, END,
                                    collector=fake_collector(called))
        self.assertEqual(set(report["by_league"]), set(LEAGUES))
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertEqual(report["certified_challenger_001_predictions"], 0)


if __name__ == "__main__":
    unittest.main()
