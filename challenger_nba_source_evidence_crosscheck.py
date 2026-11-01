"""Cross-check independently asserted NBA source digests against retained bytes.

This is a research-only file-integrity bridge, not proof of source publication
time, upstream independence, final outcome correctness, or training eligibility.
"""
import argparse
import hashlib
import json
from pathlib import Path

KINDS=("schedule","pregame_features","final_outcome")

def audit(rows, archive_root):
    root=Path(archive_root).resolve()
    checked=0
    rejected=[]
    for index,row in enumerate(rows,1):
        checks=row.get("independent_checks") if isinstance(row,dict) else None
        if not isinstance(checks,dict):
            rejected.append({"line":index,"reason":"missing_independent_checks"})
            continue
        for kind in KINDS:
            sources=checks.get(kind,{}).get("sources",[]) if isinstance(checks.get(kind),dict) else []
            if not isinstance(sources,list) or len(sources)<2:
                rejected.append({"line":index,"kind":kind,"reason":"insufficient_source_records"})
                continue
            for j,source in enumerate(sources):
                name=source.get("archive_file") if isinstance(source,dict) else None
                digest=source.get("sha256") if isinstance(source,dict) else None
                if (not isinstance(name,str) or not name or Path(name).is_absolute()
                    or ".." in Path(name).parts or not isinstance(digest,str)
                    or len(digest)!=64 or any(ch not in "0123456789abcdef" for ch in digest)):
                    rejected.append({"line":index,"kind":kind,"source":j,"reason":"invalid_archive_reference"})
                    continue
                target=root/name
                if (not target.resolve().is_relative_to(root)
                    or any(part.is_symlink() for part in [target,*list(target.parents)[:len(Path(name).parts)]])
                    or not target.is_file()):
                    rejected.append({"line":index,"kind":kind,"source":j,"reason":"missing_or_unsafe_archive"})
                    continue
                if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
                    rejected.append({"line":index,"kind":kind,"source":j,"reason":"digest_mismatch"})
                    continue
                checked+=1
    return {"source_bytes_matching_declared_hashes":checked,
            "rejected_source_references":len(rejected),"rejections":rejected,
            "independent_publication_time_verified":False,
            "upstream_source_independence_verified":False,
            "qualified_training_examples":0,"certified_predictions":0,
            "bet_ready_selections":0,"champion_001_modified":False,
            "note":"Local hash agreement is not independent authentication; human/external source audit required."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="nba_independent_evidence.jsonl")
    p.add_argument("--archive-root",default="nba_archived_sources")
    p.add_argument("--output",default="challenger_results/nba_source_evidence_crosscheck.json")
    args=p.parse_args()
    path=Path(args.input)
    rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []
    result=audit(rows,args.archive_root)
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="rejections"},sort_keys=True))

if __name__=="__main__":
    main()
