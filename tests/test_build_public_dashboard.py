"""Offline tests: public dashboard never promotes unverified betting evidence."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.build_public_dashboard import build, read_report

NOW = datetime(2026, 11, 14, 21, 0, tzinfo=timezone.utc)


def live(at=NOW):
    return {
        "source_status": "ESPN_SCOREBOARD_OBSERVED",
        "observed_at_utc": at.isoformat(),
        "date_et": at.date().isoformat(),
        "champion_001_modified": False,
        "certified_positive_ev_bets": 0,
        "wagers_placed": 0,
        "pregame_rule_context_status": "EXACT_MATCHED_UNCALIBRATED_PREGAME_RESEARCH_ONLY",
        "games": [{
            "espn_event_id": "123",
            "away_team": "Chicago Bulls",
            "home_team": "Minnesota Timberwolves",
            "scheduled_start_et": "2026-11-14T20:00:00-05:00",
            "source_event_state": "pre",
            "score_away": None, "score_home": None,
            "pregame_rule_home_win_percent": 72.9,
            "pregame_rule_probability_source_time_utc": "2026-11-14T20:40:00Z",
            "pace_extrapolated_final_home_points": None,
            "pace_extrapolated_final_away_points": None,
            "pace_extrapolated_final_total_points": None,
            "projection_status": "PREGAME_NO_LIVE_PROJECTION",
        }],
        "today_unstarted_nba_price_rows_within_120m": 100,
    }


def model():
    return {
        "champion_001_modified": False,
        "certified_positive_ev_bets": 0,
        "checked_at_utc": NOW.isoformat(),
        "by_league": {
            "nba": {"execution_status": "SUCCESS_RESEARCH_ONLY",
                    "uncalibrated_pregame_forecast_rows": 1,
                    "complete_player_last5": 25, "complete_team_last10": 30}
        },
        "sharp_edge_research": {
            "per_sport_market_evidence": {
                "nba": {
                    "archived_provider_quote_rows": 1000,
                    "fresh_paired_game_boards": 5,
                    "fresh_paired_player_prop_markets": 8,
                    "primary_source_blocker": "UNVERIFIED_MODEL_PROBABILITY_AND_CHECKOUT",
                }
            }
        },
        "source_quote_freshness": {
            "by_league": {"nba": {
                "today_upcoming_quote_rows_within_120m": 100,
                "latest_valid_source_received_utc": "2026-11-14T20:50:00Z",
                "latest_valid_archive_receipt_age_minutes": 10,
            }}
        },
    }


class PublicDashboardTests(unittest.TestCase):
    def test_minimal_valid_current_score_and_exact_rule_baseline(self):
        board = build(live=live(), model=model(), at=NOW,
                      live_run=123, model_run=456)
        self.assertEqual(board["live_source_status"], "SOURCE_OBSERVED")
        self.assertEqual(board["games"][0]["pregame_home_probability_pct"], 72.9)
        self.assertEqual(board["games"][0]["status"], "pre")
        self.assertIsNone(board["games"][0]["home_score"])
        self.assertEqual(board["market"]["paired_game_markets"], 5)
        self.assertEqual(board["market"]["paired_prop_markets"], 8)
        self.assertEqual(board["market"]["verified_checkout_prices"], 0)
        self.assertEqual(board["market"]["certified_positive_ev"], 0)
        self.assertTrue(board["model"]["champion_frozen"])
        self.assertEqual(board["sources"]["run_nba"].split("/")[-1], "456")

    def test_stale_scoreboard_is_not_displayed_as_live(self):
        board = build(live=live(NOW - timedelta(hours=4)), model=model(), at=NOW)
        self.assertEqual(board["live_source_status"], "AWAITING_FRESH_PUBLIC_SCOREBOARD")
        self.assertEqual(board["games"], [])
        self.assertIsNone(board["live_observed_at_utc"])
        self.assertEqual(board["market"]["paired_game_markets"], 5)

    def test_model_must_be_frozen_and_zero_certified(self):
        unsafe = model()
        unsafe["champion_001_modified"] = True
        r = build(live=live(), model=unsafe, at=NOW)
        self.assertIsNone(r["market"]["paired_game_markets"])
        self.assertEqual(r["market"]["certified_positive_ev"], 0)
        unsafe = model()
        unsafe["certified_positive_ev_bets"] = 1
        r = build(live=live(), model=unsafe, at=NOW)
        self.assertEqual(r["model"]["betting_state"], "HOLD")

    def test_stale_model_report_cannot_supply_current_market_coverage(self):
        old = model()
        old["checked_at_utc"] = (NOW - timedelta(hours=4)).isoformat()
        board = build(model=old, at=NOW)
        self.assertEqual(board["leagues"]["nba"]["research_freshness"], "STALE_RESEARCH")
        self.assertEqual(board["market"]["price_evidence_state"], "STALE_OR_MISSING_MODEL_REPORT")
        self.assertFalse(board["market"]["paired_market_reference_current"])
        self.assertIsNone(board["market"]["paired_game_markets"])
        self.assertIsNone(board["market"]["paired_prop_markets"])
        # Historical archive evidence remains visible as ARCHIVED, not live.
        self.assertEqual(board["market"]["archived_quotes"], 1000)
        self.assertEqual(board["market"]["certified_positive_ev"], 0)

    def test_old_quote_with_recent_model_shows_missing_current_prices(self):
        recent_model = model()
        recent_model["source_quote_freshness"]["by_league"]["nba"][
            "latest_valid_source_received_utc"] = (NOW - timedelta(hours=3)).isoformat()
        board = build(model=recent_model, at=NOW)
        self.assertEqual(board["leagues"]["nba"]["research_freshness"], "RECENT_RESEARCH")
        self.assertEqual(board["market"]["price_evidence_state"], "STALE_OR_MISSING_PRICE_RECEIPT")
        self.assertIsNone(board["market"]["paired_game_markets"])
        self.assertIsNone(board["market"]["recent_raw_quotes"])
        self.assertEqual(board["market"]["verified_checkout_prices"], 0)

    def test_current_aggregator_stays_research_only(self):
        board = build(model=model(), at=NOW)
        self.assertTrue(board["market"]["paired_market_reference_current"])
        self.assertEqual(board["market"]["paired_game_markets"], 5)
        self.assertEqual(board["market"]["price_evidence_state"],
                         "RECENT_AGGREGATOR_REFERENCE_ONLY_NO_CHECKOUT")
        self.assertEqual(board["market"]["certified_positive_ev"], 0)

    def test_no_in_game_pace_when_pregame(self):
        row = live()
        game = row["games"][0]
        game["pace_extrapolated_final_total_points"] = 256.4
        game["pace_extrapolated_final_away_points"] = 120
        game["pace_extrapolated_final_home_points"] = 136.4
        game["projection_status"] = "IN_GAME_UNCALIBRATED_PACE_ESTIMATE"
        out = build(live=row, model=model(), at=NOW)
        self.assertIsNone(out["games"][0]["pace_total"])

    def test_explicit_score_and_pace_when_inplay(self):
        row = live()
        game = row["games"][0]
        game.update(source_event_state="in", score_away=79, score_home=88,
                    period=3, clock="04:35",
                    projection_status="IN_GAME_UNCALIBRATED_PACE_ESTIMATE",
                    pace_extrapolated_final_total_points=255.2,
                    pace_extrapolated_final_home_points=134.5,
                    pace_extrapolated_final_away_points=120.7)
        out = build(live=row, model=model(), at=NOW)
        self.assertEqual(out["games"][0]["pace_total"], 255.2)
        self.assertEqual(out["games"][0]["home_score"], 88)
        self.assertEqual(out["market"]["certified_positive_ev"], 0)

    def test_invalid_probability_and_missing_source_are_na(self):
        row = live()
        row["pregame_rule_context_status"] = "NO_QUALIFIED_EXACT_MATCH"
        row["games"][0]["pregame_rule_home_win_percent"] = 99.9
        r = build(live=row, at=NOW)
        self.assertIsNone(r["games"][0]["pregame_home_probability_pct"])
        self.assertIsNone(r["market"]["paired_game_markets"])
        self.assertEqual(r["leagues"]["ncaab"]["status"], "No synced research report")

    def test_missing_files_fail_closed(self):
        with TemporaryDirectory() as d:
            self.assertIsNone(read_report(Path(d)/"not-here.json"))
            out = build(at=NOW)
            self.assertEqual(out["games"], [])
            self.assertEqual(out["model"]["betting_state"], "HOLD")
            self.assertFalse(out["live_scoreboard_not_continuous"] is False)

    def test_all_sports_report_fills_missing_leagues_not_fabricated(self):
        r = model()
        r["by_league"]["nhl"] = {"execution_status":"SUCCESS_RESEARCH_ONLY",
                                  "uncalibrated_pregame_forecast_rows": 6}
        out = build(live=live(), model=model(), all_sports=r, at=NOW, all_run=90)
        self.assertEqual(out["leagues"]["nhl"]["forecasts"], 6)
        self.assertIsNone(out["leagues"]["ncaaf"]["forecasts"])
        self.assertEqual(out["sources"]["run_all"].split("/")[-1], "90")




def schedule(at=NOW):
    from hashlib import sha256
    digest = sha256(b"original-public-espn-scoreboard-sample").hexdigest()
    return {
        "date_et": at.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date().isoformat(),
        "collected_at_utc": at.isoformat(),
        "sources": {
            lg: {"status": "retrieved", "first_day_status": "retrieved",
                 "lookahead": [{"date_et": at.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date().isoformat(),
                                "raw_events_listed": n, "original_source_sha256": digest}]}
            for lg,n in [("nba",1),("nhl",1),("nfl",0),("mlb",0),("ncaaf",0),
                         ("ncaab",0),("mls",0),("uefa_champions_league",0)]
        },
        "events": [
            {"league": lg,"provider_game_id":id_,"away_team":a,"home_team":h,
             "requested_date_et": at.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York")).date().isoformat(),
             "source_original_sha256": digest, "status":"scheduled",
             "start_utc":(at+timedelta(hours=3)).isoformat(),
             "observed_at_utc":at.isoformat()}
            for lg,id_,a,h in (("nba","123","Chicago Bulls","Minnesota Timberwolves"),
                               ("nhl","456","Boston Bruins","New York Rangers"))
        ],
    }


class AllSportFixtureTests(unittest.TestCase):
    def test_all_eight_league_slates_have_distinct_status_and_games(self):
        out=build(schedule=schedule(),model=model(),live=live(),at=NOW,schedule_run=789)
        self.assertEqual(set(out["slates"]),{"nba","nhl","nfl","mlb","ncaaf","ncaab","mls","uefa_champions_league"})
        self.assertEqual(out["slates"]["nhl"]["game_count"],1)
        self.assertEqual(out["slates"]["nhl"]["games"][0]["away"],"Boston Bruins")
        self.assertEqual(out["slates"]["nfl"]["game_count"],0)
        self.assertEqual(out["slates"]["nfl"]["status"],"NO_GAMES_LISTED")
        self.assertIsNone(out["slates"]["nhl"]["games"][0]["research_home_probability_pct"])
        self.assertEqual(out["sources"]["schedule"].split("/")[-1],"789")
        self.assertIsNone(out["market_by_league"]["nhl"]["paired_game_markets"])
        self.assertEqual(out["market_by_league"]["nhl"]["certified_positive_ev"],0)

    def test_stale_source_is_not_a_fake_zero_game_day(self):
        out=build(schedule=schedule(NOW-timedelta(hours=4)),model=model(),at=NOW)
        self.assertEqual(out["slates"]["nfl"]["status"],"NO_FRESH_SCHEDULE")
        self.assertIsNone(out["slates"]["nfl"]["game_count"])
        self.assertEqual(out["slates"]["nba"]["games"],[])

    def test_mismatched_original_hash_is_not_accepted(self):
        s=schedule()
        s["events"][1]["source_original_sha256"]="0"*64
        out=build(schedule=s,at=NOW)
        self.assertIsNone(out["slates"]["nhl"]["game_count"])
        self.assertEqual(out["slates"]["nhl"]["status"],"MATCHUPS_UNVERIFIED")
        self.assertEqual(out["slates"]["nba"]["game_count"],1)

    def test_league_specific_price_receipts_never_use_nba_quotes(self):
        m=model()
        m["by_league"]["nhl"]={"execution_status":"SUCCESS_RESEARCH_ONLY"}
        m["sharp_edge_research"]["per_sport_market_evidence"]["nhl"]={
            "archived_provider_quote_rows":0,"fresh_paired_game_boards":0,
            "fresh_paired_player_prop_markets":0}
        out=build(model=m,schedule=schedule(),at=NOW)
        self.assertEqual(out["market_by_league"]["nba"]["paired_game_markets"],5)
        self.assertIsNone(out["market_by_league"]["nhl"]["paired_game_markets"])
        self.assertIsNone(out["market_by_league"]["nhl"]["odds_receipt_utc"])
        self.assertEqual(out["market_by_league"]["nba"]["certified_positive_ev"],0)

    def test_research_forecast_requires_original_game_id_and_current_receipt(self):
        m=model()
        m["research_only_pregame_predictions"]=[{
            "league":"nhl","espn_event_id":"456","confidence_is_uncalibrated_rule_output":True,
            "native_Champion_001_model_probability":None,"verified_live_sportsbook_quote":False,
            "home_win_research_rule_probability":0.64,
            "original_forecast_recorded_utc":NOW.isoformat(),
            "start_utc":(NOW+timedelta(hours=3)).isoformat(),
        }]
        out=build(model=m,schedule=schedule(),at=NOW)
        self.assertEqual(out["slates"]["nhl"]["games"][0]["research_home_probability_pct"],64.0)
        m["research_only_pregame_predictions"][0]["espn_event_id"]="wrong"
        out=build(model=m,schedule=schedule(),at=NOW)
        self.assertIsNone(out["slates"]["nhl"]["games"][0]["research_home_probability_pct"])


    def test_new_hourly_public_scoreboard_is_source_labeled_and_not_certified(self):
        capture={
            "schema":"freddys-espn-public-hourly-v1",
            "date_et":"2026-11-14",
            "champion_001_modified":False,"certified_positive_ev":0,
            "provider_checkout_ever_verified":False,
            "leagues":{
                "nhl":{
                    "status":"ESPN_SCOREBOARD_OBSERVED",
                    "observed_at_utc":NOW.isoformat(),
                    "games":[{
                        "id":"777888999","home":"Boston Bruins","away":"New York Rangers",
                        "start_et":"2026-11-14T19:00:00-05:00","status":"pre",
                        "home_score":None,"away_score":None,
                        "market_reference":{
                            "provider_name":"ESPN BET","away_moneyline":130,
                            "home_moneyline":-150,"spread_details":"BOS -1.5",
                            "total":5.5,
                            "bookmaker_quote_timestamp_utc":None,
                            "direct_checkout_verified":False,"market_reference_only":True}
                    }]
                }
            }
        }
        board=build(public=capture,at=NOW)
        nhl=board["public_hourly_board"]["nhl"]
        self.assertEqual(nhl["line_reference_count"],1)
        self.assertEqual(nhl["games"][0]["market_reference"]["provider"],"ESPN BET")
        self.assertFalse(nhl["games"][0]["market_reference"]["direct_checkout_verified"])
        self.assertIsNone(nhl["games"][0]["market_reference"]["bookmaker_quote_timestamp_utc"])
        self.assertEqual(board["market"]["certified_positive_ev"],0)

    def test_stale_hourly_data_does_not_display_old_lines(self):
        capture={
            "schema":"freddys-espn-public-hourly-v1",
            "date_et":"2026-11-14",
            "champion_001_modified":False,"certified_positive_ev":0,
            "provider_checkout_ever_verified":False,
            "leagues":{
                "nba":{
                    "status":"ESPN_SCOREBOARD_OBSERVED",
                    "observed_at_utc":(NOW-timedelta(hours=3)).isoformat(),
                    "games":[]}
            }
        }
        board=build(public=capture,at=NOW)
        self.assertEqual(board["public_hourly_board"]["nba"]["status"],"NO_CURRENT_ESPN_SCOREBOARD")
        self.assertIsNone(board["public_hourly_board"]["nba"]["line_reference_count"])

    def test_public_data_with_checkout_claim_fails_closed(self):
        capture={"schema":"freddys-espn-public-hourly-v1",
                 "date_et":"2026-11-14",
                 "champion_001_modified":False,
                 "provider_checkout_ever_verified":True,
                 "certified_positive_ev":0,"leagues":{}}
        out=build(public=capture,at=NOW)
        self.assertEqual(out["public_hourly_board"]["nba"]["status"],"NO_CURRENT_ESPN_SCOREBOARD")


    def test_hourly_public_team_records_venue_and_broadcasts(self):
        capture={
            "schema":"freddys-espn-public-hourly-v1",
            "date_et":"2026-11-14",
            "champion_001_modified":False,"certified_positive_ev":0,
            "provider_checkout_ever_verified":False,
            "leagues":{"nba":{
                "status":"ESPN_SCOREBOARD_OBSERVED",
                "observed_at_utc":NOW.isoformat(),
                "games":[{
                    "id":"12345","home":"Minnesota Timberwolves","away":"Chicago Bulls",
                    "start_et":"2026-11-14T20:00:00-05:00","status":"pre",
                    "home_record":"12-3","away_record":"9-6","home_abbr":"MIN",
                    "away_abbr":"CHI","venue":"Target Center",
                    "broadcasts":["ESPN","ABC"],"status_detail":"8:00 PM ET",
                    "market_reference":None
                }]
            }}
        }
        out=build(public=capture,at=NOW)
        game=out["public_hourly_board"]["nba"]["games"][0]
        self.assertEqual(game["home_record"],"12-3")
        self.assertEqual(game["away_record"],"9-6")
        self.assertEqual(game["venue"],"Target Center")
        self.assertEqual(game["broadcasts"],["ESPN","ABC"])
        capture["leagues"]["nba"]["games"][0]["home_record"]="wrong"
        another=build(public=capture,at=NOW)
        self.assertIsNone(another["public_hourly_board"]["nba"]["games"][0]["home_record"])

    def test_observed_line_change_requires_same_book_game_and_date(self):
        def capture(when,total=224.5,book="DraftKings",gid="12345"):
            return {
                "schema":"freddys-espn-public-hourly-v1",
                "date_et":"2026-11-14","champion_001_modified":False,
                "provider_checkout_ever_verified":False,"certified_positive_ev":0,
                "leagues":{"nba":{
                    "status":"ESPN_SCOREBOARD_OBSERVED",
                    "observed_at_utc":when.isoformat(),
                    "games":[{
                        "id":gid,"home":"Minnesota Timberwolves","away":"Chicago Bulls",
                        "start_et":"2026-11-14T20:00:00-05:00",
                        "status":"pre",
                        "market_reference":{
                            "provider_name":book,"total":total,"spread_details":"MIN -4.5",
                            "bookmaker_quote_timestamp_utc":None,
                            "direct_checkout_verified":False,"market_reference_only":True,
                        }
                    }]
                }}
            }
        first=build(public=capture(NOW),at=NOW)
        second=build(public=capture(NOW+timedelta(minutes=30),225.5),
                     previous=first,at=NOW+timedelta(minutes=30))
        game=second["public_hourly_board"]["nba"]["games"][0]
        self.assertEqual(game["reference_change"]["previous_total"],224.5)
        self.assertEqual(game["reference_change"]["current_total"],225.5)
        self.assertEqual(len(game["reference_history"]),2)
        self.assertFalse(game["reference_change"]["sharp_action_verified"])
        self.assertIsNone(game["market_reference"]["bookmaker_quote_timestamp_utc"])
        third=build(public=capture(NOW+timedelta(minutes=60),225.5),
                    previous=second,at=NOW+timedelta(minutes=60))
        g3=third["public_hourly_board"]["nba"]["games"][0]
        self.assertEqual(len(g3["reference_history"]),2)
        self.assertNotIn("reference_change",g3)
        different=build(public=capture(NOW+timedelta(minutes=30),225.5,book="Other"),
                        previous=first,at=NOW+timedelta(minutes=30))
        self.assertNotIn("reference_change",
            different["public_hourly_board"]["nba"]["games"][0])
        mismatch=build(public=capture(NOW+timedelta(minutes=30),225.5,gid="54321"),
                       previous=first,at=NOW+timedelta(minutes=30))
        self.assertNotIn("reference_change",
            mismatch["public_hourly_board"]["nba"]["games"][0])

    def test_next_week_source_checked_events_only(self):
        a=schedule()
        from hashlib import sha256
        source=sha256(b"tomorrow ESPN original").hexdigest()
        a["sources"]["mls"]["lookahead"].append({
            "date_et":"2026-11-15",
            "original_source_sha256":source,
            "raw_events_listed":1,
        })
        a["events"].append({
            "league":"mls","provider_game_id":"99112233",
            "home_team":"LA Galaxy","away_team":"Inter Miami CF",
            "requested_date_et":"2026-11-15",
            "source_original_sha256":source,
            "status":"scheduled",
            "start_utc":"2026-11-15T20:00:00+00:00",
            "observed_at_utc":NOW.isoformat(),
        })
        b=build(schedule=a,at=NOW)
        self.assertEqual(b["slates"]["mls"]["game_count"],0)
        self.assertEqual(len(b["slates"]["mls"]["next_games"]),1)
        self.assertEqual(b["slates"]["mls"]["next_games"][0]["home"],"LA Galaxy")
        self.assertIsNone(b["slates"]["mls"]["next_games"][0]["odds"])
        a["events"][-1]["source_original_sha256"]="0"*64
        b=build(schedule=a,at=NOW)
        self.assertEqual(b["slates"]["mls"]["next_games"],[])



    def test_new_provider_board_matches_public_pregame_game_and_fails_closed(self):
        src={
            "schema":"freddys-espn-public-hourly-v1",
            "date_et":"2026-11-14","champion_001_modified":False,
            "certified_positive_ev":0,"provider_checkout_ever_verified":False,
            "leagues":{"nba":{
              "status":"ESPN_SCOREBOARD_OBSERVED",
              "observed_at_utc":NOW.isoformat(),
              "games":[{
                "id":"404445555","home":"Toronto Raptors","away":"New York Knicks",
                "start_et":"2026-11-14T20:00:00-05:00","status":"pre",
                "market_reference":None
              }]
            }}
        }
        pb={
            "schema":"freddys-existing-book-refs-v1","date_et":"2026-11-14",
            "champion_001_modified":False,"certified_positive_ev":0,
            "checkout_prices_verified":0,"provider_run":123,
            "leagues":{"nba":{"rows":[{
                "league":"nba","public_game_id":"404445555",
                "home":"Toronto Raptors","away":"New York Knicks",
                "event_start_et":"2026-11-14T20:00:00-05:00",
                "player":"Example Player","market":"player_points",
                "market_label":"points","category":"prop",
                "side":"over","line":24.5,"american_odds":-112,
                "provider_quote_utc":NOW.isoformat(),
                "source_received_utc":NOW.isoformat(),
                "provider":"SharpAPI / DraftKings-labelled",
                "is_alternate_line":False,
                "checkout_verified":False,"bet_ready":False,
                "model_probability":None,"expected_value":None,
            }]}}
        }
        out=build(public=src,provider_board=pb,at=NOW)
        rows=out["fresh_provider_markets"]["leagues"]["nba"]["rows"]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["player"],"Example Player")
        self.assertFalse(rows[0]["bookmaker_checkout_verified"])
        self.assertIsNone(rows[0]["native_model_probability"])
        self.assertEqual(out["market"]["certified_positive_ev"],0)
        pb["leagues"]["nba"]["rows"][0]["provider_quote_utc"]=(NOW-timedelta(hours=3)).isoformat()
        stale=build(public=src,provider_board=pb,at=NOW)
        self.assertEqual(stale["fresh_provider_markets"]["leagues"]["nba"]["rows"],[])

    def test_no_provider_data_never_produces_fabricated_prop_rows(self):
        out=build(at=NOW,public=None,provider_board=None)
        self.assertEqual(len(out["fresh_provider_markets"]["leagues"]),8)
        self.assertTrue(all(v["status"]=="NO_RECENT_PROVIDER_MARKETS"
                            for v in out["fresh_provider_markets"]["leagues"].values()))
        self.assertEqual(sum(len(v["rows"]) for v in out["fresh_provider_markets"]["leagues"].values()),0)



if __name__ == "__main__":
    unittest.main()
