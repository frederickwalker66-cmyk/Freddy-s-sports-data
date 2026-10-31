"""Offline NBA CDN fallback tests. No bets or certified forecasts."""
import json
import unittest
from datetime import datetime, timezone
from urllib.error import HTTPError

from challenger_nba_schedule_clock import (
    NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL, fetch_official_schedule,
    load_official_payload, official_nba_events, compare_clocks, stats_scoreboard_url,
)
from test_challenger_nba_schedule_clock import unaccepted, nba_feed, nba_game, NOW


def board(day="2026-10-29", game_start="2026-10-30T00:00:00Z",
          home="Hawks", status=1):
    return {"scoreboard": {"gameDate": day, "leagueId": "00",
                           "games": [{"gameId": "0022600001",
                                      "gameStatus": status,
                                      "gameTimeUTC": game_start,
                                      "homeTeam": {"teamCity": "Atlanta", "teamName": home},
                                      "awayTeam": {"teamCity": "Cleveland",
                                                   "teamName": "Cavaliers"}}]}}


class MockResponse:
    def __init__(self, raw):
        self.raw = raw
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return self.raw[:size]


class CdnFallbackTests(unittest.TestCase):
    def test_browser_compatible_headers_are_sent(self):
        captured = []
        def fake_opener(req, timeout):
            captured.append((req.full_url, dict(req.headers), timeout))
            return MockResponse(json.dumps(nba_feed(nba_game())).encode())
        payload = fetch_official_schedule(opener=fake_opener)
        self.assertIn("leagueSchedule", payload)
        url, headers, timeout = captured[0]
        self.assertEqual(url, NBA_SCHEDULE_URL)
        self.assertIn("Mozilla", headers["User-agent"])
        self.assertEqual(headers["Origin"], "https://www.nba.com")
        self.assertEqual(headers["Referer"], "https://www.nba.com/")
        self.assertEqual(timeout, 18)

    def test_falls_back_to_second_nba_operated_endpoint_only(self):
        calls = []
        def fake(url):
            calls.append(url)
            if url == NBA_SCHEDULE_URL:
                raise HTTPError(url, 403, "Denied", {}, None)
            return board()
        data, selected, errors = load_official_payload(fake)
        self.assertEqual(calls, [NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL])
        self.assertEqual(selected, NBA_TODAY_SCOREBOARD_URL)
        self.assertEqual(errors[NBA_SCHEDULE_URL], "HTTPError")
        report = compare_clocks(unaccepted(), data, NOW, source_url=selected,
                                source_errors=errors)
        self.assertEqual(report["classification_counts"],
                         {"nba_clock_agrees_with_espn": 1})
        self.assertEqual(report["official_nba_source_url"], selected)
        self.assertEqual(report["nba_near_time_events_checked"], 1)
        self.assertFalse(report["cases"][0]["automatically_accepted_as_schedule_match"])
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_date_scoped_nba_stats_fallback_after_two_access_denials(self):
        date_et = "2026-10-29"
        third = stats_scoreboard_url(date_et)
        calls = []
        def fake(url):
            calls.append(url)
            if url != third:
                raise HTTPError(url, 403, "Denied", {}, None)
            return board(day=date_et)
        data, selected, errors = load_official_payload(fake, date_et=date_et)
        self.assertEqual(calls, [NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL, third])
        self.assertEqual(selected, third)
        self.assertEqual(len(errors), 2)
        report = compare_clocks(unaccepted(), data, NOW, source_url=selected,
                                source_errors=errors)
        self.assertEqual(report["classification_counts"],
                         {"nba_clock_agrees_with_espn": 1})
        self.assertEqual(report["bet_ready_selections"], 0)
        self.assertEqual(report["near_time_mismatches_promoted"], 0)

    def test_all_three_official_sources_denied_stays_unavailable(self):
        def failing(url):
            raise HTTPError(url, 403, "Denied", {}, None)
        data, selected, errors = load_official_payload(failing, date_et="2026-10-29")
        self.assertIsNone(data)
        self.assertIsNone(selected)
        self.assertEqual(len(errors), 3)
        report = compare_clocks(unaccepted(), data, NOW, source_errors=errors)
        self.assertEqual(report["classification_counts"],
                         {"official_schedule_unavailable": 1})
        self.assertEqual(report["certified_champion_001_predictions"], 0)

    def test_rejects_off_domain_and_noncanonical_stats_url(self):
        with self.assertRaisesRegex(ValueError, "invalid official NBA game day"):
            stats_scoreboard_url("not-a-date")
        with self.assertRaisesRegex(ValueError, "untrusted NBA schedule URL"):
            fetch_official_schedule("https://stats.nba.com/stats/scoreboardv3?GameDate=2026-10-29&LeagueID=10")
        with self.assertRaisesRegex(ValueError, "untrusted NBA schedule URL"):
            fetch_official_schedule("https://stats.nba.com/stats/scoreboardv3?GameDate=2026-10-29&LeagueID=00&extra=1")

    def test_old_todays_scoreboard_never_used_to_match_future_game(self):
        report = compare_clocks(
            unaccepted(), board(day="2026-10-28"), NOW,
            source_url=NBA_TODAY_SCOREBOARD_URL)
        self.assertEqual(report["classification_counts"],
                         {"official_scoreboard_date_mismatch": 1})
        self.assertNotIn("official_nba_game_id", report["cases"][0])
        self.assertEqual(report["certified_champion_001_predictions"], 0)

    def test_wrong_league_scoreboard_rejected(self):
        malformed = board()
        malformed["scoreboard"]["leagueId"] = "10"
        with self.assertRaisesRegex(ValueError, "scoreboard identity"):
            official_nba_events(malformed)

    def test_bad_date_scoreboard_rejected(self):
        with self.assertRaisesRegex(ValueError, "game date"):
            official_nba_events(board(day="not a date"))

    def test_when_both_sources_fail_no_approvals(self):
        def failing(url):
            raise TimeoutError(url)
        data, selected, errors = load_official_payload(failing)
        self.assertIsNone(data)
        self.assertIsNone(selected)
        self.assertEqual(len(errors), 2)
        report = compare_clocks(unaccepted(), data, NOW,
                                source_error="both_nba_sources_unavailable",
                                source_errors=errors)
        self.assertEqual(report["classification_counts"],
                         {"official_schedule_unavailable": 1})
        self.assertEqual(report["independently_verified_sportsbook_prices"], 0)
        self.assertEqual(report["automated_bets_placed"], 0)

    def test_malformed_primary_falls_back_without_promoting(self):
        def fake(url):
            return ({"malformed": True} if url == NBA_SCHEDULE_URL else board())
        data, selected, errors = load_official_payload(fake)
        self.assertEqual(selected, NBA_TODAY_SCOREBOARD_URL)
        self.assertEqual(errors[NBA_SCHEDULE_URL], "ValueError")
        self.assertEqual(len(official_nba_events(data)), 1)

    def test_in_play_scoreboard_not_treated_as_pregame(self):
        data = board(status=2)
        self.assertEqual(official_nba_events(data), [])
        report = compare_clocks(unaccepted(), data, NOW,
                                source_url=NBA_TODAY_SCOREBOARD_URL)
        self.assertEqual(report["classification_counts"],
                         {"no_unique_official_nba_schedule_match": 1})
        self.assertEqual(report["near_time_mismatches_promoted"], 0)

    def test_untrusted_cdn_url_blocked(self):
        with self.assertRaisesRegex(ValueError, "untrusted NBA schedule URL"):
            fetch_official_schedule("https://example.net/schedule.json")

if __name__ == "__main__":
    unittest.main()
