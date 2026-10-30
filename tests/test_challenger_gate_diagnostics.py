"""Synthetic diagnostic fixtures; these do not constitute betting records."""
import unittest
from copy import deepcopy
from challenger_gate_diagnostics import diagnose, quote_age_bucket


def observation(league="nba", market="moneyline", **changes):
    row = {"id": "sgo:event:quote", "event_id": "sgo:event",
           "record_type": "pregame_odds_observation",
           "certified_prediction": False, "model_probability": None,
           "league": league, "market_type": market,
           "sportsbook": "draftkings",
           "timestamp": "2026-10-30T10:00:00Z",
           "recorded_at": "2026-10-30T10:01:00Z",
           "is_player_prop": False}
    row.update(changes)
    return row


def schedule(events=None):
    return {"events": [] if events is None else events,
            "near_time_mismatches_research_only": {"nba": {"600": 5}},
            "bet_ready_selections": 0, "champion_001_modified": False}


def audit(n, staged, events):
    return {"observations": n, "staged_for_research_only": staged,
            "quarantined": n - staged,
            "independent_schedule_events_available": events,
            "certified_champion_001_predictions": 0,
            "certified_challenger_predictions": 0,
            "independently_reverified_sportsbook_prices": 0,
            "bet_ready_selections": 0, "automated_bets_placed": 0,
            "champion_001_modified": False}


class GateDiagnosticTests(unittest.TestCase):
    def test_staged_research_is_reported_not_promoted(self):
        row = observation()
        s = schedule([{"event_id": "sgo:event"}])
        result = diagnose([row], [row], [], audit(1, 1, 1), s)
        self.assertEqual(result["per_league"]["nba"]["research_staged"], 1)
        self.assertEqual(result["research_staged"], 1)
        self.assertEqual(result["positive_ev_bets_verified"], 0)
        self.assertEqual(result["certified_champion_001_predictions"], 0)
        self.assertEqual(result["bet_ready_selections"], 0)
        self.assertFalse(result["champion_001_modified"])

    def test_quarantine_causes_and_ages_by_league(self):
        a = observation(timestamp="2026-10-30T09:59:00Z")
        b = observation(league="nfl", market="player_points",
                        recorded_at="2026-10-30T10:18:00Z")
        q = [{"observation": a, "reasons": ["not_confirmed_primary_line"]},
             {"observation": b, "reasons": ["game_day_status_not_verified",
                                            "quote_too_old_or_future"]}]
        r = diagnose([a, b], [], q, audit(2, 0, 0), schedule())
        self.assertEqual(r["per_league"]["nba"]["quote_freshness"]["fresh_0_to_120s"], 1)
        self.assertEqual(r["per_league"]["nfl"]["quote_freshness"]["stale_over_900s"], 1)
        self.assertEqual(r["per_league"]["nfl"]["quarantine_causes"]["game_day_status_not_verified"], 1)
        self.assertEqual(r["quarantined"], 2)

    def test_archive_only_quote_does_not_become_approved(self):
        row = observation(recorded_at="2026-10-30T10:05:00Z")
        self.assertEqual(quote_age_bucket(row), "archive_only_121_to_900s")
        q = [{"observation": row, "reasons": ["quote_too_old_or_future"]}]
        report = diagnose([row], [], q, audit(1, 0, 0), schedule())
        self.assertEqual(report["independently_reverified_checkout_prices"], 0)

    def test_near_10_min_time_mismatch_is_only_diagnostic(self):
        row = observation()
        q = [{"observation": row, "reasons": ["independent_schedule_unknown"]}]
        r = diagnose([row], [], q, audit(1, 0, 0), schedule())
        self.assertEqual(r["near_time_mismatches_research_only"]["nba"]["600"], 5)
        self.assertEqual(r["near_time_mismatches_promoted"], 0)

    def test_missing_quarantine_row_fails(self):
        with self.assertRaisesRegex(ValueError, "inconsistent audited"):
            diagnose([observation()], [], [], audit(1, 0, 0), schedule())

    def test_swapped_quarantined_quote_fails(self):
        a = observation()
        b = observation(league="nfl")
        with self.assertRaisesRegex(ValueError, "do not match original"):
            diagnose([a], [], [{"observation": b, "reasons": ["invalid"]}],
                     audit(1, 0, 0), schedule())

    def test_no_unsupported_certification_allowed(self):
        row = observation()
        q = [{"observation": row, "reasons": ["unknown"]}]
        state = audit(1, 0, 0)
        state["bet_ready_selections"] = 1
        with self.assertRaisesRegex(ValueError, "unsafe"):
            diagnose([row], [], q, state, schedule())

    def test_staging_without_schedule_fails(self):
        row = observation()
        with self.assertRaisesRegex(ValueError, "nonempty schedule"):
            diagnose([row], [row], [], audit(1, 1, 0), schedule())

    def test_repeated_reasons_do_not_inflate_counts(self):
        row = observation()
        with self.assertRaisesRegex(ValueError, "reason evidence missing"):
            diagnose([row], [], [{"observation": row, "reasons": ["same", "same"]}],
                     audit(1, 0, 0), schedule())

    def test_future_source_timestamp_identified(self):
        row = observation(timestamp="2026-10-30T10:02:00Z")
        self.assertEqual(quote_age_bucket(row), "future_provider_timestamp")


if __name__ == "__main__":
    unittest.main()
