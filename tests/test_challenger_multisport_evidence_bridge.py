"""Synthetic-only tests; these are not actual games or verified model training."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_multisport_evidence_bridge import (
    LEAGUES, BINARY_RESEARCH, THREE_WAY_RESEARCH, build_review_queue, main,
)

NOW = datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)


def form(tag):
    return {
        "last_games": 3, "prior_espn_event_ids": [str(i) for i in range(tag, tag+3)],
        "source_urls": ["https://site.api.espn.com/scoreboard"] * 3,
        "win_rate": 0.666667, "margin_average": 3.5,
        "retrieval_asof_utc": "2026-10-29T21:20:00Z",
        "result_start_embargo_hours": 48,
        "historical_original_publication_times_verified": False,
    }


def snapshot(league="nba", eid="401001"):
    return {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": league, "espn_schedule_event_id": eid,
        "home_team": "Example Home", "away_team": "Example Away",
        "event_start_utc": "2026-10-30T00:00:00Z",
        "snapshot_completed_at_utc": "2026-10-29T21:30:00Z",
        "schedule_observed_at_utc": "2026-10-29T21:29:00Z",
        "schedule_source_url": "https://site.api.espn.com/scoreboard",
        "team_form_available_for_both_teams": True,
        "home_team_form": form(100), "away_team_form": form(200),
        "odds_observations": [],
        "certified_prediction": False, "model_probability": None,
        "qualified_for_challenger_backtest": False,
        "bet_ready": False, "champion_001_modified": False,
    }


def linked(snap, result="home"):
    home, away = {"home": (103, 99), "away": (98, 103), "draw": (1, 1)}[result]
    return {
        "league": snap["league"], "espn_event_id": snap["espn_schedule_event_id"],
        "status": "linked_to_espn_published_final_only",
        "snapshot_completed_at_utc": "2026-10-29T21:30:00+00:00",
        "event_start_utc": snap["event_start_utc"],
        "home_team": snap["home_team"], "away_team": snap["away_team"],
        "both_teams_form_available_at_capture": True,
        "published_outcome": {
            "home": home, "away": away, "result": result,
            "published_retrieved_at_utc": "2026-10-30T06:00:00Z",
            "source_url": "https://site.api.espn.com/scoreboard",
        },
        "independent_league_outcome_verified": False,
        "model_prediction_at_capture": None,
        "qualified_for_challenger_backtest": False,
        "bet_ready": False, "champion_001_modified": False,
    }


class MultisportBridgeTests(unittest.TestCase):
    def test_all_eight_leagues_represented_separately(self):
        ss, ls = [], []
        for i, league in enumerate(LEAGUES):
            s = snapshot(league, str(401000+i))
            ss.append(s)
            ls.append(linked(s, result="draw" if league in THREE_WAY_RESEARCH else "home"))
        results, report = build_review_queue(ss, ls, NOW)
        self.assertEqual(len(results), 8)
        self.assertEqual(set(report["by_league"]), set(LEAGUES))
        self.assertEqual(report["review_queue_records"], 8)
        self.assertEqual(report["independently_verified_training_records"], 0)
        self.assertTrue(all(r["qualified_for_challenger_backtest"] is False for r in results))
        self.assertTrue(all(r["model_probability"] is None for r in results))
        self.assertTrue(all(not r["eligible_to_train_probability_model"] for r in results))
        self.assertFalse(report["champion_001_modified"])

    def test_soccer_draw_is_three_way_not_binary(self):
        for league in THREE_WAY_RESEARCH:
            s=snapshot(league)
            rows,_=build_review_queue([s],[linked(s, "draw")],NOW)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["published_result_research_label"],"draw")
            self.assertEqual(rows[0]["research_target"],"published_score_three_way_research")
            self.assertIn("three_way",rows[0]["review_status"])

    def test_binary_draw_quarantined(self):
        for league in BINARY_RESEARCH:
            s=snapshot(league)
            r,report=build_review_queue([s],[linked(s,"draw")],NOW)
            self.assertEqual(r,[])
            self.assertEqual(report["by_league"][league]["unexpected_draw_no_binary_moneyline_label"],1)

    def test_past_tipoff_snapshot_rejected(self):
        s=snapshot()
        s["snapshot_completed_at_utc"]="2026-10-30T00:00:01Z"
        r,report=build_review_queue([s],[linked(s)],NOW)
        self.assertEqual(r,[])
        self.assertEqual(report["by_league"]["nba"]["invalid_capture"],1)

    def test_feature_asof_future_rejected(self):
        s=snapshot()
        s["home_team_form"]["retrieval_asof_utc"]="2026-11-01T00:00:00Z"
        r,report=build_review_queue([s],[linked(s)],NOW)
        self.assertEqual(r,[])
        self.assertEqual(report["by_league"]["nba"]["missing_or_unverified_form"],1)

    def test_unavailable_form_does_not_impute(self):
        s=snapshot()
        s["away_team_form"]=None
        r,_=build_review_queue([s],[linked(s)],NOW)
        self.assertEqual(r,[])

    def test_mismatched_linked_result_rejected(self):
        s=snapshot()
        l=linked(s)
        l["home_team"]="Bad Home"
        r,report=build_review_queue([s],[l],NOW)
        self.assertEqual(r,[])
        self.assertEqual(report["by_league"]["nba"]["not_linked_or_untrusted_final"],1)

    def test_duplicate_links_cannot_choose_arbitrary_final(self):
        s=snapshot()
        r,report=build_review_queue([s],[linked(s), linked(s)],NOW)
        self.assertEqual(r,[])
        self.assertEqual(report["by_league"]["nba"]["missing_or_duplicate_linked_result"],1)

    def test_duplicate_same_time_conflicting_snapshots_fails_closed(self):
        s=snapshot()
        altered=deepcopy(s)
        altered["home_team_form"]["win_rate"]=0.1
        r,report=build_review_queue([s,altered],[linked(s)],NOW)
        self.assertEqual(r,[])
        self.assertEqual(report["by_league"]["nba"]["conflicting_same_time_capture"],1)

    def test_earliest_valid_snapshot_only(self):
        s=snapshot()
        newer=deepcopy(s)
        newer["snapshot_completed_at_utc"]="2026-10-29T22:00:00Z"
        r,report=build_review_queue([newer,s],[linked(s)],NOW)
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]["snapshot_utc"],"2026-10-29T21:30:00+00:00")

    def test_unsupported_league_not_silently_enabled(self):
        s=snapshot("wnba")
        r,report=build_review_queue([s],[linked(s)],NOW)
        self.assertEqual(r,[])
        self.assertEqual(report["rejected"]["unsupported_sport"],1)

    def test_never_promote_flagged_review_records(self):
        s=snapshot()
        l=linked(s)
        l["qualified_for_challenger_backtest"]=True
        r,_=build_review_queue([s],[l],NOW)
        self.assertEqual(r,[])

    def test_empty_evidence_outputs_blocked_queue(self):
        r,report=build_review_queue([],[],NOW)
        self.assertEqual(r,[])
        self.assertEqual(report["review_queue_records"],0)
        self.assertEqual(report["trained_models_created"],0)
        self.assertEqual(report["bet_ready_selections"],0)

    def test_cli_produces_review_queue_not_training_dataset(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            snap=root/"captures"/"run-1"
            snap.mkdir(parents=True)
            s=snapshot()
            (snap/"prospective_event_evidence.jsonl").write_text(json.dumps(s)+"\n")
            link=root/"linked_pregame_outcomes.jsonl"
            link.write_text(json.dumps(linked(s))+"\n")
            dest=root/"out"
            self.assertEqual(main(["--snapshot-root",str(root/"captures"),
                                   "--linked-results",str(link),
                                   "--output-dir",str(dest)]),0)
            report=json.loads((dest/"all_sports_evidence_report.json").read_text())
            self.assertEqual(report["review_queue_records"],1)
            self.assertFalse((dest/"historical_results.jsonl").exists())
            self.assertEqual(report["certified_champion_001_predictions"],0)


if __name__=="__main__":
    unittest.main()
