"""Create a research-only SHA-256 receipt manifest from real archived NBA files.

This tool does not fetch historical pages, authenticate publication times,
or qualify model training data. It records integrity of bytes already saved.
"""
import argparse
import hashlib
import json
from pathlib import Path

def inventory(root):
    if not root.is_dir():
        return []
    records=[]
    for file in sorted(root.rglob("*")):
        if not file.is_file() or file.is_symlink():
            continue
        relative=file.relative_to(root).as_posix()
        if any(part.startswith(".") for part in file.relative_to(root).parts):
            continue
        records.append({"file":relative,"sha256":hashlib.sha256(file.read_bytes()).hexdigest()})
    return records

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",default="nba_archived_sources")
    p.add_argument("--manifest",default="nba_source_receipts.json")
    p.add_argument("--report",default="challenger_results/nba_source_inventory.json")
    a=p.parse_args()
    root=Path(a.root)
    records=inventory(root)
    manifest=Path(a.manifest)
    manifest.parent.mkdir(parents=True,exist_ok=True)
    manifest.write_text(json.dumps(records,indent=2,sort_keys=True)+"\n")
    report={"archived_files_found":len(records),"independently_authenticated_publication":False,
            "qualified_training_examples":0,"champion_001_modified":False,
            "warning":"File hashes record local byte integrity only, not independent provenance."}
    output=Path(a.report)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,sort_keys=True))

if __name__=="__main__":
    main()
