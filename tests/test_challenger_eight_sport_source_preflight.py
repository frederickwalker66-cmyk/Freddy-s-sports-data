"""Synthetic eight-sport live source-only preflight, no API keys or bets."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse, parse_qs
import unittest

from challenger_eight_sport_source_preflight import run
from independent_schedule_review import SOURCES

NOW=datetime(2026,11,5,18,tzinfo=timezone.utc)
GAMES={
    ("nfl","20261108"):("401101","2026-11-08T18:00:00Z","Detroit Lions","Chicago Bears"),
    ("ncaab","20261106"):("401102","2026-11-06T23:00:00Z","Duke Blue Devils","North Carolina Tar Heels"),
    ("uefa_champions_league","20261110"):("401103","2026-11-10T20:00:00Z","Bayern Munich","Paris Saint-Germain"),
}


def fixture_fetch(denies=None, changed=None):
    denies=set(denies or [])
    changed=changed or {}
    def fetch(url):
        parts=urlparse(url)
        day=parse_qs(parts.query)["dates"][0]
        matches=[league for league,(sport,comp) in SOURCES.items()
                 if parts.path.endswith("/"+sport+"/"+comp+"/scoreboard")]
        if len(matches)!=1:raise AssertionError("unexpected URL")
        league=matches[0]
        if (league,day) in denies:
            raise TimeoutError("source failed")
        fixture=GAMES.get((league,day))
        events=[]
        if fixture:
            game_id,t,home,away=fixture
            events=[{
                "id":game_id,"date":t,"status":{"type":{"state":"pre"}},
                "competitions":[{"competitors":[
                    {"homeAway":"home","team":{"displayName":home}},
                    {"homeAway":"away","team":{"displayName":away}},
                ]}],
            }]
        if (league,day) in changed:
            events=changed[(league,day)]
        data={"events":events,"original_source_format":"wire_fixture"}
        raw=(json.dumps(data,sort_keys=True,separators=(",",":"))+"\n").encode()
        return data,raw
    return fetch


class LiveEightSportSourcePreflightTests(unittest.TestCase):
    def fixture(self, tmp, fetch=None, days=7, clock=None):
        return run(
            Path(tmp)/"capture",
            fetch=fixture_fetch() if fetch is None else fetch,
            clock=(lambda:NOW) if clock is None else clock,
            lookahead_days=days,
        )

    def test_each_league_has_a_real_distinct_source_audit(self):
        with TemporaryDirectory() as tmp:
            x=self.fixture(tmp)
            self.assertEqual(set(x["by_league"]),set(SOURCES))
            self.assertEqual(len(x["leagues_checked"]),8)
            self.assertEqual(x["totals"]["pregame_events_archived"],3)
            self.assertEqual(x["totals"]["future_games_discovered"],3)
            self.assertEqual(x["archived_game_fields_verified"],3)
            self.assertEqual(x["original_response_bytes_verified"],
                             sum(r["source_days_succeeded"]
                                 for r in x["by_league"].values()))

    def test_nfl_and_ncaab_upcoming_days_are_actual_source_dates(self):
        with TemporaryDirectory() as tmp:
            x=self.fixture(tmp)
            nfl=x["by_league"]["nfl"]
            self.assertEqual(nfl["first_upcoming_slate_date_et"],"2026-11-08")
            self.assertEqual(nfl["source_days_attempted"],4)
            ncaab=x["by_league"]["ncaab"]
            self.assertEqual(ncaab["first_upcoming_slate_date_et"],"2026-11-06")
            self.assertEqual(ncaab["source_days_attempted"],2)

    def test_uefa_lookahead_source_is_not_a_certified_bet(self):
        with TemporaryDirectory() as tmp:
            x=self.fixture(tmp)
            self.assertEqual(x["by_league"]["uefa_champions_league"][
                "first_upcoming_slate_date_et"],"2026-11-10")
            self.assertEqual(x["certified_positive_ev_bets"],0)
            self.assertEqual(x["qualified_chronological_training_games"],0)
            self.assertFalse(x["champion_001_modified"])
            self.assertFalse(x["source_independently_authenticated"])

    def test_mlb_no_listings_across_eight_successful_date_responses(self):
        with TemporaryDirectory() as tmp:
            x=self.fixture(tmp)
            m=x["by_league"]["mlb"]
            self.assertEqual(m["source_days_succeeded"],8)
            self.assertEqual(m["source_days_failed"],0)
            self.assertEqual(m["games_listed_in_checked_dates"],0)
            self.assertEqual(m["coverage_class"],
                             "espn_no_listed_games_in_fully_checked_window")

    def test_failed_mlb_response_is_not_mistaken_for_no_games(self):
        with TemporaryDirectory() as tmp:
            x=self.fixture(tmp,fetch=fixture_fetch(
                denies={("mlb","20261107")}))
            m=x["by_league"]["mlb"]
            self.assertEqual(m["source_days_failed"],1)
            self.assertEqual(m["coverage_class"],
                             "partial_or_total_source_failure_not_proof_of_no_games")

    def test_exact_original_response_file_preserves_wire_newline(self):
        with TemporaryDirectory() as tmp:
            x=self.fixture(tmp)
            root=Path(tmp)/"capture"
            s=json.loads((root/"espn_schedule_capture.json").read_text())
            q=s["sources"]["nfl"]["lookahead"][-1]
            raw=(root/"espn_original_schedule_bytes"/q["original_source_file"]).read_bytes()
            self.assertTrue(raw.endswith(b"\n"))
            self.assertEqual(hashlib.sha256(raw).hexdigest(),
                             q["original_source_sha256"])
            self.assertFalse(x["source_independently_authenticated"])

    def test_summary_and_source_reports_persist_and_same_game_counts(self):
        with TemporaryDirectory() as tmp:
            x=self.fixture(tmp)
            root=Path(tmp)/"capture"
            report=json.loads((root/"preflight_summary.json").read_text())
            source=json.loads((root/"eight_sport_schedule_coverage.json").read_text())
            games=(root/"prospective_event_evidence.jsonl").read_text().splitlines()
            self.assertEqual(report["totals"],x["totals"])
            self.assertEqual(len(games),x["archived_game_fields_verified"])
            self.assertEqual(source["original_espn_source_responses_verified"],
                             x["original_response_bytes_verified"])
            for entry in games:
                game=json.loads(entry)
                self.assertFalse(game["bet_ready"])
                self.assertIsNone(game["model_probability"])
                self.assertFalse(game["qualified_for_challenger_backtest"])

    def test_nonempty_capture_folder_refused_before_any_source_call(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/"capture"
            p.mkdir()
            (p/"existing.json").write_text("{}")
            called=[]
            with self.assertRaisesRegex(ValueError,"fresh_empty_capture_directory"):
                self.fixture(tmp,fetch=lambda url:called.append(url))
            self.assertEqual(called,[])

    def test_wrong_eastern_date_for_game_is_not_backdated(self):
        with TemporaryDirectory() as tmp:
            bad={
                ("nfl","20261108"):[{
                    "id":"401103","date":"2026-11-09T18:00:00Z",
                    "status":{"type":{"state":"pre"}},
                    "competitions":[{"competitors":[
                        {"homeAway":"home","team":{"displayName":"Detroit Lions"}},
                        {"homeAway":"away","team":{"displayName":"Chicago Bears"}},
                    ]}],
                }],
            }
            x=self.fixture(tmp,fetch=fixture_fetch(changed=bad))
            self.assertEqual(x["by_league"]["nfl"]["future_games_archived"],0)
            self.assertEqual(x["certified_challenger_001_predictions"],0)

    def test_naive_start_clock_blocked(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"start_clock_must_be_aware"):
                self.fixture(tmp,clock=lambda:datetime(2026,11,5,18))

    def test_clock_regression_before_original_capture_finished_blocked(self):
        with TemporaryDirectory() as tmp:
            ticks=iter([NOW])
            def bad_clock():
                return next(ticks,NOW-timedelta(seconds=1))
            with self.assertRaisesRegex(ValueError,"schedule_response_clock_before_scan_started"):
                self.fixture(tmp,clock=bad_clock)

    def test_illegal_more_than_seven_days_refused(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"lookahead_outside_bounded_window"):
                self.fixture(tmp,days=8)

    def test_no_model_or_positive_ev_counts_exist_anywhere_in_report(self):
        with TemporaryDirectory() as tmp:
            x=self.fixture(tmp)
            self.assertEqual(x["certified_champion_001_predictions"],0)
            self.assertEqual(x["certified_challenger_001_predictions"],0)
            self.assertEqual(x["certified_positive_ev_bets"],0)
            self.assertEqual(x["bet_ready_selections"],0)
            self.assertEqual(x["automated_bets_placed"],0)
            self.assertFalse(x["official_league_schedule_independently_verified"])


if __name__=="__main__":
    unittest.main()
