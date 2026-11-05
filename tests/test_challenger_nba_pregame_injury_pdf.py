"""Offline fixture tests for official NBA original injury PDF evidence capture."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from challenger_nba_pregame_injury_pdf import (
    INDEX_URL, MAX_INDEX_BYTES, MAX_PDF_BYTES, assemble, main, pick_index_report,
    report_label_from_url, run,
)

NOW = datetime(2026, 11, 5, 13, 0, tzinfo=timezone.utc)
PDF7 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-05_07_30AM.pdf"
PDF6 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-05_06_00AM.pdf"
PDF9 = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-05_09_00AM.pdf"
PDF = b"%PDF-1.7\n" + b"source original bytes research only\n" * 10 + b"%%EOF\n"


def html(*urls):
    return ("<html><body>" + "".join(f'<a href="{x}">Report PDF</a>' for x in urls)
            + "</body></html>").encode()


def future(eventid="401999000", start="2026-11-05T23:00:00Z",
           observed="2026-11-05T12:00:00Z"):
    return {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": "nba", "espn_schedule_event_id": eventid,
        "home_team": "Boston Celtics", "away_team": "New York Knicks",
        "event_start_utc": start, "snapshot_completed_at_utc": observed,
        "player_level_status_parsed_and_verified": False,
        "qualified_for_challenger_backtest": False, "model_probability": None,
        "certified_prediction": False, "bet_ready": False,
        "champion_001_modified": False,
    }


class NBAPregameInjuryPDFTests(unittest.TestCase):
    def test_latest_pdf_before_capture_no_future_link(self):
        chosen = pick_index_report(html(PDF6, PDF7, PDF9), NOW)
        self.assertEqual(chosen[1], PDF7)
        self.assertEqual(chosen[0], datetime(2026,11,5,12,30,tzinfo=timezone.utc))

    def test_original_index_and_pdf_stored_as_observed_not_active_roster(self):
        def fake(url, limit):
            self.assertIn(limit,(MAX_INDEX_BYTES,MAX_PDF_BYTES))
            return html(PDF7) if url==INDEX_URL else PDF
        rows, report, originals = run([future()],now=NOW,fetcher=fake)
        self.assertEqual(report["source_status"],"captured_original_index_and_pdf")
        self.assertEqual(report["original_pdf_sha256"],hashlib.sha256(PDF).hexdigest())
        self.assertEqual(originals["pdf"],PDF)
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]["report_observed_before_tipoff"])
        self.assertFalse(rows[0]["report_includes_this_game_verified"])
        self.assertFalse(rows[0]["injury_report_proves_confirmed_active"])
        self.assertFalse(rows[0]["individual_player_report_status_verified"])
        self.assertFalse(rows[0]["qualifies_player_prop_training"])
        self.assertEqual(report["nba_players_confirmed_active"],0)
        self.assertEqual(report["certified_positive_ev_bets"],0)
        self.assertFalse(report["champion_001_modified"])

    def test_absent_report_does_not_call_pdf_endpoint(self):
        urls=[]
        def fake(url,limit):
            urls.append(url)
            return b"<html><body>No reports yet</body></html>"
        rows,report,originals=run([future()],now=NOW,fetcher=fake)
        self.assertEqual(urls,[INDEX_URL])
        self.assertEqual(report["source_status"],"no_nba_pdf_index_link_labeled_in_last_24_hours")
        self.assertEqual(rows,[])
        self.assertEqual(originals,{})

    def test_dont_accept_future_report_label_as_current_evidence(self):
        rows,report,originals=run([future()],now=NOW,
            fetcher=lambda url,limit: html(PDF9) if url==INDEX_URL else PDF)
        self.assertEqual(rows,[])
        self.assertEqual(originals,{})

    def test_reject_non_nba_pdf_host_even_if_pdf_filename_matches(self):
        forged=PDF7.replace("ak-static.cms.nba.com","attacker.example")
        with self.assertRaisesRegex(ValueError,"unapproved"):
            report_label_from_url(forged)
        self.assertIsNone(pick_index_report(html(forged),NOW))

    def test_report_pdf_exact_filename_not_query_parameter(self):
        with self.assertRaisesRegex(ValueError,"unapproved"):
            report_label_from_url(PDF7+"?download=true")
        with self.assertRaisesRegex(ValueError,"invalid_nba_pdf_report_filename"):
            report_label_from_url(PDF7.replace("Injury-Report","Some-Report"))

    def test_conflicting_urls_at_same_time_rejected(self):
        # Same selected time, differing exact source URLs cannot both pass,
        # because only the canonical NBA path/filename is accepted.
        self.assertEqual(pick_index_report(html(PDF7, PDF7),NOW)[1],PDF7)

    def test_ambiguous_dst_fallback_time_blocked(self):
        ambiguous="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-01_01_30AM.pdf"
        with self.assertRaisesRegex(ValueError,"ambiguous_nba_injury_report_dst"):
            report_label_from_url(ambiguous)

    def test_invalid_pdf_does_not_get_archived_or_claim_success(self):
        rows,report,raw=run([future()],now=NOW,
            fetcher=lambda url,limit: html(PDF7) if url==INDEX_URL else b"<html>blocked</html>")
        self.assertEqual(rows,[])
        self.assertEqual(raw,{})
        self.assertEqual(report["source_status"],"blocked_ValueError")

    def test_unknown_pregame_player_data_not_inferred_from_report_existence(self):
        _,report,_=run([],now=NOW,
            fetcher=lambda url,limit: html(PDF7) if url==INDEX_URL else PDF)
        self.assertEqual(report["nba_players_with_verified_injury_status"],0)
        self.assertEqual(report["nba_players_confirmed_active"],0)
        self.assertEqual(report["event_report_contents_individually_matched"],0)

    def test_game_started_before_capture_is_rejected(self):
        r=future(start="2026-11-05T12:45:00Z")
        rows, report = assemble(html(PDF7), PDF, NOW, [r], PDF7,
                                report_label_from_url(PDF7))
        self.assertFalse(rows)
        self.assertEqual(report["excluded_future_event_reasons"],
                         {"game_started_before_capture_or_pdf_label":1})

    def test_old_pregame_schedule_cannot_be_reused_as_fresh(self):
        r=future(observed="2026-11-04T04:00:00Z")
        rows, report = assemble(html(PDF7), PDF, NOW, [r], PDF7,
                                report_label_from_url(PDF7))
        self.assertEqual(rows,[])
        self.assertEqual(report["excluded_future_event_reasons"],
                         {"pregame_event_snapshot_older_than_six_hours":1})

    def test_unqualified_original_event_is_rejected(self):
        r=future()
        r["qualified_for_challenger_backtest"]=True
        calls=[]
        with self.assertRaisesRegex(ValueError,"unquarantined"):
            assemble(html(PDF7),PDF,NOW,[r],PDF7,report_label_from_url(PDF7))

    def test_duplicate_espn_game_identity_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate_or_missing"):
            assemble(html(PDF7),PDF,NOW,[future(),future()],PDF7,
                     report_label_from_url(PDF7))

    def test_capture_network_failure_never_creates_reports_with_verified_status(self):
        def bad(url,limit):
            raise OSError("synthetic unavailable")
        rows,r,raw=run([future()],now=NOW,fetcher=bad)
        self.assertEqual(rows,[])
        self.assertEqual(raw,{})
        self.assertEqual(r["source_status"],"blocked_OSError")
        self.assertEqual(r["nba_players_with_verified_injury_status"],0)

    def test_cli_writes_original_raw_bytes_and_never_claims_picks(self):
        def fake(url,limit):
            return html(PDF7) if url==INDEX_URL else PDF
        with TemporaryDirectory() as tmp:
            d=Path(tmp)
            f=d/"pregame.jsonl"
            f.write_text(json.dumps(future())+"\n")
            with patch("challenger_nba_pregame_injury_pdf.fetch_bytes",side_effect=fake):
                self.assertEqual(main(["--events",str(f),"--output-dir",str(d/"out")]),0)
            report=json.loads((d/"out"/"nba_injury_original_report.json").read_text())
            self.assertEqual(report["qualified_player_prop_training_observations"],0)
            self.assertEqual(report["bet_ready_selections"],0)
            self.assertEqual((d/"out"/"nba_injury_original_report.pdf").read_bytes(),PDF)
            self.assertEqual(len((d/"out"/"nba_injury_event_attachments.jsonl").read_text().splitlines()),1)


if __name__=="__main__":
    unittest.main()
