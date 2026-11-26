"""Read-only ticket tracking; missing observations remain unknown."""
import json
from datetime import date
from v8_nfl_live_feed import collect
from v8_nfl_live_grading import grade_prop, grade_spread

LEGS = [
 ("CHI","DET","Colston Loveland","receiving",53),
 ("CHI","DET","DET","spread",1.5),
 ("CHI","DET","Amon-Ra St. Brown","receiving",82),
 ("PHI","DAL","Saquon Barkley","rushing",65),
 ("PHI","DAL","Dak Prescott","passing",265),
 ("KC","BUF","James Cook","touchdown",1),
 ("KC","BUF","Rashee Rice","receiving",46),
 ("KC","BUF","KC","spread",3),
]

def integer(value):
    try:
        return int(value)
    except (TypeError,ValueError):
        return None

def track(feed):
    rows=[]
    for away,home,name,market,target in LEGS:
        row={"selection":name,"market":market,"target":target,"status":"UNKNOWN"}
        games=[g for g in feed.get("games",[]) if
               {t.get("team",{}).get("abbreviation") for t in g["teams"]}=={away,home}]
        if len(games)==1:
            g=games[0]
            final=g.get("completed") is True and g.get("state")=="post"
            row["game_id"]=g["id"]
            row["clock"]=g.get("clock")
            if g.get("state")=="pre":
                row["status"]="PREGAME"
            elif market=="spread":
                scores={t["team"]["abbreviation"]:integer(t.get("score")) for t in g["teams"]}
                other=home if name==away else away
                row.update(grade_spread(scores.get(name),scores.get(other),target,final))
            else:
                stats=[p for p in g.get("players",[]) if p["name"]==name]
                if market=="touchdown":
                    # Require explicit rushing and receiving TD counts; other scoring types need review.
                    row["reason"]="anytime_touchdown_requires_scoring_play_verification"
                else:
                    matches=[p for p in stats if p["category"]==market]
                    if len(matches)==1:
                        s=matches[0]["stats"]
                        value=integer(s.get({"receiving":"receivingYards","rushing":"rushingYards","passing":"passingYards"}[market],s.get("yards",s.get("YDS"))))
                        row.update(grade_prop(value,target,final))
            row["final_game"]=final
        rows.append(row)
    return {"legs":rows,"source":feed.get("source"),"retrieved_utc":feed.get("retrieved_utc"),
            "feed_status":feed.get("status"),"sportsbook_settlement_verified":False,
            "champion_modified":False}

if __name__=="__main__":
    print(json.dumps(track(collect(date(2026,11,26))),indent=2))
