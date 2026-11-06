"""NBA-owned future-date schedule receipt fallback: offline, no API calls."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
import unittest

from challenger_eight_sport_independent_identity import run
from challenger_nba_official_pregame_schedule import parse_original
from challenger_nba_schedule_clock import NBA_SCHEDULE_URL, stats_scoreboard_url

NOW = datetime(2026, 11, 5, 18, 2, tzinfo=timezone.utc)
TOMORROW = "2026-11-06"
TIP = "2026-11-07T00:00:00Z"
GID = "0022600010"


def stats_data(day=TOMORROW, tip=TIP, league="00"):
    return json.dumps({"scoreboard": {
        "gameDate": day, "leagueId": league,
        "games": [{
            "gameId": GID, "gameStatus": 1, "gameTimeUTC": tip,
            "homeTeam": {"teamCity": "New York", "teamName": "Knicks",
                         "teamId": 1610612752},
            "awayTeam": {"teamCity": "Boston", "teamName": "Celtics",
                         "teamId": 1610612738},
        }]
    }}).encode("utf8")


def espn_record(start=TIP):
    return {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": "nba", "espn_schedule_event_id": "401001",
        "home_team": "New York Knicks", "away_team": "Boston Celtics",
        "event_start_utc": start,
        "snapshot_completed_at_utc": "2026-11-05T18:01:00Z",
        "schedule_observed_at_utc": "2026-11-05T18:00:00Z",
        "odds_observations": [], "qualified_for_challenger_backtest": False,
        "model_probability": None, "certified_prediction": False,
        "bet_ready": False, "champion_001_modified": False,
    }


def source_bundle(folder, start=TIP):
    folder.mkdir()
    (folder / "prospective_event_evidence.jsonl").write_text(
        json.dumps(espn_record(start)) + "\n")
    (folder / "eight_sport_schedule_coverage.json").write_text(json.dumps({
        "archived_games_matching_exact_original_event_fields": 1,
        "original_espn_source_responses_verified": 1,
        "certified_positive_ev_bets": 0, "champion_001_modified": False,
    }))


class FutureStatsSourceTests(unittest.TestCase):
    def test_future_date_stats_original_bytes_match_espn_identity(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            source_bundle(src)
            calls = []
            raw = stats_data()
            def fetch(url):
                calls.append(url)
                if url == NBA_SCHEDULE_URL:
                    raise HTTPError(url, 403, "Forbidden", None, None)
                self.assertEqual(url, stats_scoreboard_url(TOMORROW))
                return raw
            out = Path(tmp) / "out"
            report = run(src, out, nba_fetcher=fetch, clock=lambda: NOW)
            self.assertEqual(calls, [NBA_SCHEDULE_URL, stats_scoreboard_url(TOMORROW)])
            self.assertEqual(report["network_nba_source_failures_by_url"][NBA_SCHEDULE_URL],
                             "HTTP_403")
            self.assertEqual(report["independently_observed_nba_pregame_identity_matches_research_only"], 1)
            self.assertEqual(report["certified_positive_ev_bets"], 0)
            self.assertEqual(report["qualified_chronological_training_games"], 0)
            self.assertFalse(report["champion_001_modified"])
            self.assertEqual((out / "nba_official_stats_v3_20261106.json").read_bytes(), raw)
            rows = [json.loads(t) for t in
                    (out / "independent_game_identity.jsonl").read_text().splitlines()]
            self.assertEqual(rows[0]["nba_official_game_id"], GID)
            self.assertEqual(rows[0]["nba_original_response_sha256"],
                             hashlib.sha256(raw).hexdigest())

    def test_future_stats_rejects_wrong_game_date_stale_and_overlong_window(self):
        valid = stats_data()
        rows, checksum, kind = parse_original(valid, stats_scoreboard_url(TOMORROW), NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(kind, "nba_stats_scoreboard_v3_future_date")
        self.assertEqual(checksum, hashlib.sha256(valid).hexdigest())
        with self.assertRaisesRegex(ValueError, "stale_or_wrong_league"):
            parse_original(valid, stats_scoreboard_url("2026-11-07"), NOW)
        with self.assertRaisesRegex(ValueError, "future_scoreboard_day_outside_window"):
            parse_original(valid, stats_scoreboard_url("2026-11-13"), NOW)
        with self.assertRaisesRegex(ValueError, "source_url_not_allowed"):
            parse_original(valid, stats_scoreboard_url("2026-11-04"), NOW)
        with self.assertRaisesRegex(ValueError, "stale_or_wrong_league"):
            parse_original(stats_data(league="01"), stats_scoreboard_url(TOMORROW), NOW)

    def test_all_official_denials_remain_unverified_and_http_status_preserved(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            source_bundle(src)
            called = []
            def denied(url):
                called.append(url)
                raise HTTPError(url, 429, "Rate Limited", None, None)
            report = run(src, Path(tmp) / "out", nba_fetcher=denied,
                         clock=lambda: NOW)
            self.assertEqual(called, [NBA_SCHEDULE_URL, stats_scoreboard_url(TOMORROW)])
            self.assertEqual(set(report["network_nba_source_failures_by_url"].values()),
                             {"HTTP_429"})
            self.assertEqual(report["independently_observed_nba_pregame_identity_matches_research_only"], 0)
            self.assertEqual(report["certified_positive_ev_bets"], 0)


if __name__ == "__main__":
    unittest.main()
