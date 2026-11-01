"""Fail-closed SHA-256 verification of archived NBA source bytes.

This verifies file integrity against declared hashes, NOT independent publication
timestamps, source origin, reviewer independence, or eligibility for training.
"""
import argparse
import hashlib
import json
from pathlib import Path

def verify(manifest, root):
    results=[]
    for item in manifest:
        name=item.get("file") if isinstance(item,dict) else None
        digest=item.get("sha256") if isinstance(item,dict) else None
        reason=None
        if not isinstance(name,str) or not name or not isinstance(digest,str) or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
            reason="invalid_manifest_entry"
        else:
            candidate=root/name
            if (Path(name).is_absolute() or ".." in Path(name).parts
                    or not candidate.resolve().is_relative_to(root.resolve())
                    or any(part.is_symlink() for part in (candidate, *candidate.parents) if part != root and part != root.parent)
                    or not candidate.is_file()):
                reason="missing_or_unsafe_source_file"
            elif hashlib.sha256(candidate.read_bytes()).hexdigest()!=digest:
                reason="source_digest_mismatch"
        results.append({"file":name,"integrity_match":reason is None,"reason":reason})
    return {"files_checked":len(results),"integrity_matches":sum(x["integrity_match"] for x in results),
            "failures":sum(not x["integrity_match"] for x in results),
            "results":results,"independently_authenticated_publication":False,
            "qualified_training_examples":0,"certified_predictions":0,
            "manifest_independently_authenticated":False,
            "hash_check_is_self_attestation_when_manifest_generated_same_run":True,
            "bet_ready_selections":0,"champion_001_modified":False,
            "note":"Hash agreement is file-integrity evidence only; no independent source authentication or training promotion."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",default="nba_source_receipts.json")
    p.add_argument("--root",default="nba_archived_sources")
    p.add_argument("--output",default="challenger_results/nba_source_integrity.json")
    args=p.parse_args()
    source=Path(args.manifest)
    records=json.loads(source.read_text()) if source.is_file() else []
    if not isinstance(records,list):
        raise ValueError("manifest must be a JSON list")
    report=verify(records,Path(args.root))
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="results"},sort_keys=True))

if __name__=="__main__":
    main()
