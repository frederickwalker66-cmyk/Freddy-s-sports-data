"""Privacy-conscious NBA odds nested schema diagnostics; never emit prices."""
from collections import Counter
from research.challenger_002_nba_research_join import field

MARKETS=("PregameOdds","LiveOdds","AlternateMarketPregameOdds")
def profile(rows):
    result={"status":"RESEARCH_ODDS_SCHEMA_ONLY","records":0,"markets":{},
            "draftkings_identity_verified":False,"certified_take_count":0}
    if not isinstance(rows,list):
        result["status"]="BLOCKED_INVALID_INPUT";return result
    result["records"]=len(rows)
    for market in MARKETS:
        kinds=Counter();object_keys=set();nested_keys=set();array_items=0
        for row in rows:
            value=field(row,market)
            if value is None:kinds["null"]+=1;continue
            if isinstance(value,list):
                kinds["list"]+=1;array_items+=len(value)
                items=value
            elif isinstance(value,dict):
                kinds["dict"]+=1;items=[value]
            else:
                kinds["scalar"]+=1;continue
            for item in items:
                if not isinstance(item,dict):continue
                object_keys.update(item.keys())
                for val in item.values():
                    if isinstance(val,dict):nested_keys.update(val.keys())
                    elif isinstance(val,list):
                        for sub in val:
                            if isinstance(sub,dict):nested_keys.update(sub.keys())
        result["markets"][market]={"value_types":dict(kinds),
            "item_count":array_items,"item_field_names":sorted(object_keys),
            "nested_field_names":sorted(nested_keys)}
    return result
