"""Deterministic transfer conflict regression tests; not proof of full roster sync."""
import unittest
from nba_transaction_conflict_guard import known_transaction_conflict

class TransactionGuardTests(unittest.TestCase):
    def test_lamelo_not_hornets_in_november(self):
        self.assertTrue(known_transaction_conflict(
            "LaMelo Ball", "Atlanta Hawks", "Charlotte Hornets",
            "2026-11-20T00:00:00Z"))

    def test_lamelo_wolves_not_conflict(self):
        self.assertFalse(known_transaction_conflict(
            "LaMelo Ball", "Minnesota Timberwolves", "New York Knicks",
            "2026-11-20T00:00:00Z"))

    def test_known_other_transfers(self):
        self.assertTrue(known_transaction_conflict(
            "Naz Reid", "Minnesota Timberwolves", "New York Knicks",
            "2026-11-20T00:00:00Z"))
        self.assertTrue(known_transaction_conflict(
            "Julius Randle", "Minnesota Timberwolves", "New York Knicks",
            "2026-11-20T00:00:00Z"))

    def test_old_asof_does_not_rewrite_history(self):
        self.assertFalse(known_transaction_conflict(
            "LaMelo Ball", "Charlotte Hornets", "Atlanta Hawks",
            "2026-06-20T00:00:00Z"))

    def test_unknown_player_not_promoted(self):
        self.assertFalse(known_transaction_conflict(
            "Unverified Player", "Charlotte Hornets", "Atlanta Hawks",
            "2026-11-20T00:00:00Z"))

    def test_aliases(self):
        self.assertFalse(known_transaction_conflict(
            "LaMelo Ball", "MIN", "NYK", "2026-11-20T00:00:00Z"))

if __name__ == "__main__":
    unittest.main()
