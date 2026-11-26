"""Inspect provider schema without exposing credentials or account data."""
import json
from v8_nfl_live_feed import collect
if __name__=="__main__":
    report=collect()
    print(json.dumps({"retrieved_utc":report["retrieved_utc"],"errors":report["errors"],
        "games":[{"id":g["id"],"state":g["state"],"players":g["players"]}
                 for g in report["games"] if g["state"]=="in"]},indent=2))
