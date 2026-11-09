"""Separate NFL/NHL live source and prospective probability fixture tests.

Synthetic game scores ONLY exercise software; never represent actual picks.
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from historical_outcomes import normalize_game, scoreboard_url
from v8_nfl_nhl_forward import (
    SPEC, historical_ratings, parse_original_future_schedule, project, capture,
)

NY=ZoneInfo("America/New_York")
NOW=datetime(2026,11,9,20,tzinfo=timezone.utc)


def old_results(league, count=75, *, tie=False):
    records=[]
    for i in range(count):
        # Within 35 ET source days, completed > 48h before forecast.
        start=datetime(2026,10,10,19,tzinfo=timezone.utc)+timedelta(days=i//4,minutes=i%4)
        day=start.astimezone(NY).date()
        home_score,away_score=(100,100) if tie and i==0 else (107,97)
        if league=="nhl":
            home_score,away_score=(3,3) if tie and i==0 else (3,2)
        game={
            "id":str(50000000+i),"date":start.isoformat(),
            "season":{"type":2},
            "status":{"type":{"state":"post","completed":True}},
            "competitions":[{"competitors":[
                {"homeAway":"home","team":{"id":"101","displayName":"Home Club"},"score":str(home_score)},
                {"homeAway":"away","team":{"id":"102","displayName":"Away Club"},"score":str(away_score)},
            ]}],
        }
        records.append(normalize_game(game,league,scoreboard_url(league,day),
                                      NOW-timedelta(minutes=1)))
    return records


def source_coverage(league,n,days=35,fail=0):
    return {
        "leagues":[league],"champion_001_modified":False,"total_completed_results":n,
        "by_league":{league:{"days_attempted":days,"days_ok":days-fail,
                            "days_failed":fail,"completed_games":n}},
    }


def scheduled(league, eid=None, start=None, observed=NOW):
    eid=eid or ("50000111" if league=="nfl" else "50000112")
    start=start or NOW+timedelta(hours=3)
    day=start.astimezone(NY).date()
    return {"league":league,"espn_event_id":eid,"start_utc":start.isoformat(),
            "home_team_espn_id":"101","away_team_espn_id":"102",
            "home_team":"Home Club","away_team":"Away Club",
            "schedule_original_received_at_utc":observed.isoformat(),
            "schedule_original_sha256_local_receipt":"a"*64,
            "schedule_source_url":scoreboard_url(league,day)}


def source_bytes(league,day):
    start=datetime(day.year,day.month,day.day,20,tzinfo=NY).astimezone(timezone.utc)
    ev={"id":str(60000000+day.day),"date":start.isoformat(),
        "season":{"type":2},"status":{"type":{"state":"pre","completed":False}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":"101","displayName":"Home Club"}},
            {"homeAway":"away","team":{"id":"102","displayName":"Away Club"}},
        ]}]}
    obj={"events":[ev]}
    return obj,json.dumps(obj,separators=(",",":")).encode()


class NflNhlForwardTests(unittest.TestCase):
    def test_nfl_tie_exclusion_and_research_not_moneyline(self):
        rows=old_results("nfl",75,tie=True)
        future=[scheduled("nfl")]
        scores,report=project("nfl",rows,source_coverage("nfl",75),future,NOW)
        self.assertEqual(report["matured_ties_excluded"],1)
        self.assertEqual(report["matured_binary_games"],74)
        self.assertEqual(len(scores),1)
        self.assertIn("given_no_tie",scores[0]["model_target"])
        self.assertIn("NOT_a_market_moneyline",scores[0]["model_target"])
        self.assertEqual(scores[0]["model_version"],SPEC["nfl"]["version"])
        self.assertFalse(scores[0]["qualified_for_certified_champion_001_shadow"])
        self.assertIsNone(scores[0]["future_outcome"])
        self.assertFalse(scores[0]["certified_prediction"])
        self.assertEqual(scores[0]["stake_usd"],0)
        self.assertEqual(report["certified_positive_ev_bets"],0)

    def test_nhl_forecast_and_no_cross_league_weights(self):
        scores,report=project("nhl",old_results("nhl",75),
                              source_coverage("nhl",75),[scheduled("nhl")],NOW)
        self.assertEqual(len(scores),1)
        self.assertEqual(scores[0]["model_version"],SPEC["nhl"]["version"])
        self.assertIn("OT_SO_not_market_verified",scores[0]["model_target"])
        self.assertNotEqual(SPEC["nhl"]["k"],SPEC["nfl"]["k"])
        self.assertFalse(report["bet_ready"])

    def test_incomplete_nfl_history_and_failed_source_block(self):
        result,report=project("nfl",old_results("nfl",4),
                              source_coverage("nfl",4),[scheduled("nfl")],NOW)
        self.assertEqual(result,[])
        self.assertIn("minimum_matured_binary_history_unmet",report["hold_reasons"])
        result,report=project("nfl",old_results("nfl",75),
                              source_coverage("nfl",75,fail=1),[scheduled("nfl")],NOW)
        self.assertEqual(result,[])
        self.assertEqual(report["hold_reasons"]["historical_ESPN_source_days_failed"],1)

    def test_tampered_or_future_history_is_not_acceptable(self):
        rows=old_results("nhl",75)
        rows[0]["retrieved_at_utc"]=(NOW+timedelta(minutes=10)).isoformat()
        with self.assertRaisesRegex(ValueError,"published_final_not_retrieved_prior_to_forecast"):
            historical_ratings("nhl",rows,NOW)
        rows=old_results("nfl",75)
        rows[0]["source_url"]=scoreboard_url("nhl",NOW.date())
        with self.assertRaisesRegex(ValueError,"historical_event_or_scoreboard_day_mismatch"):
            historical_ratings("nfl",rows,NOW)

    def test_bare_schedule_bytes_no_predicted_games_or_source_forgery(self):
        day=NOW.astimezone(NY).date()
        p,raw=source_bytes("nfl",day)
        records=parse_original_future_schedule("nfl",p,raw,day,NOW)
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]["home_team_espn_id"],"101")
        self.assertEqual(len(records[0]["schedule_original_sha256_local_receipt"]),64)
        with self.assertRaisesRegex(ValueError,"source_original_ESPN_bytes_not_verified_locally"):
            parse_original_future_schedule("nfl",p,b'{"events":[]}',day,NOW)
        p["events"][0]["season"]["type"]=3
        raw=json.dumps(p).encode()
        self.assertEqual(parse_original_future_schedule("nfl",p,raw,day,NOW),[])

    def test_started_event_never_becomes_forward_forecast(self):
        result,report=project("nfl",old_results("nfl",75),
                              source_coverage("nfl",75),
                              [scheduled("nfl",start=NOW-timedelta(minutes=1))],NOW)
        self.assertEqual(result,[])
        self.assertEqual(report["hold_reasons"]["event_started_or_source_was_observed_after_forecast"],1)

    def test_end_to_end_collect_pregame_original_bytes_per_league(self):
        def fake_fetch(url):
            day=datetime.strptime(parse_qs(urlparse(url).query)["dates"][0],"%Y%m%d").date()
            league="nfl" if "/football/nfl/" in url else "nhl"
            return source_bytes(league,day)
        def fake_collector(leagues,days,last):
            self.assertEqual(len(leagues),1)
            self.assertEqual(days,35)
            league=leagues[0]
            rows=old_results(league,75)
            return rows,source_coverage(league,len(rows))
        with tempfile.TemporaryDirectory() as folder:
            for league in ("nfl","nhl"):
                out=Path(folder)/league
                preds,report=capture(
                    league,out,history_days=35,fetch_schedule=fake_fetch,
                    history_collector=fake_collector,clock=lambda:NOW)
                self.assertGreater(len(preds),0)
                self.assertEqual(report["source_days_failed"],0)
                self.assertEqual(report["certified_positive_ev_bets"],0)
                self.assertTrue((out/f"{league.upper()}_FORWARD_RESEARCH_FORECASTS.jsonl").exists())
                self.assertTrue((out/f"{league.upper()}_FORWARD_RESEARCH_STATUS.json").exists())
                self.assertTrue((out/f"{league}_original_future_schedule_20261109.json").exists())
                self.assertEqual(len(report["source_original_schedules_saved"]),
                                 SPEC[league]["lookahead_days"])
                self.assertTrue(all(row["forecast_recorded_utc"] < row["start_utc"] for row in preds))
                with self.assertRaisesRegex(ValueError,"must_be_empty"):
                    capture(league,out,history_days=35,fetch_schedule=fake_fetch,
                            history_collector=fake_collector,clock=lambda:NOW)


if __name__=="__main__":
    unittest.main()
