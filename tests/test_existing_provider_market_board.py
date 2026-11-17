"""Existing-capture market board: no paid provider calls, no stale/false odds."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from scripts.build_existing_provider_market_board import parse,LEAGUES

NOW=datetime(2026,11,17,17,0,tzinfo=timezone.utc)
GAME_START=(NOW+timedelta(hours=2)).isoformat()
def public(lg="nba",home="Cleveland Cavaliers",away="Chicago Bulls"):
    return {"schema":"freddys-espn-public-hourly-v1","date_et":"2026-11-17",
     "champion_001_modified":False,
     "leagues":{lg:{"status":"ESPN_SCOREBOARD_OBSERVED",
       "observed_at_utc":NOW.isoformat(),
       "games":[{"id":"401123456","home":home,"away":away,"status":"pre",
          "start_et":GAME_START}]}}}

def quote(**kwargs):
    data={"record_type":"pregame_odds_observation","league":"nba",
      "sportsbook":"draftkings","certified_prediction":False,
      "event_id":"nba_bulls_cavaliers_2026-11-17_c3",
      "home_team":"Cleveland Cavaliers","away_team":"Chicago Bulls",
      "event_start_time":GAME_START,
      "recorded_at":(NOW-timedelta(minutes=3)).isoformat(),
      "timestamp":(NOW-timedelta(minutes=4)).isoformat(),
      "market_type":"player_points","player_name":"Example Player",
      "is_player_prop":True,"is_alternate_line":False,
      "line":24.5,"odds_american":-110,"selection_type":"over"}
    data.update(kwargs)
    return data

def build(quotes,src=None,now=NOW):
    with TemporaryDirectory() as d:
        p=Path(d)/"odds.jsonl"
        p.write_text("".join(json.dumps(x)+"\n" for x in quotes))
        return parse(p,src if src is not None else public(),now=now,provider_run=123)

class ProviderMarketBoardTests(TestCase):
    def test_over_under_player_prop_and_pr_pra_combos_are_real_rows(self):
        examples=[
            quote(selection_type="over",odds_american=-110),
            quote(selection_type="under",odds_american=-115),
            quote(market_type="player_points_+_rebounds",line=36.5),
            quote(market_type="player_points_+_rebounds_+_assists",line=43.5),
        ]
        d=build(examples)
        nba=d["leagues"]["nba"]
        self.assertEqual(d["capture_status"],"RECENT_PROVIDER_ARTIFACT_RESEARCH_ONLY")
        self.assertEqual(nba["prop"],2)
        self.assertEqual(nba["combo"],2)
        self.assertTrue(all(not x["checkout_verified"] and
                            x["model_probability"] is None for x in nba["rows"]))
        self.assertEqual(d["certified_positive_ev"],0)

    def test_game_moneyline_spread_totals_are_distinct_and_signed(self):
        examples=[
            quote(is_player_prop=False,player_name=None,market_type="moneyline",selection_type="home",line=None,odds_american=-140),
            quote(is_player_prop=False,player_name=None,market_type="moneyline",selection_type="away",line=None,odds_american=120),
            quote(is_player_prop=False,player_name=None,market_type="point_spread",selection_type="home",line=-3.5,odds_american=-108),
            quote(is_player_prop=False,player_name=None,market_type="point_spread",selection_type="away",line=3.5,odds_american=-112),
            quote(is_player_prop=False,player_name=None,market_type="total_points",selection_type="under",line=223.5),
            quote(is_player_prop=False,player_name=None,market_type="total_points",selection_type="over",line=223.5)
        ]
        d=build(examples)
        rows=d["leagues"]["nba"]["rows"]
        self.assertEqual(d["leagues"]["nba"]["game"],6)
        self.assertIn(-3.5,[r["line"] for r in rows])
        self.assertEqual({r["market"] for r in rows},{"moneyline","point_spread","total_points"})

    def test_stale_market_prices_are_not_current(self):
        d=build([quote(timestamp=(NOW-timedelta(hours=2)).isoformat())])
        self.assertEqual(d["leagues"]["nba"]["rows"],[])
        self.assertEqual(d["capture_status"],"NO_USABLE_CURRENT_PROVIDER_ARTIFACT")
        self.assertIsNone(d["leagues"]["nba"].get("last_price"))

    def test_pregame_only_and_ESPN_identity_crosswalk(self):
        base=quote()
        bad=quote(event_start_time=(NOW+timedelta(hours=4)).isoformat())
        self.assertEqual(build([bad])["leagues"]["nba"]["rows"],[])
        bad2=quote(away_team="New York Knicks")
        self.assertEqual(build([bad2])["leagues"]["nba"]["rows"],[])
        source=public()
        source["leagues"]["nba"]["games"][0]["status"]="in"
        self.assertEqual(build([base],src=source)["leagues"]["nba"]["rows"],[])

    def test_all_eight_leagues_can_be_ingested_from_captured_quotes_when_present(self):
        self.assertEqual(len(LEAGUES),8)
        # Test a non-NBA sport and a combo with a real exact game/date match.
        s=public(lg="nfl",home="New York Giants",away="Dallas Cowboys")
        a=quote(league="nfl",home_team="New York Giants",away_team="Dallas Cowboys",
                market_type="player_rushing_+_receiving_yards",player_name="Example Runner",line=98.5)
        x=build([a],src=s)["leagues"]["nfl"]
        self.assertEqual(x["combo"],1)
        self.assertEqual(x["rows"][0]["market_label"],"Rush+Receive")

    def test_missing_provider_zip_is_not_successful_live_prices(self):
        d=parse("/does/not/exist.jsonl",public(),now=NOW)
        self.assertEqual(d["capture_status"],"NO_USABLE_CURRENT_PROVIDER_ARTIFACT")
        self.assertEqual(sum(len(x["rows"]) for x in d["leagues"].values()),0)
