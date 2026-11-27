"""Source-observed NBA score adapter; no independent settlement authentication."""
from datetime import timedelta
from challenger_research_features import validated
from v8_all_sports_season_form import season_anchor, NY
from historical_outcomes import scoreboard_url
from v8_unified_hit_rate import timestamp

def adapt_team_history(history, cutoff):
    end=timestamp(cutoff)
    anchor,season=season_anchor("nba",end)
    result=[]
    seen=set()
    for row in history:
        if row.get("league")!="nba":
            continue
        validated(row)
        start=timestamp(row["event_start_utc"])
        observed=timestamp(row["retrieved_at_utc"])
        day=start.astimezone(NY).date()
        if row.get("season_type")!=2 or day<anchor:
            continue
        if observed>=end or start+timedelta(hours=48)>end or observed<start:
            continue
        if row["source_url"]!=scoreboard_url("nba",day):
            raise ValueError("scoreboard source mismatch")
        eid=row["espn_event_id"]
        if not eid or eid in seen:
            raise ValueError("duplicate event")
        seen.add(eid)
        home,away=row["home_team_espn_id"],row["away_team_espn_id"]
        hs,aw=row["home_score"],row["away_score"]
        if not home or not away or home==away or hs==aw:
            raise ValueError("invalid NBA final score identity")
        for team,opp,points,allowed in ((home,away,hs,aw),(away,home,aw,hs)):
            result.append(dict(subject_id=team,opponent_id=opp,game_id=eid,
                season=season,final=True,settled_utc=observed.isoformat(),
                team_points=points,opponent_points=allowed,
                source_authenticated=False))
    return result
