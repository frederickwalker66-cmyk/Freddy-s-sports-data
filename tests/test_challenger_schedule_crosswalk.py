"""Synthetic-only tests for uniquely corroborated public schedules.

ESPN corroboration does not validate DraftKings checkout or establish EV.
"""
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from challenger_schedule_crosswalk import build_manifest, collect_snapshot_days
from independent_schedule_review import ingest_schedule
from challenger_audit import audit, validate

NOW = datetime(2026, 10, 29, 20, 0, tzinfo=timezone.utc)

def quote(**overrides):
    row = {
        "record_type": "pregame_odds_observation",
        "source": "sportsgameodds_v2",
        "sportsbook": "draftkings",
        "certified_prediction": False, "model_probability": None,
        "event_id": "sgo:the-game", "league": "nba",
        "home_team": "Atlanta Hawks", "away_team": "Cleveland Cavaliers",
        "market_type": "moneyline", "selection": "Atlanta Hawks",
        "selection_type": "home", "is_main_line": True,
        "is_alternate_line": False, "is_player_prop": False,
        "line": None, "odds_american": -110, "odds_decimal": 1.909,
        "timestamp": "2026-10-29T19:49:00Z",
        "recorded_at": "2026-10-29T19:50:00Z",
        "event_start_time": "2026-10-30T00:00:00Z",
    }
    row.update(overrides)
    return row

def snapshot(**overrides):
    event = {
        "league": "nba", "home_team": "Atlanta Hawks",
        "away_team": "Cleveland Cavaliers",
        "start_utc": "2026-10-30T00:00:00Z",
        "status": "scheduled", "provider_game_id": "401001",
        "source_url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        "observed_at_utc": "2026-10-29T19:55:00Z",
    }
    event.update(overrides)
    return {"collected_at_utc": "2026-10-29T19:55:00Z",
            "events": [event], "sources": {"nba": {"status": "retrieved"}}}

