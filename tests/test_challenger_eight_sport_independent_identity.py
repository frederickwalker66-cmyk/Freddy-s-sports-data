"""Upgrade #76 synthetic fail-closed NHL second-source identity checks."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_eight_sport_independent_identity import audit, run
from challenger_nhl_official_score_crosscheck import day_url

DAY = "2026-11-05"
START = "2026-11-05T23:00:00+00:00"
OBSERVED = "2026-11-05T18:02:00+00:00"


def espn_row(league="nhl", eid="401", **changes):
    d = {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": league, "espn_schedule_event_id": eid,
        "home_team": "New York Rangers" if league == "nhl" else "New York Knicks",
        "away_team": "Boston Bruins" if league == "nhl" else "Boston Celtics",
        "event_start_utc": START, "snapshot_completed_at_utc": "2026-11-05T18:01:00Z",
        "schedule_observed_at_utc": "2026-11-05T18:00:00Z",
        "odds_observations": [],
        "qualified_for_challenger_backtest": False,
        "model_probability": None, "certified_prediction": False,
        "bet_ready": False, "champion_001_modified": False,
    }
    return dict(d, **changes)


def nhl_original(home="NYR", away="BOS", start=START, duplicates=False):
    game = {
        "id": 1001, "gameDate": DAY, "startTimeUTC": start,
        "gameState": "FUT", "homeTeam": {"abbrev": home},
        "awayTeam": {"abbrev": away},
    }
    games = [game]
    if duplicates:
        games.append(dict(game, id=1002))
    return json.dumps({"currentDate": DAY, "games": games}).encode("utf8")


def receipt(raw=None, observed=OBSERVED, url=None):
    return {DAY: {
        "raw": nhl_original() if raw is None else raw,
        "observed_at_utc": observed,
        "source_url": day_url(DAY) if url is None else url,
    }}


class IndependentGameIdentityTests(unittest.TestCase):
    def test_exact_pregame_nhl_source_matches_but_no_market_or_bet(self):
        rows, report = audit([espn_row()], receipt())
        self.assertEqual(report["independently_observed_nhl_pregame_identity_matches_research_only"], 1)
        self.assertEqual(rows[0]["nhl_official_game_id"], "1001")
        self.assertTrue(rows[0]["official_league_pregame_identity_matched_research_only"])
        self.assertEqual(rows[0]["nhl_original_response_sha256"],
                         hashlib.sha256(nhl_original()).hexdigest())
        self.assertFalse(rows[0]["exact_draftkings_market_identity_verified"])
        self.assertEqual(report["certified_positive_ev_bets"], 0)
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertFalse(report["champion_001_modified"])

    def test_other_sports_remain_unverified_not_fake_match(self):
        rows, report = audit([espn_row("nba", "42"), espn_row()], receipt())
        self.assertEqual(report["archived_espn_events_reviewed"], 2)
        self.assertEqual(report["independent_identity_unverified"], 1)
        self.assertEqual(rows[0]["identity_status"], "official_league_adapter_not_available")

    def test_missing_official_response_fails_closed(self):
        rows, report = audit([espn_row()], {})
        self.assertEqual(rows[0]["identity_status"], "nhl_official_response_not_captured")
        self.assertEqual(report["independently_observed_nhl_pregame_identity_matches_research_only"], 0)

    def test_response_observed_after_game_is_not_pregame_evidence(self):
        rows, report = audit([espn_row()], receipt(observed="2026-11-06T02:00:00Z"))
        self.assertEqual(rows[0]["identity_status"], "nhl_response_not_observed_pregame")
        self.assertEqual(report["independently_observed_nhl_pregame_identity_matches_research_only"], 0)

    def test_wrong_home_away_fails_closed(self):
        rows, report = audit([espn_row()], receipt(raw=nhl_original("BOS", "NYR")))
        self.assertEqual(rows[0]["identity_status"], "nhl_match_missing_or_ambiguous")
        self.assertEqual(report["independent_identity_unverified"], 1)

    def test_kickoff_mismatch_not_rounded_into_match(self):
        rows, report = audit([espn_row()], receipt(
            raw=nhl_original(start="2026-11-05T23:02:00Z")))
        self.assertEqual(rows[0]["identity_status"], "nhl_kickoff_disagrees")
        self.assertFalse(rows[0]["official_league_pregame_identity_matched_research_only"])

    def test_ambiguous_multiple_official_games_not_arbitrarily_selected(self):
        rows, _ = audit([espn_row()], receipt(raw=nhl_original(duplicates=True)))
        self.assertEqual(rows[0]["identity_status"], "nhl_match_missing_or_ambiguous")

    def test_invalid_source_url_and_bytes_rejected_as_identity_evidence(self):
        rows, report = audit([espn_row()], receipt(url="https://example.com/score"))
        self.assertEqual(rows[0]["identity_status"], "invalid_nhl_original_response")
        self.assertIn(DAY, report["nhl_source_errors"])
        rows, _ = audit([espn_row()], receipt(raw=b"{}"))
        self.assertEqual(rows[0]["identity_status"], "invalid_nhl_original_response")

    def test_duplicate_espn_game_and_duplicate_official_game_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate_espn"):
            audit([espn_row(), espn_row()], receipt())
        with self.assertRaisesRegex(ValueError, "nhl_official_game_reused"):
            audit([espn_row(), espn_row(eid="402")], receipt())

    def test_pregame_archive_and_model_gates_cannot_be_promoted(self):
        for change in (
            {"snapshot_completed_at_utc": START},
            {"certified_prediction": True},
            {"model_probability": 0.7},
            {"qualified_for_challenger_backtest": True},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                audit([espn_row(**change)], receipt())

    def test_original_nhl_bytes_and_report_written_without_checkout_claim(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            root.mkdir()
            (root / "prospective_event_evidence.jsonl").write_text(
                json.dumps(espn_row()) + "\n")
            (root / "eight_sport_schedule_coverage.json").write_text(
                json.dumps({
                    "archived_games_matching_exact_original_event_fields": 1,
                    "original_espn_source_responses_verified": 1,
                    "certified_positive_ev_bets": 0,
                    "champion_001_modified": False,
                }))
            def fixed_clock():
                return datetime(2026, 11, 5, 18, 2, tzinfo=timezone.utc)
            out = Path(tmp) / "independent"
            summary = run(root, out, fetcher=lambda day: nhl_original(),
                          clock=fixed_clock)
            self.assertEqual(summary["independently_observed_nhl_pregame_identity_matches_research_only"], 1)
            self.assertEqual((out / "nhl_official_20261105.json").read_bytes(), nhl_original())
            self.assertEqual(summary["direct_draftkings_checkout_markets_verified"], 0)
            with self.assertRaisesRegex(ValueError, "output_directory_must_be_empty"):
                run(root, out, fetcher=lambda day: nhl_original(), clock=fixed_clock)


if __name__ == "__main__":
    unittest.main()
