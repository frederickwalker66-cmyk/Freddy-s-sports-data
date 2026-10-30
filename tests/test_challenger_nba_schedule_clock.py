"""All fixtures synthetic; NBA schedule corroboration never approves bets."""
import unittest
from copy import deepcopy
from datetime import datetime, timezone

from challenger_nba_schedule_clock import (
    compare_clocks, official_nba_events, nba_team_name,
)
from challenger_schedule_crosswalk import build_manifest
from test_challenger_schedule_crosswalk import quote, snapshot, NOW


def nba_game(start="2026-10-30T00:00:00Z", game_id="0022600010", status=1,
             home_city="Atlanta", home_name="Hawks", away_city="Cleveland",
             away_name="Cavaliers"):
    return {"gameId": game_id, "gameDateTimeUTC": start, "gameStatus": status,
            "homeTeam": {"teamCity": home_city, "teamName": home_name},
            "awayTeam": {"teamCity": away_city, "teamName": away_name}}


def nba_feed(*games):
    return {"leagueSchedule": {"seasonYear": "2026-27", "gameDates": [
        {"gameDate": "2026-10-29", "games": list(games)}]}}


def unaccepted():
    return build_manifest([quote(event_start_time="2026-10-30T00:10:00Z")],
                          [snapshot()], NOW)


class OfficialClockTests(unittest.TestCase):
    def test_public_nba_start_supports_espn_not_provider(self):
        manifest = unaccepted()
        r = compare_clocks(manifest, nba_feed(nba_game()), NOW)
        self.assertEqual(r["classification_counts"], {"nba_clock_agrees_with_espn": 1})
        self.assertEqual(r["nba_near_time_events_checked"], 1)
        self.assertTrue(r["cases"][0]["remains_quarantined"])
        self.assertFalse(r["cases"][0]["automatically_accepted_as_schedule_match"])
        self.assertEqual(r["bet_ready_selections"], 0)
        self.assertEqual(r["certified_champion_001_predictions"], 0)
        self.assertEqual(manifest["provider_event_ids_matched"], 0)

    def test_nba_start_supports_provider_not_espn(self):
        r = compare_clocks(unaccepted(),
                           nba_feed(nba_game(start="2026-10-30T00:10:00Z")), NOW)
        self.assertEqual(r["classification_counts"], {"nba_clock_agrees_with_provider": 1})
        self.assertEqual(r["near_time_mismatches_promoted"], 0)

    def test_nba_clock_supports_neither(self):
        r = compare_clocks(unaccepted(),
                           nba_feed(nba_game(start="2026-10-30T00:05:00Z")), NOW)
        self.assertEqual(r["classification_counts"], {"nba_clock_disagrees_with_both": 1})

    def test_multiple_same_team_nba_games_are_ambiguous(self):
        r = compare_clocks(unaccepted(), nba_feed(
            nba_game(), nba_game(start="2026-10-30T00:15:00Z", game_id="0022600011")), NOW)
        self.assertEqual(r["classification_counts"], {"ambiguous_nba_schedule_identity": 1})
        self.assertEqual(r["independently_verified_sportsbook_prices"], 0)

    def test_wrong_nba_teams_are_not_matched(self):
        r = compare_clocks(unaccepted(), nba_feed(
            nba_game(home_city="Boston", home_name="Celtics")), NOW)
        self.assertEqual(r["classification_counts"],
                         {"no_unique_official_nba_schedule_match": 1})

    def test_missing_official_schedule_does_not_backfill(self):
        r = compare_clocks(unaccepted(), None, NOW, "HTTPError")
        self.assertEqual(r["official_nba_source_status"], "unavailable")
        self.assertEqual(r["classification_counts"],
                         {"official_schedule_unavailable": 1})
        self.assertEqual(r["official_nba_source_error_type"], "HTTPError")

    def test_conflicting_nba_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "conflicting NBA game ID"):
            official_nba_events(nba_feed(nba_game(), nba_game(
                game_id="0022600010", start="2026-10-30T00:15:00Z")))

    def test_unplayed_nba_games_only(self):
        self.assertEqual(official_nba_events(nba_feed(nba_game(status=3))), [])
        self.assertEqual(len(official_nba_events(nba_feed(nba_game(status=1)))), 1)

    def test_alias_is_not_nickname_guessing(self):
        self.assertEqual(nba_team_name("LA Clippers"), "los angeles clippers")
        self.assertEqual(nba_team_name("Los Angeles Clippers"), "los angeles clippers")
        self.assertNotEqual(nba_team_name("Hawks"), nba_team_name("Atlanta Hawks"))

    def test_wrong_or_duplicated_quarantine_evidence_rejected(self):
        x = unaccepted()
        x["near_time_event_evidence_research_only"].append(
            deepcopy(x["near_time_event_evidence_research_only"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate quarantined"):
            compare_clocks(x, nba_feed(nba_game()), NOW)

    def test_unauthorized_promotion_fails_closed(self):
        x = unaccepted()
        x["near_time_mismatches_promoted"] = 1
        with self.assertRaisesRegex(ValueError, "unsafe schedule"):
            compare_clocks(x, nba_feed(nba_game()), NOW)

    def test_zero_nba_near_matches_skip_source(self):
        m = build_manifest([quote()], [snapshot()], NOW)
        r = compare_clocks(m, None, NOW)
        self.assertEqual(r["nba_near_time_events_checked"], 0)
        self.assertEqual(r["bet_ready_selections"], 0)

    def test_invalid_official_shape_does_not_invent_schedule(self):
        with self.assertRaisesRegex(ValueError, "missing NBA official schedule"):
            official_nba_events({"unexpected": True})


if __name__ == "__main__":
    unittest.main()
