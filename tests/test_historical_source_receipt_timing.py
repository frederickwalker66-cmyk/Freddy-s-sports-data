"""Eight-sport historical HTTP receipt-time regression tests, fixtures only."""
from datetime import date, datetime, timedelta, timezone
import unittest

from historical_outcomes import LEAGUES, collect


def response():
    return {"events": [{
        "id": "100033",
        "date": "2026-10-28T23:15:00Z",
        "season": {"type": 2},
        "status": {"type": {"state": "post", "completed": True}},
        "competitions": [{"competitors": [
            {"homeAway": "home", "team": {"id": "1", "displayName": "Home"}, "score": "117"},
            {"homeAway": "away", "team": {"id": "2", "displayName": "Away"}, "score": "102"},
        ]}],
    }]}


class ResponseClockRegression(unittest.TestCase):
    def test_all_eight_sports_stamped_after_each_successful_response(self):
        initial = datetime(2026, 10, 29, 19, tzinfo=timezone.utc)
        timeline = iter(initial + timedelta(seconds=i * 3) for i in range(9))
        data, stats = collect(tuple(LEAGUES), 1, date(2026, 10, 28),
                              fetcher=lambda _: response(), clock=lambda: next(timeline),
                              pause_seconds=0)
        self.assertEqual(len(data), 8)
        self.assertEqual(set(row["league"] for row in data), set(LEAGUES))
        self.assertEqual(set(row["retrieved_at_utc"] for row in data),
                         {(initial + timedelta(seconds=i * 3)).isoformat()
                          for i in range(1, 9)})
        self.assertTrue(all(
            datetime.fromisoformat(row["retrieved_at_utc"]) > initial for row in data
        ))
        self.assertEqual(stats["total_completed_results"], 8)
        self.assertFalse(stats["champion_001_modified"])
        self.assertEqual(stats["bet_ready_selections"], 0)

    def test_rollback_receipt_clock_cannot_become_pregame_source(self):
        initial = datetime(2026, 10, 29, 19, tzinfo=timezone.utc)
        times = iter([initial, initial - timedelta(seconds=1)])
        rows, stats = collect(("nba",), 1, date(2026, 10, 28),
                              fetcher=lambda _: response(), clock=lambda: next(times),
                              pause_seconds=0)
        self.assertEqual(rows, [])
        self.assertEqual(stats["by_league"]["nba"]["days_failed"], 1)
        self.assertEqual(stats["by_league"]["nba"]["error_types"], {"ValueError": 1})


if __name__ == "__main__":
    unittest.main()
