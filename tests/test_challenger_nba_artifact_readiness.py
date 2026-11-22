import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from research.challenger_nba_artifact_readiness import inspect
from challenger_nba_probability import VERSION, digest

class ReadinessTests(unittest.TestCase):
    def test_unconfigured(self):
        self.assertEqual(inspect("")["status"], "HOLD")
    def test_missing(self):
        self.assertEqual(inspect("/missing/nonexistent-model.json")["status"], "HOLD")
    def test_invalid_json(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"model.json"
            p.write_text("not-json")
            self.assertEqual(inspect(str(p))["status"], "HOLD")
    def test_valid_digest_research_only(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"model.json"
            model={"version":VERSION,"lane":"Challenger-001","champion_001_modified":False,"qualified_for_real_money_wagers":False,"holdout_excluded_from_coefficients":True}
            model["artifact_sha256"]=digest(model)
            p.write_text(json.dumps(model))
            self.assertEqual(inspect(str(p))["status"], "ARTIFACT_INTEGRITY_VERIFIED_RESEARCH_ONLY")
    def test_tampered_digest(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"model.json"
            p.write_text(json.dumps({"version":VERSION,"artifact_sha256":"0"*64}))
            self.assertEqual(inspect(str(p))["status"], "HOLD")

if __name__=="__main__":
    unittest.main()
