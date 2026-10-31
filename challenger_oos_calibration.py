"""Independent out-of-sample Challenger metrics by league and market.

No model fitting, fabricated probabilities, inferred wagers, or sportsbook API.
Only externally authenticated evidence may enter certified scores. Unverified
research forecasts are counted as excluded. Real settled ROI needs receipts.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

MIN_HOLDOUT=50


def implied(american):
    if type(american) not in (int,float) or not math.isfinite(american) or abs(american)<100:
        raise ValueError("invalid American odds")
    return abs(american)/(abs(american)+100) if american<0 else 100/(american+100)


def score(rows, min_holdout=MIN_HOLDOUT):
    if not isinstance(rows,list) or min_holdout<1:
        raise ValueError("invalid diagnostic request")
    groups=defaultdict(list)
    exclusions=defaultdict(int)
    for row in rows:
        if not isinstance(row,dict):
            exclusions["invalid_row"]+=1
            continue
        league=row.get("league")
        market=row.get("market_type")
        if not isinstance(league,str) or not league or not isinstance(market,str) or not market:
            exclusions["invalid_market"]+=1;continue
        if (row.get("independent_outcome_verified") is not True
                or row.get("historical_pregame_features_verified") is not True
                or row.get("model_output_before_event_verified") is not True
                or row.get("chronological_holdout") is not True
                or row.get("model_training_excludes_holdout") is not True
                or row.get("champion_001_modified") is not False):
            exclusions["unverified_or_in_sample"]+=1;continue
        if row.get("settlement") not in ("WIN","LOSS"):
            exclusions["push_void_unsettled_excluded"]+=1;continue
        p=row.get("model_probability")
        y=int(row["settlement"]=="WIN")
        if type(p) not in (int,float) or not math.isfinite(p) or not 0<p<1:
            exclusions["missing_valid_model_probability"]+=1;continue
        # Keep sport/market versions independent; never pool soccer 3-way with a two-way.
        groups[(league,market,row.get("model_version","unspecified"))].append((p,y,row))
    result=[]
    for (league,market,version),data in sorted(groups.items()):
        data.sort(key=lambda x:(x[2].get("event_start_utc",""),x[2].get("event_id","")))
        n=len(data)
        p=[x[0] for x in data]; y=[x[1] for x in data]
        brier=sum((a-b)**2 for a,b in zip(p,y))/n
        logloss=-sum(b*math.log(max(a,1e-12))+(1-b)*math.log(max(1-a,1e-12)) for a,b in zip(p,y))/n
        hit=sum((a>=0.5)==bool(b) for a,b in zip(p,y))/n
        bins=[];ece=0
        for lo,hi in ((0,.2),(.2,.4),(.4,.6),(.6,.8),(.8,1.000001)):
            d=[(a,b) for a,b in zip(p,y) if lo<=a<hi]
            if d:
                pred=sum(x[0] for x in d)/len(d);actual=sum(x[1] for x in d)/len(d)
                ece+=len(d)/n*abs(pred-actual)
                bins.append({"range":[lo,min(hi,1)],"count":len(d),
                             "predicted":round(pred,6),"actual":round(actual,6)})
        market_pairs=[]
        verified_clv=[]
        receipts=[]
        for a,b,row in data:
            if (row.get("closing_market_two_sided_verified") is True
                    and row.get("same_book_closing_lines_verified") is True):
                try:
                    q1=implied(row["closing_side_american"])
                    q2=implied(row["closing_opposite_american"])
                    market_pairs.append((q1/(q1+q2),b))
                except (ValueError,KeyError):
                    pass
            if row.get("independent_closing_price_verified") is True:
                try:
                    verified_clv.append(implied(row["closing_side_american"])-implied(row["entry_american"]))
                except (KeyError,ValueError):
                    pass
            if (row.get("actual_bet_receipt_verified") is True
                    and row.get("bookmaker_settlement_verified") is True
                    and row.get("actual_wager") is True):
                try:
                    stake=row["stake_usd"]
                    odd=row["entry_american"]
                    implied(odd)
                    if type(stake) in (int,float) and math.isfinite(stake) and stake>0:
                        net=(stake*100/abs(odd) if odd<0 else stake*odd/100) if b else -stake
                        receipts.append((float(stake),net))
                except (KeyError,ValueError):
                    pass
        base = None
        if len(market_pairs)==n:
            base={
                "brier":round(sum((q-b)**2 for q,b in market_pairs)/n,6),
                "log_loss":round(-sum(b*math.log(max(q,1e-12))+
                                    (1-b)*math.log(max(1-q,1e-12))
                                    for q,b in market_pairs)/n,6),
                "comparison":"verified_two_sided_same_book_closing_no_vig"
            }
        result.append({
            "league":league,"market_type":market,"model_version":version,
            "holdout_samples":n,"minimum_holdout_met":n>=min_holdout,
            "brier":round(brier,6) if n>=min_holdout else None,
            "log_loss":round(logloss,6) if n>=min_holdout else None,
            "hit_rate_at_0_5":round(hit,6) if n>=min_holdout else None,
            "expected_calibration_error":round(ece,6) if n>=min_holdout else None,
            "calibration_bins":bins if n>=min_holdout else [],
            "no_vig_market_comparison":base if n>=min_holdout else None,
            "closing_line_value_avg_prob_points":
                round(sum(verified_clv)/n,6) if n>=min_holdout and len(verified_clv)==n else None,
            "actual_settled_roi":
                round(sum(net for _,net in receipts)/sum(stake for stake,_ in receipts),6)
                if n>=min_holdout and len(receipts)==n else None,
            "verified_settled_receipts":len(receipts),
            "certified":n>=min_holdout and base is not None and len(verified_clv)==n and len(receipts)==n,
            "warning":"Score metrics require independent provenance. No-vig baseline/CLV/real ROI are NULL until complete verified same-book quotes and actual settlement receipts exist."
        })
    return {
        "stage":"challenger_oos_calibration_by_sport_and_market",
        "rows_received":len(rows),"exclusions":dict(sorted(exclusions.items())),
        "league_market_reports":result,
        "qualified_groups_with_50plus":sum(x["minimum_holdout_met"] for x in result),
        "certified_groups":sum(x["certified"] for x in result),
        "champion_001_modified":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence",required=True)
    p.add_argument("--output",default="calibration_output/independent_oos_scorecard.json")
    args=p.parse_args(argv)
    rows=[json.loads(x) for x in Path(args.evidence).read_text(encoding="utf8").splitlines() if x.strip()]
    report=score(rows)
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps(report,sort_keys=True))


if __name__=="__main__":
    main()
