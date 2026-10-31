"""Offline eight-competition historical results archive tests.

Pure synthetic fixtures; these are not real historical games or bookmaker data.
"""
from datetime import date, datetime, timezone
import json
from pathlib import Path
import unittest

from historical_outcomes import LEAGUES, collect, normalize_game, scoreboard_url

NOW = datetime(2026, 10, 31, 18, 0, tzinfo=timezone.utc)
DAY = date(2026, 2, 14)


def example(league, event_id, home_score=2, away_score=1):
    return {
        "id": event_id, "date": "2026-02-14T20:00:00Z",
        "season": {"type": 2},
        "status": {"type": {"state": "post", "completed": True}},
        "competitions": [{"competitors": [
            {"homeAway": "home", "team": {"id": "H_"+league,
                "displayName": "Fixture Home"}, "score": str(home_score)},
            {"homeAway": "away", "team": {"id": "A_"+league,
                "displayName": "Fixture Away"}, "score": str(away_score)},
        ]}],
    }


class AllSportResultsTests(unittest.TestCase):
    def test_exact_eight_league_source_mapping(self):
        self.assertEqual(set(LEAGUES), {"nba","nfl","mlb","nhl","ncaaf",
                                       "ncaab","mls","uefa_champions_league"})
        self.assertIn("/soccer/usa.1/",scoreboard_url("mls",DAY))
        self.assertIn("/soccer/uefa.champions/",scoreboard_url("uefa_champions_league",DAY))

    def test_soccer_draw_is_published_score_only(self):
        for league in ("mls","uefa_champions_league"):
            row = normalize_game(example(league,"40112345",2,2),league,
                scoreboard_url(league,DAY),NOW)
            self.assertEqual(row["result"],"draw")
            self.assertTrue(row["published_score_research_only"])
            self.assertFalse(row["regulation_90_min_result_verified"])
            self.assertFalse(row["bookmaker_market_settlement_verified"])
            self.assertFalse(row["official_league_result_verified"])
            self.assertFalse(row["champion_001_modified"])

    def test_unfinished_game_cannot_enter_history(self):
        game=example("mls","123")
        game["status"]["type"]["completed"]=False
        self.assertIsNone(normalize_game(game,"mls",scoreboard_url("mls",DAY),NOW))

    def test_all_eight_leagues_collect_published_score_once(self):
        urls=[]
        reverse={v:k for k,v in LEAGUES.items()}
        def fake(url):
            urls.append(url)
            league = next(k for v,k in reverse.items()
                if "/"+v[0]+"/"+v[1]+"/" in url)
            s=(2,2) if league in ("mls","uefa_champions_league") else (3,1)
            return {"events":[example(league,str(401000000+list(LEAGUES).index(league)),*s)]}
        data, report = collect(tuple(LEAGUES),1,DAY,fetcher=fake,
                                clock=lambda: NOW,pause_seconds=0)
        self.assertEqual(len(urls),8)
        self.assertEqual(len(data),8)
        self.assertEqual(report["total_completed_results"],8)
        self.assertEqual(report["sportsgameodds_api_requests"],0)
        self.assertEqual(report["certified_champion_001_predictions"],0)
        self.assertEqual(report["certified_challenger_001_predictions"],0)
        self.assertEqual(report["automated_bets_placed"],0)
        self.assertEqual(sum(x["draws"] for x in report["by_league"].values()),2)
        self.assertTrue(all(x["official_league_result_verified"] is False for x in data))
        self.assertTrue(all(x["regulation_90_min_result_verified"] is False for x in data))

    def test_failed_league_day_is_reported_not_filled(self):
        def fake(url):
            if "/soccer/usa.1/" in url:
                raise TimeoutError("synthetic timeout")
            return {"events":[]}
        rows,report=collect(("mls","nfl"),1,DAY,fetcher=fake,
                            clock=lambda:NOW,pause_seconds=0)
        self.assertEqual(rows,[])
        self.assertEqual(report["by_league"]["mls"]["days_failed"],1)
        self.assertEqual(report["by_league"]["nfl"]["days_ok"],1)
        self.assertEqual(report["by_league"]["mls"]["error_types"]["TimeoutError"],1)

    def test_workflow_contains_all_eight_leagues_without_sportsbook_calls(self):
        s=Path(".github/workflows/challenger-historical-backfill.yml").read_text()
        self.assertIn("uefa_champions_league]",s)
        self.assertIn("max-parallel: 2",s)
        self.assertIn("cancel-in-progress: false",s)
        self.assertIn("HISTORY_END_DATE",s)
        self.assertNotIn("sportsgameodds_collector.py",s)
        self.assertNotIn("collector.py --",s)


if __name__=="__main__":
    unittest.main()
