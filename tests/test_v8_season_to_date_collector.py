"""Incremental eight-league season-score coverage without fabricated games."""
import json
import tempfile
import unittest
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from historical_outcomes import normalize_game, scoreboard_url
from v8_season_to_date_collector import collect_season, _segments
from v8_all_sports_season_form import season_anchor

NOW=datetime(2026,11,13,18,tzinfo=timezone.utc)
NY=ZoneInfo("America/New_York")


def one_game(d, league="nba"):
    start=datetime(d.year,d.month,d.day,19,tzinfo=NY).astimezone(timezone.utc)
    record={
        "id":str(400000+int(d.strftime("%m%d"))), "date":start.isoformat(),
        "season":{"type":2}, "status":{"type":{"state":"post","completed":True}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":"31","displayName":"Team A"},"score":110},
            {"homeAway":"away","team":{"id":"32","displayName":"Team B"},"score":100},
        ]}]}
    return normalize_game(record,league,scoreboard_url(league,d),NOW)


def fake_collector(calls, *, failures=False):
    def fetch(leagues,days,end):
        league=leagues[0]
        calls.append((league,days,end))
        start=end-timedelta(days=days-1)
        rows=[one_game(start+timedelta(days=i),league)
              for i in range(days)
              if (start+timedelta(days=i)).month==11 and
              (start+timedelta(days=i)).day<=10]
        return rows,{
            "leagues":[league],"total_completed_results":len(rows),
            "by_league":{league:{
                "days_attempted":days,"days_ok":days-int(failures),
                "days_failed":int(failures),}},
            "sportsgameodds_api_requests":0,
            "champion_001_modified":False,
        }
    return fetch


class IncrementalSeasonCollectorTests(unittest.TestCase):
    def test_max35_contiguous_batches(self):
        start=date(2026,7,1)
        segments=_segments([start+timedelta(days=i) for i in range(87)])
        self.assertEqual([x[2] for x in segments],[35,35,17])
        self.assertTrue(all(x[2]<=35 for x in segments))

    def test_initial_complete_season_and_reuse_without_requery(self):
        calls=[]
        with tempfile.TemporaryDirectory() as tmp:
            manifest,board=collect_season("nba",Path(tmp)/"first",
                clock=lambda: NOW,collector=fake_collector(calls))
            self.assertTrue(manifest["source_coverage_complete"])
            self.assertEqual(manifest["source_days_expected"],135)
            self.assertEqual(manifest["source_days_confirmed_total"],135)
            self.assertEqual(len(calls),4)
            self.assertTrue(all(x[1]<=35 for x in calls))
            self.assertEqual(manifest["retained_published_final_results"],10)
            self.assertTrue(board["teams"]["31"]["last5"]["complete_window"])
            self.assertTrue(board["teams"]["31"]["last10"]["complete_window"])
            self.assertEqual(board["teams"]["31"]["last5"]["avg_scored"],110)
            calls=[]
            same, other=collect_season("nba",Path(tmp)/"next",
                previous_dir=Path(tmp)/"first",
                clock=lambda:NOW,collector=fake_collector(calls))
            self.assertEqual(calls,[])
            self.assertEqual(same["source_days_confirmed_total"],135)
            self.assertEqual(same["retained_published_final_results"],10)
            self.assertEqual(other["teams"]["31"]["last5"],
                             board["teams"]["31"]["last5"])
            # Next calendar day should pull just one new source day.
            tomorrow=NOW+timedelta(days=1)
            calls=[]
            newer,_=collect_season("nba",Path(tmp)/"third",
                previous_dir=Path(tmp)/"next",
                clock=lambda:tomorrow,collector=fake_collector(calls))
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0][1],1)
            self.assertTrue(newer["source_coverage_complete"])

    def test_failed_chunk_remains_incomplete_and_does_not_fabricate_l10(self):
        calls=[]
        with tempfile.TemporaryDirectory() as tmp:
            manifest,board=collect_season("mls",Path(tmp)/"first",
                clock=lambda:NOW,collector=fake_collector(calls,failures=True))
            self.assertFalse(manifest["source_coverage_complete"])
            self.assertEqual(manifest["source_days_confirmed_total"],0)
            self.assertGreater(manifest["source_days_failed_in_latest_collection"],0)
            self.assertFalse(board["teams"]["31"]["last10"]["complete_window"])
            self.assertFalse(board["teams"]["31"]["last5"]["complete_window"])
            self.assertEqual(manifest["certified_positive_ev_bets"],0)

    def test_modified_team_or_score_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            collect_season("nba",Path(tmp)/"first",
                clock=lambda:NOW,collector=fake_collector([]))
            # Mark last available day absent to force a re-query and source conflict.
            c=Path(tmp)/"first"/"SEASON_COVERAGE.json"
            obj=json.loads(c.read_text())
            obj["source_days_confirmed_et"].remove("2026-11-10")
            c.write_text(json.dumps(obj))
            def changed(leagues, days,end):
                result,report=fake_collector([])(leagues,days,end)
                for g in result:
                    g["home_score"]=101
                    g["result"]="home"
                return result,report
            report,_=collect_season("nba",Path(tmp)/"second",
                previous_dir=Path(tmp)/"first",
                clock=lambda:NOW,collector=changed)
            self.assertTrue(report["conflicting_game_event_ids"])
            self.assertFalse(report["source_coverage_complete"])


if __name__=="__main__":
    unittest.main()
