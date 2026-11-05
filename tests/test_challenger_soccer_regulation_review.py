"""Synthetic-only soccer market-scope tests; never test by using real bets."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_soccer_regulation_review import (
    plan, read_source, request_url, review, run, main, LEAGUE_CODES)

NOW = datetime(2026, 11, 5, 13, 0, tzinfo=timezone.utc)


def original(league="mls", decided="regulation", state="final", when=None,
             mismatch=False, dup=False, source_home=None):
    mls = league == "mls"
    kickoff = when or ("2026-11-04T23:00:00Z" if mls else "2026-11-04T20:00:00Z")
    if mls:
        name_h, name_a = source_home or "Inter Miami CF", "Atlanta United"
        parts = {"home": [1, 1], "away": [0, 1]}
    else:
        name_h, name_a = source_home or "Arsenal", "Bayern Munich"
        parts = {"home": [0, 1], "away": [1, 0]}
    if decided != "regulation":
        parts["home"].extend([1, 0] if decided == "extra_time" else [0, 0])
        parts["away"].extend([0, 0])
    row = {
        "game_id": ("mls" if mls else "ucl") + "-20261104-unique001",
        "league": "mls" if mls else "ucl", "date": "2026-11-04",
        "start_time": kickoff, "status": state,
        "home_team": {"name": name_h, "team_id": "soccer-home"},
        "away_team": {"name": name_a, "team_id": "soccer-away"},
        "home_score": sum(parts["home"]) + (1 if mismatch else 0),
        "away_score": sum(parts["away"]),
        "period_scores": parts, "decided_in": decided,
        "penalty_scores": {"home": 5, "away": 4} if decided == "penalties" else None,
        "winner": "soccer-home",
        "updated_at": "2026-11-05T04:00:00Z",
    }
    if state != "final":
        row.update({"home_score": None, "away_score": None,
                    "period_scores": None, "decided_in": None, "updated_at": None})
    return json.dumps([row, deepcopy(row)] if dup else [row]).encode()


def packet(league="mls", espn_id="4011234", extra=False):
    mls = league == "mls"
    fh, fa = ("Inter Miami CF", "Atlanta United FC") if mls else ("Arsenal", "Bayern Munich")
    start = "2026-11-04T23:00:00Z" if mls else "2026-11-04T20:00:00Z"
    goals = (2, 1) if mls or extra else (1, 1)
    return {
        "record_type": "challenger_original_bytes_feature_lineage_review_only",
        "league": league, "event_id": espn_id,
        "home_team": fh, "away_team": fa,
        "event_start_utc": start,
        "snapshot_completed_at_utc": "2026-11-04T18:00:00Z",
        "original_bytes_match_same_run_receipt": True,
        "same_run_receipt_independently_authenticated": False,
        "independent_outcome_review": False,
        "market_settlement_rules_verified": False,
        "qualified_for_challenger_training": False,
        "model_probability": None, "certified_prediction": False,
        "bet_ready": False, "champion_001_modified": False,
        "published_final_only": {
            "home_score": goals[0], "away_score": goals[1],
            "published_result": "home" if goals[0] > goals[1] else "draw",
            "published_at_observation_utc": "2026-11-05T05:00:00Z",
            "source_url": "https://site.api.espn.com/scoreboard",
        },
    }


class SoccerRegulationReviewTests(unittest.TestCase):
    def test_mls_regulation_score_separate_publisher_agrees_unqualified(self):
        raw = original()
        items, report = review([packet()], {"mls:2026-11-04": raw}, NOW)
        self.assertEqual(items[0]["crosscheck_status"],
                         "regulation_score_agrees_with_espn_published_score_research_only")
        self.assertEqual(items[0]["source_regulation_90min_result"], "home")
        self.assertEqual(items[0]["provider_original_bytes_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(report["regulation_score_published_agreements"]["mls"], 1)
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertFalse(items[0]["qualified_for_challenger_training"])

    def test_ucl_extra_time_winner_is_not_90min_winner(self):
        rows, report = review(
            [packet("uefa_champions_league", extra=True)],
            {"uefa_champions_league:2026-11-04": original("uefa_champions_league", "extra_time")}, NOW)
        self.assertEqual(rows[0]["source_regulation_90min_result"], "draw")
        self.assertEqual(rows[0]["source_regulation_90min_score"], {"home": 1, "away": 1})
        self.assertEqual(rows[0]["source_final_including_extra_time"], {"home": 2, "away": 1})
        self.assertEqual(rows[0]["crosscheck_status"],
                         "ninety_minute_score_secondary_only_after_extra_time_or_penalties")
        self.assertEqual(report["regulation_score_published_agreements"]["uefa_champions_league"], 0)

    def test_ucl_penalty_shootout_winner_not_used_as_three_way_result(self):
        rows, _ = review(
            [packet("uefa_champions_league")],
            {"uefa_champions_league:2026-11-04": original("uefa_champions_league", "penalties")}, NOW)
        self.assertEqual(rows[0]["source_regulation_90min_result"], "draw")
        self.assertEqual(rows[0]["crosscheck_status"],
                         "ninety_minute_score_secondary_only_after_extra_time_or_penalties")
        self.assertFalse(rows[0]["bookmaker_three_way_settlement_verified"])

    def test_no_api_key_means_no_network_calls_and_no_fake_results(self):
        calls = []
        rows, report, originals = run([packet()], key=None,
                                      fetcher=lambda *args: calls.append(args), now=NOW)
        self.assertEqual(calls, [])
        self.assertFalse(report["api_key_configured"])
        self.assertEqual(rows[0]["crosscheck_status"], "external_api_key_not_configured")
        self.assertEqual(originals, {})

    def test_real_fetch_path_is_bounded_and_league_specific(self):
        urls = [request_url("mls", "2026-11-04"),
                request_url("uefa_champions_league", "2026-11-04")]
        self.assertIn("league=mls", urls[0])
        self.assertIn("league=ucl", urls[1])
        self.assertEqual(len(plan([packet(), packet("uefa_champions_league")], NOW)), 2)

    def test_duplicate_provider_event_ids_reject_entire_response(self):
        rows, report = review([packet()], {"mls:2026-11-04": original(dup=True)}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "invalid_soccer_source_ValueError")
        self.assertEqual(report["regulation_score_published_agreements"]["mls"], 0)

    def test_nonfinal_or_postponed_no_result(self):
        rows, _ = review([packet()], {"mls:2026-11-04": original(state="scheduled")}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "publisher_event_not_final")

    def test_extra_time_score_period_sum_validation_fails_closed(self):
        rows, _ = review([packet("uefa_champions_league", extra=True)],
                         {"uefa_champions_league:2026-11-04": original("uefa_champions_league", "extra_time", mismatch=True)}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "invalid_soccer_source_ValueError")

    def test_invalid_penalty_scores_rejected(self):
        obj = json.loads(original("uefa_champions_league", "penalties"))
        obj[0]["penalty_scores"] = None
        rows, _ = review([packet("uefa_champions_league")],
                         {"uefa_champions_league:2026-11-04": json.dumps(obj).encode()}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "invalid_soccer_source_ValueError")

    def test_team_name_mismatch_never_fuzzy_matches(self):
        rows, _ = review([packet()], {"mls:2026-11-04": original(source_home="Miami")}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "no_exact_team_and_kickoff_match")

    def test_out_of_window_kickoff_not_accepted(self):
        rows, _ = review([packet()], {"mls:2026-11-04": original(when="2026-11-04T21:00:00Z")}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"], "no_exact_team_and_kickoff_match")

    def test_one_publisher_event_cannot_back_two_different_espn_ids(self):
        rows, report = review([packet(), packet(espn_id="4019999")],
                              {"mls:2026-11-04": original()}, NOW)
        self.assertEqual([x["crosscheck_status"] for x in rows],
                         ["publisher_game_linked_to_multiple_espn_ids"] * 2)
        self.assertEqual(report["regulation_score_published_agreements"]["mls"], 0)

    def test_espn_score_and_publisher_score_disagree(self):
        p = packet()
        p["published_final_only"].update({"home_score": 3, "published_result": "home"})
        rows, _ = review([p], {"mls:2026-11-04": original()}, NOW)
        self.assertEqual(rows[0]["crosscheck_status"],
                         "separate_published_full_match_scores_disagree")

    def test_unsafe_model_promotion_rejected_before_external_fetch(self):
        p = packet()
        p["qualified_for_challenger_training"] = True
        calls = []
        with self.assertRaisesRegex(ValueError, "unsafe_soccer_original"):
            run([p], key="fake-key", fetcher=lambda *args: calls.append(args), now=NOW)
        self.assertEqual(calls, [])

    def test_missing_espn_final_does_not_call_api(self):
        p = packet()
        p["published_final_only"] = None
        calls = []
        rows, report, raws = run([p], key="fake", fetcher=lambda *a: calls.append(a), now=NOW)
        self.assertFalse(calls)
        self.assertEqual(rows[0]["crosscheck_status"], "missing_espn_published_final")
        self.assertFalse(raws)

    def test_invalid_source_does_not_create_regulation_score(self):
        rows, _ = review([packet()], {"mls:2026-11-04": b"not json"}, NOW)
        self.assertIsNone(rows[0]["source_regulation_90min_score"])
        self.assertTrue(rows[0]["crosscheck_status"].startswith("invalid_soccer_source_"))

    def test_cli_missing_api_key_still_creates_quarantine_reports(self):
        with TemporaryDirectory() as temp:
            src = Path(temp) / "lineage.jsonl"
            src.write_text(json.dumps(packet()) + "\n")
            import os
            old = os.environ.pop("API_NINJAS_KEY", None)
            try:
                self.assertEqual(main(["--lineage", str(src), "--output-dir", str(Path(temp) / "out")]), 0)
            finally:
                if old is not None:
                    os.environ["API_NINJAS_KEY"] = old
            report = json.loads((Path(temp) / "out" / "soccer_90min_second_source_report.json").read_text())
            self.assertEqual(report["certified_positive_ev_bets"], 0)
            self.assertEqual(report["source_requests_attempted"], 0)
            self.assertFalse((Path(temp) / "out" / "soccer_second_source_original_bytes").exists())

    def test_valid_source_bytes_archived_without_creating_bets(self):
        with TemporaryDirectory() as temp:
            src = Path(temp) / "lineage.jsonl"
            src.write_text(json.dumps(packet()) + "\n")
            # The CLI obtains secrets from the environment, not from the JSONL.
            # The pure run() path instead exercises a fake offline fixture.
            rows, report, original_bytes = run([packet()], key="synthetic", now=NOW,
                fetcher=lambda league, day, key: original())
            self.assertEqual(original_bytes["mls:2026-11-04"], original())
            self.assertEqual(report["bet_ready_selections"], 0)
            self.assertFalse(rows[0]["independent_league_official_regulation_result_authenticated"])


if __name__ == "__main__":
    unittest.main()
