"""Synthetic lineage-only regression tests: no actual qualified training records."""
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from challenger_multisport_original_bytes_lineage import archive_rows, assemble, main
from challenger_prospective_receipts import make_receipt
from challenger_multisport_native_training import train

AT = datetime(2026, 10, 29, 21, 40, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 1, 13, 0, tzinfo=timezone.utc)


def form():
    return {"last_games": 3, "win_rate": 2 / 3,
            "margin_average": 3.0, "prior_espn_event_ids": ["121","122","123"],
            "source_urls": ["https://site.api.espn.com/scoreboard"] * 3,
            "retrieval_asof_utc": "2026-10-29T21:30:00Z",
            "result_start_embargo_hours": 48,
            "historical_original_publication_times_verified": False}


def snap(league="nfl", event="401001", features=True):
    return {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": league, "espn_schedule_event_id": event,
        "home_team": "Fictional Home", "away_team": "Fictional Away",
        "event_start_utc": "2026-10-30T00:00:00Z",
        "snapshot_completed_at_utc": "2026-10-29T21:30:00Z",
        "schedule_observed_at_utc": "2026-10-29T21:29:00Z",
        "schedule_source_url": "https://site.api.espn.com/scoreboard",
        "home_team_form": form() if features else None,
        "away_team_form": form() if features else None,
        "team_form_available_for_both_teams": features,
        "odds_observations": [], "certified_prediction": False,
        "model_probability": None, "qualified_for_challenger_backtest": False,
        "bet_ready": False, "champion_001_modified": False,
    }


def link(league="nfl", event="401001", result="home", features=True):
    return {
        "league": league, "espn_event_id": event,
        "status": "linked_to_espn_published_final_only",
        "snapshot_completed_at_utc": "2026-10-29T21:30:00Z",
        "event_start_utc": "2026-10-30T00:00:00Z",
        "home_team": "Fictional Home", "away_team": "Fictional Away",
        "both_teams_form_available_at_capture": features,
        "published_outcome": {
            "home": 1, "away": 1 if result == "draw" else 0,
            "result": result,
            "published_retrieved_at_utc": "2026-10-30T07:00:00Z",
            "source_url": "https://site.api.espn.com/scoreboard",
        },
        "independent_league_outcome_verified": False,
        "qualified_for_challenger_backtest": False,
        "model_prediction_at_capture": None, "bet_ready": False,
        "champion_001_modified": False,
    }


def save_archive(root, items, run_id="5312", altered=False):
    path = Path(root)/run_id
    path.mkdir(parents=True, exist_ok=True)
    original = "".join(json.dumps(r, sort_keys=True) + "\n" for r in items).encode()
    receipt = make_receipt(original, run_id, AT)
    (path/"point_in_time_receipt.json").write_text(json.dumps(receipt))
    (path/"prospective_event_evidence.jsonl").write_bytes(
        original.replace(b"Fictional Home", b"Fictional Wrong") if altered else original)


