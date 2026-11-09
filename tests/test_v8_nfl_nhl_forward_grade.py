"""NFL/NHL forward grade fixtures: first provenance, 48h, NFL tie exclusion."""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from historical_outcomes import normalize_game,scoreboard_url
from v8_nfl_nhl_forward import SPEC
from v8_nfl_nhl_forward_grade import GRADED,NFL_TIE,grade,load_archives

NY=ZoneInfo("America/New_York")
RECORDED=datetime(2026,11,9,22,tzinfo=timezone.utc)
START=datetime(2026,11,10,1,15,tzinfo=timezone.utc)
MATURE=datetime(2026,11,12,12,tzinfo=timezone.utc)
RUN=42711310554


def _raw(league):
    obj={"events":[{
        "id":"60000012" if league=="nfl" else "60000022",
        "date":START.isoformat(),"season":{"type":2},
        "status":{"type":{"state":"pre","completed":False}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":"201","displayName":"Alpha"}},
            {"homeAway":"away","team":{"id":"202","displayName":"Beta"}},
        ]}]}]}
    return json.dumps(obj,sort_keys=True).encode()


def write_original(root,league,*,run=RUN,probability=.63,recorded=RECORDED,
                   completed=None):
    base=Path(root)/league/str(run)
    base.mkdir(parents=True)
    raw=_raw(league)
    day=START.astimezone(NY).date()
    event={
        "record_type":"v8_genuine_forward_clocktime_multisport_Elo_research_only",
        "league":league,
        "espn_event_id":"60000012" if league=="nfl" else "60000022",
        "home_team":"Alpha","away_team":"Beta","home_team_espn_id":"201",
        "away_team_espn_id":"202","start_utc":START.isoformat(),
        "forecast_recorded_utc":recorded.isoformat(),
        "schedule_original_received_at_utc":(recorded-timedelta(minutes=1)).isoformat(),
        "schedule_original_sha256_local_receipt":hashlib.sha256(raw).hexdigest(),
        "schedule_source_url":scoreboard_url(league,day),
        "model_version":SPEC[league]["version"],
        "model_probability_home_win_research_only":probability,
        "model_probability_away_win_research_only":1-probability,
        "model_target":(
            "NFL_home_vs_away_given_no_tie_NOT_a_market_moneyline"
            if league=="nfl" else
            "NHL_fullgame_published_winner_including_OT_SO_not_market_verified"),
        "original_prediction_recorded_before_tipoff":True,
        "future_outcome":None,"published_final_observed_at_utc":None,
        "qualified_for_certified_champion_001_shadow":False,
        "model_independently_calibrated":False,"bookmaker_checkout_price_verified":False,
        "certified_prediction":False,"positive_ev_bet":False,
        "bet_ready":False,"stake_usd":0,"champion_001_modified":False,
    }
    def save(name,payload):
        (base/name).write_text(json.dumps(payload,sort_keys=True)+"\n")
    save("github_run.json",{
        "id":run,"head_branch":"main","status":"completed","conclusion":"success",
        "event":"push","created_at":(recorded-timedelta(minutes=2)).isoformat(),
        "updated_at":(completed or recorded+timedelta(minutes=3)).isoformat()})
    save(league.upper()+"_FORWARD_RESEARCH_STATUS.json",{
        "stage":"v8_nfl_nhl_forward_original_source_research_only",
        "league":league,"model_version":SPEC[league]["version"],
        "recorded_at_utc":recorded.isoformat(),
        "forecast_probabilities_recorded_before_start":1,
        "original_champion_001_certified_predictions":0,
        "certified_v8_predictions":0,"certified_positive_ev_bets":0,
        "champion_001_modified":False,"bet_ready":False})
    save(league.upper()+"_PUBLISHED_HISTORY_COVERAGE.json",{
        "leagues":[league],"champion_001_modified":False})
    save(league.upper()+"_FORWARD_RESEARCH_FORECASTS.jsonl",event)
    (base/f"{league}_original_future_schedule_{day:%Y%m%d}.json").write_bytes(raw)
    return base,event


def published(league,*,tie=False,homeid="201",start=START):
    if league=="nfl":
        scores=("20","20") if tie else ("24","17")
    else:
        scores=("3","3") if tie else ("3","2")
    original={
        "id":"60000012" if league=="nfl" else "60000022",
        "date":start.isoformat(),"season":{"type":2},
        "status":{"type":{"state":"post","completed":True}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":homeid,"displayName":"Alpha"},"score":scores[0]},
            {"homeAway":"away","team":{"id":"202","displayName":"Beta"},"score":scores[1]},
        ]}]}
    return normalize_game(original,league,scoreboard_url(league,start.astimezone(NY).date()),MATURE)


def collector(league,*,tie=False,homeid="201"):
    def download(leagues,days,end):
        assert leagues==(league,) and days==1 and end==START.astimezone(NY).date()
        result=[published(league,tie=tie,homeid=homeid)]
        return result,{"leagues":[league],"champion_001_modified":False,
            "total_completed_results":len(result),
            "by_league":{league:{"days_attempted":1,"days_ok":1,"days_failed":0}}}
    return download


