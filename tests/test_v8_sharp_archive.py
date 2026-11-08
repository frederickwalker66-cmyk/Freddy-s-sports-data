"""V8 SharpAPI historical odds command tests; no live API or wagers."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from v8_one_command import execute, selected
from v8_sharp_archive import read_archive, summarize_sharp_archive


def quote(side, odds, capture, provider_ts):
    return {
        "record_type": "pregame_odds_observation",
        "source": "sharpapi_rest", "sportsbook": "draftkings",
        "league": "nba", "event_id": "2026NBA123",
        "home_team": "Boston Celtics", "away_team": "New York Knicks",
        "market_type": "moneyline", "selection_type": side,
        "selection": "Boston Celtics" if side == "home" else "New York Knicks",
        "is_player_prop": False, "is_main_line": True, "is_alternate_line": False,
        "line": None, "odds_american": odds,
        "odds_decimal": 1 + (odds / 100 if odds > 0 else 100 / abs(odds)),
        "event_start_time": "2026-11-09T00:00:00Z",
        "timestamp": provider_ts, "recorded_at": capture,
        "model_probability": None, "certified_prediction": False,
    }


def observations():
    return [
        quote("home", -110, "2026-11-08T10:01:00Z", "2026-11-08T10:00:00Z"),
        quote("away", -110, "2026-11-08T10:01:00Z", "2026-11-08T10:00:00Z"),
        quote("home", -125, "2026-11-08T10:08:00Z", "2026-11-08T10:07:00Z"),
        quote("away", +105, "2026-11-08T10:08:00Z", "2026-11-08T10:07:00Z"),
    ]


class SharpArchiveTests(unittest.TestCase):
    def test_command_available_on_phone(self):
        self.assertEqual(selected("run_sharp"), ())

    def test_archive_produces_movement_not_sharp_bet(self):
        report, movements = summarize_sharp_archive(
            observations(), now=datetime(2026, 11, 8, 11, tzinfo=timezone.utc),
            archive_run_ids=[123],
        )
        self.assertEqual(report["observed_line_movements"], 1)
        self.assertEqual(report["valid_sharpapi_primary_moneyline_quote_observations"], 4)
        self.assertEqual(movements[0]["direction"], "toward_home")
        self.assertFalse(report["sharp_money_or_professional_action_inferred"])
        self.assertFalse(report["quote_currently_executable"])
        self.assertFalse(report["bet_ready"])
        self.assertEqual(report["certified_predictions"], 0)
        self.assertEqual(report["archive_run_ids"], [123])

    def test_without_saved_quotes_report_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            result = execute("run_sharp", output_dir=folder)
            self.assertEqual(result["sharp_archive"]["status"], "no_eligible_saved_sharpapi_quotes")
            self.assertEqual(result["certified_positive_ev_bets"], 0)
            self.assertTrue((Path(folder) / "sharp_line_movements.jsonl").is_file())

    def test_non_sharp_source_rejected(self):
        rows = observations()
        rows[0]["source"] = "sportsgameodds_v2"
        report, movements = summarize_sharp_archive(
            rows, now=datetime(2026, 11, 8, 11, tzinfo=timezone.utc))
        self.assertEqual(report["valid_sharpapi_primary_moneyline_quote_observations"], 3)
        self.assertEqual(movements, [])

    def test_read_archive_is_bounded_and_excludes_unknown_files(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "321"
            dest.mkdir()
            with (dest / "sharpapi_dk_20261108T100000Z.jsonl").open("w") as f:
                for row in observations():
                    f.write(json.dumps(row) + "\n")
            (dest / "untrusted.jsonl").write_text("{}\n")
            rows, runs, files = read_archive(root)
            self.assertEqual(len(rows), 4)
            self.assertEqual(runs, [321])
            self.assertEqual(len(files), 1)


if __name__ == "__main__":
    unittest.main()
