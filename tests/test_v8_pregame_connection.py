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
