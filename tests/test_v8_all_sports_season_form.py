"""All-eight-league season boundaries, coverage gates and game last5/10."""
import unittest
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo

from historical_outcomes import normalize_game, scoreboard_url, LEAGUES
from v8_all_sports_season_form import build_season_game_form, season_anchor

NY=ZoneInfo("America/New_York")
NOW=datetime(2026,11,13,18,tzinfo=timezone.utc)
TIP=NOW+timedelta(hours=4)


def scored(league, day, hs, aws, eid, team1="101", team2="102"):
    start=datetime(2026,11,day,19,tzinfo=NY).astimezone(timezone.utc)
    obj={
        "id":str(eid), "date":start.isoformat(), "season":{"type":2},
        "status":{"type":{"state":"post","completed":True}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":team1,"displayName":"Home"},"score":hs},
            {"homeAway":"away","team":{"id":team2,"displayName":"Away"},"score":aws},
        ]}]
    }
    return normalize_game(obj,league,scoreboard_url(league,start.astimezone(NY).date()), NOW)


def coverage(league, *, complete=True):
    start,_=season_anchor(league,NOW)
    end=NOW.astimezone(NY).date()-timedelta(days=1)
    days=[(start+timedelta(days=i)).isoformat()
          for i in range((end-start).days+1)]
    if not complete:
        days.pop()
    return {"league":league,
            "conservative_collection_anchor_et":start.isoformat(),
            "source_days_confirmed_et":days,
            "source_days_failed_in_latest_collection":0,
            "conflicting_game_event_ids":[]}


def target(league):
    return {"league":league,"espn_event_id":"900",
            "home_team_espn_id":"101","away_team_espn_id":"102",
            "start_utc":TIP.isoformat()}


class AllSportsSeasonFormTests(unittest.TestCase):
    def test_season_anchors_cover_all_eight_leagues_and_roll_over(self):
        self.assertEqual(set(LEAGUES),{"nba","nfl","mlb","nhl",
                         "ncaaf","ncaab","mls","uefa_champions_league"})
        for lg in LEAGUES:
            anchor,_=season_anchor(lg,NOW)
            self.assertEqual(anchor.month,7 if lg not in ("mlb","mls") else 1)
        self.assertEqual(season_anchor("nba","2027-02-01T15:00:00Z"),
                         (date(2026,7,1),"2026-2027"))
        self.assertEqual(season_anchor("mlb","2027-02-01T15:00:00Z"),
                         (date(2027,1,1),"2027"))

    def test_each_league_correct_last5_last10_complete_only_with_daily_coverage(self):
        for league in LEAGUES:
            with self.subTest(league=league):
                rows=[scored(league,d,110 if d%2==0 else 95,100,20000+d)
                      for d in range(1,13)]
                # Nov12 is observed final but isn't 48h matured.
                full=build_season_game_form(
                    rows,[target(league)],NOW.isoformat(),{league:coverage(league)})
                one=full["fixtures"][f"{league}:900"]
                h=one["home"]
                self.assertEqual(h["last5"]["observed_matured"],5)
                self.assertEqual(h["last10"]["observed_matured"],10)
                self.assertTrue(h["last5"]["complete_window"])
                self.assertEqual(h["last10"]["source_event_ids"][-1],"20010")
                self.assertEqual(h["last5"]["source_event_ids"][-1],"20010")
                self.assertEqual(h["back_to_back_second_night_observed_schedule_only"],True)
                self.assertFalse(one["model_form_coefficients_fitted"])
                self.assertEqual(full["certified_positive_ev_bets"],0)
                part=build_season_game_form(
                    rows,[target(league)],NOW.isoformat(),{league:coverage(league,complete=False)})
                self.assertFalse(part["fixtures"][f"{league}:900"]["home"]
                                 ["last10"]["complete_window"])
                self.assertFalse(part["fixtures"][f"{league}:900"]
                                 ["complete_source_days_since_conservative_season_anchor"])

    def test_soccer_draws_are_three_way_and_not_binary_probabilities(self):
        g=[scored("mls",8,1,1,300),scored("mls",9,2,0,301)]
        r=build_season_game_form(g,[target("mls")],NOW.isoformat(),{"mls":coverage("mls")})
        f=r["fixtures"]["mls:900"]
        self.assertTrue(f["soccer_three_way_and_90_minute_settlement_not_verified"])
        self.assertEqual(f["home"]["last5"]["draws"],1)
        self.assertEqual(f["home"]["last5"]["wins"],1)
        self.assertIsNone(f["home"]["last5"]["betting_model_probability"])
        self.assertIsNone(f["home"]["last5"]["market_line_cover_probabilities"])

    def test_leakage_and_duplicate_sources_rejected(self):
        row=scored("nba",8,113,99,300)
        later={**row,"retrieved_at_utc":(NOW+timedelta(minutes=5)).isoformat()}
        with self.assertRaisesRegex(ValueError,"history_not_observed"):
            build_season_game_form([later],[target("nba")],NOW.isoformat())
        with self.assertRaisesRegex(ValueError,"duplicate_history"):
            build_season_game_form([row,row],[target("nba")],NOW.isoformat())
        row_bad={**row,"source_url":"https://site.api.espn.com/incorrect"}
        with self.assertRaises(ValueError):
            build_season_game_form([row_bad],[target("nba")],NOW.isoformat())


if __name__=="__main__":
    unittest.main()
