"""Chronological calibration experiment on retrospective Elo ledger; research only."""
import math
from datetime import datetime

def evaluate(rows):
    games = []
    seen = set()
    for row in rows:
        key = row["espn_event_id"]
        if key in seen or row.get("record_type") != "v8_retrospective_NBA_Elo_event_replay_only":
            raise ValueError("duplicate_or_wrong_record")
        seen.add(key)
        t = datetime.fromisoformat(row["event_start_utc"])
        p = row["retrospective_simulated_home_win_probability"]
        y = row["published_score_home_won_research_label"]
        if t.tzinfo is None or type(p) not in (int,float) or not 0 < p < 1 or y not in (0,1):
            raise ValueError("invalid_record")
        games.append((t,p,int(y)))
    games.sort()
    report = {"status":"HOLD", "research_only":True, "champion_modified":False,
              "certified_predictions":0, "games":len(games)}
    if len(games)<350:
        return dict(report, reason="need_100_warmup_200_calibration_50_holdout")
    cutoff = games[-50][0]
    train = [g for g in games[100:] if g[0]<cutoff]
    test = [g for g in games if g[0]>=cutoff]
    if len(train)<200:
        return dict(report, reason="insufficient_disjoint_calibration_games")
    def adjust(p, scale):
        return 1/(1+math.exp(-scale*math.log(p/(1-p))))
    def metrics(data, scale):
        probs=[(adjust(p,scale),y) for _,p,y in data]
        return {"brier":sum((p-y)**2 for p,y in probs)/len(probs),
                "log_loss":-sum(y*math.log(max(p,1e-15))+(1-y)*math.log(max(1-p,1e-15)) for p,y in probs)/len(probs),
                "accuracy":sum((p>=.5)==bool(y) for p,y in probs)/len(probs)}
    scale=min((.25,.5,.75,1.,1.25,1.5,2.),key=lambda s:metrics(train,s)["log_loss"])
    baseline=metrics(test,1.)
    candidate=metrics(test,scale)
    return dict(report, status="RETROSPECTIVE_RESEARCH_ONLY", calibration_games=len(train),
                holdout_games=len(test), scale=scale, baseline=baseline, candidate=candidate,
                improved_brier_and_log_loss=candidate["brier"]<baseline["brier"] and candidate["log_loss"]<baseline["log_loss"],
                warning="Reconstructed forecasts; not independent certification or evidence of ROI.")
