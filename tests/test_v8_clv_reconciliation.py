"""Exact-line reported CLV movement is distinct from independently verified CLV."""
import unittest
from v8_clv_reconciliation import decimal_odds, reconcile


def quote(price, at, *, line=24.5, event="123", player="501"):
    return {
        "league": "nba", "event_id": event, "sportsbook": "DraftKings",
        "market": "player_prop", "selection": "over",
        "player_id": player, "prop_stat": "points", "line": line,
        "odds_american": price,
        "event_start_utc": "2026-11-13T23:00:00Z",
        "quote_recorded_utc": at,
    }


class CLVSafeTrackingTests(unittest.TestCase):
    def test_empty_sources_report_missing_clv_not_zero_percent(self):
        r = reconcile([], [])
        self.assertIsNone(r["verified_realized_clv_percent"])
        self.assertEqual(r["exact_same_book_event_market_line_pairs"], 0)
        self.assertEqual(r["certified_positive_ev_bets"], 0)

    def test_reported_price_improvement_not_promoted_as_realized_clv(self):
        entry = quote(120, "2026-11-13T20:00:00Z")
        close = quote(100, "2026-11-13T22:57:00Z")
        r = reconcile([entry], [close])
        self.assertEqual(r["exact_same_book_event_market_line_pairs"], 1)
        pair = r["indicative_matched_price_changes"][0]
        self.assertAlmostEqual(pair["indicative_price_advantage_percent"], 10.0)
        self.assertFalse(pair["original_receipts_independently_authenticated"])
        self.assertIsNone(pair["verified_realized_clv_percent"])
        self.assertFalse(r["independent_source_custody_and_executable_quote_verified"])

    def test_different_line_player_or_book_not_matched(self):
        entry = quote(-110, "2026-11-13T19:00:00Z")
        alternatives = [
            quote(-120, "2026-11-13T22:59:00Z", line=25.5),
            quote(-120, "2026-11-13T22:59:00Z", player="502"),
        ]
        for close in alternatives:
            r = reconcile([entry], [close])
            self.assertEqual(r["exact_same_book_event_market_line_pairs"], 0)
            self.assertEqual(r["unmatched_entry_reasons"]["missing_identical_same_book_close"], 1)
        modified = quote(-120, "2026-11-13T22:59:00Z")
        modified["sportsbook"] = "FanDuel"
        self.assertEqual(reconcile([entry], [modified])["exact_same_book_event_market_line_pairs"], 0)

    def test_inplay_stale_and_duplicate_receipt_fail(self):
        with self.assertRaisesRegex(ValueError, "CLV_inplay_or_future_quote"):
            reconcile([], [quote(-110, "2026-11-13T23:01:00Z")])
        with self.assertRaisesRegex(ValueError, "CLV_quote_not_within_final_15_minutes"):
            reconcile([], [quote(-110, "2026-11-13T22:30:00Z")])
        with self.assertRaisesRegex(ValueError, "CLV_multiple_closing_quotes_ambiguous"):
            reconcile([], [quote(-110, "2026-11-13T22:58:00Z"),
                           quote(-105, "2026-11-13T22:59:00Z")])
        self.assertGreater(decimal_odds(-110), 1)


if __name__ == "__main__":
    unittest.main()
