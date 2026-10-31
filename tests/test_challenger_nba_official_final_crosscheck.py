"""Synthetic second-source NBA outcome comparison, never training approval."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from challenger_nba_official_final_crosscheck import (
    RESEARCH_STATUS, official_final_games, review_candidates, main,
)

NOW = datetime(2026, 10, 31, 15, tzinfo=timezone.utc)


def case(**changes):
    x = {
        "record_type": "challenger_nba_history_candidate_review_only",
        "league": "nba", "market_type": "moneyline", "selection_type": "home",
        "event_id": "401701001",
        "home_team": "Los Angeles Clippers", "away_team": "Boston Celtics",
        "start_utc": "2026-10-30T23:00:00+00:00",
        "snapshot_utc": "2026-10-30T21:00:00+00:00",
        "outcome_verified_at_utc": "2026-10-31T11:00:00+00:00",
        "published_score_only": {"home": 102, "away": 97},
        "outcome": 1, "qualified_for_challenger_backtest": False,
        "eligible_to_train_probability_model": False,
        "independent_asof_review": False,
        "independent_outcome_review": False,
        "certified_prediction": False, "bet_ready": False,
        "model_probability": None, "champion_001_modified": False,
    }
    x.update(changes)
    return x


def official(score_home=102, score_away=97, status=3, started="2026-10-30T23:00:00Z"):
    return {
        "leagueSchedule": {
            "leagueId": "00", "seasonYear": "2026-27",
            "gameDates": [{"gameDate": "2026-10-30", "games": [{
                "gameId": "0022600011",
                "gameDateTimeUTC": started,
                "gameStatus": status,
                "homeTeam": {"teamCity": "LA", "teamName": "Clippers", "score": score_home},
                "awayTeam": {"teamCity": "Boston", "teamName": "Celtics", "score": score_away},
            }]}]
        }
    }


class OfficialScoreCrosscheckTests(unittest.TestCase):
    def test_score_agreement_is_research_only(self):
        rows, report = review_candidates([case()], official(), NOW)
        self.assertEqual(rows[0]["crosscheck_status"], RESEARCH_STATUS)
        self.assertEqual(rows[0]["official_nba_game_id"], "0022600011")
        self.assertEqual(rows[0]["official_nba_score"], {"home": 102, "away": 97})
        self.assertEqual(report["second_source_published_final_score_agreements"], 1)
        self.assertEqual(report["independently_qualified_training_records"], 0)
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertFalse(rows[0]["training_row_qualified"])
        self.assertFalse(rows[0]["independent_feature_asof_verified"])
        self.assertFalse(rows[0]["bet_ready"])

    def test_disagreement_does_not_promote_training(self):
        rows, report = review_candidates([case()], official(score_home=103), NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "nba_official_final_disagrees_with_espn")
        self.assertEqual(report["second_source_published_final_score_agreements"], 0)
        self.assertEqual(report["independently_qualified_training_records"], 0)

    def test_unfinished_game_or_missing_score(self):
        for payload in [official(status=1), official(status=3, score_home=None)]:
            with self.subTest(payload=payload):
                rows, report = review_candidates([case()], payload, NOW)
                self.assertEqual(rows[0]["crosscheck_status"],
                                 "official_nba_game_not_final_or_score_unavailable")
                self.assertEqual(report["independently_qualified_training_records"], 0)

    def test_official_unavailable(self):
        rows, report = review_candidates([case()], None, NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "nba_official_source_unavailable")
        self.assertFalse(report["official_source_available"])

    def test_mismatched_start_or_teams_is_not_a_match(self):
        for payload in [official(started="2026-10-31T03:00:00Z"),
                        {"leagueSchedule": {"gameDates": [{
                            "games": [{**official()["leagueSchedule"]["gameDates"][0]["games"][0],
                                       "homeTeam": {"teamCity": "New York", "teamName": "Knicks", "score": 102}}]
                        }]}}]:
            with self.subTest(payload=payload):
                rows, _ = review_candidates([case()], payload, NOW)
                self.assertEqual(rows[0]["crosscheck_status"],
                                 "official_nba_game_not_found_or_clock_mismatch")

    def test_duplicate_nba_game_identity_raises(self):
        payload=official()
        duplicate=dict(payload["leagueSchedule"]["gameDates"][0]["games"][0])
        duplicate["awayTeam"]={"teamCity":"Brooklyn","teamName":"Nets","score":90}
        payload["leagueSchedule"]["gameDates"][0]["games"].append(duplicate)
        with self.assertRaisesRegex(ValueError, "conflicting NBA official game ID"):
            official_final_games(payload)

    def test_ambiguous_two_distinct_official_games(self):
        payload=official()
        duplicate=dict(payload["leagueSchedule"]["gameDates"][0]["games"][0])
        duplicate["gameId"]="0022600012"
        payload["leagueSchedule"]["gameDates"][0]["games"].append(duplicate)
        rows,_=review_candidates([case()],payload,NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "ambiguous_official_game_identity")

    def test_invalid_source_shape_fails_closed(self):
        for payload in [{}, {"leagueSchedule": {"gameDates": "bad"}},
                        {"leagueSchedule": {"leagueId": "10", "gameDates": []}}]:
            with self.assertRaises(ValueError):
                official_final_games(payload)

    def test_bad_candidate_state_rejected(self):
        for updates in [{"qualified_for_challenger_backtest":True},
                        {"independent_asof_review":True},
                        {"model_probability":0.7},
                        {"champion_001_modified":True},
                        {"snapshot_utc":"2026-10-30T23:00:00Z"},
                        {"outcome_verified_at_utc":"2026-11-02T00:00:00Z"},
                        {"published_score_only":{"home":102,"away":97},"outcome":0}]:
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    review_candidates([case(**updates)],official(),NOW)

    def test_duplicate_candidate_ids_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate"):
            review_candidates([case(),case()],official(),NOW)

    def test_cli_stages_without_trainable_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            src=root/"candidates.jsonl"
            src.write_text(json.dumps(case())+"\n",encoding="utf-8")
            with patch("challenger_nba_official_final_crosscheck.fetch_official_schedule",
                       return_value=official()) as fetch:
                self.assertEqual(main(["--candidates",str(src),"--output-dir",str(root)]),0)
                fetch.assert_called_once()
            report=json.loads((root/"nba_official_final_crosscheck_report.json").read_text())
            self.assertEqual(report["second_source_published_final_score_agreements"],1)
            self.assertFalse((root/"historical_results.jsonl").exists())
            self.assertFalse((root/"research_model.json").exists())

    def test_cli_official_fetch_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            src=root/"candidates.jsonl"
            src.write_text(json.dumps(case())+"\n",encoding="utf-8")
            with patch("challenger_nba_official_final_crosscheck.fetch_official_schedule",
                       side_effect=OSError("blocked")):
                self.assertEqual(main(["--candidates",str(src),"--output-dir",str(root)]),0)
            report=json.loads((root/"nba_official_final_crosscheck_report.json").read_text())
            self.assertEqual(report["official_source_failure_type"],"OSError")
            self.assertEqual(report["independently_qualified_training_records"],0)


if __name__=="__main__":
    unittest.main()
