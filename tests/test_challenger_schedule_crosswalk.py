"""Synthetic-only tests for uniquely corroborated public schedules.

ESPN corroboration does not validate DraftKings checkout or establish EV.
"""
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from challenger_schedule_crosswalk import build_manifest, collect_snapshot_days
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

    def test_missing_source_rejects_every_event(self):
        src = quote()
        m = build_manifest([src], [], NOW)
        self.assertEqual(m["events"], [])
        self.assertIn("independent_schedule_unknown",
                      validate(src, {}))

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

    def test_only_bounded_future_dates(self):
        days = collect_snapshot_days([quote()], NOW)
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0].isoformat(), "2026-10-29")
        self.assertEqual(collect_snapshot_days([
            quote(event_start_time="2026-11-15T00:00:00Z")], NOW), [])

if __name__ == "__main__":
    unittest.main()
