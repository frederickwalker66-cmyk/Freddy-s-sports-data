"""Synthetic-only college NCAA-derived published result crosscheck regression tests."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_college_ncaa_score_review import (
    SOURCE_BASE, corroborate, main, parse_scoreboard, plan, run, scoreboard_path,
)

NOW = datetime(2026, 11, 5, 13, tzinfo=timezone.utc)
START = "2026-11-04T23:00:00+00:00"


def packet(league="ncaab", event_id="4019001", home="Duke Blue Devils",
           away="North Carolina Tar Heels", final=True, start=START):
    return {
        "record_type": "challenger_original_bytes_feature_lineage_review_only",
        "league": league, "event_id": event_id, "home_team": home,
        "away_team": away, "event_start_utc": start,
        "snapshot_completed_at_utc": "2026-11-04T21:00:00Z",
        "original_bytes_match_same_run_receipt": True,
        "same_run_receipt_independently_authenticated": False,
        "published_final_only": ({
            "home_score": 77, "away_score": 68, "published_result": "home",
            "published_at_observation_utc": "2026-11-05T03:20:00Z",
            "source_url": "https://site.api.espn.com/scoreboard"
        } if final else None),
        "independent_outcome_review": False,
        "market_settlement_rules_verified": False,
        "qualified_for_challenger_training": False,
        "model_probability": None,
        "certified_prediction": False,
        "bet_ready": False, "champion_001_modified": False,
    }


def raw(state="final", home="Duke", away="North Carolina", hscore="77", ascore="68",
        when=START, gid="7100001", duplicated=False):
    epoch = int(datetime.fromisoformat(when).timestamp())
    game = {
        "gameID": gid, "startTimeEpoch": str(epoch), "startDate": "2026-11-04",
        "gameState": state, "home": {"names": {"short": home, "full": ""},
                                    "score": hscore},
        "away": {"names": {"short": away, "full": ""},
                 "score": ascore}
    }
    return json.dumps({"updated_at": "2026-11-05 13:00:00",
                       "games": [{"game": game}, {"game": deepcopy(game)}] if duplicated
                       else [{"game": game}]}).encode()


class CollegeNCAASourceTests(unittest.TestCase):
    def test_basketball_agreement_separate_source_not_training(self):
        result, report = corroborate(
            [packet()], {"ncaab:2026-11-04": raw()}, NOW)
        self.assertEqual(result[0]["crosscheck_status"],
                         "ncaa_derived_final_score_agrees_research_only")
        self.assertEqual(result[0]["ncaa_contest_id"], "7100001")
        self.assertEqual(result[0]["ncaa_proxy_raw_sha256"],
                         hashlib.sha256(raw()).hexdigest())
        self.assertEqual(report["ncaa_derived_score_agreements"]["ncaab"], 1)
        self.assertEqual(report["independently_qualified_training_games"], 0)
        self.assertFalse(result[0]["qualified_for_challenger_training"])

    def test_college_football_current_week_route_only_no_guessed_week(self):
        p = packet("ncaaf",home="Alabama Crimson Tide",away="Georgia Bulldogs")
        self.assertEqual(plan([p], NOW)["ncaaf"], "football/fbs")
        self.assertEqual(scoreboard_path("ncaaf",football_week=10,
                                         football_year=2026),
                         "football/fbs/2026/10/all-conf")
        with self.assertRaises(ValueError):
            scoreboard_path("ncaaf",football_week=10)
        records, report = corroborate([p], {"ncaaf":raw(home="Alabama",away="Georgia")}, NOW)
        self.assertEqual(records[0]["crosscheck_status"],
                         "ncaa_derived_final_score_agrees_research_only")
        self.assertEqual(report["ncaa_derived_score_agreements"]["ncaaf"],1)

    def test_final_scores_disagree_and_never_promote(self):
        rows, report=corroborate([packet()], {"ncaab:2026-11-04":raw(hscore="84")}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "ncaa_derived_score_disagrees_with_espn")
        self.assertEqual(report["bet_ready_selections"], 0)

    def test_live_score_cannot_be_treated_as_final(self):
        rows,_=corroborate([packet()], {"ncaab:2026-11-04":raw(state="live")}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "ncaa_event_not_final_or_incomplete_score")

    def test_missing_score_cannot_be_zero_imputed(self):
        rows,_=corroborate([packet()], {"ncaab:2026-11-04":raw(hscore="",ascore="68")}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "ncaa_event_not_final_or_incomplete_score")

    def test_unknown_school_identity_never_fuzzy_matches(self):
        p=packet(home="Miami Ohio RedHawks",away="Georgia Bulldogs")
        rows,_=corroborate([p], {"ncaab:2026-11-04":raw(home="Miami",away="Georgia")}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"],"unreviewed_college_school_identity")

    def test_reversed_home_and_away_cannot_count(self):
        rows,_=corroborate([packet()],
                          {"ncaab:2026-11-04":raw(home="North Carolina",away="Duke")}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"],"no_exact_ncaa_match_in_checked_source")

    def test_missing_start_epoch_never_guesses(self):
        s=json.loads(raw())
        s["games"][0]["game"]["startTimeEpoch"]=""
        rows,_=corroborate([packet()],
                          {"ncaab:2026-11-04":json.dumps(s).encode()}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"],"no_exact_ncaa_match_in_checked_source")

    def test_wrong_start_more_than_30_minutes_rejected(self):
        rows,_=corroborate([packet()],
                          {"ncaab:2026-11-04":raw(when="2026-11-04T20:00:00+00:00")}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"],"no_exact_ncaa_match_in_checked_source")

    def test_duplicate_source_contest_id_rejects_entire_day(self):
        rows,report=corroborate([packet()],
                               {"ncaab:2026-11-04":raw(duplicated=True)}, NOW)
        self.assertTrue(rows[0]["crosscheck_status"].startswith("invalid_source_"))
        self.assertEqual(report["ncaa_derived_score_agreements"]["ncaab"],0)

    def test_bad_2026_source_schema_rejects_old_or_graphql_error(self):
        rows,_=corroborate([packet()],{"ncaab:2026-11-04":
                             json.dumps({"data":{"contests":[]}}).encode()},NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "invalid_source_ValueError")
        rows,_=corroborate([packet()],{"ncaab:2026-11-04":
                             json.dumps({"message":"Resource not found"}).encode()},NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "invalid_source_ValueError")

    def test_no_published_final_skips_network(self):
        calls=[]
        rows,report,source=run([packet(final=False)],
                     fetcher=lambda route:calls.append(route),now=NOW)
        self.assertEqual(calls,[])
        self.assertEqual(source,{})
        self.assertEqual(rows[0]["crosscheck_status"], "awaiting_espn_published_final")

    def test_network_failure_returns_blocked_not_agreement(self):
        def fail(_):
            raise OSError("test offline")
        rows,report,source=run([packet()],fetcher=fail,now=NOW)
        self.assertEqual(rows[0]["crosscheck_status"],"source_unavailable")
        self.assertEqual(report["network_failures"]["ncaab:2026-11-04"],"OSError")
        self.assertEqual(source,{})

    def test_requires_original_unmodified_undisputed_packet(self):
        p=packet()
        p["qualified_for_challenger_training"]=True
        calls=[]
        with self.assertRaisesRegex(ValueError,"unquarantined"):
            run([p],fetcher=lambda route:calls.append(route),now=NOW)
        self.assertEqual(calls,[])

    def test_duplicates_in_primary_packets_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate"):
            corroborate([packet(),packet()],{"ncaab:2026-11-04":raw()},NOW)

    def test_response_corrupt_bytes_blocked(self):
        rows,_=corroborate([packet()],{"ncaab:2026-11-04":b"not json"},NOW)
        self.assertTrue(rows[0]["crosscheck_status"].startswith("invalid_source_"))

    def test_bounded_dates_and_source_request_count(self):
        p1=packet(event_id="4019001")
        p2=packet(event_id="4019002")
        p2["event_start_utc"]="2026-11-03T23:00:00Z"
        p2["snapshot_completed_at_utc"]="2026-11-03T21:00:00Z"
        p2["published_final_only"]["published_at_observation_utc"]="2026-11-04T03:20:00Z"
        planned=plan([p1,p2],NOW,max_dates=1)
        self.assertEqual(list(planned),["ncaab:2026-11-04"])
        rows, report=corroborate([p1,p2],{"ncaab:2026-11-04":raw()},NOW,max_dates=1)
        self.assertEqual(rows[1]["crosscheck_status"],
                         "outside_bounded_ncaa_basketball_dates")
        self.assertEqual(report["requested_routes"],planned)

    def test_empty_input_no_requests_no_models_and_only_two_files(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            p=root/"source.jsonl"
            p.write_text("")
            self.assertEqual(main(["--lineage",str(p),"--output-dir",str(root/"out")]),0)
            files=sorted(x.name for x in (root/"out").iterdir())
            self.assertEqual(files,["college_ncaa_score_report.json",
                                    "college_ncaa_score_review.jsonl"])
            summary=json.loads((root/"out"/files[0]).read_text())
            self.assertEqual(summary["independently_qualified_training_games"],0)
            self.assertFalse(summary["champion_001_modified"])

    def test_manual_football_path_needs_explicit_year_and_week(self):
        with self.assertRaises(ValueError):
            scoreboard_path("ncaaf",football_week=12,football_year=2023)
        with self.assertRaises(ValueError):
            scoreboard_path("ncaaf",football_week=0,football_year=2026)
        self.assertEqual(scoreboard_path("ncaab",day="2026-11-04"),
                         "basketball-men/d1/2026/11/04/all-conf")


if __name__=="__main__":
    unittest.main()