class ResearchLeagueGradingTests(unittest.TestCase):
    def test_original_forecasts_recovered_from_both_real_artifact_shapes(self):
        with tempfile.TemporaryDirectory() as folder:
            for sport in ("nfl","nhl"):
                write_original(folder,sport)
                found,receipt=load_archives(folder,sport)
                self.assertEqual(len(found),1)
                self.assertEqual(receipt["original_completed_github_run_ids"],[RUN])
                self.assertEqual(found[0]["model_probability_home_win_research_only"],.63)
                self.assertTrue(found[0]["github_run_completed_at_utc"])
                self.assertFalse(found[0]["certified_prediction"])

    def test_48h_delays_score_and_then_graded_binary_research(self):
        with tempfile.TemporaryDirectory() as folder:
            for sport in ("nfl","nhl"):
                write_original(folder,sport)
                forecasts,_=load_archives(folder,sport)
                def blocked(*args):
                    raise AssertionError("no_future_published_results")
                pending,rows=grade(sport,forecasts,now=RECORDED,collector=blocked)
                self.assertEqual(pending["actual_ESPN_published_grades"],0)
                self.assertEqual(rows[0]["grade_status"],"PENDING_48H_POST_START_MATURITY")
                graded,ledger=grade(sport,forecasts,now=MATURE,collector=collector(sport))
                self.assertEqual(graded["actual_ESPN_published_grades"],1)
                self.assertEqual(ledger[0]["grade_status"],GRADED)
                self.assertAlmostEqual(
                    ledger[0]["published_result_research_only"]["Brier_research"],
                    (.63-1)**2,places=8)
                self.assertIsNone(graded["research_Brier"]) # 50 minimum
                self.assertEqual(graded["certified_positive_ev_bets"],0)

    def test_nfl_tie_is_excluded_not_labeled_as_loss(self):
        with tempfile.TemporaryDirectory() as folder:
            write_original(folder,"nfl")
            f,_=load_archives(folder,"nfl")
            out,ledger=grade("nfl",f,now=MATURE,collector=collector("nfl",tie=True))
            self.assertEqual(out["actual_ESPN_published_grades"],0)
            self.assertEqual(out["NFL_ties_excluded_from_conditional_binary_target"],1)
            self.assertEqual(ledger[0]["grade_status"],NFL_TIE)
            self.assertTrue(ledger[0]["NFL_tie_excluded_from_binary_grading"])
            self.assertIsNone(ledger[0]["published_result_research_only"])

    def test_nhl_published_tie_remains_hold_not_invented_winner(self):
        with tempfile.TemporaryDirectory() as folder:
            write_original(folder,"nhl")
            f,_=load_archives(folder,"nhl")
            out,ledger=grade("nhl",f,now=MATURE,collector=collector("nhl",tie=True))
            self.assertEqual(out["actual_ESPN_published_grades"],0)
            self.assertEqual(ledger[0]["grade_status"],
                             "HOLD_NHL_TIED_PUBLISHED_FINAL_NO_VERIFIED_WINNER")

    def test_changed_identity_and_unavailable_source_remain_hold(self):
        with tempfile.TemporaryDirectory() as folder:
            write_original(folder,"nfl")
            f,_=load_archives(folder,"nfl")
            _,rows=grade("nfl",f,now=MATURE,collector=collector("nfl",homeid="500"))
            self.assertEqual(rows[0]["grade_status"],"HOLD_CHANGED_EVENT_OR_TEAM_IDENTITY")
            def unreachable(*args):
                return [],{"leagues":["nfl"],"champion_001_modified":False,
                    "total_completed_results":0,
                    "by_league":{"nfl":{"days_attempted":1,"days_ok":0,"days_failed":1}}}
            _,rows=grade("nfl",f,now=MATURE,collector=unreachable)
            self.assertEqual(rows[0]["grade_status"],"HOLD_ESPN_SOURCE_DAY_UNAVAILABLE")

    def test_changed_original_bytes_and_ended_gitHub_run_quarantined(self):
        with tempfile.TemporaryDirectory() as folder:
            base,_=write_original(folder,"nfl")
            day=START.astimezone(NY).date()
            (base/f"nfl_original_future_schedule_{day:%Y%m%d}.json").write_bytes(b'{"events":[]}')
            f,r=load_archives(folder,"nfl")
            self.assertEqual(f,[])
            self.assertEqual(r["source_exclusions"]["unsafe_source_run_ValueError"],1)
        with tempfile.TemporaryDirectory() as folder:
            write_original(folder,"nhl",completed=START+timedelta(minutes=5))
            f,r=load_archives(folder,"nhl")
            self.assertEqual(f,[])
            self.assertEqual(r["source_exclusions"]["unsafe_source_run_ValueError"],1)

    def test_later_reforecast_cannot_replace_earliest(self):
        with tempfile.TemporaryDirectory() as folder:
            write_original(folder,"nfl")
            write_original(folder,"nfl",run=RUN+1,
                           recorded=RECORDED+timedelta(minutes=5),probability=.9)
            f,r=load_archives(folder,"nfl")
            self.assertEqual(len(f),1)
            self.assertAlmostEqual(f[0]["model_probability_home_win_research_only"],.63)
            self.assertEqual(r["source_exclusions"]["later_forecast_ignored"],1)


if __name__=="__main__":
    unittest.main()
