"""Synthetic all-eight-sport #79-82 exact-market and model readiness gates."""
from copy import deepcopy
import unittest

from challenger_exact_market_research_gate import audit as market_audit
from challenger_model_completion_gate import evaluate
from independent_schedule_review import SOURCES

START = "2026-11-05T23:00:00Z"
COMPLETE = "2026-11-05T18:01:00Z"


def snapshot(league="nba", quotes=None):
    return {
        "record_type": "prospective_evidence_snapshot_research_only",
        "league": league, "espn_schedule_event_id": "401",
        "home_team": "New York Knicks", "away_team": "Boston Celtics",
        "event_start_utc": START, "snapshot_completed_at_utc": COMPLETE,
        "odds_observations": quotes if quotes is not None else [],
        "model_probability": None, "qualified_for_challenger_backtest": False,
        "certified_prediction": False, "bet_ready": False,
        "champion_001_modified": False,
    }


def quote(**changes):
    q = {
        "odds_provider": "sharpapi_rest", "odds_provider_event_id": "provider-001",
        "market_type": "moneyline", "selection_type": "home",
        "selection": "New York Knicks", "line": None,
        "odds_american": -125,
        "player_id_research_only": None,
        "provider_updated_at_utc": "2026-11-05T18:00:30Z",
        "received_at_utc": "2026-11-05T18:00:40Z",
        "direct_draftkings_checkout_verified": False,
        "market_primary_line_verified": False,
        "player_available_verified": False,
    }
    return dict(q, **changes)


def identity(source=None, quote_count=0):
    status = ("nba_exact_pregame_game_identity_agrees_research_only"
              if source != "absent" else "nba_official_response_not_captured")
    return {
        "league": "nba", "espn_event_id": "401",
        "home_team": "New York Knicks", "away_team": "Boston Celtics",
        "event_start_utc": START,
        "espn_archive_completed_utc": COMPLETE,
        "aggregator_quote_rows_not_checkout_verified": quote_count,
        "identity_status": status,
        "official_league_pregame_identity_matched_research_only": source != "absent",
        "nba_official_game_id": "0022600010" if source != "absent" else None,
        "draftkings_checkout_price_verified": False,
        "native_model_probability_verified": False,
        "certified_prediction": False,
        "bet_ready": False, "champion_001_modified": False,
    }


def identity_report(games=1, matched=1):
    d = {
        "stage": "challenger_78_independent_league_identity_research_only",
        "archived_espn_events_reviewed": games,
        "independently_observed_nba_pregame_identity_matches_research_only": matched,
        "independently_observed_nhl_pregame_identity_matches_research_only": 0,
        "independently_observed_mlb_pregame_identity_matches_research_only": 0,
        "champion_001_modified": False,
    }
    for k in (
        "direct_draftkings_checkout_markets_verified",
        "verified_native_model_probabilities",
        "qualified_chronological_training_games",
        "certified_champion_001_predictions",
        "certified_challenger_001_predictions",
        "certified_positive_ev_bets",
        "bet_ready_selections",
        "automated_bets_placed",
    ):
        d[k] = 0
    return d


def schedule_report():
    d = {
        "stage": "challenger_eight_sport_seven_day_schedule_coverage_research_only",
        "by_league": {
            lg: {"archived_pregame_games": 1 if lg == "nba" else 0}
            for lg in SOURCES
        },
        "totals": {"pregame_events_archived": 1},
        "archived_games_matching_exact_original_event_fields": 1,
        "original_espn_source_responses_verified": 1,
        "original_source_hashes_independently_publisher_signed": False,
        "independent_league_schedule_verified": False,
        "historical_feature_publication_authenticated": False,
        "champion_001_modified": False,
    }
    for key in (
        "qualified_chronological_training_games",
        "certified_champion_001_predictions",
        "certified_challenger_001_predictions",
        "certified_positive_ev_bets",
        "bet_ready_selections",
        "automated_bets_placed",
    ):
        d[key] = 0
    return d


