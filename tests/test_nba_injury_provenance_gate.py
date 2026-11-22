import unittest
from research.nba_injury_provenance_gate import reconcile_player

AS_OF = "2026-11-22T23:00:00Z"
SOURCE = "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-22_04_30PM.pdf"

def record(date, status, observed="2026-11-22T21:30:00Z", source_type="nba_official_report"):
    return dict(game_date=date, team="BOS", player="Jayson Tatum", status=status,
                observed_at_utc=observed, source_url=SOURCE, source_type=source_type)

class InjuryProvenanceTests(unittest.TestCase):
    def test_prior_day_out_does_not_carry_forward(self):
        result = reconcile_player("2026-11-22", "BOS", "Jayson Tatum",
                                  [record("2026-11-21", "OUT")], AS_OF)
        self.assertEqual(result["official_designation"], "UNVERIFIED")
        self.assertEqual(result["prior_game_records_excluded"], 1)
        self.assertFalse(result["certified_take"])

    def test_latest_same_game_official_revision_wins(self):
        rows = [record("2026-11-22", "QUESTIONABLE", "2026-11-22T20:00:00Z"),
                record("2026-11-22", "NOT_LISTED", "2026-11-22T22:00:00Z")]
        result = reconcile_player("2026-11-22", "BOS", "Jayson Tatum", rows, AS_OF)
        self.assertEqual(result["official_designation"], "NOT_LISTED")
        self.assertFalse(result["confirmed_active"])
        self.assertEqual(result["decision"], "HOLD")

    def test_third_party_cannot_override_official(self):
        rows = [record("2026-11-22", "QUESTIONABLE"),
                record("2026-11-22", "AVAILABLE", "2026-11-22T22:30:00Z", "third_party")]
        result = reconcile_player("2026-11-22", "BOS", "Jayson Tatum", rows, AS_OF)
        self.assertEqual(result["official_designation"], "QUESTIONABLE")

    def test_future_dated_rejected(self):
        with self.assertRaises(ValueError):
            reconcile_player("2026-11-22", "BOS", "Jayson Tatum",
                             [record("2026-11-22", "OUT", "2026-11-23T00:00:00Z")], AS_OF)

if __name__ == "__main__":
    unittest.main()
