"""Read-only inventory of trained Challenger NBA artifact readiness."""
import argparse
import json
from pathlib import Path
from challenger_nba_probability import VERSION, digest

def inspect(path):
    if not path:
        return {"status":"HOLD","reason":"artifact_path_not_configured","predictions":0,"certified_takes":0}
    p=Path(path)
    if not p.is_file() or p.is_symlink():
        return {"status":"HOLD","reason":"trained_artifact_missing_or_unsafe","predictions":0,"certified_takes":0}
    try:
        model=json.loads(p.read_text())
        if not isinstance(model,dict): raise ValueError("invalid_artifact")
        expected=model.get("artifact_sha256")
        copy=dict(model)
        copy.pop("artifact_sha256",None)
        if not isinstance(expected,str) or digest(copy)!=expected:
            raise ValueError("artifact_digest_mismatch")
        if model.get("version")!=VERSION or model.get("lane")!="Challenger-001":
            raise ValueError("wrong_model")
        if model.get("champion_001_modified") is not False or model.get("qualified_for_real_money_wagers") is not False:
            raise ValueError("unsafe_model_flags")
        if model.get("holdout_excluded_from_coefficients") is not True:
            raise ValueError("holdout_not_separated")
        return {"status":"ARTIFACT_INTEGRITY_VERIFIED_RESEARCH_ONLY","reason":"independent_provenance_and_pregame_inputs_not_verified","predictions":0,"certified_takes":0}
    except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError) as exc:
        return {"status":"HOLD","reason":str(exc),"predictions":0,"certified_takes":0}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--artifact",default="")
    args=parser.parse_args()
    print(json.dumps(inspect(args.artifact),sort_keys=True))
