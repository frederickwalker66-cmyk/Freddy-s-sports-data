"""Inspect paired NBA snapshots without assuming the SportsDataIO odds schema.

Only produces non-sensitive schema and join diagnostics. No game prices,
player records, or licensed rows are emitted. No certified bets.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

def profile(scores, odds):
    if not isinstance(scores,list) or not isinstance(odds,list):
        return {"status":"BLOCKED","reason":"NON_ARRAY_INPUT","certified_take_count":0}
    def keys(rows):
        return sorted({k for row in rows if isinstance(row,dict) for k in row})
    score_keys=keys(scores)
    odds_keys=keys(odds)
    candidates=("GameID","GameId","GameIDOriginal","Game")
    def ids(rows,field):
        result=[]
        for row in rows:
            if isinstance(row,dict) and row.get(field) is not None:
                val=row[field]
                if isinstance(val,(str,int)) and str(val).strip():
                    result.append(str(val))
        return result
    diagnostics=[]
    for field in candidates:
        a=ids(scores,field); b=ids(odds,field)
        if not a or not b: continue
        common=set(a)&set(b)
        diagnostics.append({"field":field,"scores_with_key":len(a),
                            "odds_with_key":len(b),
                            "unique_matching_ids":len(common),
                            "scores_duplicate_ids":sum(v-1 for v in Counter(a).values() if v>1),
                            "odds_duplicate_ids":sum(v-1 for v in Counter(b).values() if v>1)})
    return {"status":"RESEARCH_SCHEMA_DIAGNOSTIC_ONLY",
            "score_records":len(scores),"odds_records":len(odds),
            "scores_top_level_keys":score_keys,
            "odds_top_level_keys":odds_keys,
            "join_candidates":diagnostics,
            "pregame_custody_verified":False,
            "draftkings_market_verified":False,
            "training_rows_approved":0,
            "certified_take_count":0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--scores",required=True)
    p.add_argument("--odds",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    result=profile(json.loads(Path(args.scores).read_text()),
                   json.loads(Path(args.odds).read_text()))
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result["status"],"certified_take_count":0}))
if __name__=="__main__":
    main()
