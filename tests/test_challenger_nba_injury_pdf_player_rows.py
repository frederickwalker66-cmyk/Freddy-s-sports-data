"""Synthetic PDF-column and strict as-of NBA injury-row tests. No paid APIs."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from challenger_nba_injury_pdf_player_rows import (
    TEAM_CODES, link_players, parse_pdf_bytes, parse_table,
    parsed_pdf_report_time, run, word_lines,
)

NOW = datetime(2026, 11, 5, 13, tzinfo=timezone.utc)
URL = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-05_07_30AM.pdf"
LABEL = datetime(2026, 11, 5, 12, 30, tzinfo=timezone.utc)
PDF = b"%PDF-1.7\n" + b"synthetic test bytes " * 12 + b"\n%%EOF"
HTML = b"<html>NBA original index bytes for synthetic fixture</html>"


def cells(**kw):
    out = {k: "" for k in ("date","time","matchup","team","player","status","reason")}
    out.update(kw)
    return out


def pages():
    return [[
        cells(date="11/05/2026",time="09:00 (ET)",matchup="ORL@PHX",
              team="Orlando Magic",player="Banchero, Paolo",status="Out",
              reason="Injury/Illness - Right High Ankle"),
        cells(reason="Sprain"),
        cells(player="Suggs, Jalen",status="Questionable",
              reason="Injury/Illness - Right Knee"),
        cells(team="Phoenix Suns",reason="NOT YET SUBMITTED"),
        cells(time="10:00 (ET)",matchup="MIA@GSW",
              team="Miami Heat",reason="NOT YET SUBMITTED"),
        cells(team="Golden State Warriors",
              player="Butler III, Jimmy",status="Out",
              reason="Injury/Illness - Right ACL Repair"),
        cells(reason="/ Surgery"),
        cells(date="11/06/2026",time="07:00 (ET)",matchup="BOS@CHA",
              team="Boston Celtics",reason="NOT YET SUBMITTED"),
    ], [
        cells(matchup="WAS@ATL",team="Washington Wizards",reason="NOT YET SUBMITTED"),
        cells(team="Atlanta Hawks",reason="NOT YET SUBMITTED"),
    ]]


def game(event="4019001", start="2026-11-06T02:00:00Z",
         home="Phoenix Suns",away="Orlando Magic"):
    return {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": "nba", "espn_schedule_event_id": event,
        "home_team": home, "away_team": away, "event_start_utc": start,
        "snapshot_completed_at_utc": "2026-11-05T12:40:00Z",
        "player_level_status_parsed_and_verified": False,
        "qualified_for_challenger_backtest": False,
        "certified_prediction": False, "model_probability": None,
        "bet_ready": False, "champion_001_modified": False,
    }


def archive(folder, pdf=PDF, html=HTML, claimed=True):
    root=Path(folder)
    data = {
        "stage":"challenger_original_nba_pregame_injury_pdf_archive_research_only",
        "source_status":"captured_original_index_and_pdf" if claimed else "blocked_OSError",
        "capture_observed_at_utc":NOW.isoformat(),
        "official_nba_index_url":"https://official.nba.com/nba-injury-report-2026-27-season/",
        "official_nba_index_sha256":hashlib.sha256(html).hexdigest(),
        "official_nba_report_url":URL,
        "original_pdf_sha256":hashlib.sha256(pdf).hexdigest(),
        "original_pdf_authorship_cryptographically_verified":False,
        "report_filename_label_externally_authenticated":False,
        "nba_players_confirmed_active":0,
        "qualified_player_prop_training_observations":0,
        "certified_positive_ev_bets":0,
        "champion_001_modified":False,
    }
    (root/"nba_injury_original_report.json").write_text(json.dumps(data))
    if claimed:
        (root/"nba_injury_original_report.pdf").write_bytes(pdf)
        (root/"nba_injury_original_index.html").write_bytes(html)
    return data


class NBAOfficialPDFPlayerRowsTests(unittest.TestCase):
    def test_real_layout_columns_after_extract_words(self):
        width=800
        def w(x, top, value): return {"x0":x,"top":top,"text":value}
        ws = [
            w(18,100,"11/05/2026"),w(120,100,"09:00"),w(150,100,"(ET)"),
            w(186,100,"ORL@PHX"),w(258,100,"Orlando"),w(304,100,"Magic"),
            w(410,100,"Banchero,"),w(474,100,"Paolo"),
            w(558,100,"Out"),
            w(638,100,"Injury/Illness"),w(724,100,"-"),
            w(639,115,"Sprain"),
        ]
        rows=word_lines(ws,width)
        self.assertEqual(rows[0]["matchup"],"ORL@PHX")
        self.assertEqual(rows[0]["team"],"Orlando Magic")
        self.assertEqual(rows[0]["player"],"Banchero, Paolo")
        self.assertEqual(rows[0]["status"],"Out")
        self.assertEqual(rows[1]["reason"],"Sprain")

    def test_extract_players_and_multiline_reasons(self):
        rows,filings,count=parse_table(pages(),LABEL,LABEL)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]["source_player_name_display"],"Paolo Banchero")
        self.assertEqual(rows[0]["source_reason"],
                         "Injury/Illness - Right High Ankle Sprain")
        self.assertEqual(rows[1]["source_injury_designation"],"Questionable")
        self.assertEqual(rows[2]["source_player_name_display"],"Jimmy Butler III")
        self.assertEqual(rows[2]["source_reason"],
                         "Injury/Illness - Right ACL Repair / Surgery")
        self.assertEqual(count["explicit_player_rows"],3)
        self.assertEqual(count["team_filings_missing"],5)

    def test_unsubmitted_team_does_not_prove_any_player_available(self):
        rows,filings,_=parse_table(pages(),LABEL,LABEL)
        self.assertTrue(all(x["confirmed_all_players_available"] is False for x in filings))
        self.assertFalse(any(x["team_name"]=="Phoenix Suns" for x in rows))
        self.assertEqual(len([x for x in filings if x["team_name"]=="Phoenix Suns"]),1)

    def test_source_filename_and_pdf_printed_time_must_match(self):
        with self.assertRaisesRegex(ValueError,"printed_pdf_time_disagrees"):
            parse_table(pages(),LABEL,datetime(2026,11,5,13,tzinfo=timezone.utc))
        self.assertEqual(parsed_pdf_report_time(
            "Injury Report: 11/05/26 07:30 AM\nPage 1 of 2"),LABEL)

    def test_one_exact_future_event_match_still_not_active(self):
        players,filings,_=parse_table(pages(),LABEL,LABEL)
        out,_,counter=link_players(players,filings,[game()],NOW)
        self.assertEqual(out[0]["espn_event_id_research_match"],"4019001")
        self.assertEqual(out[0]["game_match_status"],"exact_date_clubs_research_only")
        self.assertIsNone(out[0]["nba_person_id"])
        self.assertFalse(out[0]["player_current_game_active_status_verified"])
        self.assertFalse(out[0]["qualified_for_prop_training"])
        self.assertEqual(counter["exact_date_clubs_research_only"],2)
        self.assertIsNone(out[2]["espn_event_id_research_match"])

    def test_no_upcoming_game_or_game_started_never_attached(self):
        players,filings,_=parse_table(pages(),LABEL,LABEL)
        out,_,_=link_players(players,filings,[game(start="2026-11-05T12:45:00Z")],NOW)
        self.assertTrue(all(x["espn_event_id_research_match"] is None for x in out))

    def test_different_clubs_do_not_match_similar_team_names(self):
        rows,filings,_=parse_table(pages(),LABEL,LABEL)
        out,_,_=link_players(rows,filings,[game(home="Boston Celtics",away="Orlando Magic")],NOW)
        self.assertTrue(all(x["espn_event_id_research_match"] is None for x in out))

    def test_duplicate_club_player_in_same_match_rejected(self):
        p=pages()
        p[0].insert(2,deepcopy(p[0][0]))
        with self.assertRaisesRegex(ValueError,"duplicate_player"):
            parse_table(p,LABEL,LABEL)

    def test_team_wrong_for_matchup_hard_error(self):
        p=pages()
        p[0][0]["team"]="Boston Celtics"
        with self.assertRaisesRegex(ValueError,"does_not_belong"):
            parse_table(p,LABEL,LABEL)

    def test_invalid_player_status_not_assumed_available(self):
        p=pages()
        p[0][0]["status"]="Maybe"
        rows,filings,counts=parse_table(p,LABEL,LABEL)
        self.assertEqual(rows[0]["source_player_name_display"],"Jalen Suggs")
        self.assertGreater(counts["unparsed_player_status_cell"],0)

    def test_unknown_team_name_does_not_create_identity(self):
        p=pages()
        p[0][0]["team"]="Unverified Basketball Team"
        rows,filings,counts=parse_table(p,LABEL,LABEL)
        self.assertNotIn("Paolo Banchero", [r["source_player_name_display"] for r in rows])
        self.assertGreater(counts["unknown_pdf_team_name"],0)

    def test_body_without_date_never_guesses_game_day(self):
        p=[[cells(matchup="ORL@PHX",team="Orlando Magic",
                  player="Banchero, Paolo",status="Out",reason="Leg")]]
        rows,filings,_=parse_table(p,LABEL,LABEL)
        self.assertFalse(rows)
        self.assertFalse(filings)

    def test_cannot_link_unsafe_snapshot(self):
        rows,filings,_=parse_table(pages(),LABEL,LABEL)
        g=game()
        g["bet_ready"]=True
        with self.assertRaisesRegex(ValueError,"unsafe_nba_pregame"):
            link_players(rows,filings,[g],NOW)

    def test_wrong_original_pdf_hash_blocks_all_results(self):
        with TemporaryDirectory() as tmp:
            archive(tmp)
            (Path(tmp)/"nba_injury_original_report.pdf").write_bytes(PDF+b"altered")
            with self.assertRaisesRegex(ValueError,"bytes_changed"):
                run(tmp,[game()],NOW)

    def test_blocked_pdf_source_yields_empty_immutable_review(self):
        with TemporaryDirectory() as tmp:
            archive(tmp,claimed=False)
            rows,filings,report=run(tmp,[game()],NOW)
            self.assertEqual(rows,[])
            self.assertEqual(filings,[])
            self.assertEqual(report["pdf_extraction_error"],"original_nba_pdf_not_captured")
            self.assertEqual(report["qualified_prop_training_observations"],0)

    def test_report_pdf_player_parser_exception_quarantines_results(self):
        with TemporaryDirectory() as tmp:
            archive(tmp)
            with patch("challenger_nba_injury_pdf_player_rows.parse_pdf_bytes",
                       side_effect=ValueError("untrusted layout")):
                rows,filings,report=run(tmp,[game()],NOW)
            self.assertFalse(rows)
            self.assertEqual(report["pdf_extraction_error"],
                             "pdf_player_extraction_blocked_ValueError")
            self.assertFalse(report["injury_report_status_is_final_lineup_verified"])

    def test_verified_raw_bytes_can_produce_review_only_rows(self):
        with TemporaryDirectory() as tmp:
            archive(tmp)
            with patch("challenger_nba_injury_pdf_player_rows.parse_pdf_bytes",
                       return_value=parse_table(pages(),LABEL,LABEL)):
                rows,filings,report=run(tmp,[game()],NOW)
            self.assertEqual(len(rows),3)
            self.assertEqual(report["player_rows_extracted_from_official_pdf"],3)
            self.assertEqual(report["matched_pregame_game_statuses"]
                             ["exact_date_clubs_research_only"],2)
            self.assertEqual(report["active_player_roster_verified"],0)
            self.assertEqual(report["certified_champion_001_predictions"],0)

    def test_unsupported_provider_source_does_not_allow_training(self):
        with TemporaryDirectory() as tmp:
            report=archive(tmp)
            report["nba_players_confirmed_active"]=1
            (Path(tmp)/"nba_injury_original_report.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,"unsafe_nba_original"):
                run(tmp,[game()],NOW)

    def test_no_player_id_is_claimed_even_when_status_is_available(self):
        p=pages()
        p[0][0]["status"]="Available"
        rows,_,_=parse_table(p,LABEL,LABEL)
        self.assertEqual(rows[0]["source_injury_designation"],"Available")
        self.assertIsNone(rows[0]["nba_person_id"])
        self.assertFalse(rows[0]["player_current_game_active_status_verified"])


if __name__=="__main__":
    unittest.main()