class OriginalLineageTests(unittest.TestCase):
    def test_real_bytes_produced_research_packet_without_training_promotion(self):
        with TemporaryDirectory() as temp:
            save_archive(temp, [snap()])
            source, counts = archive_rows(temp, NOW)
            rows, summary = assemble(source, [link()], NOW, counts)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertIsNotNone(row["asof_features_for_manual_review_only"])
            self.assertEqual(row["published_final_only"]["published_result"], "home")
            self.assertIn("independent_original_capture_authentication", row["missing_evidence"])
            self.assertFalse(row["qualified_for_challenger_training"])
            self.assertFalse(row["same_run_receipt_independently_authenticated"])
            self.assertEqual(summary["independently_qualified_training_examples"], 0)
            with self.assertRaisesRegex(ValueError, "only_manual"):
                train(rows, now=NOW)

    def test_no_archived_receipt_means_no_review_events(self):
        with TemporaryDirectory() as temp:
            folder=Path(temp)/"5312"
            folder.mkdir()
            (folder/"prospective_event_evidence.jsonl").write_text(json.dumps(snap())+"\n")
            source, stats = archive_rows(temp, NOW)
            self.assertEqual(len(source), 0)
            self.assertEqual(stats["archives_missing_receipt_or_numeric_run_id"], 1)

    def test_tampered_original_file_is_excluded(self):
        with TemporaryDirectory() as temp:
            save_archive(temp, [snap()], altered=True)
            source, stats = archive_rows(temp, NOW)
            self.assertFalse(source)
            self.assertEqual(stats["archives_invalid_receipt_or_bytes"], 1)

    def test_missing_final_blocks_no_fabricated_results(self):
        with TemporaryDirectory() as temp:
            save_archive(temp,[snap()])
            source, stats = archive_rows(temp, NOW)
            rows,_ = assemble(source, [], NOW, stats)
            self.assertIsNone(rows[0]["published_final_only"])
            self.assertIn("missing_or_ambiguous_published_final_link", rows[0]["missing_evidence"])

    def test_missing_pregame_form_cannot_generate_numeric_features(self):
        with TemporaryDirectory() as temp:
            save_archive(temp, [snap(features=False)])
            source,_=archive_rows(temp, NOW)
            rows,_=assemble(source, [link(features=False)], NOW)
            self.assertIsNone(rows[0]["asof_features_for_manual_review_only"])
            self.assertIn("pregame_team_form_missing_or_invalid",rows[0]["missing_evidence"])

    def test_soccer_three_way_requires_regulation_settlement(self):
        with TemporaryDirectory() as temp:
            save_archive(temp,[snap("mls")])
            source,_=archive_rows(temp,NOW)
            rows,_=assemble(source,[link("mls",result="draw")],NOW)
            self.assertIn("soccer_regulation_90_minute_result_unverified",rows[0]["missing_evidence"])
            self.assertFalse(rows[0]["market_settlement_rules_verified"])

    def test_duplicated_links_block_linked_final(self):
        with TemporaryDirectory() as temp:
            save_archive(temp,[snap()])
            source,_=archive_rows(temp,NOW)
            rows,_=assemble(source,[link(),link()],NOW)
            self.assertIsNone(rows[0]["published_final_only"])
            self.assertIn("missing_or_ambiguous_published_final_link",rows[0]["missing_evidence"])

    def test_all_eight_leagues_have_separate_provenance_review(self):
        leagues=("nba","nfl","mlb","nhl","ncaaf","ncaab","mls","uefa_champions_league")
        with TemporaryDirectory() as temp:
            save_archive(temp,[snap(l,str(401100+i)) for i,l in enumerate(leagues)])
            source,_=archive_rows(temp,NOW)
            rows,report=assemble(source,[link(l,str(401100+i)) for i,l in enumerate(leagues)],NOW)
            self.assertEqual(len(rows),8)
            self.assertEqual(set(x["league"] for x in rows),set(leagues))
            self.assertEqual(report["certified_champion_001_predictions"],0)
            self.assertEqual(report["model_artifacts_emitted"],0)
            self.assertEqual(report["player_prop_models_emitted"],0)

    def test_cli_writes_only_nontraining_review_files(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            save_archive(root/"sources",[snap()])
            links=root/"links.jsonl"
            links.write_text(json.dumps(link())+"\n")
            self.assertEqual(main(["--snapshot-root",str(root/"sources"),
                                   "--linked-results",str(links),
                                   "--output-dir",str(root/"out")]),0)
            self.assertEqual(sorted(x.name for x in (root/"out").iterdir()),[
                "original_bytes_lineage_report.json", "original_bytes_lineage_review.jsonl"])
            self.assertFalse((root/"out"/"challenger_reviewed_pregame_games.jsonl").exists())


if __name__=="__main__":
    unittest.main()
