"""Public ESPN hourly collector never promotes public line labels into bet certification."""
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from scripts.collect_public_scoreboards import parse_market, parse_scoreboard, collect

NOW = datetime(2026,11,17,16,0,tzinfo=timezone.utc)
DAY="2026-11-17"

def fixture(*, with_odds=True, state="pre"):
    odds=[{
        "provider":{"name":"ESPN BET"},
        "details":"CHI -4.5",
        "overUnder":224.5,
        "overOdds":-110,
        "underOdds":-110,
        "homeTeamOdds":{"moneyLine":-175,"spreadOdds":-105},
        "awayTeamOdds":{"moneyLine":145,"spreadOdds":-115},
    }] if with_odds else []
    return {"events":[{
        "id":"401234567",
        "date":"2026-11-17T23:00:00Z",
        "status":{"type":{"state":state},"period":2,"displayClock":"09:35"},
        "competitions":[{"competitors":[
            {"homeAway":"home","team":{"displayName":"Chicago Bulls"},"score":"65"},
            {"homeAway":"away","team":{"displayName":"New York Knicks"},"score":"58"},
        ],"odds":odds}],
    }]}

class PublicHourlyESPNTests(TestCase):
    def test_reports_explicit_provider_not_verified_checkout(self):
        rows=parse_scoreboard("nba",fixture(),date_et=DAY,observed_at=NOW.isoformat())
        self.assertEqual(len(rows),1)
        m=rows[0]["market_reference"]
        self.assertEqual(m["provider_name"],"ESPN BET")
        self.assertEqual(m["home_moneyline"],-175)
        self.assertEqual(m["away_moneyline"],145)
        self.assertEqual(m["spread_details"],"CHI -4.5")
        self.assertEqual(m["total"],224.5)
        self.assertIsNone(m["bookmaker_quote_timestamp_utc"])
        self.assertFalse(m["direct_checkout_verified"])
        self.assertIsNone(rows[0]["home_score"])

    def test_no_soccer_binary_moneyline(self):
        m=parse_market(fixture()["events"][0]["competitions"][0],"mls")
        self.assertIsNone(m["away_moneyline"])
        self.assertIsNone(m["home_moneyline"])

    def test_live_scores_observed_without_live_betting_certification(self):
        rows=parse_scoreboard("nba",fixture(state="in"),date_et=DAY,observed_at=NOW.isoformat())
        self.assertEqual(rows[0]["home_score"],65)
        self.assertEqual(rows[0]["away_score"],58)
        self.assertFalse(rows[0]["market_reference"]["direct_checkout_verified"])

    def test_missing_book_odds_are_none_not_zero(self):
        rows=parse_scoreboard("ncaab",fixture(with_odds=False),date_et=DAY,observed_at=NOW.isoformat())
        self.assertIsNone(rows[0]["market_reference"])
        self.assertEqual(len(rows),1)

    def test_collector_checks_exactly_eight_sports(self):
        report=collect(fetch=lambda u:fixture(),clock=lambda:NOW)
        self.assertEqual(len(report["leagues"]),8)
        self.assertTrue(all(x["status"]=="ESPN_SCOREBOARD_OBSERVED"
                            for x in report["leagues"].values()))
        self.assertFalse(report["provider_checkout_ever_verified"])
        self.assertEqual(report["certified_positive_ev"],0)

    def test_one_provider_error_does_not_suppress_other_leagues(self):
        def fetch(url):
            if "/nfl/" in url:
                raise OSError("source not available")
            return fixture()
        report=collect(fetch=fetch,clock=lambda:NOW)
        self.assertEqual(report["leagues"]["nfl"]["status"],"SOURCE_UNAVAILABLE")
        self.assertIsNone(report["leagues"]["nfl"]["game_count"])
        self.assertEqual(report["leagues"]["nba"]["game_count"],1)

    def test_wrong_day_and_invalid_team_are_excluded(self):
        d=fixture()
        d["events"][0]["date"]="2026-11-18T23:00:00Z"
        self.assertEqual(parse_scoreboard("nba",d,date_et=DAY,observed_at=NOW.isoformat()),[])
        d["events"][0]["date"]="2026-11-17T23:00:00Z"
        d["events"][0]["competitions"][0]["competitors"][0]["team"]["displayName"]=""
        self.assertEqual(parse_scoreboard("nba",d,date_et=DAY,observed_at=NOW.isoformat()),[])

    def test_untrusted_provider_does_not_show_prices(self):
        comp=fixture()["events"][0]["competitions"][0]
        comp["odds"][0]["provider"]={}
        self.assertIsNone(parse_market(comp,"nba"))
