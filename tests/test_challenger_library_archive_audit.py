"""Offline synthetic checks for recovered user-owned history archives."""
import hashlib
import io
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
import zipfile

from challenger_library_archive_audit import (
    LEAGUES, audit_history, audit_legacy,
)


def archive(folder, tamper=None, training=False):
    root = Path(folder)
    db = root / "source.sqlite"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE published_games(
            league TEXT,season TEXT,espn_event_id TEXT,start_utc TEXT,
            home_score INTEGER,away_score INTEGER,published_result TEXT,
            bookmaker_settlement_verified INTEGER,
            independent_outcome_adjudication INTEGER,
            historically_qualified_training INTEGER);
        CREATE TABLE source_observations(
            league TEXT,espn_event_id TEXT,run_id TEXT,retrieved_at_utc TEXT,
            eligible_for_training INTEGER);
        CREATE TABLE archive_windows(run_id TEXT,league TEXT);
        CREATE TABLE conflicting_events(league TEXT,espn_event_id TEXT);
    """)
    for i, league in enumerate(LEAGUES):
        event = str(400000000 + i)
        con.execute(
            "INSERT INTO published_games VALUES(?,?,?,?,?,?,?,?,?,?)",
            (league, "2025-26", event, "2026-11-01T22:00:00Z",
             104, 99, "home", 0, 0, int(training and i == 0)))
        con.execute(
            "INSERT INTO source_observations VALUES(?,?,?,?,?)",
            (league, event, "888", "2026-11-02T03:00:00Z", 0))
        con.execute("INSERT INTO archive_windows VALUES(?,?)", ("888", league))
    con.commit()
    con.close()
    contents = {
        "historical_published_scores.sqlite": db.read_bytes(),
        "history_coverage.json": json.dumps({
            "stage":"challenger_multiseason_published_score_sqlite_research_only",
            "published_games_deduplicated":8,"consistent_repeated_observations":0,
            "archive_windows_accepted":8,"archives_rejected":0,
            "distinct_gitHub_run_ids":1,
            "conflicting_event_ids_quarantined":0,
            "independently_qualified_training_records":0,
            "champion_001_modified":False}).encode(),
        "champion_authentication.json": json.dumps({
            "original_executable_verified":False,
            "immutable_model_version_authenticated":False,
            "reproducible_reference_outputs_verified":False,
            "champion_001_modified":False}).encode(),
        "oos_calibration_report.json":json.dumps({
            "certified_groups":0,"rows_received":0}).encode(),
        "independently_qualified_holdout.jsonl":b"",
    }
    members = [
        {"name":name,"sha256":hashlib.sha256(raw).hexdigest(),
         "bytes":len(raw)} for name,raw in contents.items()
        if name!="independently_qualified_holdout.jsonl"
    ]
    contents["artifact_integrity_manifest.json"]=json.dumps({
        "artifacts":members,"externally_signed":False,
        "independently_authenticated":False,
        "champion_001_modified":False}).encode()
    if tamper:
        contents[tamper] += b"tampered"
    target = root / "research.zip"
    with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as z:
        for name,raw in contents.items():
            z.writestr(name,raw)
    return target


class ArchiveAuditTests(unittest.TestCase):
    def test_real_source_semantics_stay_research_only(self):
        with TemporaryDirectory() as tmp:
            result = audit_history(archive(tmp))
            self.assertEqual(result["deduplicated_historical_games"],8)
            self.assertEqual(result["archived_source_observations"],8)
            self.assertEqual(result["source_observations_retrieved_after_or_at_game_start"],8)
            self.assertEqual(result["qualified_chronological_training_games"],0)
            self.assertEqual(result["certified_positive_ev_bets"],0)
            self.assertFalse(result["original_hashes_independently_publisher_signed"])
            self.assertFalse(result["champion_001_modified"])

    def test_hash_tampering_is_not_accepted(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"tampered_original_archive_bytes"):
                audit_history(archive(tmp,tamper="history_coverage.json"))

    def test_self_proclaimed_model_training_row_rejected(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"unverified_historical_result_attempted_promotion"):
                audit_history(archive(tmp,training=True))

    def test_old_provider_timestamp_cannot_become_dk_quote(self):
        with TemporaryDirectory() as tmp:
            target=Path(tmp)/"legacy.zip"
            with zipfile.ZipFile(target,"w") as z:
                z.writestr("01_historical_game_results.csv",
                           "status,start_time_is_actual_confirmed\nFINAL,NO\n")
                z.writestr("03_archived_quotes_TIMESTAMP_BEFORE_START_UNCONFIRMED.csv",
                           "pregame_confirmed,usable_for_model_backtest,sportsbook\nNO,NO,draftkings\n")
            result=audit_legacy(target)
            self.assertEqual(result["legacy_result_rows_not_merged"],1)
            self.assertEqual(result["draftkings_labeled_unconfirmed"],1)
            self.assertEqual(result["direct_draftkings_checkout_quotes_verified"],0)

    def test_pregame_flag_promoted_to_true_fails_closed(self):
        with TemporaryDirectory() as tmp:
            target=Path(tmp)/"legacy.zip"
            with zipfile.ZipFile(target,"w") as z:
                z.writestr("01_historical_game_results.csv",
                           "status,start_time_is_actual_confirmed\nFINAL,NO\n")
                z.writestr("03_archived_quotes_TIMESTAMP_BEFORE_START_UNCONFIRMED.csv",
                           "pregame_confirmed,usable_for_model_backtest,sportsbook\nYES,YES,draftkings\n")
            with self.assertRaisesRegex(ValueError,"legacy_quotes_cannot_be_promoted"):
                audit_legacy(target)


if __name__=="__main__":
    unittest.main()
