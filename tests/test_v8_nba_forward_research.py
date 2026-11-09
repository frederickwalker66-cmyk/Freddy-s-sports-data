"""Fixtures: genuine wall-clock forward prediction recording, never Champion certification."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from historical_outcomes import normalize_game, scoreboard_url
from v8_nba_forward_research import (
    BASE, VERSION, capture, parse_schedule_original, project,
)

NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 9, 20, 0, tzinfo=timezone.utc)


def completed(i, captured=None):
    captured = captured or NOW - timedelta(minutes=2)
    start = datetime(2026, 10, 15, 19, 0, tzinfo=timezone.utc) + timedelta(days=i // 6, minutes=i % 6)
    day = start.astimezone(NY).date()
    item = {
        "id": str(40000000+i), "date": start.isoformat(),
        "season": {"type": 2},
        "status": {"type": {"state": "post", "completed": True}},
        "competitions": [{"competitors": [
            {"homeAway":"home","team":{"id":"101","displayName":"Home Team"},"score": 112 if i % 3 else 90},
            {"homeAway":"away","team":{"id":"102","displayName":"Away Team"},"score": 103},
        ]}],
    }
    return normalize_game(item, "nba", scoreboard_url("nba", day), captured)


def prior(n=100):
    return [completed(i) for i in range(n)]


def source_coverage(n=100, days=35, failed=0):
    return {
        "leagues":["nba"], "total_completed_results":n,
        "champion_001_modified":False,
        "by_league":{"nba":{
            "days_attempted":days,
            "days_ok":days-failed,"days_failed":failed,
            "completed_games":n,
        }},
    }


def prospective(event_id="40111111", start=None):
    start = start or NOW + timedelta(hours=4)
    return {
        "id":event_id,"date":start.isoformat(),"season":{"type":2},
        "status":{"type":{"state":"pre","completed":False}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":"101","displayName":"Home Team"}},
            {"homeAway":"away","team":{"id":"102","displayName":"Away Team"}},
        ]}],
    }


def original_for_day(day, *, one=True):
    start = datetime(day.year,day.month,day.day,23,0,tzinfo=NY).astimezone(timezone.utc)
    # 23:00 NY always on requested Eastern day.
    data={"events":[prospective(event_id="4011"+day.strftime("%m%d"),start=start)] if one else []}
    raw=json.dumps(data, separators=(",",":")).encode()
    return data,raw


def future_event(event_id="40111111", start=None):
    start=start or (NOW+timedelta(hours=4))
    return {
        "league":"nba","espn_event_id":event_id,"start_utc":start.isoformat(),
        "home_team_espn_id":"101", "away_team_espn_id":"102",
        "home_team":"Home Team", "away_team":"Away Team",
        "schedule_original_received_at_utc":NOW.isoformat(),
        "schedule_original_sha256_local_receipt":"a"*64,
        "schedule_source_url":scoreboard_url("nba",start.astimezone(NY).date()),
    }


class ForwardResearchTests(unittest.TestCase):
    def test_nba_100_real_shaped_old_scores_yield_actual_early_forecast(self):
        records, r=project(prior(),[future_event()],source_coverage(),NOW)
        self.assertEqual(len(records),1)
        x=records[0]
        self.assertEqual(x["forecast_recorded_utc"],NOW.isoformat())
        self.assertLess(x["forecast_recorded_utc"],x["start_utc"])
        self.assertEqual(x["model_version"],VERSION)
        self.assertTrue(0 < x["model_probability_home_win_research_only"] < 1)
        self.assertIsNone(x["outcome"])
        self.assertFalse(x["forecast_reconstructed_after_game"])
        self.assertFalse(x["qualifies_for_original_champion_shadow_quota"])
        self.assertFalse(x["certified_prediction"])
        self.assertFalse(x["verified_positive_ev"])
        self.assertEqual(x["stake_usd"],0)
        self.assertEqual(r["v8_research_forward_predictions"],1)
        self.assertEqual(r["original_champion_001_predictions_certified"],0)
        self.assertFalse(r["champion_001_modified"])

    def test_started_games_never_become_pregame_predictions(self):
        gone=future_event(start=NOW-timedelta(minutes=3))
        records,r=project(prior(),[gone],source_coverage(),NOW)
        self.assertEqual(records,[])
        self.assertEqual(r["hold_reasons"]["event_started_before_completed_forecast"],1)

    def test_no_history_and_failed_source_days_both_block(self):
        zero,r=project([], [future_event()],source_coverage(n=0),NOW)
        self.assertEqual(zero,[])
        self.assertIn("insufficient_prior_matured_NBA_games",r["hold_reasons"])
        gap,r=project(prior(),[future_event()],source_coverage(failed=1),NOW)
        self.assertEqual(gap,[])
        self.assertIn("incomplete_historical_published_result_source_days",r["hold_reasons"])

    def test_future_leaking_historical_receipt_rejected(self):
        rows=prior()
        rows[0]["retrieved_at_utc"]=(NOW+timedelta(minutes=5)).isoformat()
        with self.assertRaisesRegex(ValueError,"historical_source_not_captured_prior_to_forecast"):
            project(rows,[future_event()],source_coverage(),NOW)

    def test_bad_scoreboard_url_and_duplicate_event_identity_rejected(self):
        rows=prior()
        rows[0]["source_url"]=scoreboard_url("nba",datetime(2026,10,2,tzinfo=timezone.utc).date())
        with self.assertRaisesRegex(ValueError,"historical_NBA_scoreboard_day_or_url_mismatch"):
            project(rows,[future_event()],source_coverage(),NOW)
        with self.assertRaisesRegex(ValueError,"duplicate_future_NBA_identity"):
            project(prior(),[future_event(),future_event()],source_coverage(),NOW)

    def test_real_bytes_source_needed_for_original_schedule(self):
        day=NOW.astimezone(NY).date()
        payload, raw=original_for_day(day)
        items=parse_schedule_original(payload,raw,day,NOW,scoreboard_url("nba",day))
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]["home_team_espn_id"],"101")
        self.assertEqual(len(items[0]["schedule_original_sha256_local_receipt"]),64)
        with self.assertRaisesRegex(ValueError,"schedule_original_bytes_not_consistent"):
            parse_schedule_original(payload,b'{"events":[]}',day,NOW,scoreboard_url("nba",day))

    def test_capture_writes_original_pregame_model_artifact_without_bets(self):
        def fetch(url):
            day_text=parse_qs(urlparse(url).query)["dates"][0]
            d=datetime.strptime(day_text,"%Y%m%d").date()
            return original_for_day(d,one=True)
        def historical(leagues,days,end_date):
            self.assertEqual(leagues,("nba",))
            self.assertEqual(days,35)
            return prior(),source_coverage()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/"original_capture"
            records, report=capture(root,history_days=35,fetch_schedule=fetch,
                                    history_collector=historical,clock=lambda:NOW)
            self.assertEqual(len(records),2)
            self.assertEqual(report["source_days_failed"],0)
            self.assertEqual(report["certified_positive_ev_bets"],0)
            self.assertTrue((root/"NBA_FORWARD_FORECASTS.jsonl").is_file())
            self.assertTrue((root/"nba_original_future_schedule_20261109.json").is_file())
            self.assertEqual(len((root/"NBA_FORWARD_FORECASTS.jsonl").read_text().splitlines()),2)
            with self.assertRaisesRegex(ValueError,"fresh_empty"):
                capture(root,history_days=35,fetch_schedule=fetch,
                        history_collector=historical,clock=lambda:NOW)


if __name__=="__main__":
    unittest.main()
