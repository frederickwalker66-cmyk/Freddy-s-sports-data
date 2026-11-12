"""Synthetic exact-player, exact-stat NFL/NBA props: research only, no APIs."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from v8_sharp_player_props import inspect_player_prop, summarize_player_props
from v8_one_command import execute, selected
from v8_edge_value import rank_research_edges, research_edge

NOW=datetime(2026, 11, 12, 11, tzinfo=timezone.utc)
START="2026-11-13T01:00:00Z"


def prop(side="over", odds=-110, capture="2026-11-12T10:01:00Z",
         timestamp="2026-11-12T10:00:00Z", league="nfl", **overrides):
    result={
        "source": "sharpapi_rest", "sportsbook": "draftkings",
        "record_type": "pregame_odds_observation",
        "league": league, "event_id": "provider-nfl-2026-1" if league=="nfl"
            else "provider-nba-2026-1",
        "home_team": "Home Test", "away_team": "Away Test",
        "player_id": "42", "player_name": "Example Player",
        "market_type": "receiving_yards" if league=="nfl" else "points",
        "line": 64.5 if league=="nfl" else 24.5,
        "selection_type": side, "selection": "Over" if side=="over" else "Under",
        "is_player_prop": True, "is_main_line": True,
        "is_alternate_line": False,
        "odds_american": odds,
        "odds_decimal": 1 + (odds/100 if odds>0 else 100/abs(odds)),
        "event_start_time": START, "timestamp": timestamp,
        "recorded_at": capture, "model_probability": None,
        "certified_prediction": False,
    }
    result.update(overrides)
    return result


def two_snapshots(league="nfl"):
    return [
        prop("over", -110, league=league),
        prop("under", -110, league=league),
        prop("over", -125, "2026-11-12T10:08:00Z", "2026-11-12T10:07:00Z",
             league=league),
        prop("under", +105, "2026-11-12T10:08:00Z", "2026-11-12T10:07:00Z",
             league=league),
    ]


def edge_prop(league="nfl", **overrides):
    result={
        "league": league, "market": "player_prop", "selection": "over",
        "event_id": "espn-forecast-for-review", "bookmaker": "SampleBook",
        "champion_001_modified": False, "model_version": "test-model-not-certified",
        "model_probability_source": "native_independent_pregame",
        "independent_model_review": True, "independent_price_review": True,
        "player_id": "42", "player_name": "Example Player",
        "prop_stat": "receiving_yards" if league=="nfl" else "points",
        "line": 64.5 if league=="nfl" else 24.5,
        "is_alternate_line": False,
        "independent_player_active_review": True,
        "independent_prop_stat_settlement_review": True,
        "independent_prop_model_review": True,
        "model_probability": 0.58, "american_odds": -110,
        "start_utc": START,
        "model_forecast_recorded_utc": "2026-11-12T09:50:00Z",
        "price_recorded_utc": "2026-11-12T09:52:00Z",
    }
    result.update(overrides)
    return result


class NFLPlayerPropSharpResearchTests(unittest.TestCase):
    def test_nfl_and_nba_exact_same_line_repricing_is_not_sharp_money(self):
        for league in ("nba", "nfl"):
            with self.subTest(league=league):
                report, moves=summarize_player_props(two_snapshots(league), now=NOW)
                self.assertEqual(report["valid_exact_player_prop_quote_observations"],4)
                self.assertEqual(report["two_sided_same_line_snapshots"],2)
                self.assertEqual(report["exact_player_stat_line_repricings_historical"],1)
                self.assertEqual(report["upcoming_repricing_research_observations"],1)
                self.assertEqual(report["certified_positive_ev_bets"],0)
                self.assertEqual(report["automated_wagers"],0)
                self.assertFalse(report["champion_001_modified"])
                self.assertFalse(moves[0]["sharp_money_flow_verified"])
                self.assertFalse(moves[0]["player_active_independently_verified"])
                self.assertFalse(moves[0]["direct_draftkings_checkout_verified"])
                self.assertEqual(moves[0]["direction"],"toward_over")

    def test_changed_stat_player_or_line_never_reuses_same_market(self):
        rows=two_snapshots()
        rows[2]["line"]=65.5
        rows[3]["line"]=65.5
        report,moves=summarize_player_props(rows,now=NOW)
        self.assertEqual(moves,[])
        self.assertEqual(report["two_sided_same_line_snapshots"],2)
        rows=two_snapshots()
        rows[2]["player_id"]="different-player"
        rows[3]["player_id"]="different-player"
        report,moves=summarize_player_props(rows,now=NOW)
        self.assertEqual(moves,[])
        rows=two_snapshots()
        rows[2]["market_type"]="receptions"
        rows[3]["market_type"]="receptions"
        report,moves=summarize_player_props(rows,now=NOW)
        self.assertEqual(moves,[])

    def test_missing_player_id_primary_line_and_source_quarantined(self):
        for key,value in (("player_id",None),("is_main_line",None),
                          ("is_alternate_line",True),("source","other"),
                          ("line",-1),("selection_type","home")):
            with self.subTest(key=key):
                row=prop(**{key:value})
                item,reason=inspect_player_prop(row)
                self.assertIsNone(item)
                self.assertIsNotNone(reason)
                report,moves=summarize_player_props([row],now=NOW)
                self.assertEqual(report["valid_exact_player_prop_quote_observations"],0)
                self.assertEqual(moves,[])

    def test_future_stale_and_inplay_prices_fail_closed(self):
        for changes in (
            {"recorded_at":"2026-11-12T11:02:00Z"},
            {"timestamp":"2026-11-12T09:00:00Z"},
            {"event_start_time":"2026-11-12T09:00:00Z"},
            {"timestamp":"2026-11-12T10:03:00Z"},
        ):
            with self.subTest(changes=changes):
                report,_=summarize_player_props([prop(**changes)],now=NOW)
                self.assertEqual(report["valid_exact_player_prop_quote_observations"],0)
                self.assertEqual(report["certified_positive_ev_bets"],0)

    def test_stale_upcoming_or_started_event_has_no_watchlist(self):
        later=datetime(2026,11,12,15,tzinfo=timezone.utc)
        report,moves=summarize_player_props(two_snapshots(),now=later)
        self.assertEqual(len(moves),1)
        self.assertEqual(report["upcoming_repricing_research_observations"],0)
        self.assertEqual(report["decision"],"PASS_NO_VALIDATED_PROP_EDGE")

    def test_command_one_click_archive_report_does_not_place_bet(self):
        self.assertEqual(selected("run_nfl_props_edge"),("nba","nfl"))
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/"result"
            all_rows=two_snapshots("nfl")+two_snapshots("nba")
            report=execute("run_nfl_props_edge",sharp_rows=all_rows,
                           sharp_run_ids=[4321],now=NOW,output_dir=out)
            view=report["nfl_and_player_props_edge_research"]
            self.assertEqual(view["nfl_exact_prop_archive_observations"],4)
            self.assertEqual(view["nba_exact_prop_archive_observations"],4)
            self.assertEqual(view["nfl_primary_moneyline_archive_observations"],0)
            self.assertEqual(view["certified_positive_ev_bets"],0)
            self.assertEqual(report["research_edge_candidates"],[])
            self.assertFalse(view["champion_001_modified"])
            self.assertTrue((out/"sharp_prop_line_movements.jsonl").is_file())
            self.assertTrue((out/"NFL_PLAYER_PROP_SHARP_EDGE_RESEARCH.json").is_file())
            self.assertTrue((out/"ONE_COMMAND_REPORT.json").is_file())
            self.assertEqual(json.loads(
                (out/"NFL_PLAYER_PROP_SHARP_EDGE_RESEARCH.json").read_text())["decision"],
                "PASS_NO_INDEPENDENTLY_VERIFIED_EDGE")

    def test_empty_prop_archive_explicit_zero_not_made_up(self):
        with tempfile.TemporaryDirectory() as folder:
            report=execute("run_nfl_props_edge",output_dir=folder)
            self.assertEqual(report["sharp_player_props"]["status"],
                             "no_eligible_archived_player_prop_quotes")
            self.assertEqual(report["certified_positive_ev_bets"],0)

    def test_player_prop_indicative_ev_math_requires_full_review(self):
        for league in ("nba","nfl"):
            with self.subTest(league=league):
                r=research_edge(edge_prop(league))
                self.assertTrue(r["positive_ev_research_only"])
                self.assertGreater(r["indicative_ev_roi_percent"],0)
                self.assertEqual(r["prop_stat"],"receiving_yards"
                                 if league=="nfl" else "points")
                self.assertFalse(r["verified_executable_checkout_price"])
                self.assertFalse(r["certified_prediction"])
                self.assertEqual(r["stake_usd"],0)

    def test_prop_missing_player_review_or_wrong_settlement_rejected(self):
        for key,value in (
            ("independent_player_active_review",False),
            ("independent_prop_model_review",False),
            ("independent_prop_stat_settlement_review",False),
            ("is_alternate_line",True),
            ("player_id",None),
            ("line",None),
            ("prop_stat","not_a_supported_prop"),
            ("selection","home"),
        ):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    research_edge(edge_prop(**{key:value}))

    def test_nfl_conditional_elo_must_not_be_moneyline_ev(self):
        candidate=edge_prop()
        candidate.update(market="moneyline",selection="home")
        with self.assertRaisesRegex(ValueError,
                                    "nfl_conditional_elo_is_not_a_market_moneyline"):
            research_edge(candidate)
        candidate.update(
            model_target="NFL_fullgame_moneyline_ties_refunds_reviewed",
            independent_market_settlement_review=True)
        result=research_edge(candidate)
        self.assertFalse(result["certified_prediction"])

    def test_props_not_deduplicated_across_different_players(self):
        p=edge_prop("nba")
        other=edge_prop("nba",player_id="43",player_name="Another Player")
        ranked=rank_research_edges([p,other])
        self.assertEqual(len(ranked),2)
        self.assertEqual({x["player_id"] for x in ranked},{"42","43"})
        self.assertTrue(all(not x["bet_ready"] for x in ranked))


if __name__=="__main__":
    unittest.main()
