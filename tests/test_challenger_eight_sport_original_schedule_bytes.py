"""Synthetic original ESPN JSON byte archives for the eight-sport live capture."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import urlparse, parse_qs

from independent_schedule_review import ingest_schedule, SOURCES
from challenger_prospective_pregame import build
from challenger_all_sports_schedule_coverage import audit, main

NOW = datetime(2026, 11, 5, 17, tzinfo=timezone.utc)
END = NOW + timedelta(minutes=3)
GAME = "2026-11-08T18:00:00Z"


def game(eid="401101"):
    return {"id":eid,"date":GAME,"status":{"type":{"state":"pre"}},
            "competitions":[{"competitors":[
                {"homeAway":"home","team":{"displayName":"Detroit Lions"}},
                {"homeAway":"away","team":{"displayName":"Chicago Bears"}}
            ]}]}


def wire_fetch(url):
    p=urlparse(url)
    date=parse_qs(p.query)["dates"][0]
    source=[league for league,(sport,name) in SOURCES.items()
            if p.path.endswith("/"+sport+"/"+name+"/scoreboard")]
    if len(source)!=1:
        raise AssertionError("unexpected ESPN source")
    events=[game()] if source[0]=="nfl" and date=="20261108" else []
    data={"events":events,"original_wire_fixture":True}
    raw=(json.dumps(data,sort_keys=True,separators=(",",":"))+"\n").encode()
    return data,raw


def fresh(root,fetch=wire_fetch):
    raw_dir=Path(root)/"espn_original_schedule_bytes"
    s=ingest_schedule("2026-11-05",fetch=fetch,now=NOW,
                      clock=lambda:NOW,lookahead_days=3,
                      original_dir=raw_dir)
    records,report=build(s,[],[],None,END)
    return s,records,report,raw_dir


class EightSportOriginalSourceTests(unittest.TestCase):
    def test_original_responses_captured_and_validated_across_all_eight_sports(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            result=audit(s,r,rows,original_dir=path)
            self.assertTrue(s["original_source_bytes_capture_enabled"])
            self.assertEqual(result["totals"]["pregame_events_archived"],1)
            self.assertEqual(result["by_league"]["nfl"]["archived_pregame_games"],1)
            self.assertEqual(result["original_espn_source_responses_verified"],
                sum(v["days_retrieved"] for v in s["sources"].values()))
            self.assertEqual(result["certified_positive_ev_bets"],0)
            self.assertEqual(result["qualified_chronological_training_games"],0)
            self.assertFalse(result["original_source_hashes_independently_publisher_signed"])
            self.assertFalse(result["champion_001_modified"])

    def test_actual_wire_bytes_remain_intact_not_reformatted(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            q=s["sources"]["nfl"]["lookahead"][-1]
            raw=(path/q["original_source_file"]).read_bytes()
            self.assertTrue(raw.endswith(b"\n"))
            self.assertEqual(hashlib.sha256(raw).hexdigest(),q["original_source_sha256"])
            self.assertEqual(q["original_source_bytes"],len(raw))
            self.assertEqual(rows[0]["espn_original_schedule_sha256_research_only"],
                             q["original_source_sha256"])

    def test_original_archive_required_when_capture_flag_is_true(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            with self.assertRaisesRegex(ValueError,"original_espn_source_archive_required"):
                audit(s,r,rows)

    def test_original_bytes_changed_after_capture_are_rejected(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            p=path/s["sources"]["nfl"]["lookahead"][-1]["original_source_file"]
            p.write_bytes(p.read_bytes()+b" ")
            with self.assertRaisesRegex(ValueError,"original_espn_source_bytes_or_sha_mismatch"):
                audit(s,r,rows,original_dir=path)

    def test_original_file_missing_fails_closed(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            p=path/s["sources"]["nfl"]["lookahead"][-1]["original_source_file"]
            p.unlink()
            with self.assertRaises(FileNotFoundError):
                audit(s,r,rows,original_dir=path)

    def test_file_path_traversal_in_receipt_refused(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            s["sources"]["nfl"]["lookahead"][-1]["original_source_file"]="../../data.json"
            with self.assertRaisesRegex(ValueError,"invalid_original_espn_schedule_filename_or_hash"):
                audit(s,r,rows,original_dir=path)

    def test_fake_sha_label_cannot_match_original_source(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            s["sources"]["nfl"]["lookahead"][-1]["original_source_sha256"]="0"*64
            with self.assertRaisesRegex(ValueError,"original_espn_source_bytes_or_sha_mismatch"):
                audit(s,r,rows,original_dir=path)

    def test_edited_derived_espn_team_with_unchanged_source_is_rejected(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            s["events"][0]["home_team"]="Green Bay Packers"
            with self.assertRaisesRegex(ValueError,"archived_game_does_not_match_original_espn_event"):
                audit(s,r,rows,original_dir=path)

    def test_edited_derived_event_start_with_unchanged_source_is_rejected(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            s["events"][0]["start_utc"]="2026-11-08T19:00:00+00:00"
            with self.assertRaisesRegex(ValueError,"archived_game_does_not_match_original_espn_event"):
                audit(s,r,rows,original_dir=path)

    def test_edited_derived_sha_link_is_rejected(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            s["events"][0]["source_original_sha256"]="a"*64
            with self.assertRaisesRegex(ValueError,"archived_game_original_espn_sha_receipt_mismatch"):
                audit(s,r,rows,original_dir=path)

    def test_edited_raw_game_listing_counts_are_rejected(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            s["sources"]["nfl"]["lookahead"][-1]["raw_events_listed"]=3
            with self.assertRaisesRegex(ValueError,"original_espn_events_not_equal_saved_snapshot"):
                audit(s,r,rows,original_dir=path)

    def test_changed_archived_home_team_cannot_inherit_original_event_id(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            rows[0]["home_team"]="Green Bay Packers"
            with self.assertRaisesRegex(ValueError,"archived_game_does_not_match_original_espn_event"):
                audit(s,r,rows,original_dir=path)

    def test_changed_archived_away_team_cannot_inherit_original_event_id(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            rows[0]["away_team"]="Minnesota Vikings"
            with self.assertRaisesRegex(ValueError,"archived_game_does_not_match_original_espn_event"):
                audit(s,r,rows,original_dir=path)

    def test_changed_archived_kickoff_cannot_inherit_original_event_id(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            rows[0]["event_start_utc"]="2026-11-08T18:01:00+00:00"
            with self.assertRaisesRegex(ValueError,"archived_game_does_not_match_original_espn_event"):
                audit(s,r,rows,original_dir=path)

    def test_changed_archived_source_url_rejected_even_on_espn_host(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            rows[0]["schedule_source_url"]=(
                "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261109")
            with self.assertRaisesRegex(ValueError,"archived_game_does_not_match_original_espn_event"):
                audit(s,r,rows,original_dir=path)

    def test_changed_archived_observation_clock_rejected_even_before_game(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            rows[0]["schedule_observed_at_utc"]=(NOW+timedelta(seconds=30)).isoformat()
            with self.assertRaisesRegex(ValueError,"archived_game_does_not_match_original_espn_event"):
                audit(s,r,rows,original_dir=path)

    def test_missing_original_sha_link_in_archived_game_fails_closed(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            rows[0]["espn_original_schedule_sha256_research_only"]=None
            with self.assertRaisesRegex(ValueError,"archived_game_original_espn_sha_receipt_mismatch"):
                audit(s,r,rows,original_dir=path)

    def test_forged_original_sha_link_in_archived_game_fails_closed(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            rows[0]["espn_original_schedule_sha256_research_only"]="f"*64
            with self.assertRaisesRegex(ValueError,"archived_game_original_espn_sha_receipt_mismatch"):
                audit(s,r,rows,original_dir=path)

    def test_snapshot_completion_timestamp_must_match_report_exactly(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            rows[0]["snapshot_completed_at_utc"]=(END-timedelta(seconds=30)).isoformat()
            with self.assertRaisesRegex(ValueError,"archive_record_timestamp_not_pregame"):
                audit(s,r,rows,original_dir=path)

    def test_prospective_report_claimed_total_must_equal_archived_rows(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            r["scheduled_pregame_events"]=2
            with self.assertRaisesRegex(ValueError,"prospective_report_total_does_not_match_original_archive"):
                audit(s,r,rows,original_dir=path)

    def test_verified_exact_original_game_field_count_matches_archived_rows(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            result=audit(s,r,rows,original_dir=path)
            self.assertEqual(result["archived_games_matching_exact_original_event_fields"],1)
            self.assertEqual(result["totals"]["pregame_events_archived"],1)
            self.assertEqual(result["certified_positive_ev_bets"],0)
            self.assertFalse(result["champion_001_modified"])

    def test_reconstructed_json_payload_without_original_wire_bytes_refused(self):
        with TemporaryDirectory() as tmp:
            def parsed_only(url):
                return wire_fetch(url)[0]
            s=ingest_schedule("2026-11-05",fetch=parsed_only,
                       now=NOW,clock=lambda:NOW,lookahead_days=0,
                       original_dir=Path(tmp)/"original")
            self.assertEqual(s["sources"]["nfl"]["days_unavailable"],1)
            self.assertEqual(s["sources"]["nfl"]["lookahead"][0]["reason"],"ValueError")
            self.assertFalse(list((Path(tmp)/"original").glob("*.json")))

    def test_structurally_different_supplied_parsed_and_wire_views_refused(self):
        with TemporaryDirectory() as tmp:
            def inconsistent(url):
                payload,raw=wire_fetch(url)
                payload["forged"]="new field"
                return payload,raw
            s=ingest_schedule("2026-11-05",fetch=inconsistent,now=NOW,
                              clock=lambda:NOW,lookahead_days=0,
                              original_dir=Path(tmp)/"original")
            self.assertEqual(s["sources"]["nfl"]["days_unavailable"],1)
            self.assertEqual(s["sources"]["nfl"]["lookahead"][0]["reason"],"ValueError")

    def test_legacy_diagnostic_fixture_without_original_archive_still_uncertified(self):
        def fetch(url):
            return wire_fetch(url)[0]
        s=ingest_schedule("2026-11-05",fetch=fetch,now=NOW,
                          clock=lambda:NOW,lookahead_days=3)
        records,r=build(s,[],[],None,END)
        result=audit(s,r,records)
        self.assertFalse(s["original_source_bytes_capture_enabled"])
        self.assertEqual(result["original_espn_source_responses_verified"],0)
        self.assertEqual(result["certified_champion_001_predictions"],0)

    def test_research_report_cli_reads_original_sources_from_capture_dir(self):
        with TemporaryDirectory() as tmp:
            s,rows,r,path=fresh(tmp)
            base=Path(tmp)
            (base/"espn_schedule_capture.json").write_text(json.dumps(s))
            (base/"prospective_report.json").write_text(json.dumps(r))
            (base/"prospective_event_evidence.jsonl").write_text(
                "".join(json.dumps(x)+"\n" for x in rows))
            self.assertEqual(main(["--capture-dir",tmp]),0)
            result=json.loads((base/"eight_sport_schedule_coverage.json").read_text())
            self.assertEqual(result["original_espn_source_responses_verified"],
                sum(v["days_retrieved"] for v in s["sources"].values()))
            self.assertEqual(result["bet_ready_selections"],0)
            self.assertEqual(result["automated_bets_placed"],0)


if __name__=="__main__":
    unittest.main()
