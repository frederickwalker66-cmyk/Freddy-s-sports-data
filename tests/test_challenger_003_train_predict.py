import unittest
from research.challenger_003_train_predict import train,predict

class Challenger003Tests(unittest.TestCase):
    def test_no_training_without_data(self):
        self.assertEqual(train([])["status"],"HOLD")
    def test_rejects_postgame_features(self):
        row={"event_id":"a","event_start_at":"2026-01-01T10:00:00Z",
             "observed_at":"2026-01-01T11:00:00Z",
             "outcome_observed_at":"2026-01-01T12:00:00Z",
             "outcome":1,"features":{"x":1}}
        with self.assertRaises(ValueError):train([row])
    def test_schema_guard(self):
        artifact={"features":["x"],"means":[0],"std":[1],"weights":[0,1]}
        with self.assertRaises(ValueError):predict(artifact,{"y":1})
    def test_research_probability_not_certified(self):
        artifact={"features":["x"],"means":[0],"std":[1],"weights":[0,1]}
        r=predict(artifact,{"x":1})
        self.assertEqual(r["decision"],"HOLD")
        self.assertFalse(r["certified"])
if __name__=="__main__":unittest.main()
