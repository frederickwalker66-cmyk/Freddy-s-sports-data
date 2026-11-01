"""Offline fixtures; tests do not certify the current official data feeds."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from official_source_refresh import latest_nba_report, refresh, player_prop_source_gates

class OfficialSourceTests(unittest.TestCase):
    def test_player_prop_source_gates_explain_exact_injury_and_identity_gaps(self):
        sources = {
            "nba": {"status": "evidence_downloaded", "player_status_parsed": False},
            "nba_player_index": {"status": "evidence_downloaded",
                                 "provider_id_crosswalk_verified": False,
                                 "game_day_active_verified": False},
            "nfl": {"status": "not_connected", "player_status_parsed": False,
                     "game_day_actives_verified": False},
            "mlb_roster": {"status": "complete",
                           "provider_id_crosswalk_verified": False},
            "mlb_lineups": {"lineups_confirmed_as_playing": False},
        }
        out = player_prop_source_gates(sources)
        self.assertIn("injury_document_not_parsed_to_player_status",
                      out["nba"]["missing_evidence"])
        self.assertIn("odds_provider_to_official_player_id_crosswalk_unverified",
                      out["nba"]["missing_evidence"])
        self.assertIn("official_nfl_player_status_not_ingested",
                      out["nfl"]["missing_evidence"])
        self.assertIn("confirmed_game_day_lineups_unverified",
                      out["mlb"]["missing_evidence"])
        self.assertTrue(all(x["blocked"] for x in out.values()))
        self.assertTrue(all(x["player_props_cleared"] == 0 for x in out.values()))

    def test_missing_source_inventory_fails_closed(self):
        report = player_prop_source_gates({})
        self.assertIn("official_injury_document_unavailable",
                      report["nba"]["missing_evidence"])
        self.assertIn("current_player_index_unavailable",
                      report["nba"]["missing_evidence"])
        self.assertIn("active_roster_source_incomplete",
                      report["mlb"]["missing_evidence"])
        with self.assertRaises(ValueError):
            player_prop_source_gates(None)

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
            if "/commonallplayers?" in url:
                headers = ["PERSON_ID", "DISPLAY_FIRST_LAST", "TEAM_ID",
                           "TEAM_ABBREVIATION", "ROSTERSTATUS"]
                rows = [[i, f"NBA Fixture {i}", 1610612737 + (i % 30),
                         "ABC", "1"] for i in range(1, 321)]
                return {"resultSets": [{"name": "CommonAllPlayers",
                                        "headers": headers, "rowSet": rows}]}
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
            self.assertEqual(report["sources"]["nba_player_index"]["status"], "evidence_downloaded")
            self.assertEqual(report["sources"]["nba_player_index"]["player_count"], 320)
            self.assertFalse(report["sources"]["nba_player_index"]["provider_id_crosswalk_verified"])
            self.assertEqual(report["sources"]["mlb_roster"]["fetched_teams"], 25)
            self.assertFalse(report["sources"]["mlb_roster"]["provider_id_crosswalk_verified"])
            self.assertFalse(report["sources"]["mlb_lineups"]["lineups_confirmed_as_playing"])
            self.assertEqual(report["sources"]["nfl"]["status"], "not_connected")
            self.assertEqual(report["player_props_cleared"], 0)
            self.assertIn("player_prop_source_gates", report)
            self.assertTrue(report["player_prop_source_gates"]["nba"]["blocked"])
            self.assertFalse(report["champion_001_modified"])
            self.assertTrue((Path(d) / "source_refresh_report.json").exists())

    def test_missing_official_data_is_reported_not_silently_accepted(self):
        def error(*args, **kwargs):
            raise RuntimeError("blocked")
        with TemporaryDirectory() as d:
            report = refresh("2026-10-28", d, error, error)
            self.assertEqual(report["sources"]["nba"]["status"], "unavailable")
            self.assertEqual(report["sources"]["nba_player_index"]["status"], "unavailable")
            self.assertEqual(report["sources"]["mlb_roster"]["status"], "unavailable")
            self.assertEqual(report["sources"]["mlb_lineups"]["status"], "unavailable")
            self.assertEqual(report["player_props_cleared"], 0)

    def test_incomplete_nba_roster_cannot_pass(self):
        def error(*args, **kwargs):
            raise RuntimeError("offline")
        def bad_json(url):
            if "commonallplayers" in url:
                return {"resultSets": [{"name": "CommonAllPlayers",
                                        "headers": ["PERSON_ID"],
                                        "rowSet": []}]}
            raise RuntimeError("offline")
        with TemporaryDirectory() as d:
            report = refresh("2026-10-28", d, error, bad_json)
            self.assertEqual(report["sources"]["nba_player_index"]["status"], "unavailable")
            self.assertEqual(report["player_props_cleared"], 0)

if __name__ == "__main__":
    unittest.main()
