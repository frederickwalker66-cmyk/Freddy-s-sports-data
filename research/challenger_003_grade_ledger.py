"""Grade only immutable pregame Challenger-003 research predictions.
No odds-derived model probabilities; no self-reported settlement without receipt.
The resulting records are audit output, not automatically trusted training data.
"""
import argparse, hashlib, json
from pathlib import Path
from research.challenger_002_baseline import timestamp

def grade(predictions, results):
    by_id={}
    for r in results:
        key=r["event_id"]
        if key in by_id:raise ValueError("duplicate_settlement")
        by_id[key]=r
    seen=set(); graded=[]; pending=[]; rejected=[]
    for p in predictions:
        key=p["event_id"]
        if key in seen:raise ValueError("duplicate_prediction")
        seen.add(key)
        try:
            observed=timestamp(p["observed_at"]); start=timestamp(p["event_start_at"])
            probability=p["research_probability"]
            if observed>=start or type(probability) not in (int,float) or not 0<=probability<=1:
                raise ValueError("invalid_pregame_prediction")
            if p.get("model_id")!="Challenger-003":raise ValueError("wrong_model")
            if key not in by_id:
                pending.append(key);continue
            r=by_id[key]
            settled=timestamp(r["outcome_observed_at"])
            if settled<=start or type(r["outcome"]) is not int or r["outcome"] not in (0,1):
                raise ValueError("invalid_settlement")
            digest=r.get("outcome_receipt_sha256")
            if not isinstance(digest,str) or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("missing_settlement_receipt_digest")
            graded.append({"event_id":key,"research_probability":probability,
                           "outcome":r["outcome"],"brier":round((probability-r["outcome"])**2,8),
                           "outcome_receipt_sha256":digest,
                           "status":"LOCALLY_GRADED_NOT_INDEPENDENTLY_AUTHENTICATED"})
        except (KeyError,ValueError,TypeError) as e:
            rejected.append({"event_id":key,"reason":str(e)})
    return {"model_id":"Challenger-003","graded":graded,"pending":pending,
            "rejected":rejected,"graded_count":len(graded),
            "mean_brier":round(sum(x["brier"] for x in graded)/len(graded),8) if graded else None,
            "training_admission":"BLOCKED_UNTIL_PROVIDER_PROVENANCE_VERIFIED",
            "certified_take_count":0}
def main():
    p=argparse.ArgumentParser();p.add_argument("--predictions",required=True)
    p.add_argument("--results",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    def read(path):return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
    report=grade(read(a.predictions),read(a.results))
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in ("graded","pending","rejected")},sort_keys=True))
if __name__=="__main__":main()