class SameRunMarketTests(unittest.TestCase):
    def test_no_quotes_keeps_zeros_and_distinguishes_identity(self):
        rows, report = market_audit([snapshot()], [identity()], identity_report())
        self.assertEqual(rows, [])
        self.assertEqual(report["provider_quote_rows_reviewed"], 0)
        self.assertEqual(report["by_league"]["nba"]["league_identity_matched_research_only"], 1)
        self.assertEqual(report["certified_positive_ev_bets"], 0)

    def test_complete_moneyline_metadata_remains_aggregator_only(self):
        rows, report = market_audit(
            [snapshot(quotes=[quote()])], [identity(quote_count=1)],
            identity_report())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["research_status"],
                         "research_only_exact_aggregator_market_fields_not_direct_bookmaker_quote")
        self.assertEqual(report["research_market_fields_reconciled"], 1)
        self.assertFalse(rows[0]["direct_draftkings_checkout_verified"])
        self.assertFalse(rows[0]["bet_ready"])
        self.assertEqual(report["direct_draftkings_checkout_quotes_verified"], 0)

    def test_unmatched_league_source_blocks_market_reconciliation(self):
        rows, report = market_audit(
            [snapshot(quotes=[quote()])], [identity("absent", 1)],
            identity_report(matched=0))
        self.assertEqual(rows[0]["research_status"],
                         "league_game_identity_not_independently_matched")
        self.assertEqual(report["research_market_fields_reconciled"], 0)

    def test_stale_quote_bad_price_and_swapped_selection_fail(self):
        for edit, status in (
            ({"received_at_utc": "2026-11-05T17:50:00Z"},
             "quote_stale_or_not_actually_pregame"),
            ({"odds_american": -65}, "invalid_exact_american_price"),
            ({"selection": "Boston Celtics"}, "moneyline_selection_team_identity_mismatch"),
        ):
            with self.subTest(edit=edit):
                rows, report = market_audit(
                    [snapshot(quotes=[quote(**edit)])],
                    [identity(quote_count=1)], identity_report())
                self.assertEqual(rows[0]["research_status"], status)
                self.assertEqual(report["research_market_fields_reconciled"], 0)

    def test_source_attempted_to_flip_direct_verification_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "attempted_certification"):
            market_audit(
                [snapshot(quotes=[quote(direct_draftkings_checkout_verified=True)])],
                [identity(quote_count=1)], identity_report())

    def test_repeated_exact_market_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate_exact_provider_market"):
            market_audit([snapshot(quotes=[quote(), quote()])],
                         [identity(quote_count=2)], identity_report())

    def test_review_field_mismatch_or_count_mismatch_rejected(self):
        wrong = identity(quote_count=1)
        wrong["home_team"] = "Other Team"
        with self.assertRaisesRegex(ValueError, "identity_and_quote_game"):
            market_audit([snapshot()], [wrong], identity_report())
        with self.assertRaisesRegex(ValueError, "quote_count"):
            market_audit([snapshot()], [identity(quote_count=1)], identity_report())


class CompletionGateTests(unittest.TestCase):
    def reports(self):
        _, m = market_audit([snapshot(quotes=[quote()])],
                            [identity(quote_count=1)], identity_report())
        return schedule_report(), identity_report(), m

    def test_all_software_reconciliation_passes_but_deployment_blocked(self):
        schedule, identities, market = self.reports()
        report = evaluate(schedule, identities, market)
        self.assertTrue(report["research_source_and_identity_audit_complete"])
        self.assertEqual(report["league_count"], 8)
        self.assertEqual(report["archived_pregame_games"], 1)
        self.assertEqual(report["model_update_status"],
                         "BLOCKED_MISSING_INDEPENDENT_EXTERNAL_EVIDENCE")
        self.assertEqual(report["certified_champion_001_predictions"], 0)
        self.assertEqual(report["independently_verified_bookmaker_prices"], 0)
        self.assertFalse(report["model_training_completed"])
        self.assertFalse(report["champion_001_modified"])

    def test_fake_model_approval_or_bookmaker_receipt_refused(self):
        s, i, m = self.reports()
        m["direct_draftkings_checkout_quotes_verified"] = 1
        with self.assertRaisesRegex(ValueError, "promoted_to_prediction"):
            evaluate(s, i, m)
        s, i, m = self.reports()
        i["certified_challenger_001_predictions"] = 1
        with self.assertRaisesRegex(ValueError, "promoted_to_prediction"):
            evaluate(s, i, m)

    def test_source_counts_and_league_identity_cannot_be_forged(self):
        s, i, m = self.reports()
        s["totals"]["pregame_events_archived"] = 2
        with self.assertRaisesRegex(ValueError, "source_game_counts"):
            evaluate(s, i, m)
        s, i, m = self.reports()
        m["by_league"]["nba"]["league_identity_matched_research_only"] = 0
        with self.assertRaisesRegex(ValueError, "counts_disagree"):
            evaluate(s, i, m)

    def test_frozen_champion_cannot_be_promoted_by_self_issued_manifest(self):
        s, i, m = self.reports()
        forged = {
            "champion_001_modified": False,
            "certified_champion_001_predictions": 0,
            "original_executable_verified": True,
            "immutable_model_version_authenticated": True,
            "reproducible_reference_outputs_verified": True,
        }
        with self.assertRaisesRegex(ValueError, "unsafe_or_unattested_champion"):
            evaluate(s, i, m, forged)

    def test_wrong_stages_and_missing_leagues_fail(self):
        s, i, m = self.reports()
        s["stage"] = "untrusted"
        with self.assertRaisesRegex(ValueError, "incompatible_stage"):
            evaluate(s, i, m)
        s, i, m = self.reports()
        del s["by_league"]["nba"]
        with self.assertRaisesRegex(ValueError, "missing_eight_sport"):
            evaluate(s, i, m)


if __name__ == "__main__":
    unittest.main()
