"""Synthetic fixtures only; they are not historical performance claims."""
import unittest
from datetime import date,datetime,timezone
from historical_outcomes import normalize_game,collect,scoreboard_url,LEAGUES
from challenger_elo_walkforward import evaluate,pregame_probability,embargoed_forecasts,validate_game

NOW=datetime(2026,10,29,20,tzinfo=timezone.utc)
def game(eid="22",when="2026-10-29T01:00:00Z",hs="102",as_="98",post=True):
    return {
        "id":eid,"date":when,
        "status":{"type":{"state":"post" if post else "in","completed":post}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":"1","displayName":"Home Team"},"score":hs},
            {"homeAway":"away","team":{"id":"2","displayName":"Away Team"},"score":as_},
        ]}]
    }

def outcome(i,league="nba",home="1",away="2",score_h=100,score_a=90,when=None):
    when=when or "2026-01-{:02d}T18:00:00+00:00".format(1+i%25)
    return {
        "record_type":"historical_completed_game_research",
        "outcome_source":"espn_public_scoreboard","official_league_result_verified":False,
        "champion_001_modified":False,"league":league,"espn_event_id":str(i),
        "event_start_utc":when,"home_team_espn_id":home,"away_team_espn_id":away,
        "home_score":score_h,"away_score":score_a,
        "result":"home" if score_h>score_a else "away" if score_h<score_a else "draw"
    }
class HistoricalTests(unittest.TestCase):
    def test_completed_game_only(self):
        url=scoreboard_url("nba",date(2026,10,28))
        row=normalize_game(game(), "nba",url,NOW)
        self.assertEqual((row["home_score"],row["away_score"],row["result"]),(102,98,"home"))
        self.assertFalse(row["official_league_result_verified"])
        self.assertIsNone(normalize_game(game(post=False),"nba",url,NOW))
    def test_noncompleted_score_and_future_fail_closed(self):
        u=scoreboard_url("nba",date(2026,10,28))
        self.assertIsNone(normalize_game(game(hs="TBD"),"nba",u,NOW))
        self.assertIsNone(normalize_game(game(when="2026-10-30T01:00:00Z"),"nba",u,NOW))
    def test_late_eastern_game_kept(self):
        sample={"events":[game(when="2026-10-29T01:00:00Z")]}
        rows,r=collect(("nba",),1,date(2026,10,28),fetcher=lambda url:sample,
                       clock=lambda:NOW,pause_seconds=0)
        self.assertEqual(len(rows),1)
        self.assertEqual(r["total_completed_results"],1)
    def test_provider_failure_reported_not_silent(self):
        def fail(_):raise TimeoutError("test")
        rows,r=collect(("nba",),1,date(2026,10,28),fetcher=fail,clock=lambda:NOW,pause_seconds=0)
        self.assertEqual(len(rows),0)
        self.assertEqual(r["by_league"]["nba"]["days_failed"],1)
    def test_all_eight_leagues_configured(self):
        self.assertEqual(len(LEAGUES),8)

class EloTests(unittest.TestCase):
    def test_initial_home_probability_not_market_implied(self):
        self.assertGreater(pregame_probability(1500,1500),0.5)
        self.assertLess(pregame_probability(1500,1500),0.7)
    def test_ties_and_three_way_not_certified(self):
        r=evaluate([outcome(1,league="mls",score_h=2,score_a=2),
                    outcome(2,league="nfl",score_h=0,score_a=0)],min_games=0,min_eval=1)
        self.assertEqual(r["by_league"]["mls"]["status"],"three_way_model_required")
        self.assertEqual(r["by_league"]["nfl"]["excluded_ties"],1)
        self.assertEqual(r["certified_champion_001_predictions"],0)
    def test_real_outcome_requirement(self):
        sample=outcome(1);sample["result"]="away"
        with self.assertRaises(ValueError):evaluate([sample])
    def test_reject_duplicate_ids(self):
        with self.assertRaises(ValueError):evaluate([outcome(1),outcome(1)])
    def test_walkforward_scores_no_claim_of_calibration(self):
        rows=[]
        for i in range(120):
            rows.append(outcome(i+1,home=str(i%8+1),away=str((i+3)%8+1),
                score_h=100 if i%3!=0 else 90,score_a=90 if i%3!=0 else 100,
                when="2026-01-{:02d}T{:02d}:00:00+00:00".format(i//4%28+1,i%4)))
        rep=evaluate(rows,min_games=80,min_eval=30)
        item=rep["by_league"]["nba"]
        self.assertEqual(item["evaluation_games"],40)
        self.assertEqual(item["status"],"provisional_walkforward_diagnostic")
        self.assertTrue(0<=item["diagnostic_brier"]<=1)
        self.assertFalse(item["calibrated_probability_model_certified"])
        self.assertFalse(item["bet_ready"])
    def test_simultaneous_kickoff_update_not_leaked(self):
        g1=outcome(1,home="A",away="B",score_h=10,score_a=9)
        g2=outcome(2,home="A",away="C",score_h=5,score_a=8)
        # When all games start together, their pregame forecasts must be
        # independent of each other's *results* and input ordering.
        a=evaluate([g1,g2],min_games=0,min_eval=1)["by_league"]["nba"]["diagnostic_brier"]
        b=evaluate([g2,g1],min_games=0,min_eval=1)["by_league"]["nba"]["diagnostic_brier"]
        self.assertEqual(a,b)

    def test_previous_score_unavailable_for_nearby_start(self):
        # Same team starts a second event one hour later. The first result
        # must NOT affect its second pregame forecast.
        g1=outcome(1,home="A",away="B",score_h=100,score_a=90,
                   when="2026-01-01T12:00:00+00:00")
        opposite=outcome(1,home="A",away="B",score_h=90,score_a=100,
                         when="2026-01-01T12:00:00+00:00")
        g2=outcome(2,home="A",away="C",score_h=101,score_a=90,
                   when="2026-01-01T13:00:00+00:00")
        g3=outcome(3,home="A",away="D",score_h=101,score_a=90,
                   when="2026-01-04T13:00:00+00:00")
        a,_=embargoed_forecasts([validate_game(v) for v in (g1,g2,g3)])
        b,_=embargoed_forecasts([validate_game(v) for v in (opposite,g2,g3)])
        self.assertEqual(a[1][0],b[1][0])
        self.assertNotEqual(a[2][0],b[2][0])
        self.assertFalse(evaluate([g1,g2])["by_league"]["nba"][
            "historical_final_publication_timestamp_verified"])
        with self.assertRaises(ValueError):
            embargoed_forecasts([validate_game(g1)],lag_hours=0)
