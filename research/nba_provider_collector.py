"""Fetch normalized NBA provider snapshots from explicitly configured HTTPS endpoints.

Never log tokens or create empty/fabricated betting artifacts. Endpoint owners must
provide JSON records in the schema consumed by nba_provider_snapshot_validation.
"""
import json,os,sys,urllib.request
from pathlib import Path
from research.nba_provider_snapshot_validation import validate

def collect(kind):
    prefix="NBA_"+kind.upper()
    url=os.environ.get(prefix+"_SNAPSHOT_URL","").strip()
    token=os.environ.get(prefix+"_SNAPSHOT_TOKEN","").strip()
    if not url:
        return {"kind":kind,"status":"NOT_CONFIGURED","count":0}
    if not url.startswith("https://") or "@" in url.split("/")[2]:
        raise ValueError(kind+": configured URL must be HTTPS without embedded credentials")
    headers={"Accept":"application/json","User-Agent":"FreddyNBAProviderCollector/1"}
    if token:headers["Authorization"]="Bearer "+token
    req=urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(req,timeout=25) as response:
        payload=json.load(response)
    validated=validate(payload,kind)
    if validated["record_count"]<1:
        return {"kind":kind,"status":"EMPTY","count":0}
    out=Path("provider_snapshots");out.mkdir(exist_ok=True)
    (out/(kind+".json")).write_text(json.dumps(payload,indent=2)+"\n")
    return {"kind":kind,"status":"SCHEMA_VALID_AUTHENTICITY_UNVERIFIED","count":validated["record_count"]}

def main():
    statuses=[]
    for kind in ("props","odds"):
        try:statuses.append(collect(kind))
        except Exception as exc:
            statuses.append({"kind":kind,"status":"ERROR","count":0,"error_type":type(exc).__name__})
    Path("provider_snapshots").mkdir(exist_ok=True)
    Path("provider_snapshots/discovery.json").write_text(json.dumps(statuses,indent=2)+"\n")
    print(json.dumps(statuses))
    if any(x["status"]=="ERROR" for x in statuses):sys.exit(1)

if __name__=="__main__":main()
