"""Player L5/L10 sport stat schemas and no fake edge for 8 leagues."""
import unittest
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from v8_all_sports_player_form import (
    build_all_player_form, SPORT_PATH,ESPN_SUMMARY_ROOT,STATS,historical_line_hits)
from v8_all_sports_season_form import season_anchor
from historical_outcomes import LEAGUES

NOW=datetime(2026,11,13,18,tzinfo=timezone.utc)
TIP=NOW+timedelta(hours=5)
NY=ZoneInfo("America/New_York")


def history(league,day):
    start=datetime(2026,11,day,19,tzinfo=NY).astimezone(timezone.utc)
    field=STATS[league][0]
    return {
        "league":league,"espn_event_id":str(20000+day),
        "espn_player_id":"8001","espn_team_id":"501",
        "event_start_utc":start.isoformat(),
        "retrieved_at_utc":NOW.isoformat(),
        "season_type":2,
        "source_url":ESPN_SUMMARY_ROOT+SPORT_PATH[league]+"/summary?event="+str(20000+day),
        "did_not_play":False,
        "stats":{field:day},
        "published_boxscore_research_only":True,
        "qualified_for_player_prop_training":False,
        "independently_verified_player_stats":False,
        "champion_001_modified":False,
    }


def target(league):
    return {"league":league,"espn_event_id":"9000",
            "espn_player_id":"8001","start_utc":TIP.isoformat()}


def coverage(league,complete=True):
    anchor,_=season_anchor(league,NOW)
    date0=NOW.astimezone(NY).date()
    dates=[(anchor+timedelta(days=d)).isoformat()
           for d in range((date0-anchor).days)]
    if not complete:
        dates.pop()
    return {
        "conservative_collection_anchor_et":anchor.isoformat(),
        "source_days_confirmed_et":dates,
        "source_days_failed_in_latest_collection":0,
        "conflicting_game_event_ids":[],
    }


class AllSportPlayerRollingFormTests(unittest.TestCase):
    def test_sport_specific_schemas_all_eight_have_l5_and_l10(self):
        self.assertEqual(set(STATS),set(LEAGUES))
        for league in LEAGUES:
            with self.subTest(league=league):
                rows=[history(league,d) for d in range(1,13)]
                r=build_all_player_form(rows,[target(league)],NOW.isoformat(),
                                        {league:coverage(league)})
                p=r["players_by_event"][f"{league}:9000:8001"]
                self.assertTrue(p["last5"]["complete_window_for_sport_stats"])
                self.assertTrue(p["last10"]["complete_window_for_sport_stats"])
                self.assertEqual(p["last10"]["actual_historical_espn_event_ids"][-1],"20010")
                self.assertEqual(p["last5"]["season_to_date_stats_last_window_average"]
                                 [STATS[league][0]],8.0)
                self.assertIsNone(p["independent_prop_model_probabilities"])
                self.assertEqual(r["certified_positive_ev_bets"],0)
                partial=build_all_player_form(rows,[target(league)],NOW.isoformat(),
                                              {league:coverage(league,complete=False)})
                p2=partial["players_by_event"][f"{league}:9000:8001"]
                self.assertFalse(p2["last5"]["complete_window_for_sport_stats"])
                self.assertIsNone(p2["last5"]["season_to_date_stats_last_window_average"]
                                  [STATS[league][0]])

    def test_missing_one_stat_never_becomes_zero(self):
        row=history("nba",7)
        r=build_all_player_form([row],[target("nba")],NOW.isoformat(),
                                {"nba":coverage("nba")})
        p=r["players_by_event"]["nba:9000:8001"]
        self.assertFalse(p["last5"]["complete_window_for_sport_stats"])
        self.assertIsNone(p["last5"]["season_to_date_stats_last_window_average"]["assists"])

    def test_DNP_and_immature_not_eligible(self):
        rows=[history("nba",8),history("nba",9),history("nba",12)]
        rows[1]["did_not_play"]=True
        result=build_all_player_form(rows,[target("nba")],NOW.isoformat())
        self.assertEqual(result["historical_mature_player_appearance_rows"],1)
        self.assertEqual(result["rejected_history_reasons"]["DNP_not_an_appearance"],1)
        self.assertEqual(result["rejected_history_reasons"]["result_not_matured_48h"],1)

    def test_wrong_ESPN_identity_future_stamp_and_duplicate_rejected(self):
        x=history("nhl",9)
        with self.assertRaisesRegex(ValueError,"duplicate_ESPN"):
            build_all_player_form([x,x],[target("nhl")],NOW.isoformat())
        with self.assertRaisesRegex(ValueError,"invalid_ESPN_player"):
            build_all_player_form([{**x,"source_url":"https://other"}],
                                  [target("nhl")],NOW.isoformat())
        with self.assertRaisesRegex(ValueError,"observed_out_of_order"):
            build_all_player_form([{**x,"retrieved_at_utc":
                                  (NOW+timedelta(days=1)).isoformat()}],
                                  [target("nhl")],NOW.isoformat())

    def test_historical_hit_rate_is_not_model_probability(self):
        items=[{"league":"nba","row":{"stats":{"points":v}}}
               for v in (19,21,20,24,27,16,26,30,13,25)]
        r=historical_line_hits(items,"points",20,"over",10)
        self.assertEqual(r["wins"],6)
        self.assertEqual(r["pushes"],1)
        self.assertAlmostEqual(r["descriptive_hit_rate_not_model_probability"],6/9)
        no=historical_line_hits(items[:4],"points",20,"over",5)
        self.assertFalse(no["complete_window"])
        self.assertIsNone(no["descriptive_hit_rate_not_model_probability"])


if __name__=="__main__":
    unittest.main()