class CrosswalkTests(unittest.TestCase):
    def test_public_schedule_matches_provider_id_research_only(self):
        src = quote()
        m = build_manifest([src], [snapshot()], NOW)
        self.assertEqual(m["provider_event_ids_matched"], 1)
        self.assertEqual(m["events"][0]["event_id"], "sgo:the-game")
        self.assertEqual(m["events"][0]["espn_event_id"], "401001")
        events = {x["event_id"]: x for x in m["events"]}
        self.assertEqual(validate(src, events), [])
        staged, quarantined, report = audit([src], events)
        self.assertEqual((len(staged), len(quarantined)), (1, 0))
        self.assertEqual(report["bet_ready_selections"], 0)
        self.assertEqual(report["independently_reverified_sportsbook_prices"], 0)
        self.assertEqual(report["certified_champion_001_predictions"], 0)

    def test_source_unavailable_reports_upstream_failure_without_unlocking_quotes(self):
        row = quote()
        src = {"date_et": "2026-10-29",
               "collected_at_utc": "2026-10-29T19:55:00Z",
               "events": [],
               "sources": {"nba": {"status": "unavailable",
                                   "reason": "HTTPError", "days_checked": 1}}}
        manifest = build_manifest([row], [src], NOW)
        self.assertEqual(manifest["schedule_source_gap"], "all_queried_sources_unavailable")
        self.assertEqual(manifest["schedule_source_queries"][0]["error_type"], "HTTPError")
        self.assertEqual(manifest["schedule_source_queries"][0]["requested_date_et"], "2026-10-29")
        self.assertEqual(manifest["provider_event_ids_matched"], 0)
        self.assertEqual(manifest["bet_ready_selections"], 0)
        self.assertFalse(manifest["independent_sportsbook_price_verified"])
        self.assertEqual(manifest["certified_model_predictions"], 0)
        self.assertFalse(manifest["champion_001_modified"])

    def test_retrieved_empty_espn_scoreboard_is_not_called_a_transport_failure(self):
        src = {"date_et": "2026-10-29",
               "collected_at_utc": "2026-10-29T19:55:00Z",
               "events": [], "sources": {"nba": {"status": "retrieved",
                                                "scheduled_events": 0,
                                                "days_checked": 1}}}
        manifest = build_manifest([quote()], [src], NOW)
        self.assertEqual(manifest["schedule_source_gap"], "zero_eligible_future_source_events")
        self.assertIsNone(manifest["schedule_source_queries"][0]["error_type"])
        self.assertEqual(manifest["provider_event_ids_matched"], 0)
        self.assertEqual(manifest["bet_ready_selections"], 0)

    def test_missing_source_rejects_every_event(self):
        src = quote()
        m = build_manifest([src], [], NOW)
        self.assertEqual(m["events"], [])
        self.assertIn("independent_schedule_unknown",
                      validate(src, {}))

    def test_clippers_full_name_alias_but_not_nickname_only(self):
        quote_la = quote(home_team="LA Clippers")
        espn = snapshot(home_team="Los Angeles Clippers")
        match = build_manifest([quote_la], [espn], NOW)
        self.assertEqual(match["provider_event_ids_matched"], 1)
        self.assertEqual(match["bet_ready_selections"], 0)
        self.assertFalse(match["independent_sportsbook_price_verified"])
        nickname = build_manifest([quote(home_team="Clippers")], [espn], NOW)
        self.assertEqual(nickname["events"], [])

    def test_reversed_teams_must_not_match(self):
        m = build_manifest([quote(home_team="Cleveland Cavaliers",
                                  away_team="Atlanta Hawks")],
                           [snapshot()], NOW)
        self.assertEqual(m["provider_event_ids_matched"], 0)

    def test_ambiguous_multiple_espn_events_are_not_selected(self):
        snap = snapshot()
        other = deepcopy(snap["events"][0])
        other["provider_game_id"] = "401002"
        snap["events"].append(other)
        m = build_manifest([quote()], [snap], NOW)
        self.assertEqual(m["provider_event_ids_matched"], 0)

    def test_mismatched_start_time_quarantined(self):
        m = build_manifest([quote()], [snapshot(start_utc="2026-10-30T00:10:00Z")], NOW)
        self.assertEqual(m["events"], [])
        self.assertEqual(m["provider_event_ids_matched"], 0)
        self.assertEqual(m["near_time_mismatches_research_only"]["nba"]["-600"], 1)
        self.assertEqual(m["near_time_mismatches_promoted"], 0)
        detail = m["near_time_event_evidence_research_only"]
        self.assertEqual(len(detail), 1)
        self.assertEqual(detail[0]["provider_event_id"], "sgo:the-game")
        self.assertEqual(detail[0]["signed_provider_minus_espn_seconds"], -600)
        self.assertFalse(detail[0]["matched_for_research"])

    def test_far_time_mismatch_does_not_become_near_match(self):
        m = build_manifest([quote()], [snapshot(start_utc="2026-10-30T00:30:00Z")], NOW)
        self.assertEqual(m["events"], [])
        self.assertEqual(m["near_time_mismatches_research_only"], {})

    def test_provider_id_conflicting_teams_rejected(self):
        rows = [quote(), quote(home_team="Brooklyn Nets")]
        m = build_manifest(rows, [snapshot()], NOW)
        self.assertEqual(m["provider_event_ids_matched"], 0)
        self.assertEqual(m["provider_event_ids_quarantined"]["conflicting_provider_event_identity"], 1)

    def test_schedule_source_must_be_espn(self):
        m = build_manifest([quote()], [snapshot(source_url="https://unknown.example.com/")], NOW)
        self.assertEqual(m["events"], [])
        self.assertEqual(m["invalid_schedule_rows"], 1)

    def test_schedule_collected_after_tipoff_cannot_match(self):
        snap = snapshot()
        snap["events"][0]["start_utc"] = "2026-10-29T19:00:00Z"
        m = build_manifest([quote()], [snap], NOW)
        self.assertEqual(m["events"], [])

    def test_game_day_missing_player_status_stays_quarantined(self):
        src = quote(market_type="player_points", selection="Over",
                    selection_type="over", player_name="Test Example",
                    player_id="P1", is_player_prop=True, line=20.5)
        events = {e["event_id"]: e for e in build_manifest([src], [snapshot()], NOW)["events"]}
        reasons = validate(src, events)
        self.assertIn("game_day_status_not_verified", reasons)
        self.assertIn("roster_not_independently_verified", reasons)

    def test_no_sportsbook_prices_or_training_emitted(self):
        m = build_manifest([quote()], [snapshot()], NOW)
        self.assertFalse(m["independent_sportsbook_price_verified"])
        self.assertEqual(m["certified_model_predictions"], 0)
        self.assertEqual(m["bet_ready_selections"], 0)
        self.assertFalse(m["champion_001_modified"])

    def test_future_fixture_date_may_differ_from_capture_day_without_backdating(self):
        # Reproduces the Nov 6 live SharpAPI crosswalk root cause: 12 future
        # provider events were rejected because a future ESPN fixture date
        # was mistaken for the date the HTTP response had to arrive.
        future = "2026-10-30T23:00:00Z"  # Oct 30 Eastern, captured Oct 29
        later = NOW + timedelta(seconds=15)
        game = {"id": "401001", "date": future,
                "status": {"type": {"state": "pre"}},
                "competitions": [{"competitors": [
                    {"homeAway": "home", "team": {"displayName": "Atlanta Hawks"}},
                    {"homeAway": "away", "team": {"displayName": "Cleveland Cavaliers"}},
                ]}]}
        def fetch(url):
            return {"events": [game] if "/basketball/nba/" in url else []}
        source = ingest_schedule("2026-10-30", fetch=fetch, now=NOW,
                                 clock=lambda: later)
        self.assertEqual(source["sources"]["nba"]["scheduled_events"], 1)
        self.assertEqual(source["date_et"], "2026-10-30")
        self.assertEqual(source["events"][0]["observed_at_utc"], later.isoformat())
        self.assertEqual(source["sources"]["nba"]["lookahead"][0][
            "response_observed_at_utc"], later.isoformat())
        m = build_manifest([quote(event_start_time=future)], [source],
                           later + timedelta(seconds=1))
        self.assertEqual(m["provider_event_ids_seen"], 1)
        self.assertEqual(m["provider_event_ids_matched"], 1)
        self.assertEqual(m["certified_model_predictions"], 0)
        self.assertFalse(m["independent_sportsbook_price_verified"])
        self.assertEqual(m["bet_ready_selections"], 0)

    def test_actual_eastern_midnight_crossing_still_rejects_date_backdating(self):
        capture = datetime(2026, 11, 6, 4, 59, tzinfo=timezone.utc)
        later = datetime(2026, 11, 6, 5, 1, tzinfo=timezone.utc)
        source = ingest_schedule("2026-11-06", fetch=lambda _: {"events": []},
                                 now=capture, clock=lambda: later)
        self.assertEqual(source["events"], [])
        self.assertEqual(source["sources"]["nba"]["status"], "unavailable")
        self.assertEqual(source["sources"]["nba"]["reason"], "ValueError")

    def test_only_bounded_future_dates(self):
        days = collect_snapshot_days([quote()], NOW)
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0].isoformat(), "2026-10-29")
        self.assertEqual(collect_snapshot_days([
            quote(event_start_time="2026-11-15T00:00:00Z")], NOW), [])


    def test_late_night_stale_odds_are_counted_not_misrepresented_as_missing_games(self):
        late = NOW + timedelta(hours=8)
        stale = quote(event_start_time="2026-10-30T00:00:00Z")
        m = build_manifest([stale], [], late)
        self.assertEqual(m["provider_event_ids_seen"],0)
        self.assertEqual(m["schedule_source_gap"],"no_source_queries_recorded")
        self.assertEqual(
            m["quote_observation_timing_research_only"],
            {"game_started_before_audit":1})
        self.assertEqual(m["source_fixture_dates_queried_et"],[])
        self.assertEqual(m["certified_model_predictions"],0)
        self.assertEqual(m["bet_ready_selections"],0)

    def test_future_valid_quote_can_match_but_remains_uncertified(self):
        m = build_manifest([quote()], [snapshot(date_et="2026-10-29")], NOW)
        self.assertEqual(
            m["quote_observation_timing_research_only"],
            {"eligible_future_quote_rows_not_yet_matched":1})
        self.assertEqual(m["source_fixture_dates_queried_et"],["2026-10-29"])
        self.assertEqual(m["provider_event_ids_matched"],1)
        self.assertFalse(m["independent_sportsbook_price_verified"])
        self.assertFalse(m["champion_001_modified"])

    def test_future_receipt_and_far_away_quote_fail_closed(self):
        rows=[
            quote(recorded_at="2026-10-29T20:02:00Z"),
            quote(event_start_time="2026-11-10T00:00:00Z"),
            quote(event_start_time="invalid"),
            quote(sportsbook="different_book"),
        ]
        m=build_manifest(rows,[],NOW)
        self.assertEqual(m["provider_event_ids_seen"],0)
        self.assertEqual(m["quote_observation_timing_research_only"],{
            "invalid_or_missing_time":1,
            "invalid_untrusted_quote_identity":1,
            "observation_timestamp_in_future":1,
            "outside_bounded_pregame_horizon":1,
        })
        self.assertEqual(m["provider_event_ids_matched"],0)
        self.assertEqual(m["certified_model_predictions"],0)
        self.assertEqual(m["bet_ready_selections"],0)

if __name__ == "__main__":
    unittest.main()
