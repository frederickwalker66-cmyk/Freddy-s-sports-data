"""Synthetic SportsGameOdds fixtures. No external calls or live betting."""
import unittest
from datetime import datetime, timezone
from challenger_audit import audit
from sportsgameodds_collector import normalize_event, price, line_number

NOW = datetime(2026, 10, 28, 20, tzinfo=timezone.utc)

def fixture():
    def market(kind, side, entity, odds="-110", value=None):
        book = {"odds": odds, "available": True, "lastUpdatedAt": "2026-10-28T19:59:15Z"}
        if kind == "ou":
            book["overUnder"] = value
        if kind == "sp":
            book["spread"] = value
        return {"periodID": "game", "betTypeID": kind, "statID": "points",
                "statEntityID": entity, "sideID": side,
                "playerID": entity if entity == "PLAYER_TEST" else None,
                "byBookmaker": {"draftkings": book}}
    return {"eventID": "E1", "leagueID": "NBA",
            "teams": {"home": {"names": {"long": "Home"}},
                      "away": {"names": {"long": "Away"}}},
            "status": {"started": False, "startsAt": "2026-10-28T23:00:00Z"},
            "players": {"PLAYER_TEST": {"name": "Sample Player"}},
            "odds": {"a": market("ml", "home", "home", "-150"),
                     "b": market("sp", "away", "away", "-110", "+3.5"),
                     "c": market("ou", "over", "all", "-108", "220.5"),
                     "d": market("ou", "over", "PLAYER_TEST", "+115", "19.5")}}

class CollectorTests(unittest.TestCase):
    def test_four_families_and_quarantine(self):
        rows, errors = normalize_event(fixture(), NOW)
        self.assertEqual(len(rows), 4)
        self.assertFalse(errors)
        self.assertEqual(set(r["market_type"] for r in rows),
                         {"moneyline", "point_spread", "total_points", "player_points"})
        self.assertTrue(all(r["model_probability"] is None for r in rows))
        self.assertTrue(all(r["is_main_line"] is False for r in rows))
        staged, quarantine, report = audit(rows, {})
        self.assertEqual((len(staged), len(quarantine)), (0, 4))
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_stale_quote(self):
        e = fixture()
        e["odds"]["a"]["byBookmaker"]["draftkings"]["lastUpdatedAt"] = "2026-10-28T19:43:00Z"
        rows, reasons = normalize_event(e, NOW)
        self.assertEqual(len(rows), 3)
        self.assertEqual(reasons["stale_missing_or_future_quote_time"], 1)

    def test_live_event(self):
        e = fixture()
        e["status"]["started"] = True
        self.assertEqual(normalize_event(e, NOW)[0], [])

    def test_missing_bookmaker(self):
        e = fixture()
        e["odds"]["a"]["byBookmaker"] = {"fanduel": {"odds": "-110"}}
        self.assertEqual(len(normalize_event(e, NOW)[0]), 3)

    def test_missing_player(self):
        e = fixture()
        e["players"] = {}
        self.assertEqual(len(normalize_event(e, NOW)[0]), 3)

    def test_bad_price_and_line(self):
        self.assertIsNone(price("-99"))
        self.assertIsNone(price(True))
        self.assertEqual(price("+100"), 100)
        self.assertIsNone(line_number("NaN"))
        e = fixture()
        e["odds"]["b"]["byBookmaker"]["draftkings"]["spread"] = None
        self.assertEqual(len(normalize_event(e, NOW)[0]), 3)

    def test_mlb_run_line(self):
        e = fixture()
        e["leagueID"] = "MLB"
        rows, _ = normalize_event(e, NOW)
        self.assertIn("run_line", [r["market_type"] for r in rows])

    def test_multi_sport_league_support_and_proper_spread_names(self):
        cases = {
            "NBA": ("basketball", "point_spread"),
            "NCAAB": ("basketball", "point_spread"),
            "WNBA": ("basketball", "point_spread"),
            "NFL": ("football", "point_spread"),
            "NCAAF": ("football", "point_spread"),
            "MLB": ("baseball", "run_line"),
            "NHL": ("hockey", "puck_line"),
            "MLS": ("soccer", "goal_spread"),
            "UEFA_CHAMPIONS_LEAGUE": ("soccer", "goal_spread"),
        }
        for league, (sport, spread_market) in cases.items():
            with self.subTest(league=league):
                event = fixture()
                event["leagueID"] = league
                rows, errors = normalize_event(event, NOW)
                self.assertFalse(errors)
                self.assertEqual(len(rows), 4)
                self.assertEqual(rows[0]["sport"], sport)
                self.assertEqual(rows[1]["market_type"], spread_market)
                self.assertTrue(all(row["model_probability"] is None for row in rows))

    def test_ten_minute_quote_is_archived_but_not_bet_ready(self):
        event = fixture()
        event["odds"]["a"]["byBookmaker"]["draftkings"]["lastUpdatedAt"] = "2026-10-28T19:50:00Z"
        rows, _ = normalize_event(event, NOW)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["source_age_seconds"], 600)
        staged, quarantined, report = audit(rows, {})
        self.assertEqual((len(staged), len(quarantined)), (0, 4))
        self.assertIn("quote_too_old_or_future", quarantined[0]["reasons"])
        self.assertEqual(report["bet_ready_selections"], 0)
