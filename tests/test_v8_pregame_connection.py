import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import v8_one_command


class PregameV8ConnectionTests(unittest.TestCase):
    def test_run_nba_cli_writes_five_gate_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot = root / "snapshot.json"
            snapshot.write_text(json.dumps({"sport": "nba", "selections": []}), encoding="utf-8")
            report = {"requested_leagues": ["nba"], "research_edge_candidates": []}
            with patch.object(v8_one_command, "run_full_stack", return_value=report):
                v8_one_command.main(["--command", "run_nba", "--pregame-input", str(snapshot),
                                     "--output-dir", str(root / "out")])
            data = json.loads((root / "out" / "PREGAME_FIVE_GATE_REPORT.json").read_text())
            self.assertEqual(data["counts"]["TAKE"], 0)
            self.assertEqual(report["pregame_five_gate"]["status"],
                             "HOLD_UNTIL_TRUSTED_FEEDS_AND_MODEL_RECEIPTS")

    def test_run_nba_without_snapshot_emits_fresh_hold_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            out = root / "out"
            out.mkdir()
            (out / "PREGAME_FIVE_GATE_REPORT.json").write_text('{"stale":true}')
            report = {"requested_leagues": ["nba"], "research_edge_candidates": []}
            with patch.object(v8_one_command, "run_full_stack", return_value=report):
                v8_one_command.main(["--command", "run_nba", "--output-dir", str(out)])
            pregame = json.loads((out / "PREGAME_FIVE_GATE_REPORT.json").read_text())
            main = json.loads((out / "ONE_COMMAND_REPORT.json").read_text())
            self.assertNotIn("stale", pregame)
            self.assertEqual(pregame["counts"]["TAKE"], 0)
            self.assertEqual(main["pregame_five_gate"], pregame)
