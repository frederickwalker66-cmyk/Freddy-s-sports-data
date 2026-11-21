"""New isolated Challenger-003: reproducible chronological binary-market predictor.
Champion-001 is never read or modified. Research probabilities are NOT certified.
Train from authenticated, point-in-time JSONL only; never infer probabilities from odds.
"""
import argparse, hashlib, json, math
from pathlib import Path
from research.challenger_002_baseline import timestamp, sigmoid

def train(rows, min_train=200, min_test=50):
    seen=set()
    clean=[]
    for r in rows:
        eid=r["event_id"]; start=timestamp(r["event_start_at"])
        obs=timestamp(r["observed_at"]); settled=timestamp(r["outcome_observed_at"])
        if not eid or eid in seen or obs>=start or settled<=start or type(r["outcome"]) is not int or r["outcome"] not in (0,1):
            raise ValueError("invalid_or_duplicate_or_postgame_row")
        seen.add(eid)
        f=r["features"]
        if not isinstance(f,dict) or not f or any(type(v) not in (int,float) or not math.isfinite(v) for v in f.values()):
            raise ValueError("invalid_features")
        clean.append((start,obs,settled,eid,f,r["outcome"]))
    clean.sort(key=lambda x:(x[0],x[3]))
    cut=int(len(clean)*0.7); tr=clean[:cut]; te=clean[cut:]
    if len(tr)<min_train or len(te)<min_test:
        return {"status":"HOLD","blockers":["INSUFFICIENT_POINT_IN_TIME_ROWS"],"train_rows":len(tr),"test_rows":len(te)}
    if any(x[1]>=te[0][0] or x[2]>=te[0][0] for x in tr):
        return {"status":"HOLD","blockers":["LABEL_OR_FEATURE_LEAKAGE_ACROSS_SPLIT"]}
    keys=sorted(tr[0][4])
    if any(sorted(x[4])!=keys for x in clean):
        return {"status":"HOLD","blockers":["FEATURE_SCHEMA_MISMATCH"]}
    means=[sum(x[4][k] for x in tr)/len(tr) for k in keys]
    std=[max(1e-9,(sum((x[4][k]-m)**2 for x in tr)/len(tr))**0.5) for k,m in zip(keys,means)]
    def vector(x):return [1.0]+[(x[4][k]-m)/s for k,m,s in zip(keys,means,std)]
    w=[0.0]*(len(keys)+1)
    for _ in range(500):
        grad=[0.0]*len(w)
        for x in tr:
            v=vector(x); err=sigmoid(sum(a*b for a,b in zip(w,v)))-x[5]
            for j in range(len(w)):grad[j]+=err*v[j]
        for j in range(len(w)):w[j]-=.05*(grad[j]/len(tr)+(.001*w[j] if j else 0))
    probs=[sigmoid(sum(a*b for a,b in zip(w,vector(x)))) for x in te]
    brier=sum((p-x[5])**2 for p,x in zip(probs,te))/len(te)
    base=sum(x[5] for x in tr)/len(tr)
    base_brier=sum((base-x[5])**2 for x in te)/len(te)
    artifact={"model_id":"Challenger-003","features":keys,"means":means,"std":std,"weights":w,
              "training_last_event":tr[-1][0].isoformat(),"holdout_first_event":te[0][0].isoformat()}
    return {"status":"RESEARCH_TRAINED_NOT_CERTIFIED","train_rows":len(tr),"test_rows":len(te),
            "holdout_brier":round(brier,6),"baseline_brier":round(base_brier,6),
            "holdout_beats_baseline":brier<base_brier,"artifact":artifact,
            "blockers":["PROVENANCE_AND_CALIBRATION_REVIEW","LIVE_ODDS_AND_ROSTER_VERIFICATION",
                        "INDEPENDENT_OUT_OF_SAMPLE_CERTIFICATION"],"certified_take_count":0}
def predict(artifact, features):
    if sorted(features)!=artifact["features"]:raise ValueError("feature_schema_mismatch")
    z=artifact["weights"][0]
    for i,k in enumerate(artifact["features"]):
        v=features[k]
        if type(v) not in (int,float) or not math.isfinite(v):raise ValueError("nonfinite_feature")
        z+=artifact["weights"][i+1]*(v-artifact["means"][i])/artifact["std"][i]
    return {"model_id":"Challenger-003","research_probability":round(sigmoid(z),6),
            "decision":"HOLD","certified":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--train");p.add_argument("--predict")
    p.add_argument("--artifact");p.add_argument("--features");p.add_argument("--output",required=True)
    a=p.parse_args()
    if a.train:
        rows=[json.loads(s) for s in Path(a.train).read_text().splitlines() if s.strip()]
        result=train(rows)
        if result.get("artifact") and a.artifact:
            Path(a.artifact).parent.mkdir(parents=True,exist_ok=True)
            Path(a.artifact).write_text(json.dumps(result["artifact"],sort_keys=True)+"\n")
            result["artifact_sha256"]=hashlib.sha256(Path(a.artifact).read_bytes()).hexdigest()
        result.pop("artifact",None)
    elif a.predict and a.artifact and a.features:
        result=predict(json.loads(Path(a.artifact).read_text()),json.loads(Path(a.features).read_text()))
    else:p.error("provide --train or --predict with --artifact and --features")
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,sort_keys=True))
if __name__=="__main__":main()
