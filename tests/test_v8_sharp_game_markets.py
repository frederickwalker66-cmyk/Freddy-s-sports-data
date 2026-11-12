"""Full-game ML, spread and total research only; no external or paid data calls."""
import unittest
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from v8_sharp_game_markets import inspect_full_game_quote, summarize_full_game_markets
from v8_one_command import execute

NOW = datetime(2026, 11, 12, 16, tzinfo=timezone.utc)


def game(league="nba", market="moneyline", side="home", line=None, odds=-110,
         quoted="2026-11-12T15:49:00Z", received="2026-11-12T15:50:00Z",
         **custom):
    default_line = {"moneyline":None, "point_spread":-4.5,
                    "total_points":219.5}[market]
    v = default_line if line is None and market != "moneyline" else line
    row = {
        "source":"sharpapi_rest", "record_type":"pregame_odds_observation",
        "league":league, "sport":"basketball" if league=="nba" else "football",
        "event_id":"NBA_TEST_2026_11_12" if league=="nba" else "NFL_TEST_2026_11_12",
        "home_team":"Home Club", "away_team":"Away Club",
        "event_start_time":"2026-11-13T00:00:00Z"
          if league=="nba" else "2026-11-13T01:15:00Z",
        "sportsbook":"draftkings", "is_player_prop":False,
        "is_main_line":True, "is_alternate_line":False,
        "market_type":market, "line":v, "selection_type":side,
        "selection":side, "odds_american":odds,
        "odds_decimal":1+(odds/100 if odds>0 else 100/abs(odds)),
        "recorded_at":received, "timestamp":quoted,
        "model_probability":None, "certified_prediction":False,
    }
    row.update(custom)
    return row


def pair(league="nba", market="moneyline", line=None, quoted="2026-11-12T15:49:00Z",
         received="2026-11-12T15:50:00Z", first_odds=-110, second_odds=-110):
    if market=="total_points":
        first,second="over","under"
        vals=(219.5,219.5)
    elif market=="point_spread":
        first,second="home","away"
        vals=(-4.5,4.5)
    else:
        first,second="home","away"
        vals=(None,None)
    if line is not None and market=="point_spread":
        vals=(line,-line)
    if line is not None and market=="total_points":
        vals=(line,line)
    return [
        game(league,market,first,vals[0],first_odds,quoted,received),
        game(league,market,second,vals[1],second_odds,quoted,received),
    ]


