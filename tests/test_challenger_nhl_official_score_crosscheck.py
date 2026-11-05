"""Synthetic-only NHL league-owned secondary scoreboard safety tests."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_nhl_official_score_crosscheck import (
    corroborate, fetch_scoreboard, main, parse_scoreboard, run,
)

NOW = datetime(2026, 11, 5, 13, 0, tzinfo=timezone.utc)
DAY = "2026-11-04"


def packet(event_id="4019001", start="2026-11-04T23:00:00Z"):
    return {
        "record_type": "challenger_original_bytes_feature_lineage_review_only",
        "league": "nhl", "event_id": event_id,
        "home_team": "New York Rangers", "away_team": "Los Angeles Kings",
        "event_start_utc": start,
        "snapshot_completed_at_utc": "2026-11-04T21:30:00Z",
        "original_bytes_match_same_run_receipt": True,
        "same_run_receipt_independently_authenticated": False,
        "published_final_only": {
            "home_score": 3, "away_score": 2, "published_result": "home",
            "published_at_observation_utc": "2026-11-05T04:30:00Z",
            "source_url": "https://site.api.espn.com/scoreboard",
        },
        "qualified_for_challenger_training": False,
        "independent_outcome_review": False,
        "market_settlement_rules_verified": False,
        "model_probability": None, "certified_prediction": False,
        "bet_ready": False, "champion_001_modified": False,
    }


def scoreboard(home_score=3, away_score=2, game_state="OFF",
               official_date=DAY, duplicate=False):
    game = {
        "id": 2026020201, "gameDate": official_date,
        "startTimeUTC": "2026-11-04T23:00:00Z",
        "gameType": 2, "gameState": game_state,
        "homeTeam": {"abbrev": "NYR", "score": home_score},
        "awayTeam": {"abbrev": "LAK", "score": away_score},
        "gameOutcome": {"lastPeriodType": "OT"},
    }
    return json.dumps({"currentDate": official_date,
                       "games": [game, deepcopy(game)] if duplicate else [game]}).encode()


class NHLOfficialScoreTests(unittest.TestCase):
    def test_official_separate_source_agreement_still_uncertified(self):
        rows, report, source = corroborate([packet()], {DAY: scoreboard()}, NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "nhl_second_source_final_score_agrees_research_only")
        self.assertEqual(rows[0]["nhl_last_period_type_research"], "OT")
        self.assertEqual(rows[0]["nhl_official_event_id"], "2026020201")
        self.assertEqual(len(rows[0]["nhl_original_source_sha256"]), 64)
        self.assertEqual(report["published_final_score_agreements"], 1)
        self.assertEqual(report["certified_positive_ev_bets"], 0)
        self.assertEqual(report["independently_verified_training_games"], 0)
        self.assertFalse(report["champion_001_modified"])

    def test_disagreement_never_qualifies_training(self):
        rows, _, _ = corroborate([packet()], {DAY: scoreboard(4, 2)}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "nhl_official_final_disagrees_with_espn")
        self.assertFalse(rows[0]["qualified_for_challenger_training"])

    def test_live_or_scheduled_scores_do_not_count_as_final(self):
        rows, report, _ = corroborate([packet()], {DAY: scoreboard(game_state="LIVE")}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "official_nhl_game_not_final_or_score_invalid")
        self.assertEqual(report["published_final_score_agreements"], 0)

    def test_duplicate_official_game_id_invalidates_whole_source_day(self):
        rows, _, _ = corroborate([packet()], {DAY: scoreboard(duplicate=True)}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "invalid_source_ValueError")
        self.assertIsNone(rows[0]["nhl_official_score"])

    def test_wrong_source_calendar_day_invalidates_source(self):
        rows, _, _ = corroborate([packet()], {DAY: scoreboard(official_date="2026-11-03")}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "invalid_source_ValueError")

    def test_malformed_json_fail_closed(self):
        rows, _, _ = corroborate([packet()], {DAY: b"{broken"}, NOW)
        self.assertTrue(rows[0]["crosscheck_status"].startswith("invalid_source_"))

    def test_missing_nhl_source_is_reported(self):
        rows, report, _ = corroborate([packet()], {}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "source_unavailable")
        self.assertEqual(report["source_dates_successfully_parsed"], [])

    def test_unqualified_source_packet_rejected_before_fetch(self):
        p = packet()
        p["qualified_for_challenger_training"] = True
        called = []
        with self.assertRaisesRegex(ValueError, "unquarantined"):
            run([p], fetcher=lambda date: called.append(date), now=NOW)
        self.assertEqual(called, [])

    def test_unknown_nhl_team_name_fails_not_fuzzy_match(self):
        p = packet()
        p["home_team"] = "New York"
        with self.assertRaisesRegex(ValueError, "crosswalk"):
            corroborate([p], {DAY: scoreboard()}, NOW)

    def test_absent_primary_final_requires_no_network_calls(self):
        p = packet()
        p["published_final_only"] = None
        calls = []
        rows, report, raw = run([p], fetcher=lambda day: calls.append(day), now=NOW)
        self.assertEqual(calls, [])
        self.assertEqual(raw, {})
        self.assertEqual(rows[0]["crosscheck_status"], "awaiting_primary_published_final")
        self.assertEqual(report["source_dates_selected"], [])

    def test_exact_recent_date_bounded_and_old_date_excluded(self):
        old = packet(event_id="4019002", start="2026-11-03T23:00:00Z")
        old["snapshot_completed_at_utc"] = "2026-11-03T21:30:00Z"
        old["published_final_only"]["published_at_observation_utc"] = "2026-11-04T04:30:00Z"
        rows, report, _ = corroborate([old, packet()], {DAY: scoreboard()}, NOW, max_days=1)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["crosscheck_status"], "outside_bounded_recent_source_dates")
        self.assertEqual(report["source_dates_selected"], [DAY])

    def test_fetch_failure_degrades_to_blocked_status(self):
        def raise_network(_day):
            raise OSError("synthetic unavailable source")
        rows, report, raw = run([packet()], fetcher=raise_network, now=NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "source_unavailable")
        self.assertEqual(report["network_source_failures_by_day"][DAY], "OSError")
        self.assertFalse(raw)

    def test_cli_empty_input_only_writes_noncertified_reports(self):
        with TemporaryDirectory() as temp:
            src = Path(temp) / "lineage.jsonl"
            src.write_text("")
            self.assertEqual(main(["--lineage", str(src),
                                   "--output-dir", str(Path(temp)/"out")]), 0)
            folder = Path(temp)/"out"
            self.assertEqual(sorted(p.name for p in folder.iterdir()),
                             ["nhl_official_score_crosscheck.jsonl",
                              "nhl_official_score_crosscheck_report.json"])
            report = json.loads((folder/"nhl_official_score_crosscheck_report.json").read_text())
            self.assertEqual(report["nhl_events_reviewed"], 0)


if __name__ == "__main__":
    unittest.main()
