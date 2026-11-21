import datetime as dt
import unittest
from scripts.player_prop_integrity_gate import validate

class IntegrityGateTests(unittest.TestCase):
    def test_missing_fields_are_quarantined(self):
        reasons = validate({}, dt.datetime.now(dt.timezone.utc))
        self.assertIn("missing_player_id", reasons)
        self.assertIn("invalid_timestamp", reasons)

    def test_mismatched_team_is_quarantined(self):
        now = dt.datetime.now(dt.timezone.utc)
        iso = lambda t: t.isoformat()
        record = dict(player_id="p1", team_id="A", roster_team_id="B",
                      event_id="e1", sportsbook="DraftKings", market="points",
                      line=20.5, odds=-110, status="active",
                      observed_at=iso(now), roster_verified_at=iso(now),
                      injury_verified_at=iso(now),
                      starts_at=iso(now + dt.timedelta(hours=2)))
        self.assertIn("roster_team_mismatch", validate(record, now))
        record["roster_team_id"] = "A"
        self.assertEqual([], validate(record, now))
        record["roster_verified_at"] = iso(now + dt.timedelta(minutes=1))
        self.assertIn("verification_after_odds_capture", validate(record, now))

if __name__ == "__main__":
    unittest.main()
