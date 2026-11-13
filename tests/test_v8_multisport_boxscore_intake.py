"""Parser never merges category stats across different players or games."""
import unittest
from datetime import datetime,timedelta,timezone
from v8_multisport_boxscore_intake import parse_box_score,_ip_outs
from historical_outcomes import normalize_game,scoreboard_url
from v8_all_sports_player_form import STATS
from zoneinfo import ZoneInfo

NOW=datetime(2026,11,13,18,tzinfo=timezone.utc)
NY=ZoneInfo("America/New_York")
START=datetime(2026,11,5,19,tzinfo=NY).astimezone(timezone.utc)


def official_game(league):
    event={
        "id":"403","date":START.isoformat(),"season":{"type":2},
        "status":{"type":{"state":"post","completed":True}},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"id":"101","displayName":"A"},"score":110},
            {"homeAway":"away","team":{"id":"102","displayName":"B"},"score":100},
        ]}]}
    return normalize_game(event,league,scoreboard_url(league,
                                     START.astimezone(NY).date()),NOW)


def summary(league,category,labels,values):
    return {
        "header":{"id":"403","competitions":[{
            "date":START.isoformat(),
            "status":{"type":{"completed":True}},
            "competitors":[{"team":{"id":"101"}},{"team":{"id":"102"}}],
        }]},
        "boxscore":{"players":[
            {"team":{"id":"101"},
             "statistics":[{"name":category,"names":labels,"athletes":[
                 {"athlete":{"id":"555","displayName":"Example"},
                  "didNotPlay":False,"stats":values}]}]},
            {"team":{"id":"102"},
             "statistics":[{"name":category,"names":labels,"athletes":[
                 {"athlete":{"id":"556","displayName":"Other"},
                  "didNotPlay":False,"stats":values}]}]},
        ]}
    }


class ESPNMultiLeagueStatsTests(unittest.TestCase):
    def test_NBA_NCAAB_points_rebounds_assists_threepoint_makes(self):
        for league in ("nba","ncaab"):
            x=summary(league,"players",["MIN","PTS","REB","AST","3PT","STL","BLK"],
                      ["33:20","25","9","7","3-7","2","1"])
            p=parse_box_score(league,x,official_game(league),NOW.isoformat())
            self.assertEqual(len(p),2)
            self.assertEqual(p[0]["stats"]["points"],25)
            self.assertEqual(p[0]["stats"]["threes_made"],3)
            self.assertEqual(p[0]["stats"]["assists"],7)
            self.assertTrue(p[0]["published_boxscore_research_only"])
            self.assertFalse(p[0]["independently_verified_player_stats"])

    def test_NFL_and_college_passing_rushing_receiving(self):
        for league in ("nfl","ncaaf"):
            x=summary(league,"passing",["C/ATT","YDS","TD","INT"],
                      ["23/38","284","3","1"])
            cats=x["boxscore"]["players"]
            for group in cats:
                group["statistics"].append({
                    "name":"rushing","names":["CAR","YDS","TD"],
                    "athletes":[{"athlete":{"id":"555" if group["team"]["id"]=="101"
                                           else "556"},"didNotPlay":False,
                                 "stats":["5","21","1"]}]})
            p=parse_box_score(league,x,official_game(league),NOW.isoformat())
            self.assertEqual(p[0]["stats"]["passing_completions"],23)
            self.assertEqual(p[0]["stats"]["passing_yards"],284)
            self.assertEqual(p[0]["stats"]["rushing_yards"],21)

    def test_MLB_innings_not_naive_decimal_5point2(self):
        x=summary("mlb","pitching",["IP","H","ER","BB","SO"],
                  ["5.2","3","1","2","8"])
        p=parse_box_score("mlb",x,official_game("mlb"),NOW.isoformat())
        self.assertEqual(p[0]["stats"]["pitching_outs"],17)
        self.assertEqual(p[0]["stats"]["pitching_strikeouts"],8)
        self.assertEqual(_ip_outs("5.3"),None)

    def test_hockey_goalie_saves_not_skater_shots(self):
        x=summary("nhl","goalies",["SV","GA"],["26","2"])
        p=parse_box_score("nhl",x,official_game("nhl"),NOW.isoformat())
        self.assertEqual(p[0]["stats"],{"saves":26})

    def test_MLS_UEFA_soccer_stats_only_when_vectors_available(self):
        for league in ("mls","uefa_champions_league"):
            x=summary(league,"soccer",["G","A","SH","SOG","MIN"],
                      ["1","1","4","2","90"])
            p=parse_box_score(league,x,official_game(league),NOW.isoformat())
            self.assertEqual(p[0]["stats"]["shots_on_target"],2)

    def test_cross_match_team_and_event_mismatch_fail(self):
        x=summary("nba","basketball",["MIN","PTS"],["25","16"])
        x["header"]["id"]="wrong"
        with self.assertRaisesRegex(ValueError,"event_ID_mismatch"):
            parse_box_score("nba",x,official_game("nba"),NOW.isoformat())
        x["header"]["id"]="403"
        x["boxscore"]["players"][0]["team"]["id"]="999"
        with self.assertRaisesRegex(ValueError,"team_disagrees"):
            parse_box_score("nba",x,official_game("nba"),NOW.isoformat())


if __name__=="__main__":
    unittest.main()