class FullGameMarketTests(unittest.TestCase):
    def test_three_market_board_for_nba_and_nfl_is_not_a_bet(self):
        rows=[]
        for league in ("nba","nfl"):
            for market in ("moneyline","point_spread","total_points"):
                rows.extend(pair(league,market))
        r,moves=summarize_full_game_markets(rows,now=NOW)
        self.assertEqual(r["today_recent_upcoming_full_games"],2)
        self.assertEqual(r["paired_primary_snapshots_historical"],6)
        self.assertEqual(r["historical_full_game_market_movements"],0)
        self.assertEqual(r["today_recent_upcoming_market_movement_observations"],0)
        self.assertEqual(r["certified_positive_ev_bets"],0)
        self.assertFalse(r["champion_001_modified"])
        for item in r["today_game_market_board"]:
            self.assertTrue(item["all_three_game_markets_present"])
            self.assertEqual(set(item["paired_primary_markets"]),{
                "moneyline","point_spread","total_points"})
            self.assertEqual(item["certified_positive_ev_bets"],0)
            self.assertFalse(item["verified_sportsbook_checkout"])
            for snap in item["paired_primary_markets"].values():
                self.assertFalse(snap["bookmaker_checkout_price_verified"])
                self.assertFalse(snap["native_model_probability_verified"])
        self.assertEqual(moves,[])

    def test_price_repricing_only_at_same_game_and_handicap(self):
        rows=pair(market="total_points",line=220.5,
                  quoted="2026-11-12T15:19:00Z",received="2026-11-12T15:20:00Z")
        rows+=pair(market="total_points",line=220.5,
                  quoted="2026-11-12T15:49:00Z",received="2026-11-12T15:50:00Z",
                  first_odds=-125,second_odds=+105)
        r,moves=summarize_full_game_markets(rows,now=NOW)
        self.assertEqual(len(moves),1)
        self.assertEqual(r["today_recent_upcoming_market_movement_observations"],1)
        self.assertEqual(moves[0]["line_change"],0)
        self.assertGreater(moves[0]["same_line_no_vig_market_price_change_pp"],0)
        self.assertFalse(moves[0]["changed_line_cannot_compare_probability"])
        self.assertFalse(moves[0]["certified_positive_ev"])

    def test_clv_not_fabricated_from_early_bookmaker_repricing(self):
        rows=pair(market="total_points",line=220.5,
                  quoted="2026-11-12T15:19:00Z",received="2026-11-12T15:20:00Z")
        rows+=pair(market="total_points",line=220.5,
                   quoted="2026-11-12T15:49:00Z",received="2026-11-12T15:50:00Z",
                   first_odds=-125,second_odds=+105)
        with tempfile.TemporaryDirectory() as root:
            result=execute("run_nfl_props_edge",sharp_rows=rows,now=NOW,
                           output_dir=root)
            clv=result["sharp_edge_clv"]
            self.assertEqual(clv["exact_market_entry_close_pairs"],0)
            self.assertEqual(clv["tracked_verified_entry_receipts_in_this_run"],0)
            self.assertEqual(clv["tracked_matching_verified_closing_quote_receipts_in_this_run"],0)
            self.assertEqual(clv["archived_provider_market_repricing_observations"],1)
            self.assertIsNone(clv["realized_clv_percent"])
            self.assertIsNone(clv["measured_positive_clv_bets"])
            self.assertFalse(clv["market_repricing_is_verified_clv"])
            self.assertFalse(clv["champion_001_modified"])
            self.assertEqual(clv["automated_wagers"],0)
            self.assertTrue((Path(root)/"NBA_NFL_SHARP_EDGE_CLV.json").is_file())
            saved=json.loads((Path(root)/"NBA_NFL_SHARP_EDGE_CLV.json").read_text())
            self.assertIsNone(saved["realized_clv_percent"])

    def test_handicap_line_move_never_claims_same_outcome_probability(self):
        rows=pair(market="point_spread",line=-4.5,
                  quoted="2026-11-12T15:19:00Z",received="2026-11-12T15:20:00Z")
        rows+=pair(market="point_spread",line=-5.5,
                  quoted="2026-11-12T15:49:00Z",received="2026-11-12T15:50:00Z")
        r,moves=summarize_full_game_markets(rows,now=NOW)
        self.assertEqual(len(moves),1)
        self.assertEqual(moves[0]["line_change"],-1)
        self.assertIsNone(moves[0]["same_line_no_vig_market_price_change_pp"])
        self.assertTrue(moves[0]["changed_line_cannot_compare_probability"])
        self.assertEqual(
            r["today_game_market_board"][0]["paired_primary_markets"]
            ["point_spread"]["home_or_over_line"],-5.5)

    def test_wrong_spread_opposition_or_total_points_quarantined(self):
        for market,changed_line,reason in (
            ("point_spread",4.0,"spread_sides_not_opposites"),
            ("total_points",220.5,"total_sides_different")):
            rows=pair(market=market)
            rows[1]["line"]=changed_line
            r,moves=summarize_full_game_markets(rows,now=NOW)
            self.assertEqual(r["paired_primary_snapshots_historical"],0)
            self.assertEqual(r["excluded_or_unpaired_reasons"][reason],1)
            self.assertEqual(moves,[])

    def test_duplicate_or_single_side_never_completes_a_market(self):
        rows=pair()+[pair()[0]]
        r,_=summarize_full_game_markets(rows,now=NOW)
        self.assertEqual(r["paired_primary_snapshots_historical"],0)
        self.assertEqual(
            r["excluded_or_unpaired_reasons"]["unpaired_or_duplicate_game_market"],1)
        r,_=summarize_full_game_markets(pair()[:1],now=NOW)
        self.assertEqual(r["paired_primary_snapshots_historical"],0)

    def test_source_alternate_inplay_future_and_wrong_status_rejected(self):
        for change in (
            {"source":"not_sharpapi"}, {"is_alternate_line":True},
            {"is_main_line":False}, {"certified_prediction":True},
            {"model_probability":0.71},
            {"recorded_at":"2026-11-12T16:10:00Z"},
            {"timestamp":"2026-11-12T15:30:00Z"},
            {"event_start_time":"2026-11-12T15:00:00Z"},
        ):
            with self.subTest(change=change):
                r,_=summarize_full_game_markets(
                    [dict(row,**change) for row in pair()],now=NOW)
                self.assertEqual(r["paired_primary_snapshots_historical"],0)
                self.assertEqual(r["certified_positive_ev_bets"],0)

    def test_malformed_american_price_or_invalid_market_side_rejected(self):
        for change in ({"odds_american":50},{"odds_decimal":12.0},
                       {"selection_type":"under"},
                       {"event_id":None},{"line":8.5}):
            with self.subTest(change=change):
                market = "moneyline"
                r,_=summarize_full_game_markets([dict(row,**change)
                    for row in pair(market=market)],now=NOW)
                self.assertEqual(r["paired_primary_snapshots_historical"],0)

    def test_old_markets_not_in_todays_board(self):
        rows=pair(quoted="2026-11-10T15:49:00Z",
                  received="2026-11-10T15:50:00Z")
        report,_=summarize_full_game_markets(rows,now=NOW)
        self.assertEqual(report["today_recent_upcoming_full_games"],0)
        self.assertEqual(report["paired_primary_snapshots_historical"],1)
        self.assertEqual(report["certified_positive_ev_bets"],0)

    def test_offline_one_command_archives_game_board_and_props(self):
        rows=[]
        for market in ("moneyline","point_spread","total_points"):
            rows+=pair("nba",market)
            rows+=pair("nfl",market)
        with tempfile.TemporaryDirectory() as tmp:
            r=execute("run_nfl_props_edge",sharp_rows=rows,
                      sharp_run_ids=[43148647803],now=NOW,output_dir=tmp)
            report=r["sharp_full_game_markets"]
            self.assertEqual(report["today_recent_upcoming_full_games"],2)
            self.assertTrue((Path(tmp)/"sharp_game_market_movements.jsonl").exists())
            self.assertTrue((Path(tmp)/"NBA_NFL_FULL_GAME_MARKETS_RESEARCH.json").exists())
            self.assertEqual(r["certified_positive_ev_bets"],0)
            self.assertFalse(r["champion_001_modified"])


if __name__=="__main__":
    unittest.main()
