"""SHA-256 manifest for research artifacts. No signatures or legal immutability.

A checksum copied beside an artifact detects unintentional changes but does
not independently authenticate its origin or make temporary Actions storage
durable. The frozen Champion model is never loaded, executed or modified.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path


def build(paths, run_id=None, commit=None):
    if not isinstance(paths,list) or not paths:
        raise ValueError("explicit nonempty artifact paths required")
    manifest=[]
    for x in paths:
        p=Path(x)
        if not p.is_file() or p.is_symlink():
            raise ValueError("missing or linked artifact")
        data=p.read_bytes()
        manifest.append({"name":p.name,"bytes":len(data),
                         "sha256":hashlib.sha256(data).hexdigest()})
    if len({x["name"] for x in manifest})!=len(manifest):
        raise ValueError("duplicate artifact names are ambiguous")
    return {
        "stage":"research_artifact_manifest",
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "github_run_id_unverified":str(run_id) if run_id else None,
        "source_commit_sha_unverified":str(commit) if commit else None,
        "artifacts":sorted(manifest,key=lambda x:x["name"]),
        "externally_signed":False,
        "durable_storage_verified":False,
        "independently_authenticated":False,
        "champion_001_modified":False,
        "warning":"Self-issued SHA256 detects later byte changes only. Sign and store separately with object lock and versioned long-term storage to prove custody."
    }


def verify(paths, manifest):
    current={Path(p).name:Path(p) for p in paths}
    expected={v["name"]:v for v in manifest["artifacts"]}
    if set(current)!=set(expected):
        return False
    for name,info in expected.items():
        p=current[name]
        if not p.is_file() or p.is_symlink():
            return False
        data=p.read_bytes()
        if len(data)!=info["bytes"] or hashlib.sha256(data).hexdigest()!=info["sha256"]:
            return False
    return True


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--files",nargs="+",required=True)
    p.add_argument("--run-id")
    p.add_argument("--commit")
    p.add_argument("--output",default="research_artifact_manifest.json")
    args=p.parse_args(argv)
    report=build(args.files,args.run_id,args.commit)
    dest=Path(args.output)
    if dest.exists():
        raise FileExistsError("refuse overwrite of existing research manifest")
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf8")
    if not verify(args.files,report):
        raise RuntimeError("artifact digest verification failed")
    print(json.dumps({"manifest":str(dest),"artifacts_verified":len(args.files),
                      "durable_storage_verified":False,
                      "independently_authenticated":False},sort_keys=True))


if __name__=="__main__":
    main()
