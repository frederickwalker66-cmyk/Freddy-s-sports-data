"""Offline fixtures; tests do not certify the current official data feeds."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from official_source_refresh import latest_nba_report, refresh

class OfficialSourceTests(unittest.TestCase):
    def test_nba_selects_latest_same_day_injury_pdf(self):
        markup = """
          <a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-10-28_03_00PM.pdf">older</a>
          <a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-10-28_05_15PM.pdf">new</a>
          <a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-10-27_11_45PM.pdf">prior</a>
        """
        self.assertTrue(latest_nba_report(markup, "2026-10-28").endswith("_05_15PM.pdf"))
        self.assertIsNone(latest_nba_report(markup, "2026-10-29"))

    def test_sources_are_evidence_only_and_no_props_clear(self):
        def fake_fetch(url, max_bytes=5000000, timeout=20):
            if "official.nba.com" in url:
                return b'<a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-10-28_05_00PM.pdf">current</a>'
            if "cms.nba.com" in url:
                return b"%PDF-1.7 fictional fixture"
            raise ValueError("unknown fixture URL")
        def fake_json(url):
            if "/teams?" in url:
                return {"teams": [{"id": i, "name": f"Team {i}"} for i in range(100, 125)]}
            if "/roster?" in url:
                return {"roster": [{"person": {"id": 500, "fullName": "Example Player"},
                                    "status": {"code": "A", "description": "Active"}}]}
            if "/schedule?" in url:
                return {"dates": [{"games": [{"gamePk": 777, "status": {"abstractGameState": "Preview"}}]}]}
            if "/game/777/boxscore" in url:
                return {"teams": {"home": {"team": {"id": 100}, "battingOrder": []},
                                  "away": {"team": {"id": 101}, "battingOrder": []}}}
            raise ValueError("unknown JSON fixture")
        with TemporaryDirectory() as d:
            report = refresh("2026-10-28", d, fake_fetch, fake_json)
            self.assertEqual(report["sources"]["nba"]["status"], "evidence_downloaded")
            self.assertFalse(report["sources"]["nba"]["player_status_parsed"])
            self.assertEqual(report["sources"]["mlb_roster"]["fetched_teams"], 25)
            self.assertFalse(report["sources"]["mlb_roster"]["provider_id_crosswalk_verified"])
            self.assertFalse(report["sources"]["mlb_lineups"]["lineups_confirmed_as_playing"])
            self.assertEqual(report["sources"]["nfl"]["status"], "not_connected")
            self.assertEqual(report["player_props_cleared"], 0)
            self.assertFalse(report["champion_001_modified"])
            self.assertTrue((Path(d) / "source_refresh_report.json").exists())

    def test_missing_official_data_is_reported_not_silently_accepted(self):
        def error(*args, **kwargs):
            raise RuntimeError("blocked")
        with TemporaryDirectory() as d:
            report = refresh("2026-10-28", d, error, error)
            self.assertEqual(report["sources"]["nba"]["status"], "unavailable")
            self.assertEqual(report["sources"]["mlb_roster"]["status"], "unavailable")
            self.assertEqual(report["sources"]["mlb_lineups"]["status"], "unavailable")
            self.assertEqual(report["player_props_cleared"], 0)

if __name__ == "__main__":
    unittest.main()
