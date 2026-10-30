"""Daily learning audit invariants: research can be measured, never promoted."""
import unittest
from daily_research_audit import summarize

def sample():
    return {"id": "sgo:E1:O1", "timestamp": "2026-10-28T21:00:00+00:00",
            "line": None, "odds_american": -110, "league": "nba",
            "market_type": "moneyline", "certified_prediction": False,
            "model_probability": None}

def report():
    return {
        "observations": 1, "quarantined": 1, "staged_for_research_only": 0,
        "bet_ready_selections": 0, "certified_challenger_predictions": 0,
        "certified_champion_001_predictions": 0, "automated_bets_placed": 0,
        "independently_reverified_sportsbook_prices": 0,
        "champion_001_modified": False, "quarantine_causes": {"independent_schedule_unknown": 1}
    }

class DailyResearchAuditTests(unittest.TestCase):
    def test_records_quality_without_training(self):
        result = summarize([sample()], report())
        self.assertEqual(result["by_league"], {"nba": 1})
        self.assertEqual(result["total_odds_observations"], 1)
        self.assertEqual(result["certified_shadow_predictions"], 0)
        self.assertEqual(result["learned_model_updates"], 0)
        self.assertFalse(result["production_model_changed"])

    def test_schedule_corroborated_research_staging_is_not_bet_ready(self):
        r=report()
        r["quarantined"]=0
        r["staged_for_research_only"]=1
        r["independent_schedule_events_available"]=1
        result=summarize([sample()],r)
        self.assertEqual(result["staged_research_only_count"],1)
        self.assertEqual(result["certified_shadow_predictions"],0)

    def test_research_staging_without_schedule_is_blocked(self):
        r=report()
        r["quarantined"]=0
        r["staged_for_research_only"]=1
        with self.assertRaisesRegex(ValueError,"schedule provenance"):
            summarize([sample()],r)

    def test_missing_quarantine_fails_closed(self):
        p = report()
        p["quarantined"] = 0
        with self.assertRaises(ValueError):
            summarize([sample()], p)

    def test_non_model_provider_probabilities_fail_closed(self):
        row = sample()
        row["model_probability"] = .72
        with self.assertRaises(ValueError):
            summarize([row], report())

    def test_invalid_champion_modification_blocked(self):
        p = report()
        p["champion_001_modified"] = True
        with self.assertRaises(ValueError):
            summarize([sample()], p)
