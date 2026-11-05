"""Research-only multi-sport settlement review; no automatic calibration promotion."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_multisport_native_capture import capture_multisport
from challenger_multisport_calibration_review import evaluate_unqualified, main
from test_challenger_multisport_native_capture import NOW, START, snapshot, candidate, model

FINAL_ASOF = START + timedelta(hours=6)


def linked(league, event_id="401232344", result="home"):
    return {
        "league": league, "espn_event_id": event_id,
        "status": "linked_to_espn_published_final_only",
        "snapshot_completed_at_utc": (NOW - timedelta(minutes=10)).isoformat(),
        "event_start_utc": START.isoformat(),
        "home_team": "Home", "away_team": "Away",
        "published_outcome": {
            "result": result,
            "source_url": "https://site.api.espn.com/scoreboard",
            "published_retrieved_at_utc": (START + timedelta(hours=4)).isoformat(),
        },
        "independent_league_outcome_verified": False,
        "qualified_for_challenger_backtest": False,
        "model_prediction_at_capture": None, "bet_ready": False,
        "champion_001_modified": False,
    }


class MultisportReviewTests(unittest.TestCase):
    def _scored(self, league):
        rows, report = capture_multisport([snapshot(league)], [candidate(league)],
                                           {league: model(league)}, now=NOW)
        self.assertEqual(report["unique_games_scored_uncertified"], 1)
        return rows

    def test_binary_published_final_creates_only_review_queue(self):
        rows = self._scored("nfl")
        queue, report = evaluate_unqualified(rows, [linked("nfl")], FINAL_ASOF)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["calibration_label"], None)
        self.assertFalse(queue[0]["qualified_for_calibration"])
        self.assertFalse(queue[0]["independent_outcome_verified"])
        self.assertFalse(report["training_dataset_emitted"])
        self.assertEqual(report["certified_positive_ev_bets"], 0)

    def test_soccer_three_way_exposes_draw_and_never_grades_regulation(self):
        rows = self._scored("mls")
        queue, report = evaluate_unqualified(rows, [linked("mls", result="draw")], FINAL_ASOF)
        self.assertEqual(len(queue), 1)
        self.assertEqual(set(queue[0]["native_research_probabilities_claimed"]),
                         {"home", "draw", "away"})
        self.assertFalse(queue[0]["soccer_regulation_90_min_outcome_adjudicated"])
        self.assertIsNone(queue[0]["calibration_label"])
        self.assertEqual(report["soccer_90_minute_outcomes_adjudicated"], 0)

    def test_missing_draw_side_blocks_soccer(self):
        rows = [r for r in self._scored("uefa_champions_league")
                if r["selection_key"] != "draw"]
        queue, report = evaluate_unqualified(rows, [linked("uefa_champions_league")], FINAL_ASOF)
        self.assertFalse(queue)
        self.assertEqual(report["failed_joins"]["missing_or_duplicate_model_outcome_sides"], 1)

    def test_duplicate_and_mismatched_probabilities_block(self):
        rows = self._scored("ncaab")
        r, report = evaluate_unqualified(rows + [rows[0]], [linked("ncaab")], FINAL_ASOF)
        self.assertFalse(r)
        self.assertEqual(report["failed_joins"]["missing_or_duplicate_model_outcome_sides"], 1)
        rows = deepcopy(self._scored("ncaab"))
        rows[0]["research_probability"] = .9
        r, report = evaluate_unqualified(rows, [linked("ncaab")], FINAL_ASOF)
        self.assertFalse(r)
        self.assertEqual(report["failed_joins"]["invalid_multioutcome_probability_vector"], 1)

    def test_wrong_team_and_unverified_final_block(self):
        rows = self._scored("mlb")
        bad = linked("mlb")
        bad["home_team"] = "Wrong"
        queue, _ = evaluate_unqualified(rows, [bad], FINAL_ASOF)
        self.assertFalse(queue)
        bad = linked("mlb")
        bad["independent_league_outcome_verified"] = True
        queue, _ = evaluate_unqualified(rows, [bad], FINAL_ASOF)
        self.assertFalse(queue)

    def test_stale_forecasts_do_not_create_calibrated_accuracy(self):
        rows = self._scored("nhl")
        for row in rows:
            row["scored_at_utc"] = (START + timedelta(seconds=2)).isoformat()
        queue, report = evaluate_unqualified(rows, [linked("nhl")], FINAL_ASOF)
        self.assertFalse(queue)
        self.assertEqual(report["independently_verified_calibration_examples"], 0)

    def test_missing_archive_report_all_sports(self):
        with TemporaryDirectory() as folder:
            out = Path(folder) / "out"
            self.assertEqual(main(["--archive-root", str(Path(folder)/"empty"),
                                   "--output-dir", str(out)]), 0)
            report = json.loads((out/"multisport_review_report.json").read_text())
            self.assertEqual(report["unqualified_matched_games"], 0)
            self.assertEqual(len(report["all_leagues"]), 8)
            self.assertFalse((out/"challenger_oos_probabilities.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
