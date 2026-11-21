"""Fail-closed NBA score/odds research join. No certified training data is emitted."""
import hashlib
import json
from collections import Counter

def field(row, name):
    if not isinstance(row, dict):
        return None
    matches=[k for k in row if k.casefold()==name.casefold()]
    return row[matches[0]] if len(matches)==1 else None

def build(scores, odds, scores_meta, odds_meta):
    result={"status":"RESEARCH_JOIN_ONLY","certified_take_count":0,
            "training_rows_approved":0,"pregame_eligible_rows":0,
            "joined_game_count":0,"rejected_count":0,
            "blockers":["INDEPENDENT_PREGAME_CUSTODY_UNVERIFIED",
                        "DRAFTKINGS_MARKET_IDENTITY_UNVERIFIED",
                        "FINAL_OUTCOMES_NOT_INDEPENDENTLY_VERIFIED"],
            "research_join_rows":[]}
    if not isinstance(scores,list) or not isinstance(odds,list) or not isinstance(scores_meta,dict) or not isinstance(odds_meta,dict):
        result["status"]="BLOCKED_INVALID_INPUT"
        return result
    if scores_meta.get("date") != odds_meta.get("date"):
        result["status"]="BLOCKED_DATE_MISMATCH"
        return result
    if scores_meta.get("kind")!="nba_scores" or odds_meta.get("kind")!="nba_odds":
        result["status"]="BLOCKED_SOURCE_KIND"
        return result
    def index(rows):
        ids=[str(field(r,"GameID")) for r in rows if field(r,"GameID") is not None]
        counts=Counter(ids)
        return {str(field(r,"GameID")):r for r in rows if field(r,"GameID") is not None and counts[str(field(r,"GameID"))]==1}, counts
    s,sc=index(scores);o,oc=index(odds)
    duplicate=set(k for k,v in sc.items() if v>1)|set(k for k,v in oc.items() if v>1)
    for gid in sorted(set(s)&set(o)-duplicate):
        sr=s[gid];orr=o[gid]
        sg=field(sr,"GlobalGameID");og=field(orr,"GlobalGameID")
        if sg is None or og is None or str(sg)!=str(og):
            result["rejected_count"]+=1
            continue
        result["research_join_rows"].append({
            "game_id_sha256":hashlib.sha256(gid.encode()).hexdigest(),
            "game_date":scores_meta["date"],
            "scores_retrieved_at":scores_meta.get("retrieved_at"),
            "odds_retrieved_at":odds_meta.get("retrieved_at"),
            "scores_payload_sha256":scores_meta.get("canonical_payload_sha256"),
            "odds_payload_sha256":odds_meta.get("canonical_payload_sha256"),
            "pregame_market_field_present":isinstance(field(orr,"PregameOdds"),(list,dict)),
            "live_market_field_present":isinstance(field(orr,"LiveOdds"),(list,dict)),
            "certified":False})
    result["joined_game_count"]=len(result["research_join_rows"])
    result["rejected_count"]+=len(duplicate)+len(set(s)^set(o))
    return result

if __name__=="__main__":
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser()
    for k in ("scores","odds","scores-meta","odds-meta","output"):
        p.add_argument("--"+k,required=True)
    a=p.parse_args()
    result=build(json.loads(Path(a.scores).read_text()),json.loads(Path(a.odds).read_text()),
                 json.loads(Path(a.scores_meta).read_text()),json.loads(Path(a.odds_meta).read_text()))
    Path(a.output).write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="research_join_rows"}))
