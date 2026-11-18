"""Offline checks that V9 staff meetings can safely wake the existing V8 source watchdog."""
from pathlib import Path
import unittest

from v8_source_cadence_watchdog import TARGET, MAX_AGE_MINUTES, MAX_RECOVERY_ATTEMPTS_PER_DAY

ROOT=Path(__file__).resolve().parents[1]
WATCHDOG=ROOT/".github/workflows/v8-source-cadence-watchdog.yml"
MEETING=ROOT/".github/workflows/v9-pregame-meeting.yml"

class V9HeartbeatRecoveryTests(unittest.TestCase):
    def test_wakeup_is_wired_to_completed_pregame_meeting(self):
        text=WATCHDOG.read_text(encoding="utf-8")
        trigger=text.split("  workflow_run:",1)[1].split("  push:",1)[0]
        self.assertIn("Freddy's Picks AI V9 — Six Staff Pregame Meeting (read-only)",trigger)
        self.assertIn("types: [completed]",trigger)
        self.assertIn("branches: [main]",trigger)
        # Prevent an unbounded source->watchdog->source recursion.
        self.assertNotIn(TARGET,trigger)
        self.assertNotIn("V8 public-source schedule recovery (research only)",trigger)
        self.assertIn("github.event.workflow_run.conclusion == 'success'",text)

    def test_watchdog_only_requests_bounded_free_source(self):
        text=WATCHDOG.read_text(encoding="utf-8")
        self.assertIn("cron: '17 * * * *'",text)
        self.assertIn("cron: '41 * * * *'",text)
        self.assertIn("v8_source_cadence_watchdog.py",text)
        self.assertIn("--execute-recovery",text)
        self.assertEqual(TARGET,"challenger-eight-sport-source-preflight.yml")
        self.assertEqual(MAX_AGE_MINUTES,150)
        self.assertEqual(MAX_RECOVERY_ATTEMPTS_PER_DAY,4)
        self.assertNotIn("collect-sharpapi.yml",text)
        self.assertIn("actions: write",text)

    def test_meeting_uses_source_archives_and_stays_read_only(self):
        text=MEETING.read_text(encoding="utf-8")
        self.assertIn("v9_pregame_staff_meeting.py",text)
        self.assertIn("--lookahead-minutes 720",text)
        self.assertIn("permissions:\n  contents: read\n  actions: read",text)
        self.assertNotIn("--execute-recovery",text)
        self.assertNotIn("actions: write",text)

if __name__=="__main__":
    unittest.main()
