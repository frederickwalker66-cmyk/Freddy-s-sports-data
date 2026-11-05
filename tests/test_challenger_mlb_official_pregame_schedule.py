"""Upgrade #77: offline tests of MLB-operated pregame source corroboration."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_mlb_official_pregame_schedule import (
    day_url, parse_schedule,
)
from challenger_eight_sport_independent_identity import audit, run

DAY = "2026-07-04"
START = "2026-07-04T23:05:00Z"
OBS = "2026-07-04T18:02:00Z"


def row(start=START, game_id="888", **changes):
    basic = {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": "mlb", "espn_schedule_event_id": game_id,
        "home_team": "New York Yankees", "away_team": "Boston Red Sox",
        "event_start_utc": start,
        "snapshot_completed_at_utc": "2026-07-04T18:01:00Z",
        "schedule_observed_at_utc": "2026-07-04T18:00:00Z",
        "odds_observations": [],
        "qualified_for_challenger_backtest": False,
        "model_probability": None, "certified_prediction": False,
        "bet_ready": False, "champion_001_modified": False,
    }
    return dict(basic, **changes)


def raw(date=DAY, start=START, game_pk=777001, away="Boston Red Sox",
        home="New York Yankees", away_id=111, home_id=147,
        state="Preview", detailed="Scheduled", game_type="R", more_games=None):
    game = {
        "gamePk": game_pk, "gameDate": start, "officialDate": date,
        "gameType": game_type,
        "status": {"abstractGameState": state, "detailedState": detailed},
        "teams": {
            "home": {"team": {"id": home_id, "name": home}},
            "away": {"team": {"id": away_id, "name": away}},
        },
    }
    return json.dumps({"totalGames": 1, "dates": [{
        "date": date, "games": [game] + list(more_games or []),
    }]}).encode("utf8")


def receipt(body=None, day=DAY, observed=OBS, source_url=None):
    return {day: {
        "raw": raw(date=day) if body is None else body,
        "source_url": day_url(day) if source_url is None else source_url,
        "observed_at_utc": observed,
    }}


class MLBOriginalScheduleTests(unittest.TestCase):
    def test_exact_response_exposes_native_mlb_id_and_teams(self):
        games = parse_schedule(raw(), DAY)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]["mlb_game_pk"], "777001")
        self.assertEqual((games[0]["home_id"], games[0]["away_id"]), (147, 111))

    def test_offseason_empty_dates_is_valid_not_fake_game(self):
        self.assertEqual(parse_schedule(b'{"totalGames":0,"dates":[]}', "2026-11-05"), [])

    def test_bad_day_schema_duplicate_or_malformed_team_quarantined(self):
        for bad in (
            raw(date="2026-07-05"),
            raw(more_games=[json.loads(raw())["dates"][0]["games"][0]]),
            raw(home_id=111),
            raw(game_pk=True),
            b'{"unexpected":"data"}',
        ):
            with self.subTest(bad=bad[:50]), self.assertRaises(ValueError):
                parse_schedule(bad, DAY)

    def test_finished_cancelled_and_exhibition_games_not_pregame(self):
        for opts in (
            {"state": "Final"},
            {"detailed": "Postponed"},
            {"game_type": "S"},
        ):
            with self.subTest(opts=opts):
                self.assertEqual(parse_schedule(raw(**opts), DAY), [])


class MLBIdentityCrosscheckTests(unittest.TestCase):
    def test_exact_mlb_game_reconciled_without_bet_promotion(self):
        rows, report = audit([row()], {}, receipt())
        self.assertEqual(report["independently_observed_mlb_pregame_identity_matches_research_only"], 1)
        self.assertEqual(report["independently_observed_nhl_pregame_identity_matches_research_only"], 0)
        self.assertEqual(rows[0]["mlb_official_game_pk"], "777001")
        self.assertEqual(rows[0]["mlb_official_home_team_id"], 147)
        self.assertEqual(rows[0]["mlb_original_response_sha256"],
                         hashlib.sha256(raw()).hexdigest())
        self.assertFalse(rows[0]["draftkings_checkout_price_verified"])
        self.assertFalse(rows[0]["qualified_for_training"])
        self.assertFalse(report["champion_001_modified"])
        for key in (
            "direct_draftkings_checkout_markets_verified",
            "verified_native_model_probabilities",
            "certified_champion_001_predictions",
            "certified_challenger_001_predictions",
            "certified_positive_ev_bets",
            "automated_bets_placed",
        ):
            self.assertEqual(report[key], 0)

    def test_missing_and_invalid_original_bytes_do_not_match(self):
        rows, _ = audit([row()], {}, {})
        self.assertEqual(rows[0]["identity_status"], "mlb_official_response_not_captured")
        rows, report = audit([row()], {}, receipt(body=b"{}"))
        self.assertEqual(rows[0]["identity_status"], "invalid_mlb_original_response")
        self.assertIn(DAY, report["mlb_source_errors"])

    def test_official_response_after_first_pitch_rejected(self):
        rows, _ = audit([row()], {}, receipt(observed="2026-07-05T00:05:00Z"))
        self.assertEqual(rows[0]["identity_status"], "mlb_response_not_observed_pregame")

    def test_swapped_sides_unknown_name_and_wrong_start_rejected(self):
        for opts, expected in (
            ({"home": "Boston Red Sox", "away": "New York Yankees"},
             "mlb_match_missing_or_ambiguous"),
            ({"home": "Unverified Yankees"}, "mlb_match_missing_or_ambiguous"),
            ({"start": "2026-07-04T23:07:00Z"}, "mlb_kickoff_disagrees"),
        ):
            with self.subTest(opts=opts):
                rows, report = audit([row()], {}, receipt(body=raw(**opts)))
                self.assertEqual(rows[0]["identity_status"], expected)
                self.assertEqual(report["independently_observed_mlb_pregame_identity_matches_research_only"], 0)

    def test_ambiguous_two_games_never_arbitrarily_choose_first(self):
        extra = json.loads(raw())["dates"][0]["games"][0]
        extra["gamePk"] = 777002
        rows, _ = audit([row()], {}, receipt(body=raw(more_games=[extra])))
        self.assertEqual(rows[0]["identity_status"], "mlb_match_missing_or_ambiguous")

    def test_one_mlb_pk_cannot_certify_two_espn_games(self):
        with self.assertRaisesRegex(ValueError, "mlb_official_game_reused"):
            audit([row(), row(game_id="889")], {}, receipt())

    def test_conflicting_revised_official_start_fails_closed(self):
        early_start = "2026-07-05T04:30:00Z"
        packets = {
            **receipt(day="2026-07-04", body=raw(date="2026-07-04", start=early_start)),
            **receipt(day="2026-07-05", body=raw(date="2026-07-05", start="2026-07-05T04:31:30Z")),
        }
        rows, _ = audit([row(start=early_start)], {}, packets)
        self.assertEqual(rows[0]["identity_status"], "mlb_conflicting_official_game_revisions")

    def test_midnight_eastern_official_stadium_previous_day(self):
        early_start = "2026-07-05T04:30:00Z"
        rows, report = audit([row(start=early_start)], {},
                             receipt(day="2026-07-04", body=raw(
                                 date="2026-07-04", start=early_start)))
        self.assertEqual(report["independently_observed_mlb_pregame_identity_matches_research_only"], 1)
        self.assertEqual(rows[0]["mlb_official_source_url"], day_url("2026-07-04"))

    def test_no_fabricated_pregame_archive_or_promoted_forecasts(self):
        for changes in (
            {"snapshot_completed_at_utc": START},
            {"model_probability": 0.65},
            {"certified_prediction": True},
            {"bet_ready": True},
            {"champion_001_modified": True},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                audit([row(**changes)], {}, receipt())

    def test_read_only_end_to_end_capture_writes_official_mlb_wire_bytes(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "espn"
            src.mkdir()
            (src / "prospective_event_evidence.jsonl").write_text(json.dumps(row()) + "\n")
            (src / "eight_sport_schedule_coverage.json").write_text(
                json.dumps({
                    "archived_games_matching_exact_original_event_fields": 1,
                    "original_espn_source_responses_verified": 1,
                    "certified_positive_ev_bets": 0,
                    "champion_001_modified": False,
                }))
            called = []
            def fake_fetch(day):
                called.append(day)
                return raw()
            def clock():
                return datetime(2026, 7, 4, 18, 2, tzinfo=timezone.utc)
            target = Path(tmp) / "independent"
            report = run(src, target, clock=clock,
                         fetcher=lambda day: self.fail("NHL should not be fetched"),
                         mlb_fetcher=fake_fetch)
            self.assertEqual(called, [DAY])
            self.assertEqual((target / "mlb_official_20260704.json").read_bytes(), raw())
            self.assertEqual(report["independently_observed_mlb_pregame_identity_matches_research_only"], 1)
            self.assertEqual(report["official_mlb_dates_requested"], [DAY])
            self.assertEqual(report["direct_draftkings_checkout_markets_verified"], 0)


if __name__ == "__main__":
    unittest.main()
