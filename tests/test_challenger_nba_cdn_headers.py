"""NBA public CDN request compatibility and exact access-denial diagnostics."""
from datetime import datetime, timezone
from urllib.error import HTTPError
from unittest.mock import patch
import unittest

import challenger_nba_pregame_roster_identity as mod

NOW = datetime(2026, 11, 5, 22, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, data):
        self.data=data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit):
        return self.data[:limit]


def injury_source(folder, events, now):
    return ([{
        "record_type": "nba_official_pdf_player_status_extracted_for_review_only",
        "game_date_et": "2026-11-05", "matchup": "BOS@NYK",
        "team_name": "Boston Celtics", "nba_team_abbreviation": "BOS",
        "source_player_name_display": "Jayson Tatum",
        "source_injury_designation": "Out",
        "nba_person_id": None, "espn_athlete_id": None,
        "player_current_game_active_status_verified": False,
        "roster_player_id_crosswalk_verified": False,
        "qualified_for_prop_training": False,
        "market_eligibility_verified": False,
        "certified_prediction": False, "bet_ready": False,
        "champion_001_modified": False,
    }], [], {
        "stage": "challenger_nba_official_pregame_pdf_player_rows_review_only",
        "original_pdf_source_status": "captured_original_index_and_pdf",
        "pdf_extraction_error": None, "original_pdf_sha256": "a"*64,
        "actual_original_pdf_observed_utc": "2026-11-05T21:45:00Z",
        "player_rows_extracted_from_official_pdf": 1,
        "teams_report_not_yet_submitted": 0,
        "active_player_roster_verified": 0,
        "individual_player_id_crosswalk_verified": 0,
        "qualified_prop_training_observations": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "certified_positive_ev_bets": 0, "bet_ready_selections": 0,
        "champion_001_modified": False,
    })


class NBACompatHeaderTests(unittest.TestCase):
    def test_two_approved_nba_schedule_urls_use_public_browser_compatible_headers(self):
        for url in (mod.NBA_SCHEDULE_URL, mod.NBA_TODAY_SCOREBOARD_URL):
            with self.subTest(url=url):
                seen=[]
                def open_fake(req, timeout):
                    seen.append((req,timeout))
                    return FakeResponse(b'{"source":"test original bytes"}')
                with patch.object(mod, "urlopen", side_effect=open_fake):
                    raw=mod.fetch_source(url,mod.MAX_SCHEDULE_BYTES)
                self.assertEqual(raw,b'{"source":"test original bytes"}')
                self.assertEqual(len(seen),1)
                request, timeout=seen[0]
                self.assertEqual(request.full_url,url)
                self.assertEqual(timeout,18)
                self.assertIn("Mozilla/5.0",request.get_header("User-agent"))
                self.assertIn("application/json",request.get_header("Accept"))
                self.assertEqual(request.get_header("Accept-language"),"en-US,en;q=0.9")
                self.assertEqual(request.get_header("Origin"),"https://www.nba.com")
                self.assertEqual(request.get_header("Referer"),"https://www.nba.com/")

    def test_unapproved_nba_schedule_url_never_opens_network(self):
        with patch.object(mod, "urlopen") as opened:
            with self.assertRaises(ValueError):
                mod.fetch_source("https://attacker.example/scoreboard.json",
                                 mod.MAX_SCHEDULE_BYTES)
            opened.assert_not_called()

    def test_wrong_source_byte_budget_blocks_before_http(self):
        with patch.object(mod, "urlopen") as opened:
            with self.assertRaisesRegex(ValueError,"wrong_nba_official_schedule_source_size_limit"):
                mod.fetch_source(mod.NBA_TODAY_SCOREBOARD_URL,mod.MAX_BOX_BYTES)
            opened.assert_not_called()

    def test_two_real_http_403_failures_preserve_exact_denial_without_training(self):
        called=[]
        def denied(url,cap):
            called.append(url)
            raise HTTPError(url,403,"Forbidden",None,None)
        rows,report,originals=mod.run(
            "synthetic",now=NOW,clock=lambda:NOW,
            pdf_reader=injury_source,fetcher=denied,
        )
        self.assertEqual(called,[mod.NBA_SCHEDULE_URL,mod.NBA_TODAY_SCOREBOARD_URL])
        self.assertEqual(report["official_nba_schedule_source_errors"],{
            mod.NBA_SCHEDULE_URL:"HTTP_403",
            mod.NBA_TODAY_SCOREBOARD_URL:"HTTP_403",
        })
        self.assertEqual(report["status"],"official_nba_schedule_and_daily_board_unavailable")
        self.assertEqual(rows[0]["crosscheck_status"],"official_nba_future_schedule_unavailable")
        self.assertEqual(originals,{})
        self.assertEqual(report["independently_confirmed_active_players"],0)
        self.assertEqual(report["qualified_player_prop_training_observations"],0)
        self.assertFalse(report["champion_001_modified"])

    def test_http_429_denial_not_masked_or_retried(self):
        called=[]
        def denied(url,cap):
            called.append(url)
            raise HTTPError(url,429,"Too Many Requests",None,None)
        _,report,_=mod.run("synthetic",now=NOW,clock=lambda:NOW,
                           pdf_reader=injury_source,fetcher=denied)
        self.assertEqual(len(called),2)
        self.assertEqual(set(report["official_nba_schedule_source_errors"].values()),{"HTTP_429"})


if __name__ == "__main__":
    unittest.main()
