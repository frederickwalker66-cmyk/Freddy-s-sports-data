"""#89-92: source-time prior-score availability and hypothetical Elo diagnostics.

Read-only research, never model training. Distinguishes strict observed-at
source availability from hindsight Elo with an assumed 48-hour lag.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from itertools import groupby
import json
import math
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import zipfile

from challenger_library_archive_audit import audit_history

LEAGUES = ('nba','nfl','mlb','nhl','ncaaf','ncaab','mls','uefa_champions_league')
SOCCER = {'mls', 'uefa_champions_league'}
WARMUP = 80
MIN_EVALUATION = 30
EMBARGO_HOURS = 48
ELO_K = 20.0
HOME_ADVANTAGE = 60.0


def utc(value):
    if not isinstance(value,str):
        raise ValueError("missing_utc_timestamp")
    d=datetime.fromisoformat(value.replace("Z","+00:00"))
    if d.tzinfo is None:
        raise ValueError("timestamp_must_be_offset_aware")
    return d.astimezone(timezone.utc)


def checked_zip(path):
    z=zipfile.ZipFile(path)
    info=z.infolist()
    if (len(info)>100 or sum(i.file_size for i in info)>25_000_000
            or len({i.filename for i in info})!=len(info)
            or any(i.flag_bits & 1 or i.filename.startswith("/")
                   or ".." in Path(i.filename).parts for i in info)):
        z.close()
        raise ValueError("invalid_input_zip_members")
    return z


def read_rows(path):
    """Validate bytes, SQLite and noncertification BEFORE examining results."""
    audit=audit_history(path)
    with checked_zip(path) as z:
        raw=z.read('historical_published_scores.sqlite')
    with TemporaryDirectory() as tmp:
        p=Path(tmp)/'history.sqlite'
        p.write_bytes(raw)
        con=sqlite3.connect('file:'+str(p)+'?mode=ro&immutable=1',uri=True)
        try:
            con.execute('PRAGMA query_only=ON')
            con.execute('PRAGMA trusted_schema=OFF')
            rows=con.execute('''SELECT league,espn_event_id,start_utc,
                home_team_id,away_team_id,home_score,away_score,
                published_result,season_type,
                bookmaker_settlement_verified,independent_outcome_adjudication,
                historically_qualified_training FROM published_games''').fetchall()
            observations=con.execute('''SELECT league,espn_event_id,
                retrieved_at_utc,eligible_for_training FROM source_observations''').fetchall()
        finally:
            con.close()
    obs=defaultdict(list)
    for lg,eid,retrieved,ready in observations:
        if ready!=0:
            raise ValueError('recovered_observation_attempted_training_promotion')
        obs[(lg,eid)].append(utc(retrieved))
    games=[]
    for lg,eid,started,home,away,hs,as_,outcome,season_type,settlement,official,training in rows:
        start=utc(started)
        if (lg not in LEAGUES or not str(eid).isdigit()
                or not home or not away or home==away
                or type(hs) is not int or type(as_) is not int
                or min(hs,as_)<0 or max(hs,as_)>999
                or outcome!=('home' if hs>as_ else 'away' if hs<as_ else 'draw')
                or settlement!=0 or official!=0 or training!=0):
            raise ValueError('unsafe_recovered_score_or_unverified_settlement')
        seen=obs.get((lg,eid),[])
        if not seen or min(seen)<start:
            raise ValueError('missing_or_unexpected_pregame_final_score_receipt')
        games.append({
            'league':lg,'event_id':eid,'start':start,
            'home_id':str(home),'away_id':str(away),
            'home_score':hs,'away_score':as_,'result':outcome,
            'first_score_observed':min(seen),'season_type':season_type,
        })
    expected=audit.get('deduplicated_historical_games',audit.get('historical_games_unique'))
    if len(games)!=expected or set(obs)!={(g['league'],g['event_id']) for g in games}:
        raise ValueError('library_history_row_counts_unreconciled')
    return sorted(games,key=lambda x:(x['start'],x['league'],x['event_id'])),audit


def strict_asof_review(games):
    """Only scores actually retrieved before each later game can inform it."""
    reports={}
    for lg in LEAGUES:
        group=[g for g in games if g['league']==lg]
        seen_ids=set()
        seen_results=[]
        ready=0
        prior_count=0
        examples=[]
        for game in group:
            if game['event_id'] in seen_ids:
                raise ValueError('duplicate_event_in_strict_asof')
            seen_ids.add(game['event_id'])
            cutoff=game['start']
            earlier=[x for x in seen_results
                     if x['first_score_observed']<cutoff and
                     x['start']+timedelta(hours=EMBARGO_HOURS)<=cutoff]
            prior_count+=len(earlier)
            home_games=[x for x in earlier if game['home_id'] in
                        (x['home_id'],x['away_id'])]
            away_games=[x for x in earlier if game['away_id'] in
                        (x['home_id'],x['away_id'])]
            # Strict availability is STILL not independently attested.
            if lg not in SOCCER and len(home_games)>=3 and len(away_games)>=3:
                ready+=1
                if len(examples)<3:
                    examples.append(game['event_id'])
            seen_results.append(game)
        reports[lg]={
            'distinct_game_scores':len(group),
            'earlier_result_observations_accessible_by_event_start':prior_count,
            'events_with_three_prior_team_results_observed_pregame_research_only':ready,
            'example_espn_event_ids_research_only':examples,
            'historical_feature_publication_authenticated':False,
            'qualified_training_games':0,
        }
    return reports


def hypothetical_elo(games):
    """Hindsight-only Elo: ASSUMED lag, deliberately ignores archive retrieval.

    Not a valid as-of score, not a native Challenger model and not wager-ready.
    Simultaneous games are scored before any same-time outcomes are applied.
    """
    results={}
    for league in LEAGUES:
        group=sorted((g for g in games if g['league']==league),
                     key=lambda x:(x['start'],x['event_id']))
        if league in SOCCER:
            results[league]={
                'status':'three_way_soccer_model_required',
                'published_games':len(group),'evaluation_games':0,
                'hypothetical_brier':None,'hypothetical_log_loss':None}
            continue
        ratings=defaultdict(lambda:1500.0)
        pending=[]
        scored=[]
        draws=0
        for tip,batch in groupby(group,key=lambda g:g['start']):
            ready=[p for p in pending if p[0]<=tip]
            pending=[p for p in pending if p[0]>tip]
            for _,home,away,y,p in sorted(ready,key=lambda r:(r[0],r[1],r[2])):
                move=ELO_K*(y-p)
                ratings[home]+=move
                ratings[away]-=move
            for g in batch:
                if g['result']=='draw':
                    draws+=1
                    continue
                home,away=g['home_id'],g['away_id']
                p=1/(1+10**((ratings[away]-ratings[home]-HOME_ADVANTAGE)/400))
                y=1 if g['result']=='home' else 0
                if not 0<p<1:
                    raise ValueError('invalid_research_elo_probability')
                scored.append((p,y))
                pending.append((tip+timedelta(hours=EMBARGO_HOURS),home,away,y,p))
        evaluated=scored[WARMUP:]
        enough=len(evaluated)>=MIN_EVALUATION
        results[league]={
            'status':'hypothetical_retrospective_diagnostic_only' if enough else
                     'insufficient_retro_eval_games',
            'published_games':len(group),
            'excluded_draws':draws,
            'hypothetical_warmup_games':min(WARMUP,len(scored)),
            'evaluation_games':len(evaluated),
            'hypothetical_brier':round(sum((p-y)**2 for p,y in evaluated)/len(evaluated),6)
                                if enough else None,
            'neutral_50_50_brier':0.25 if enough else None,
            'hypothetical_log_loss':round(-sum(y*math.log(p)+(1-y)*math.log(1-p)
                                for p,y in evaluated)/len(evaluated),6) if enough else None,
        }
    return results


def review(path):
    games,audit=read_rows(path)
    strict=strict_asof_review(games)
    hindsight=hypothetical_elo(games)
    total_strict=sum(
        x['events_with_three_prior_team_results_observed_pregame_research_only']
        for x in strict.values())
    return {
        'stage':'challenger_92_library_asof_feature_and_counterfactual_elo_review',
        'source_zip_sha256':audit.get('history_zip_sha256',audit.get('original_zip_sha256')),
        'original_zip_and_sqlite_integrity_verified_locally':True,
        'distinct_historical_games':len(games),
        'source_observations_seen_after_game_start':audit.get(
            'source_observations_retrieved_after_or_at_game_start',
            audit.get('retrieved_at_or_after_kickoff')),
        'strict_asof_research_games_with_prior_source_access':total_strict,
        'strict_asof_by_league':strict,
        'hypothetical_retrospective_elo_48h_assumption_by_league':hindsight,
        'actual_pregame_forecasts_generated':0,
        'hypothetical_elo_is_not_native_challenger_model':True,
        'historical_asof_original_source_publication_authenticated':False,
        'historical_final_result_adjudication_authenticated':False,
        'historical_250_qualified_training_holdout_met':False,
        'model_training_performed':False,
        'calibration_independently_certified':False,
        'direct_draftkings_market_prices_verified':0,
        'certified_champion_001_predictions':0,
        'certified_challenger_001_predictions':0,
        'certified_positive_ev_bets':0,
        'automated_bets_placed':0,
        'champion_001_modified':False,
        'release_decision':'HOLD_NO_TRAINING_OR_DEPLOYMENT',
        'warning':('Archive first-seen score timestamps were postgame. Hypothetical '
                   'Elo assumes historical final scores could be used 48h after games, '
                   'even if the archive was retrieved much later. Such diagnostics '
                   'are NOT actual pregame forecasts, independent model validation, '
                   'betting edges, or certified training observations.'),
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args(argv)
    r=review(a.archive)
    out=Path(a.output)
    if out.exists():
        raise FileExistsError('research_report_must_not_overwrite')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n',encoding='utf8')
    print(json.dumps({
        'distinct_games':r['distinct_historical_games'],
        'strict_asof_research_games':r['strict_asof_research_games_with_prior_source_access'],
        'certified_predictions':0,'champion_001_modified':False},sort_keys=True))


if __name__=='__main__':
    main()
