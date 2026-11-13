"""Source-timed NBA boxscore feature integration: no original forecast mutation."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from historical_outcomes import normalize_game, scoreboard_url
from v8_nba_player_form_pipeline import run_player_form_research
from v8_nba_slate_best_bets import run as run_slate

NOW = datetime(2026, 11, 13, 18, 0, tzinfo=timezone.utc)
HISTORY_START = NOW - timedelta(days=4)
TIP = NOW + timedelta(hours=5)
EID = "40123401"


def historical_score():
    d = HISTORY_START.astimezone(ZoneInfo("America/New_York")).date()
    event = {
        "id": EID, "date": HISTORY_START.isoformat(),
        "season": {"type": 2},
        "status": {"type": {"state": "post", "completed": True}},
        "competitions": [{"competitors": [
            {"homeAway": "home", "team": {"id": "101", "displayName": "Home"},
             "score": 115},
            {"homeAway": "away", "team": {"id": "102", "displayName": "Away"},
             "score": 100},
        ]}],
    }
    result = normalize_game(
        event, "nba", scoreboard_url("nba", d), NOW-timedelta(minutes=10))
    assert result is not None
    return result


def nba_summary():
    def athlete(tid):
        return {
            "team": {"id": tid},
            "statistics": [{
                "names": ["MIN", "PTS", "REB", "AST", "STL", "BLK", "3PT"],
                "athletes": [{
                    "athlete": {
                        "id": "902" if tid == "101" else "903",
                        "displayName": "Historical Player " + tid},
                    "starter": True, "didNotPlay": False,
                    "stats": ["33", "24", "8", "7", "1", "1", "3-7"],
                }],
            }],
        }
    return {
        "header": {
            "id": EID,
            "competitions": [{
                "date": HISTORY_START.isoformat(),
                "status": {"type": {"completed": True}},
                "competitors": [{"team": {"id": "101"}}, {"team": {"id": "102"}}],
            }],
        },
        "boxscore": {"players": [athlete("101"), athlete("102")]},
    }


def fixture_schedule():
    return [{"espn_event_id": "4001", "league": "nba",
             "home_team_espn_id": "101", "away_team_espn_id": "102",
             "start_utc": TIP.isoformat(), "home_team": "Home",
             "away_team": "Away"}]


def make_history(tmp):
    p = Path(tmp)/"NBA_HISTORICAL_PUBLISHED_RESULTS_RESEARCH.jsonl"
    p.write_text(json.dumps(historical_score())+"\n")
    return p


class NBAPlayerFormPipelineTests(unittest.TestCase):
    def test_matches_exact_espn_teams_and_writes_nonbet_research_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            def fetch(eid):
                calls.append(eid)
                return nba_summary()
            result = run_player_form_research(
                make_history(tmp), fixture_schedule(), Path(tmp)/"out",
                coverage={"source_days_failed": 0}, fetcher=fetch,
                clock=lambda: NOW)
            self.assertEqual(calls, [EID])
            self.assertEqual(result["historical_summaries_validated"], 1)
            self.assertEqual(result["future_player_targets_staged_unverified_roster"], 2)
            self.assertEqual(result["players_with_complete_last5"], 0)
            self.assertEqual(result["players_with_complete_last10"], 0)
            self.assertFalse(result["current_team_and_active_status_verified"])
            self.assertEqual(result["certified_positive_ev_bets"], 0)
            players = json.loads((Path(tmp)/"out"/"NBA_PLAYER_LAST5_LAST10.json").read_text())
            self.assertEqual({x["historical_espn_player_id"] for x in players}, {"902", "903"})
            self.assertEqual(players[0]["player_last5"]["matured_appearances_available"], 1)
            self.assertEqual(players[0]["player_last5"]["averages_when_every_selected_game_has_stat"]["points"], 24)
            self.assertEqual(players[0]["player_last5"]["averages_when_every_selected_game_has_stat"]["threes_made"], 3)
            self.assertIsNone(players[0]["prop_probability"])
            self.assertTrue((Path(tmp)/"out"/"NBA_PLAYER_LAST5_LAST10.md").is_file())

    def test_no_history_no_api_calls_no_unverified_complete_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            def forbidden(*args):
                raise AssertionError("no ESPN request should have been made")
            report = run_player_form_research(
                Path(tmp)/"not_there.jsonl", fixture_schedule(), Path(tmp)/"out",
                coverage={"source_days_failed": 0}, fetcher=forbidden,
                clock=lambda: NOW)
            self.assertEqual(report["status"], "HOLD_NO_CAPTURED_HISTORICAL_NBA_SCORES")
            self.assertEqual(report["historical_summaries_attempted"], 0)
            incomplete = run_player_form_research(
                make_history(tmp), fixture_schedule(), Path(tmp)/"missing",
                coverage={"source_days_failed": 1}, fetcher=forbidden,
                clock=lambda: NOW)
            self.assertIn("INCOMPLETE", incomplete["status"])

    def test_mismatched_summary_identity_is_rejected_and_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            def bad(eid):
                response = nba_summary()
                response["header"]["id"] = "other"
                return response
            report = run_player_form_research(
                make_history(tmp), fixture_schedule(), Path(tmp)/"out",
                coverage={"source_days_failed": 0}, fetcher=bad,
                clock=lambda: NOW)
            self.assertEqual(report["historical_summaries_attempted"], 1)
            self.assertEqual(report["historical_summaries_validated"], 0)
            self.assertEqual(report["future_player_targets_staged_unverified_roster"], 0)
            self.assertEqual(report["certified_positive_ev_bets"], 0)

    def test_slate_run_writes_player_form_separately_without_changing_moneyline(self):
        with tempfile.TemporaryDirectory() as tmp:
            def forward(folder, **kwargs):
                folder.mkdir(parents=True)
                (folder/"NBA_HISTORICAL_PUBLISHED_RESULTS_RESEARCH.jsonl").write_text(
                    json.dumps(historical_score())+"\n")
                future_event = {
                    "id": "4001", "date": TIP.isoformat(),
                    "season": {"type": 2},
                    "status": {"type": {"state": "pre"}},
                    "competitions": [{"competitors": [
                        {"homeAway": "home", "team": {"id":"101", "displayName":"Home"}},
                        {"homeAway": "away", "team": {"id":"102", "displayName":"Away"}},
                    ]}],
                }
                day = TIP.astimezone(ZoneInfo("America/New_York")).date()
                (folder/f"nba_original_future_schedule_{day:%Y%m%d}.json").write_text(
                    json.dumps({"events":[future_event]}))
                return [], {"source_days_failed": 0, "champion_001_modified": False}
            r, fore = run_slate(Path(tmp)/"out", now=NOW,
                                forward_runner=forward,
                                player_form_fetcher=lambda eid: nba_summary(),
                                calibration={"status":"HOLD"})
            self.assertEqual(fore, [])
            self.assertEqual(r["nba_player_last5_last10_research"]
                             ["historical_summaries_validated"], 1)
            self.assertEqual(r["best_bets_ranked_by_certified_ev"], [])
            self.assertEqual(r["independently_certified_positive_ev_bets"], 0)
            self.assertTrue((Path(tmp)/"out"/"nba_player_form"/
                             "NBA_PLAYER_LAST5_LAST10.json").is_file())


if __name__ == "__main__":
    unittest.main()
