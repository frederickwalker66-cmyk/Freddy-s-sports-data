"""#83 offline original nflverse NFL pregame identity verification tests."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_nflverse_pregame_crosscheck import (
    SOURCE_URL, audit, parse_future, run,
)
DAY = "2026-11-08"
TIP = "2026-11-08T18:00:00Z"
OBS = "2026-11-05T18:58:00Z"
HEADER = "game_id,season,game_type,gameday,gametime,away_team,home_team,away_score,home_score,espn"
LINE = "2026_10_NYJ_NE,2026,REG,2026-11-08,13:00,NYJ,NE,,,401873200"


def csv_source(line=LINE):
    return (HEADER + "\n" + line + "\n").encode()


def row(eid="401873200", start=TIP, **changes):
    d = {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": "nfl", "espn_schedule_event_id": eid,
        "home_team": "New England Patriots", "away_team": "New York Jets",
        "event_start_utc": start,
        "schedule_observed_at_utc": "2026-11-05T18:45:00Z",
        "snapshot_completed_at_utc": "2026-11-05T18:46:00Z",
        "model_probability": None, "certified_prediction": False,
        "qualified_for_challenger_backtest": False, "bet_ready": False,
        "champion_001_modified": False,
    }
    return dict(d, **changes)


def receipt(raw=None, observed=OBS):
    return {"raw": csv_source() if raw is None else raw,
            "source_url": SOURCE_URL, "observed_at_utc": observed}


class NFLversePregameTests(unittest.TestCase):
    def test_future_unplayed_original_csv_parses_exact_teams_clock_and_id(self):
        data = parse_future(csv_source())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["nflverse_game_id"], "2026_10_NYJ_NE")
        self.assertEqual(data[0]["start"].isoformat(), "2026-11-08T18:00:00+00:00")

    def test_completed_game_never_claims_future(self):
        self.assertEqual(parse_future(csv_source(LINE.replace("NE,,,", "NE,17,21,"))), [])

    def test_invalid_csv_duplicate_gid_and_partial_score_rejected(self):
        for bad in (
            b"broken,header\n",
            csv_source(LINE + "\n" + LINE),
            csv_source(LINE.replace("NE,,,", "NE,17,,")),
            csv_source(LINE.replace("NE,,,", "NYJ,,,")),
            csv_source(LINE.replace("2026_10_NYJ_NE", "unsafe-id")),
        ):
            with self.subTest(raw=bad[:65]), self.assertRaises(ValueError):
                parse_future(bad)

    def test_matching_same_run_nflverse_source_is_only_third_party(self):
        rows, report = audit([row()], receipt())
        self.assertEqual(report["independent_third_party_pregame_identity_matches_research_only"], 1)
        self.assertEqual(report["official_nfl_operated_identity_matches_verified"], 0)
        self.assertEqual(rows[0]["nflverse_game_id"], "2026_10_NYJ_NE")
        self.assertEqual(rows[0]["nflverse_original_sha256"], hashlib.sha256(csv_source()).hexdigest())
        self.assertFalse(rows[0]["source_publication_timestamp_authenticated"])
        self.assertFalse(rows[0]["independent_training_feature_verified"])
        self.assertFalse(rows[0]["independent_official_league_verified"])
        self.assertEqual(report["qualified_training_games"], 0)
        self.assertEqual(report["certified_positive_ev_bets"], 0)

    def test_missing_source_and_invalid_schema_never_promoted(self):
        rows, r = audit([row()], None)
        self.assertEqual(rows[0]["identity_status"], "nflverse_original_response_not_captured")
        rows, r = audit([row()], receipt(raw=b"bad"))
        self.assertEqual(rows[0]["identity_status"], "nflverse_invalid_original_response")
        self.assertIsNotNone(r["original_source_error"])

    def test_late_observation_wrong_kickoff_and_espn_id(self):
        rows, _ = audit([row()], receipt(observed="2026-11-08T19:00:00Z"))
        self.assertEqual(rows[0]["identity_status"], "nflverse_response_not_observed_pregame")
        rows, _ = audit([row()], receipt(raw=csv_source(LINE.replace("13:00", "13:02"))))
        self.assertEqual(rows[0]["identity_status"], "nflverse_kickoff_disagrees")
        rows, _ = audit([row()], receipt(raw=csv_source(LINE.replace("401873200", "401873299"))))
        self.assertEqual(rows[0]["identity_status"], "nflverse_missing_ambiguous_or_conflicting_espn_id")

    def test_swapped_teams_not_accepted(self):
        rows, report = audit([row()], receipt(raw=csv_source(LINE.replace("NYJ,NE,,,", "NE,NYJ,,,"))))
        self.assertEqual(report["independent_third_party_pregame_identity_matches_research_only"], 0)

    def test_same_source_game_cannot_be_reused_across_espn_ids(self):
        line2 = LINE.replace("401873200", "")  # ambiguous ESPN id, same league game
        data = csv_source(line2)
        with self.assertRaisesRegex(ValueError, "reused_by_two_espn"):
            audit([row(), row(eid="401873201")], receipt(raw=data))

    def test_fake_model_or_postgame_pregame_snapshot_rejected(self):
        for change in (
            {"model_probability": 0.73},
            {"bet_ready": True},
            {"champion_001_modified": True},
            {"snapshot_completed_at_utc": TIP},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                audit([row(**change)], receipt())

    def test_end_to_end_original_csv_preserved_and_no_wagers(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp)/"source"
            src.mkdir()
            (src/"prospective_event_evidence.jsonl").write_text(json.dumps(row())+"\n")
            output = Path(tmp)/"nfl"
            t = datetime.fromisoformat(OBS.replace("Z", "+00:00"))
            report = run(src, output, fetcher=lambda: csv_source(), clock=lambda:t)
            self.assertEqual((output/"nflverse_games_original.csv").read_bytes(), csv_source())
            self.assertEqual(report["independent_third_party_pregame_identity_matches_research_only"], 1)
            self.assertEqual(report["automated_bets_placed"], 0)

    def test_outage_is_not_fabricated_source(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp)/"source"
            src.mkdir()
            (src/"prospective_event_evidence.jsonl").write_text(json.dumps(row())+"\n")
            def denied():
                raise OSError("blocked")
            result = run(src, Path(tmp)/"nfl", fetcher=denied)
            self.assertEqual(result["independent_third_party_pregame_identity_matches_research_only"], 0)
            self.assertEqual(result["network_source_failure"], "OSError")


if __name__ == "__main__":
    unittest.main()
