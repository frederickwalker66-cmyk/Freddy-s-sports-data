"""Offline synthetic tests; zero external quotes, real stakes, or wagers."""
from datetime import datetime, timedelta, timezone
import unittest

from v8_arbitrage_research import scan_arbitrage, american_decimal

NOW = datetime(2026, 11, 12, 14, 0, tzinfo=timezone.utc)
Q = "2026-11-12T13:59:15Z"
R = "2026-11-12T13:59:30Z"
START = "2026-11-12T22:00:00Z"


def quote(side="home", odds=110, book="book_a", league="nba",
          market="moneyline", **overrides):
    row = {
        "source": "manual_research",
        "record_type": "pregame_odds_observation",
        "league": league, "event_id": "event-001",
        "home_team": "Home Club", "away_team": "Away Club",
        "event_start_utc": START,
        "quote_at_utc": Q, "observed_at_utc": R,
        "sportsbook": book, "market_type": market,
        "selection_type": side, "settlement_scope": "full_game_including_overtime",
        "is_main_line": True, "is_alternate_line": False,
        "is_live": False, "certified_prediction": False,
        "model_probability": None,
        "odds_american": odds, "line": None,
    }
    row.update(overrides)
    return row


class V8CrossBookArbitrageTests(unittest.TestCase):
    def test_mathematical_two_book_example_is_research_only(self):
        report = scan_arbitrage(
            [quote("home", 110, "book_a"), quote("away", 110, "book_b")],
            now=NOW, bankroll="100.00")
        self.assertEqual(report["theoretical_arbitrage_candidates"], 1)
        bet = report["candidates"][0]
        self.assertEqual(bet["inverse_decimal_odds_sum"], round(2 / 2.1, 7))
        self.assertEqual(bet["theoretical_min_profit_usd"], "5.00")
        self.assertEqual([leg["research_stake_usd"] for leg in bet["legs"]],
                         ["50.00", "50.00"])
        self.assertEqual(bet["theoretical_roi_percent"], 5)
        self.assertFalse(bet["actual_bookmaker_checkout_prices_verified"])
        self.assertFalse(bet["independent_settlement_rule_equivalence_verified"])
        self.assertEqual(report["certified_positive_ev_bets"], 0)
        self.assertEqual(report["automated_wagers"], 0)
        self.assertFalse(report["champion_001_modified"])

    def test_one_book_is_not_crossbook_arbitrage(self):
        r = scan_arbitrage([quote("home", 200), quote("away", 200)], now=NOW)
        self.assertEqual(r["theoretical_arbitrage_candidates"], 0)
        self.assertEqual(r["excluded_or_unsupported"]["single_book_no_crossbook_arbitrage"], 1)

    def test_no_opportunity_when_inverse_sum_not_below_one(self):
        r = scan_arbitrage([quote("home", -110), quote("away", -110, "book_b")],
                           now=NOW)
        self.assertEqual(r["theoretical_arbitrage_candidates"], 0)

    def test_latest_book_quote_replaces_more_favorable_old_snapshot(self):
        rows = [
            quote("home", 170, "book_a", quote_at_utc="2026-11-12T13:58:20Z",
                  observed_at_utc="2026-11-12T13:58:30Z"),
            quote("home", -110, "book_a"),
            quote("away", 105, "book_b")]
        r = scan_arbitrage(rows, now=NOW)
        self.assertEqual(r["theoretical_arbitrage_candidates"], 0)

    def test_older_quote_and_mismatched_clock_do_not_count(self):
        r = scan_arbitrage([
            quote("home", 150, "book_a",
                  observed_at_utc="2026-11-12T13:57:00Z",
                  quote_at_utc="2026-11-12T13:56:45Z"),
            quote("away", 150, "book_b"),
        ], now=NOW)
        self.assertEqual(r["theoretical_arbitrage_candidates"], 0)
        self.assertIn("stale_source_or_research_quote", r["excluded_or_unsupported"])
        r = scan_arbitrage([
            quote("home", 150, "book_a", quote_at_utc="2026-11-12T13:58:40Z",
                  observed_at_utc="2026-11-12T13:58:45Z"),
            quote("away", 150, "book_b")
        ], now=NOW)
        self.assertEqual(r["theoretical_arbitrage_candidates"], 0)

    def test_market_and_settlement_cannot_be_crossed(self):
        for field, value in (("event_id", "event-different"),
                             ("home_team", "Different Team"),
                             ("event_start_utc", "2026-11-12T23:00:00Z"),
                             ("settlement_scope", "regulation_only"),
                             ("market_type", "point_spread")):
            with self.subTest(field=field):
                r = scan_arbitrage([
                    quote("home", 150, "book_a"),
                    quote("away", 150, "book_b", **{field: value})
                ], now=NOW)
                self.assertEqual(r["theoretical_arbitrage_candidates"], 0)

    def test_exact_spread_and_total_lines(self):
        for market, h, a in (("point_spread", -3.5, 3.5),
                              ("total_points", 221.5, 221.5)):
            x, y = ("home", "away") if market == "point_spread" else ("over", "under")
            r = scan_arbitrage([
                quote(x, 105, "book_a", market=market, line=h),
                quote(y, 105, "book_b", market=market, line=a),
            ], now=NOW)
            self.assertEqual(r["theoretical_arbitrage_candidates"], 1)
            r2 = scan_arbitrage([
                quote(x, 105, "book_a", market=market, line=h),
                quote(y, 105, "book_b", market=market, line=a + 1),
            ], now=NOW)
            self.assertEqual(r2["theoretical_arbitrage_candidates"], 0)

    def test_player_identity_and_stat_line_must_match(self):
        base={"market": "player_prop", "line": 24.5,
              "player_id": "league-player-42", "prop_stat": "points"}
        home = quote("over", 120, "book_a", market="player_prop",
                     player_id=base["player_id"], prop_stat=base["prop_stat"], line=24.5)
        away = quote("under", 120, "book_b", market="player_prop",
                     player_id=base["player_id"], prop_stat=base["prop_stat"], line=24.5)
        r = scan_arbitrage([home, away], now=NOW)
        self.assertEqual(r["theoretical_arbitrage_candidates"], 1)
        for field, value in (("player_id", None), ("prop_stat", "assists"),
                             ("line", 25.5)):
            with self.subTest(field=field):
                r = scan_arbitrage([home, dict(away, **{field: value})], now=NOW)
                self.assertEqual(r["theoretical_arbitrage_candidates"], 0)

    def test_three_way_soccer_includes_draw_and_90_min_scope(self):
        kwargs={"league": "mls", "market": "three_way_90_minute",
                "settlement_scope": "regulation_90_minutes",
                "draw_included_in_outcome_partition": True}
        rows=[quote(s, 220, f"book_{s}", **kwargs)
              for s in ("home","draw","away")]
        r = scan_arbitrage(rows, now=NOW)
        self.assertEqual(r["theoretical_arbitrage_candidates"], 1)
        self.assertEqual(len(r["candidates"][0]["legs"]), 3)
        self.assertGreater(float(r["candidates"][0]["theoretical_min_profit_usd"]), 0)
        self.assertEqual(scan_arbitrage(rows[:2],now=NOW)["theoretical_arbitrage_candidates"], 0)
        self.assertEqual(scan_arbitrage(
            rows[:2]+[dict(rows[2], settlement_scope="regulation_time")],
            now=NOW)["theoretical_arbitrage_candidates"], 0)

    def test_nfl_moneyline_tie_void_cannot_be_called_arb(self):
        r=scan_arbitrage([quote("home", 150, "a", league="nfl"),
                          quote("away", 150, "b", league="nfl")], now=NOW)
        self.assertEqual(r["theoretical_arbitrage_candidates"], 0)
        self.assertEqual(r["excluded_or_unsupported"]["nfl_tie_void_risk_moneyline_not_supported"], 2)

    def test_missing_scope_alternate_or_inplay_is_rejected(self):
        for changes in ({"settlement_scope":None}, {"is_alternate_line":True},
                        {"is_live":True}, {"model_probability":0.7},
                        {"certified_prediction":True}, {"source":"unknown"},
                        {"quote_at_utc":"2026-11-12T15:00:00Z"}):
            with self.subTest(changes=changes):
                r=scan_arbitrage([quote("home",150,"a",**changes),
                                  quote("away",150,"b")],now=NOW)
                self.assertEqual(r["theoretical_arbitrage_candidates"],0)

    def test_invalid_input_rejected_and_no_model_probabilities(self):
        self.assertEqual(str(american_decimal(-110)),str(Decimal("1")+Decimal(100)/Decimal(110)))
        for invalid in (0,99,True,1000000):
            with self.assertRaises(ValueError):
                american_decimal(invalid)
        for amount in ("0.00","10000.01","50.005","nan"):
            with self.assertRaises(ValueError):
                scan_arbitrage([],now=NOW,bankroll=amount)
        with self.assertRaises(ValueError):
            scan_arbitrage([],now=datetime(2026,11,12,14))


from decimal import Decimal
if __name__ == "__main__":
    unittest.main()
