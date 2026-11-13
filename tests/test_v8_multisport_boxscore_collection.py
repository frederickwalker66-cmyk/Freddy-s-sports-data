"""Bounded eight-league historical player boxes with persist/reuse, no odds."""
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from historical_outcomes import normalize_game,scoreboard_url
from v8_multisport_boxscore_collection import collect_player_boxes

NOW=datetime(2026,11,13,18,tzinfo=timezone.utc)
NY=ZoneInfo("America/New_York")
START=datetime(2026,11,7,19,tzinfo=NY).astimezone(timezone.utc)


def score():
    ev={"id":"3001","date":START.isoformat(),
        "season":{"type":2},"status":{"type":{"state":"post","completed":True}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":"101","displayName":"Home"},"score":122},
            {"homeAway":"away","team":{"id":"102","displayName":"Away"},"score":108}]}]}
    return normalize_game(ev,"nba",
                          scoreboard_url("nba",START.astimezone(NY).date()),NOW)


def summary():
    return {
        "header":{"id":"3001","competitions":[{
            "date":START.isoformat(),"status":{"type":{"completed":True}},
            "competitors":[{"team":{"id":"101"}},{"team":{"id":"102"}}]}]},
        "boxscore":{"players":[
            {"team":{"id":"101"},"statistics":[{
                "name":"players","names":["MIN","PTS","REB","AST","3PT"],
                "athletes":[{"athlete":{"id":"901"},"didNotPlay":False,
                             "stats":["31","29","9","7","3-8"]}]}]},
            {"team":{"id":"102"},"statistics":[{
                "name":"players","names":["MIN","PTS","REB","AST","3PT"],
                "athletes":[{"athlete":{"id":"902"},"didNotPlay":False,
                             "stats":["28","22","6","2","2-5"]}]}]},
        ]}
    }


def season_files(root):
    p=Path(root)
    p.mkdir(parents=True,exist_ok=True)
    (p/"SEASON_RESULTS.jsonl").write_text(json.dumps(score())+"\n")
    (p/"SEASON_COVERAGE.json").write_text(json.dumps({
        "league":"nba","champion_001_modified":False,
        "conservative_collection_anchor_et":"2026-07-01",
        "source_coverage_complete":True,
    }))
    return p


class MultiSportSeasonBoxTests(unittest.TestCase):
    def test_nba_fetch_once_then_cache_without_refetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=season_files(Path(tmp)/"source")
            calls=[]
            def fetch(league,eid):
                calls.append((league,eid))
                return summary()
            manifest,board=collect_player_boxes(
                "nba",root,Path(tmp)/"first",clock=lambda:NOW,fetcher=fetch)
            self.assertEqual(calls,[("nba","3001")])
            self.assertEqual(manifest["total_player_box_rows_captured"],2)
            self.assertTrue(board["player_boxscore_event_coverage_complete"])
            self.assertEqual(board["players"]["901"]["historical_appearances_in_cached_season"],1)
            self.assertEqual(board["players_with_complete_last5"],0)
            calls=[]
            newer,board2=collect_player_boxes(
                "nba",root,Path(tmp)/"second",previous_dir=Path(tmp)/"first",
                clock=lambda:NOW,fetcher=fetch)
            self.assertEqual(calls,[])
            self.assertEqual(newer["total_player_box_rows_captured"],2)
            self.assertEqual(board2["players"]["901"]["last5"],
                             board["players"]["901"]["last5"])

    def test_unverified_or_mismatched_source_never_joins_players(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=season_files(Path(tmp)/"source")
            def wrong(league,eid):
                x=summary()
                x["boxscore"]["players"][0]["team"]["id"]="999"
                return x
            m,board=collect_player_boxes(
                "nba",root,Path(tmp)/"bad",clock=lambda:NOW,fetcher=wrong)
            self.assertEqual(m["boxscore_events_with_usable_stats_now"],0)
            self.assertFalse(m["player_boxscore_event_coverage_complete"])
            self.assertEqual(board["players_with_complete_last10"],0)
            self.assertEqual(m["certified_positive_ev_bets"],0)

    def test_bound_under_250_per_league(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=season_files(Path(tmp)/"source")
            with self.assertRaisesRegex(ValueError,"max_player_summary_requests_exceeded"):
                collect_player_boxes("nba",root,Path(tmp)/"bad",
                                     clock=lambda:NOW,max_new_summaries=251)


if __name__=="__main__":
    unittest.main()
