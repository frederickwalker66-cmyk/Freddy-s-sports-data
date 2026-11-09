"""Synthetic safety/regression tests for retrospective NBA Elo (never certified)."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from historical_outcomes import normalize_game, scoreboard_url
from v8_nba_oos_research import benchmark, save


NOW = datetime(2026, 3, 1, tzinfo=timezone.utc)


def game(event_id, start, hscore, ascore):
    stamp = start.isoformat().replace("+00:00", "Z")
    day = start.astimezone(ZoneInfo("America/New_York")).date()
    match = {
        "id": str(event_id), "date": stamp, "season": {"type": 2},
        "status": {"type": {"state": "post", "completed": True}},
        "competitions": [{"competitors": [
            {"homeAway": "home", "team": {
                "id": str(event_id % 15 + 1),
                "displayName": "Synthetic Home Team"}, "score": hscore},
            {"homeAway": "away", "team": {
                "id": str((event_id + 7) % 15 + 16),
                "displayName": "Synthetic Away Team"}, "score": ascore},
        ]}],
    }
    return normalize_game(match, "nba", scoreboard_url("nba", day), NOW)


def report(n, days=35, failed=0):
    return {
        "stage": "challenger_historical_backfill_research_only",
        "league": "nba", "days_requested": days,
        "window_start_et": "2026-01-12", "window_end_et": "2026-02-15",
        "scoreboard_days_successful": days - failed,
        "scoreboard_days_failed": failed,
        "published_completed_game_results": n,
        "qualified_training_examples": 0,
        "officially_adjudicated_results": 0,
        "independent_result_adjudication_verified": False,
        "historical_pregame_feature_timestamps_verified": False,
        "bookmaker_market_settlement_verified": False,
        "champion_001_modified": False,
    }


def history(num):
    # All event dates fit inside one genuine-style bounded 35-day source window.
    base = datetime(2026, 1, 12, 23, tzinfo=timezone.utc)
    return [
        game(40000000 + i, base + timedelta(days=i // 4, minutes=i % 4),
             110 if i % 3 else 99, 99 if i % 3 else 110)
        for i in range(num)
    ]


class NbaOosResearchTests(unittest.TestCase):
    def test_120_completed_games_yield_retrospective_metrics_not_certification(self):
        rows = history(120)
        diag, ledger = benchmark(rows, report(120), now=NOW)
        self.assertEqual(diag["status"], "RETROSPECTIVE_DIAGNOSTIC_AVAILABLE_UNVERIFIED")
        self.assertEqual(diag["warmup_games"], 80)
        self.assertEqual(diag["retrospective_evaluation_games"], 40)
        self.assertIsInstance(diag["brier_score_retrospective_research_only"], float)
        self.assertIsInstance(diag["log_loss_retrospective_research_only"], float)
        self.assertIsInstance(diag["neutral_50_50_brier_comparison_not_bookmaker"], float)
        self.assertEqual(len(ledger), 120)
        self.assertTrue(all(x["historical_forecast_actually_recorded_before_tipoff"] is False
                            and x["qualified_as_true_pregame_shadow"] is False
                            and x["certified_prediction"] is False for x in ledger))
        self.assertEqual(diag["certified_positive_ev_bets"], 0)
        with tempfile.TemporaryDirectory() as folder:
            save(diag, ledger, folder)
            self.assertEqual(len((Path(folder) / "NBA_ELO_RETROSPECTIVE_LEDGER.jsonl").read_text().splitlines()), 120)

    def test_small_sample_blocks_metrics(self):
        rows = history(12)
        report_obj, ledger = benchmark(rows, report(12), now=NOW)
        self.assertEqual(report_obj["status"], "HOLD_INSUFFICIENT_RESEARCH_HISTORY")
        self.assertIsNone(report_obj["brier_score_retrospective_research_only"])
        self.assertEqual(report_obj["certified_v8_predictions"], 0)
        self.assertEqual(len(ledger), 12)

    def test_non_NBA_and_promoted_flags_rejected(self):
        rows = history(2)
        bad = report(2)
        bad["qualified_training_examples"] = 2
        with self.assertRaisesRegex(ValueError, "unsupported_or_promoted"):
            benchmark(rows, bad, now=NOW)
        rows[0]["league"] = "nfl"
        with self.assertRaisesRegex(ValueError, "non_NBA_result_contamination"):
            benchmark(rows, report(2), now=NOW)

    def test_bad_event_url_and_duplicate_event_quarantined(self):
        rows = history(2)
        rows[0]["source_url"] = rows[0]["source_url"].replace("20260112", "20260113")
        with self.assertRaises(ValueError):
            benchmark(rows, report(2), now=NOW)
        rows = history(2)
        rows.append(dict(rows[0]))
        with self.assertRaisesRegex(ValueError, "duplicate_NBA_event"):
            benchmark(rows, report(3), now=NOW)

    def test_missing_source_days_are_reported_not_imputed(self):
        rows = history(4)
        data, ledger = benchmark(rows, report(4, failed=1), now=NOW)
        self.assertEqual(data["source_days_failed"], 1)
        self.assertFalse(data["whole_requested_window_fetched"])
        self.assertEqual(data["original_actual_pregame_model_forecast_receipts"], 0)

    def test_no_data_returns_blocked_without_fake_games(self):
        data, ledger = benchmark([], report(0, failed=35), now=NOW)
        self.assertEqual(data["published_completed_games"], 0)
        self.assertEqual(data["status"], "HOLD_INSUFFICIENT_RESEARCH_HISTORY")
        self.assertEqual(ledger, [])
        self.assertEqual(data["certified_champion_001_predictions"], 0)


if __name__ == "__main__":
    unittest.main()
