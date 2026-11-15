"""Offline regression checks for laptop engineering / phone GitHub workflow UX.

Only checks the local installation and safe routing contracts; never asserts
authenticated probabilities, live data coverage, or betting eligibility.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WindowsPhoneWorkstationTests(unittest.TestCase):
    def test_local_setup_matches_python_ci_and_does_not_touch_champion(self):
        script = (ROOT / "scripts/windows_setup.ps1").read_text(encoding="utf-8")
        self.assertIn("Python 3.12", script)
        self.assertIn("-m venv", script)
        self.assertIn("requirements-calibration.txt", script)
        self.assertIn("requirements-injury-pdf.txt", script)
        self.assertIn("-m unittest discover -s tests -v", script)
        self.assertNotIn("git push", script)
        self.assertNotIn("reset --hard", script)
        self.assertNotIn("SHARPAPI_KEY", script)

    def test_local_runner_is_fail_closed_and_never_automatically_pushes(self):
        script = (ROOT / "scripts/windows_model.ps1").read_text(encoding="utf-8")
        self.assertIn("git pull --ff-only origin main", script)
        self.assertIn("Local changes exist", script)
        self.assertIn("Scripts\\python.exe", script)
        self.assertIn("v8_one_command.py", script)
        self.assertIn("local_work", script)
        for command in ("run_nba", "run_nfl", "run_nhl", "run_all"):
            self.assertIn(command, script)
        self.assertNotIn("git push", script)
        self.assertNotIn("SHARPAPI_KEY", script)
        self.assertNotIn("actions/dispatches", script)

    def test_vscode_tasks_only_invoke_approved_windows_script(self):
        tasks = json.loads((ROOT / ".vscode/tasks.json").read_text(encoding="utf-8"))
        self.assertEqual(tasks["version"], "2.0.0")
        labels = [item["label"] for item in tasks["tasks"]]
        self.assertEqual(len(labels), len(set(labels)))
        self.assertGreaterEqual(len(labels), 9)
        for task in tasks["tasks"]:
            self.assertEqual(task["command"], "powershell.exe")
            self.assertIn("-ExecutionPolicy", task["args"])
            self.assertIn("Bypass", task["args"])
            self.assertTrue(any("windows_model.ps1" in arg or
                                "windows_setup.ps1" in arg
                                for arg in task["args"]))
            self.assertNotIn("git push", " ".join(task["args"]))

    def test_local_files_and_secrets_are_ignored(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for line in (".env", ".venv/", "local_work/", "*.key"):
            self.assertIn(line, gitignore)

    def test_dashboard_mobile_controls_use_only_authenticated_github_links(self):
        site = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        self.assertIn('id="control"', site)
        self.assertIn("actions/workflows/v8-one-command.yml", site)
        self.assertIn("actions/workflows/freddys-command-center.yml", site)
        self.assertIn("WINDOWS_PHONE_ENGINEERING.md", site)
        self.assertIn("ACCOUNT LOGIN REQUIRED", site)
        self.assertNotIn("github_pat_", site)
        self.assertNotIn("ghp_", site)
        css = (ROOT / "docs/styles.css").read_text(encoding="utf-8")
        self.assertIn("remote-control-grid", css)
        self.assertIn("auto-fit", css)

    def test_workflow_control_commands_are_actual_existing_choices(self):
        phone = (ROOT / ".github/workflows/freddys-command-center.yml").read_text(encoding="utf-8")
        sport = (ROOT / ".github/workflows/v8-one-command.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", phone)
        self.assertIn("workflow_dispatch:", sport)
        self.assertIn("full_refresh_recalibrate", phone)
        for command in ("run_nba", "run_nfl", "run_nhl", "run_all"):
            self.assertRegex(sport, r"(?m)^\s+- " + re.escape(command) + r"\s*$")
        self.assertIn("confirm_paid_api", phone)
        self.assertIn("Champion-001", (ROOT / "WINDOWS_PHONE_ENGINEERING.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
