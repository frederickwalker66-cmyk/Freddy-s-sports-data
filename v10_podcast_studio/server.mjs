import http from 'node:http';import {timingSafeEqual,createHmac} from 'node:crypto';import {Script} from 'node:vm';
const people={Bella:['ZiWfeUWO2JpAtPiRibtD','Host and meeting manager'],David:['2W3ktgP14sBp51pZmeuS','Statistics analyst'],Cassidy:['DQhiAUrU5tMfpg9uNiku','Sharp Edge analyst'],Roger:['Qcs9afjSSfOxjd3ZXgP2','Parlay analyst'],Sarah:['V3vLUgWq7G1IeyDYZnIs','Risk manager'],'Adam Stone':['ZTCNLgI96Mvf8kTqLAmb','Moderator and audit engineer']};
const v10ModelGuide={identity:'Freddys Picks AI V10 studio integrates read-only V9/V10 research, not the frozen production model itself.',sports:['NBA','NFL','MLB','NHL','NCAAF','NCAAB','MLS','UEFA Champions League'],markets:['moneyline','spread','game total','player points','rebounds','assists','PTS+REB+AST','PTS+REB','PTS+AST','REB+AST','parlays'],analysis:['last five and last ten games','injuries and lineups','back-to-back and rest','DraftKings prices','line movement','closing line value (CLV)','probability calibration','expected value (EV)','data timestamps','independent validation'],governance:'Champion-001 is frozen. Challenger-001 research and training remain separate. Never invent native model probabilities, verified odds, outcomes, or positive EV. No certified pick without a documented pregame prediction, odds, model probability and independent result audit. Otherwise HOLD/PASS.',roles:{Bella:'Lead the meeting, coordinate analysts, summarize source status and disagreements.',David:'Analyze game and player historical samples, last 5/10, opponent, pace, injury, rest and data quality.',Cassidy:'Evaluate Sharp Edge, implied vs independently produced probability, EV, CLV and calibration; HOLD without evidence.',Roger:'Construct and stress-test parlays, correlated legs, combined probability and payout; do not label unverified legs as bets.',Sarah:'Assess bankroll exposure, risk, uncertainty, stale prices, correlation and missing evidence.', 'Adam Stone':'Moderate, verify source provenance, audit Champion vs Challenger separation and call out unsupported claims.'}};
const analystContext=(speaker)=>{const snap=globalThis.v10ResearchSnapshot;const reports=Array.isArray(snap?.reports)?snap.reports:[];const recent=reports.slice(0,18).map(x=>({name:String(x.name).slice(0,100),summary:String(x.summary).slice(0,1000)}));return JSON.stringify({model:v10ModelGuide,analyst:speaker,role:v10ModelGuide.roles[speaker],research:snap?{source:'signed GitHub research bridge',createdAt:snap.createdAt,receivedAt:snap.receivedAt,runId:snap.runId,reports:recent,certified:false}:{source:'none received since server start',reports:[],certified:false},note:'Signed research is context, not a verified live betting feed. Explicitly say when latest games, odds, injuries, player props or Champion probabilities are unavailable.'}).slice(0,13000)};
const scoreboardSources={NBA:'basketball/nba',NFL:'football/nfl',MLB:'baseball/mlb',NHL:'hockey/nhl',NCAAF:'football/college-football',NCAAB:'basketball/mens-college-basketball',MLS:'soccer/usa.1',UCL:'soccer/uefa.champions'};
let publicScoreboardCache={at:0,items:[],errors:[]};
const loadPublicScoreboards=async()=>{if(Date.now()-publicScoreboardCache.at<60000&&publicScoreboardCache.at)return publicScoreboardCache;const outcomes=await Promise.allSettled(Object.entries(scoreboardSources).map(async([sport,path])=>{const url='https://site.api.espn.com/apis/site/v2/sports/'+path+'/scoreboard';const r=await fetch(url,{headers:{accept:'application/json','user-agent':'Freddys-V10-Research/1.0'},signal:AbortSignal.timeout(7000)});if(!r.ok)throw Error(sport+' HTTP '+r.status);const j=await r.json();return {sport,events:(Array.isArray(j.events)?j.events:[]).slice(0,30).map(e=>({id:String(e.id||''),name:String(e.name||'').slice(0,140),date:e.date||null,status:e.status?.type?.description||null,shortStatus:e.status?.type?.shortDetail||null,competitors:(e.competitions?.[0]?.competitors||[]).map(c=>({team:c.team?.displayName||null,score:c.score||null,homeAway:c.homeAway||null})),source:'ESPN public scoreboard'}))}}));const items=[],errors=[];outcomes.forEach((x,i)=>{if(x.status==='fulfilled')items.push(x.value);else errors.push({sport:Object.keys(scoreboardSources)[i],error:String(x.reason?.message||'Unavailable').slice(0,110)})});publicScoreboardCache={at:Date.now(),items,errors};return publicScoreboardCache};

/* ET date-scoped daily slate. ESPN is a public scores/schedule provider, NOT a bookmaker.
 * Preserve every returned event (no 30-game cap); NCAA group 50 = Division I. */
const easternDate=(d=new Date())=>{
 const parts=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d).filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));
 return parts.year+'-'+parts.month+'-'+parts.day
};
const easternClock=date=>{if(!date||!Number.isFinite(Date.parse(date)))return 'Time unavailable';return new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(date))};
let dailySlateCache=new Map();
const dailySlateLoad=async(date=easternDate())=>{
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Number.isFinite(Date.parse(date+'T12:00:00Z')))throw Error('INVALID_SLATE_DATE');
 const existing=dailySlateCache.get(date);
 if(existing?.pending)return existing.pending;
 if(existing?.data&&Date.now()-existing.at<300000)return existing.data;
 const safeDate=date.replaceAll('-','');
 const task=(async()=>{
  const results=await Promise.allSettled(Object.entries(scoreboardSources).map(async([sport,path])=>{
   const url=new URL('https://site.api.espn.com/apis/site/v2/sports/'+path+'/scoreboard');
   url.searchParams.set('dates',safeDate);url.searchParams.set('limit','500');
   if(sport==='NCAAF'||sport==='NCAAB')url.searchParams.set('groups','50');
   const resp=await fetch(url,{headers:{accept:'application/json','user-agent':'Freddys-V10-DailySlate/1.0'},signal:AbortSignal.timeout(12000)});
   if(!resp.ok)throw Error(sport+' provider HTTP '+resp.status);
   const payload=await resp.json();
   if(!Array.isArray(payload.events))throw Error(sport+' invalid events format');
   const seen=new Set();
   const games=payload.events.map(event=>{
    const id=String(event.id||'').slice(0,36);
    const contest=event.competitions?.[0]||{};
    const teams=(contest.competitors||[]).map(x=>({team:String(x.team?.displayName||'Unknown').slice(0,110),abbreviation:String(x.team?.abbreviation||'').slice(0,12),score:x.score==null?null:String(x.score).slice(0,12),homeAway:x.homeAway||null,record:x.records?.[0]?.summary||null,teamId:String(x.team?.id||'').slice(0,24)}));
    const utc=event.date||contest.date||null;
    const status=String(event.status?.type?.description||'Scheduled').slice(0,90);const state=String(event.status?.type?.state||'pre').slice(0,20);
    return{id,sport,name:String(event.name||'').slice(0,180),startUTC:utc,startEastern:easternClock(utc),dateEastern:utc&&Number.isFinite(Date.parse(utc))?easternDate(new Date(utc)):null,status,shortStatus:String(event.status?.type?.shortDetail||'').slice(0,90),state,completed:!!event.status?.type?.completed,teams,neutralSite:!!contest.neutralSite,
      review:{reviewed:'SCHEDULE_AND_SCORE_ONLY',moneyline:'HOLD: sportsbook price and certified probability required',spread:'HOLD: line and certified probability required',total:'HOLD: total price and certified probability required',playerProps:'HOLD: verified player/game props, stats and injuries required',combos:'HOLD: correlation and joint probability unverified',calibratedChampionModel:false,betReady:false}};
   }).filter(x=>x.id&&x.dateEastern===date&&!seen.has(x.id)&&seen.add(x.id));
   games.sort((a,b)=>(Date.parse(a.startUTC)||0)-(Date.parse(b.startUTC)||0)||a.id.localeCompare(b.id));
   return {sport,games,returnedCount:payload.events.length,excludedOutsideEasternDate:payload.events.length-games.length,possibleTruncation:payload.events.length>=500,coverage:'ESPN date-filtered scoreboard with limit=500'+((sport==='NCAAF'||sport==='NCAAB')?' and Division I groups=50':''),source:'ESPN public scoreboard'}
  }));
  const sports=[],errors=[];
  results.forEach((r,i)=>{if(r.status==='fulfilled')sports.push(r.value);else errors.push({sport:Object.keys(scoreboardSources)[i],error:String(r.reason?.message||'feed unavailable').slice(0,170)})});
  const games=sports.flatMap(x=>x.games).sort((a,b)=>(Date.parse(a.startUTC)||0)-(Date.parse(b.startUTC)||0)||a.sport.localeCompare(b.sport));
  const board={dateEastern:date,timezone:'America/New_York',retrievedAt:new Date().toISOString(),source:'ESPN public scoreboards: schedules and scores, not sportsbook odds',
    leaguesRequested:8,leaguesReturned:sports.length,gameCount:games.length,sports,errors,
    potentiallyIncomplete:sports.filter(x=>x.possibleTruncation).map(x=>x.sport),verifiedBookmakerPrices:0,certifiedChampionProbabilities:0,
    perGameScheduleInspected:games.length,individualAnalystDebatesCompleted:0,perGameDecisions:{HOLD:games.length,PLAY:0},
    status:errors.length?'PARTIAL_COVERAGE':'SCHEDULES_RETRIEVED',
    consensus:{twoLeg:{status:'NO_PLAY',certifiedLegs:[],required:2},fiveLeg:{status:'NO_PLAY',certifiedLegs:[],required:5},reason:'No authenticated DraftKings prices, independently certified Champion-001 probabilities, timestamped injury/prop market verification, or parlay joint probability. Never fabricate or force legs.'},
    note:'ESPN is not a sportsbook, may delay/cap returned event coverage, and does not validate EV. College Division I uses groups=50. Only fixtures whose scheduled start falls on the selected Eastern date appear. This is a schedule/market-readiness check for every returned game, not independent player-form analysis, verified prices, or a claim that ESPN covers every fixture.'};
  dailySlateCache.set(date,{at:Date.now(),data:board});
  for(const [key,val] of dailySlateCache)if(key!==date&&Date.now()-val.at>3600000)dailySlateCache.delete(key);
  console.log('V10_DAILY_SLATE',JSON.stringify({date,leagues:board.leaguesReturned,games:board.gameCount,errors:board.errors,truncation:board.potentiallyIncomplete}));
  return board
 })();
 dailySlateCache.set(date,{at:Date.now(),pending:task,data:existing?.data});
 try{return await task}catch(e){dailySlateCache.delete(date);throw e}
};

/* Non-predictive team form, requested on demand. ESPN may not cover all events or seasons.
   Never infer a betting probability from win/loss form or historical trend alone. */
const teamFormCache=new Map();
const fetchTeamForm=async(sport,team,cutoffUTC)=>{
 const cacheKey=sport+':'+team.teamId+':'+String(cutoffUTC).slice(0,10);
 const cached=teamFormCache.get(cacheKey);
 if(cached&&Date.now()-cached.at<900000)return cached.report;
 if(!/^[a-z0-9_-]{1,24}$/i.test(team.teamId||''))return {team:team.team,source:'ESPN team schedule',status:'TEAM_ID_UNAVAILABLE',last5:[],last10:[]};
 const gameDateEastern=easternDate(new Date(cutoffUTC));const year=Number(gameDateEastern.slice(0,4)),month=Number(gameDateEastern.slice(5,7));const season=year+(['NBA','NHL','NCAAB','UCL'].includes(sport)&&month>=7?1:0);
 const url='https://site.api.espn.com/apis/site/v2/sports/'+scoreboardSources[sport]+'/teams/'+encodeURIComponent(team.teamId)+'/schedule?limit=250&season='+season;
 try{
  const resp=await fetch(url,{headers:{accept:'application/json','user-agent':'Freddys-V10-FormReview/1.0'},signal:AbortSignal.timeout(9500)});
  if(!resp.ok)throw Error('ESPN team schedule HTTP '+resp.status);
  const payload=await resp.json();
  if(!Array.isArray(payload.events))throw Error('No array of team schedule events');
  const games=payload.events.map(event=>{
   const contest=event.competitions?.[0]||{},teams=contest.competitors||[],self=teams.find(c=>String(c.team?.id||'')===team.teamId),opp=teams.find(c=>String(c.team?.id||'')!==team.teamId);
   const utc=event.date||contest.date||null,when=Date.parse(utc||'');
   if(!self||!opp||!Number.isFinite(when)||when>=Date.parse(cutoffUTC||''))return null;
   const type=event.status?.type||contest.status?.type||{};
   const finished=type.completed===true||type.state==='post'||type.name==='STATUS_FINAL'||event.status?.completed===true;
   if(!finished)return null;
   const valueOfScore=c=>c.score&&typeof c.score==='object'?(c.score.value??c.score.displayValue):c.score;
   const selfScore=Number(valueOfScore(self)),oppScore=Number(valueOfScore(opp));
   const haveScores=self.score!=null&&opp.score!=null&&Number.isFinite(selfScore)&&Number.isFinite(oppScore);
   const outcome=typeof self.winner==='boolean'?(self.winner?'W':haveScores&&selfScore===oppScore?'T':'L'):haveScores?(selfScore>oppScore?'W':selfScore<oppScore?'L':'T'):null;
   if(!outcome)return null;
   return {dateUTC:utc,dateEastern:easternDate(new Date(when)),opponent:String(opp.team?.displayName||'Unknown').slice(0,90),homeAway:String(self.homeAway||'').slice(0,12),result:outcome,teamScore:haveScores?selfScore:null,opponentScore:haveScores?oppScore:null,eventId:String(event.id||'').slice(0,36)}
  }).filter(Boolean).sort((a,b)=>Date.parse(b.dateUTC)-Date.parse(a.dateUTC));
  if(!games.length)console.log('V10_TEAM_FORM_EMPTY',JSON.stringify({sport,teamId:team.teamId,season,returned:payload.events.length,sample:payload.events.slice(0,2).map(e=>({date:e.date,id:e.id,completed:e.status?.type?.completed??e.competitions?.[0]?.status?.type?.completed,state:e.status?.type?.state??e.competitions?.[0]?.status?.type?.state,statusKeys:Object.keys(e.status||{}),competitionStatusKeys:Object.keys(e.competitions?.[0]?.status||{}),ids:(e.competitions?.[0]?.competitors||[]).map(c=>c.team?.id),scores:(e.competitions?.[0]?.competitors||[]).map(c=>c.score)}))}));
 const count=(arr)=>({games:arr.length,wins:arr.filter(x=>x.result==='W').length,losses:arr.filter(x=>x.result==='L').length,ties:arr.filter(x=>x.result==='T').length});
  const report={team:team.team,teamId:team.teamId,source:'ESPN public team season schedule',fetchedAt:new Date().toISOString(),status:games.length?'AVAILABLE':'NO_COMPLETED_GAMES_RETURNED',
   last5:games.slice(0,5),last10:games.slice(0,10),last5Record:count(games.slice(0,5)),last10Record:count(games.slice(0,10)),
   sourceCoverage:'Only completed events returned by ESPN for this team before the selected game. Other seasons or providers may not be represented.'};
  teamFormCache.set(cacheKey,{at:Date.now(),report});return report;
 }catch(e){return {team:team.team,teamId:team.teamId,source:'ESPN public team season schedule',fetchedAt:new Date().toISOString(),status:'UNAVAILABLE',error:String(e.message||e).slice(0,130),last5:[],last10:[]}}
};
const selectedGameForm=async(date,sport,eventId)=>{
 const slate=await dailySlateLoad(date);
 const selected=slate.sports.find(x=>x.sport===sport)?.games.find(x=>x.id===eventId);
 if(!selected)throw Error('SCHEDULED_GAME_NOT_FOUND');
 const reports=await Promise.all(selected.teams.slice(0,2).map(team=>fetchTeamForm(sport,team,selected.startUTC)));
 return {source:'ESPN public team schedules',verifiedAt:new Date().toISOString(),dateEastern:date,sport,gameId:eventId,gameName:selected.name,
   teams:reports,confidenceNote:'These are descriptive completed-game records, NOT an independently calibrated probability. Injuries, player props, bookmaker lines, and Champion-001 probabilities are unavailable.',
   certifiedEV:0,betReady:false,decision:'HOLD'}
};


/* Odds preflight: calculations on user-reported quotes only.
 * No sportsbook authentication, no independently certified model p, no betting execution. */
const americanImplied=price=>{
 if(typeof price!=='number'||!Number.isInteger(price)||Math.abs(price)<100||Math.abs(price)>50000)return null;
 return price>0?100/(price+100):(-price)/((-price)+100)
};
const oddsPreflightMath=(american,opposite)=>{
 const probability=americanImplied(american),other=opposite==null?null:americanImplied(opposite);
 if(probability==null||opposite!=null&&other==null)throw Error('INVALID_AMERICAN_ODDS');
 return {americanOdds:american,breakEvenProbability:probability,breakEvenPercent:Math.round(probability*10000)/100,
  opposingAmericanOdds:opposite==null?null:opposite,
  pairedImpliedProbability:other,
  pairedOverround:other==null?null:probability+other-1,
  pairedNoVigProbability:other==null?null:probability/(probability+other),
  sourceClass:'USER_REPORTED_NOT_VERIFIED',isChampion001ModelProbability:false}
};
const auditOddsPreflight=async raw=>{
 if(!raw||typeof raw!=='object'||Array.isArray(raw))throw Error('INVALID_QUOTE_OBJECT');
 const date=String(raw.date||''),sport=String(raw.sport||''),gameId=String(raw.gameId||'');
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Object.hasOwn(scoreboardSources,sport)||!/^[a-zA-Z0-9_-]{1,36}$/.test(gameId))throw Error('INVALID_GAME_SCOPE');
 if(Math.abs(Date.parse(date+'T12:00:00Z')-Date.parse(easternDate()+'T12:00:00Z'))/86400000>14)throw Error('OUT_OF_SUPPORTED_DATE_WINDOW');
 const permitted=['moneyline','spread','total','player_points','player_rebounds','player_assists','player_combo'];
 const market=String(raw.market||'');
 if(!permitted.includes(market))throw Error('UNSUPPORTED_MARKET');
 const selection=String(raw.selection||'').trim();
 if(!selection||selection.length>110||/[<>{}\r\n]/.test(selection))throw Error('INVALID_SELECTION');
 const requireLine=market!=='moneyline';
 let line=null;
 if(requireLine){if(typeof raw.line!=='number'||!Number.isFinite(raw.line)||Math.abs(raw.line)>1000)throw Error('MISSING_VALID_LINE');line=raw.line}
 const americanOdds=raw.americanOdds,opposingOdds=raw.opposingOdds??null;
 const calc=oddsPreflightMath(americanOdds,opposingOdds);
 const sourceTime=typeof raw.observedAt==='string'&&raw.observedAt?Date.parse(raw.observedAt):NaN;
 const ageSeconds=Number.isFinite(sourceTime)?Math.round((Date.now()-sourceTime)/1000):null;
 const freshClaim=ageSeconds!=null&&ageSeconds>=0&&ageSeconds<=120;
 const slate=await dailySlateLoad(date);
 const game=slate.sports.find(x=>x.sport===sport)?.games.find(x=>x.id===gameId);
 if(!game)throw Error('GAME_NOT_IN_VERIFIED_SCHEDULE');
 const pregame=game.state==='pre'&&Number.isFinite(Date.parse(game.startUTC))&&Date.parse(game.startUTC)>Date.now();
 return {
  event:{dateEastern:date,sport,gameId,gameName:game.name,startUTC:game.startUTC,startEastern:game.startEastern,state:game.state,providerStatus:game.status},
  observation:{market,selection,line,providerClaim:'DraftKings — self-reported; NOT authenticated',observedAt:raw.observedAt||null,ageSeconds,
   sourceTimeWithin120Seconds: freshClaim,quoteVerifiedAtBook:false,eventIdentityVerifiedWithSportsbook:false,marketIdentityVerified:false,
   mainLineVerified:false,oppositeSideMarketIdentityVerified:false},
  arithmetic:{...calc,twoOutcomeMathApplicable:!(market==='moneyline'&&(sport==='MLS'||sport==='UCL')),
   pairedNoVigProbability:market==='moneyline'&&(sport==='MLS'||sport==='UCL')?null:calc.pairedNoVigProbability,
   pairedOverround:market==='moneyline'&&(sport==='MLS'||sport==='UCL')?null:calc.pairedOverround,
   note:'Break-even uses reported American odds. Paired no-vig is illustrative only: both quotes and identical two-way market identity were NOT independently verified.'},
  safeguards:{pregame,sourceFreshnessClaim:freshClaim,verifiedBookmakerPrice:false,verifiedChampion001ModelProbability:false,verifiedInjuries:false,verifiedPlayerPropSource:false,verifiedCorrelation:false},
  certifiedModelProbability:null,expectedValue:null,expectedValuePercent:null,certifiedSharpEdge:false,betReady:false,decision:'HOLD',
  summary:'Freddy, the arithmetic is valid for the user-reported price, but this is not authenticated live DraftKings odds, not a native Champion-001 probability, and not a certified bet. Do not promote to a two- or five-leg ticket.'
 }
};

const minimalDailyForModels=async()=>{
 const slate=await dailySlateLoad();
 return JSON.stringify({date:slate.dateEastern,retrievedAt:slate.retrievedAt,leagues:slate.sports.map(x=>({sport:x.sport,events:x.games.map(g=>({id:g.id,name:g.name,when:g.startEastern,status:g.shortStatus})).slice(0,12),count:x.games.length})),errors:slate.errors,allFullEventsAvailableVia:'/api/daily-slate',limit:'Partial context only. Never infer unsupplied games, odds, prediction probabilities or injury facts.'}).slice(0,13500)
};

const liveScoreboardContext=async()=>{const feed=await loadPublicScoreboards();return JSON.stringify({retrievedAt:new Date(feed.at).toISOString(),source:'ESPN public scoreboard; informational, not a sportsbook feed',events:feed.items.map(x=>({sport:x.sport,events:x.events.slice(0,12)})),errors:feed.errors,notAvailable:['DraftKings sportsbook odds','player prop prices','injury verification','Champion-001 native model probabilities','certified Sharp Edge']}).slice(0,14000)};

const modelResearchPaths={
 NBA:{path:'data/v8_forward/LEADERBOARD.json',branch:'research/forward-ledger'},
 NFL:{path:'data/v8_forward/nfl/FORWARD_RESEARCH_LEADERBOARD.json',branch:'research/nfl-nhl-forward-ledger'},
 NHL:{path:'data/v8_forward/nhl/FORWARD_RESEARCH_LEADERBOARD.json',branch:'research/nfl-nhl-forward-ledger'}
};
let modelResearchCache={at:0,board:null};
const fetchModelJson=async(entry)=>{
 const url='https://api.github.com/repos/frederickwalker66-cmyk/Freddy-s-sports-data/contents/'+entry.path+'?ref='+encodeURIComponent(entry.branch);
 const headers={accept:'application/vnd.github+json','user-agent':'freddys-v10-model-readonly','x-github-api-version':'2022-11-28'};
 if(process.env.GITHUB_READ_TOKEN)headers.authorization='Bearer '+process.env.GITHUB_READ_TOKEN;
 const r=await fetch(url,{headers,signal:AbortSignal.timeout(8500)});
 if(!r.ok)throw Error('GitHub model report HTTP '+r.status);
 const obj=await r.json();
 if(obj.encoding!=='base64'||typeof obj.content!=='string')throw Error('GitHub model report encoding unavailable');
 const raw=Buffer.from(obj.content.replace(/\s/g,''),'base64');
 if(raw.length>50000)throw Error('Model report exceeds safe size');
 return JSON.parse(raw.toString('utf8'));
};
const modelBoardFor=async()=>{
 if(modelResearchCache.board&&Date.now()-modelResearchCache.at<300000)return modelResearchCache.board;
 const records=await Promise.allSettled(Object.entries(modelResearchPaths).map(async([sport,path])=>({sport,source:path,data:await fetchModelJson(path)})));
 const models={},errors=[];
 for(let i=0;i<records.length;i++){
  const x=records[i],sport=Object.keys(modelResearchPaths)[i];
  if(x.status!=='fulfilled'){errors.push({sport,error:String(x.reason?.message||'unavailable').slice(0,130)});continue}
  const {data,source}=x.value;
  if(data.champion_001_modified!==false||data.certified_positive_ev_bets!==0||data.bet_ready!==false){
   errors.push({sport,error:'Research provenance or certification guard did not match; report withheld'});continue
  }
  const row=(data.research_model_scorecards_including_small_samples||data.research_model_scorecards_including_insufficient_samples||[])[0]||{};
  const graded=Number(sport==='NBA'?data.nba_forward_forecasts_graded_research_only:data.graded_research_games);
  if(!Number.isInteger(graded)||graded<0){errors.push({sport,error:'Missing graded research sample'});continue}
  const acc=sport==='NBA'?row.home_vs_away_classification_accuracy:row.research_direction_accuracy;
  const brier=sport==='NBA'?row.mean_Brier_lower_is_better:row.research_Brier;
  const researchAccuracy=typeof acc==='number'&&Number.isFinite(acc)?acc:null;
  const researchBrier=typeof brier==='number'&&Number.isFinite(brier)?brier:null;
  const generatedAt=data.generated_at_utc||null;
  models[sport]={
   label:'Genuine pregame Elo research only',sourceBranch:source.branch,sourcePath:source.path,
   generatedAt,ageHours:generatedAt&&Number.isFinite(Date.parse(generatedAt))?Math.round((Date.now()-Date.parse(generatedAt))/360000)/10:null,
   gradedResearchGames:graded,originalForecasts:Number(sport==='NBA'?data.nba_unique_original_forecasts_archived:data.original_saved_forecasts)||null,
   researchAccuracy,researchBrier,
   modelVersion:String(row.model_version||row.model||'').slice(0,100),
   researchStatus:String(data.status||data.ranking_status||'RESEARCH_ONLY').slice(0,120),
   independentlyCertified:false,champion001Certified:false,betReady:false,certifiedPositiveEV:0
  };
 }
 const board={
  status:Object.keys(models).length?'RESEARCH_ONLY':'RESEARCH_UNAVAILABLE',fetchedAt:new Date().toISOString(),
  source:'Public Github durable forward research ledgers, read-only',models,errors,
  sportsCoveredByScoresOnly:['MLB','NCAAF','NCAAB','MLS','UCL'],
  champion001Frozen:true,champion001Authenticated:false,certifiedChampionPredictions:0,
  verifiedLiveDraftKingsCheckout:false,certifiedEV:0,wagersPlaced:0,
  warning:'Historical pregame research reports are NOT current market prices, independently certified Champion-001 probabilities, reliable prop odds, profitable betting selections or verified same-game parlay EV. HOLD/PASS unless independently certified.'
 };
 modelResearchCache={at:Date.now(),board};return board
};


/* Server-owned read-only sports refresh: continues without any browser/voice room.
   ESPN = scores/schedules, GitHub = dated, uncertified research; never infer betting prices. */
const continuousFeed={startedAt:new Date().toISOString(),enabled:false,cycles:0,scoreChecks:0,slateChecks:0,modelChecks:0,lastCycleAt:null,nextCycleAt:null,warnings:[],lastSlateAt:0,lastModelAt:0};
const continuousFeedStatus=()=>{
 const score=publicScoreboardCache,board=dailySlateCache.get(easternDate())?.data,model=modelResearchCache.board;
 const age=t=>t==null?null:Math.max(0,Math.floor((Date.now()-t)/1000));
 const scoreAge=score.at?age(score.at):null;
 return {online:true,source:'Freddys V10 continuous public sports evidence',mode:continuousFeed.enabled?'CONTINUOUS':'STARTING',startedAt:continuousFeed.startedAt,lastCycleAt:continuousFeed.lastCycleAt,nextCycleAt:continuousFeed.nextCycleAt,completedCycles:continuousFeed.cycles,
  scores:{source:'ESPN public scoreboards',fetchedAt:score.at?new Date(score.at).toISOString():null,ageSeconds:scoreAge,leaguesRequested:8,leaguesReturned:score.items.length,leagues:score.items.map(x=>x.sport),liveGames:score.items.flatMap(x=>x.events.filter(e=>/in progress|live|halftime|intermission/i.test(String(e.status||''))).map(e=>({sport:x.sport,name:e.name,status:e.shortStatus||e.status}))).slice(0,20),errors:score.errors,fresh:scoreAge!==null&&scoreAge<=300,refreshCount:continuousFeed.scoreChecks},
  slate:{dateEastern:board?.dateEastern||easternDate(),fetchedAt:board?.retrievedAt||null,gamesReturned:board?.gameCount||0,leaguesReturned:board?.leaguesReturned||0,errors:board?.errors||[],refreshCount:continuousFeed.slateChecks},
  research:{source:'GitHub published historical Elo ledgers, not Champion-001',fetchedAt:model?.fetchedAt||null,sports:Object.keys(model?.models||{}),reportGeneratedAt:Object.fromEntries(Object.entries(model?.models||{}).map(([n,x])=>[n,x.generatedAt||null])),errors:model?.errors||[],refreshCount:continuousFeed.modelChecks},
  notConnected:['Authenticated DraftKings odds','verified player-prop prices','verified injuries','native frozen Champion-001 probabilities','certified Sharp Edge EV'],
  champion001Frozen:true,certifiedPredictions:0,certifiedEV:0,bettingDecision:'HOLD',warnings:continuousFeed.warnings.slice(-5),
  refreshPolicy:'Scoreboards 60s when any live game detected, 180s otherwise. Daily slate 5m, research 10m. While Railway service stays online; source availability and accuracy are not guaranteed.'};
};
const continuousFeedTick=async()=>{
 if(!continuousFeed.enabled)return;
 let live=false;continuousFeed.lastCycleAt=new Date().toISOString();
 try{
  const scores=await loadPublicScoreboards();continuousFeed.scoreChecks++;
  live=scores.items.some(x=>x.events.some(e=>/in progress|live|halftime|intermission/i.test(String(e.status||''))));
  if(scores.errors.length)continuousFeed.warnings.push('ESPN partial '+scores.errors.map(x=>x.sport).join(','));
 }catch(e){continuousFeed.warnings.push('ESPN '+String(e.message||e).slice(0,90))}
 if(Date.now()-continuousFeed.lastSlateAt>=300000){try{const board=await dailySlateLoad();continuousFeed.slateChecks++;continuousFeed.lastSlateAt=Date.now();if(board.errors.length)continuousFeed.warnings.push('Slate partial '+board.errors.map(x=>x.sport).join(','))}catch(e){continuousFeed.warnings.push('Slate '+String(e.message||e).slice(0,90))}}
 if(Date.now()-continuousFeed.lastModelAt>=600000){try{const board=await modelBoardFor();continuousFeed.modelChecks++;continuousFeed.lastModelAt=Date.now();if(board.errors.length)continuousFeed.warnings.push('Research partial '+board.errors.map(x=>x.sport).join(','))}catch(e){continuousFeed.warnings.push('Research '+String(e.message||e).slice(0,90))}}
 if(!v10SourceState.checkedAt||Date.now()-Date.parse(v10SourceState.checkedAt)>=900000)void refreshV10Sources().catch(e=>console.warn('V10_SOURCE_MONITOR_ERROR',String(e.message||e).slice(0,90)));
 continuousFeed.warnings=continuousFeed.warnings.slice(-5);continuousFeed.cycles++;
 const ms=live?60000:180000;continuousFeed.nextCycleAt=new Date(Date.now()+ms).toISOString();
 console.log('V10_CONTINUOUS_REFRESH',JSON.stringify({cycles:continuousFeed.cycles,leagues:publicScoreboardCache.items.length,live,scoreChecks:continuousFeed.scoreChecks,slateChecks:continuousFeed.slateChecks,modelChecks:continuousFeed.modelChecks,warnings:continuousFeed.warnings,next:continuousFeed.nextCycleAt}));
 setTimeout(continuousFeedTick,ms);
};
const launchContinuousFeed=()=>{if(continuousFeed.enabled)return;continuousFeed.enabled=true;void continuousFeedTick()};


/* GitHub workflow metadata only: never treat run success as authenticated sportsbook quotes. */
const v10SourceSpecs=[
 ['sharpapi','SharpAPI odds collector','collect-sharpapi.yml','odds_research'],
 ['sportsdataio','SportsDataIO research intake','sportsdataio-research-intake.yml','stats_research'],
 ['sportsgameodds','SportsGameOdds capped collection','sportsgameodds-research.yml','odds_research'],
 ['nba_injury','NBA injury source monitor','challenger-nba-injury-source.yml','roster_research'],
 ['pregame','Prospective pregame research','challenger-prospective-pregame.yml','shadow_research'],
 ['v10_bridge','Signed V10 research bridge','v10-research-bridge.yml','research_delivery']
];
const v10SourceState={checkedAt:null,status:'NOT_CHECKED',collectors:[],errors:[],pending:null};
const publicSourceReadiness=()=>({
 source:'GitHub Actions latest-100 run metadata, not provider data',checkedAt:v10SourceState.checkedAt,status:v10SourceState.status,errors:v10SourceState.errors,collectors:v10SourceState.collectors,
 certified:{draftKingsDirectPrices:false,playerPropPrices:false,injuriesAuthenticated:false,champion001NativeProbabilities:false,independentSharpEdgeEV:false,certifiedBets:0,decision:'HOLD'},
 caveat:'Workflow success does not verify API entitlements, the data inside a run, provider market prices, player injuries or independently certified model probabilities. A run not in the most recent 100 is unknown, not absent.'
});
const refreshV10Sources=async(force=false)=>{
 if(v10SourceState.pending)return v10SourceState.pending;
 if(!force&&v10SourceState.checkedAt&&Date.now()-Date.parse(v10SourceState.checkedAt)<900000)return publicSourceReadiness();
 const task=(async()=>{
  v10SourceState.checkedAt=new Date().toISOString();
  try{
   const headers={'accept':'application/vnd.github+json','user-agent':'freddys-v10-source-status','x-github-api-version':'2022-11-28'};
   if(process.env.GITHUB_READ_TOKEN)headers.authorization='Bearer '+process.env.GITHUB_READ_TOKEN;
   const response=await fetch('https://api.github.com/repos/frederickwalker66-cmyk/Freddy-s-sports-data/actions/runs?per_page=100',{headers,signal:AbortSignal.timeout(10000)});
   if(!response.ok)throw Error('GitHub Actions HTTP '+response.status);
   const j=await response.json();if(!Array.isArray(j.workflow_runs))throw Error('No GitHub workflow_runs in response');
   const runs=j.workflow_runs;
   v10SourceState.collectors=v10SourceSpecs.map(([key,name,file,type])=>{
    const relevant=runs.filter(r=>String(r.path||'').includes('/'+file)||String(r.path||'').startsWith('.github/workflows/'+file+'@')).sort((a,b)=>Date.parse(b.created_at||0)-Date.parse(a.created_at||0));
    const last=relevant[0],recentSuccess=relevant.find(x=>x.conclusion==='success');const t=last?.updated_at||last?.created_at||null;
    return {key,name,workflow:file,category:type,coverage:last?'RUN_METADATA_FOUND':'NOT_IN_RECENT_100',lastRunId:last?.id??null,lastRunEvent:last?.event||null,lastRunAt:t,lastStatus:last?.status||null,lastConclusion:last?.conclusion||null,ageHours:t&&Number.isFinite(Date.parse(t))?Math.round((Date.now()-Date.parse(t))/360000)/10:null,lastSuccessInWindow:recentSuccess?.updated_at||null,underlyingMarketDataAuthenticated:false,certifiedPicks:0};
   });
   v10SourceState.status='METADATA_RETRIEVED';v10SourceState.errors=[];
   console.log('V10_SOURCE_READINESS',JSON.stringify({status:v10SourceState.status,matched:v10SourceState.collectors.filter(x=>x.lastRunId).length,collectors:v10SourceState.collectors.map(x=>[x.key,x.lastConclusion,x.ageHours])}));
  }catch(e){v10SourceState.status='METADATA_UNAVAILABLE';v10SourceState.errors=[String(e.message||e).slice(0,135)];console.warn('V10_SOURCE_READINESS_ERROR',v10SourceState.errors[0])}
  return publicSourceReadiness();
 })();
 v10SourceState.pending=task;
 try{return await task}finally{v10SourceState.pending=null}
};

const voiceProfiles={Bella:{stability:0.64,similarity_boost:0.78,style:0.16},David:{stability:0.76,similarity_boost:0.78,style:0.08},Cassidy:{stability:0.62,similarity_boost:0.78,style:0.20},Roger:{stability:0.68,similarity_boost:0.78,style:0.14},Sarah:{stability:0.78,similarity_boost:0.78,style:0.08},'Adam Stone':{stability:0.74,similarity_boost:0.78,style:0.10}};
const anamPersonaIds={Adam:process.env.ANAM_ADAM_PERSONA_ID,Bella:process.env.ANAM_BELLA_PERSONA_ID,David:process.env.ANAM_DAVID_PERSONA_ID,Cassidy:process.env.ANAM_CASSIDY_PERSONA_ID,Roger:process.env.ANAM_ROGER_PERSONA_ID,Sarah:process.env.ANAM_SARAH_PERSONA_ID};
const anamPersonaId=anamPersonaIds.Adam;
const castPortraitIds={Bella:'410bd990-d7ca-4054-bf5b-ce862d249a8a',David:'fa2b8027-f776-4485-820f-a79cf8412b6f',Cassidy:'9bff6b0b-d649-4b28-ae1c-241ec7ebafe3',Roger:'2a900f85-6f8e-4070-825e-07ac8a55b7c4',Sarah:'2891de34-9f0c-4b47-a7f5-091844dda047','Adam Stone':'65aba6fd-25a5-4ac7-a600-667f48ffb368'};
const castPortraitSources={"Bella":"https://newgxnc1uqs0jnqm.public.blob.vercel-storage.com/avatar-previews/PUHzIr1FTdih7EnH0pXlGzOeJp2D6XBv/one-shot_PUHzIr1FTdih7EnH0pXlGzOeJp2D6XBv_410bd990-d7ca-4054-bf5b-ce862d249a8a-cropped-oN4HLgVd5eT2COmZdxtMwsgZQdDVMA.png","David":"https://newgxnc1uqs0jnqm.public.blob.vercel-storage.com/avatar-previews/PUHzIr1FTdih7EnH0pXlGzOeJp2D6XBv/one-shot_PUHzIr1FTdih7EnH0pXlGzOeJp2D6XBv_fa2b8027-f776-4485-820f-a79cf8412b6f-cropped-qtUMonDvmS5os7wvqh7YjMzvpK2FIH.png","Cassidy":"https://newgxnc1uqs0jnqm.public.blob.vercel-storage.com/avatar-previews/PUHzIr1FTdih7EnH0pXlGzOeJp2D6XBv/one-shot_PUHzIr1FTdih7EnH0pXlGzOeJp2D6XBv_9bff6b0b-d649-4b28-ae1c-241ec7ebafe3-cropped-XYMeCkKkRbvExJQExd2bbDcGMdePdT.png","Roger":"https://newgxnc1uqs0jnqm.public.blob.vercel-storage.com/avatar-previews/PUHzIr1FTdih7EnH0pXlGzOeJp2D6XBv/one-shot_PUHzIr1FTdih7EnH0pXlGzOeJp2D6XBv_2a900f85-6f8e-4070-825e-07ac8a55b7c4-cropped-LK41dgeP8kL8ALR9NgGC4kVIO2FjT9.png","Sarah":"https://newgxnc1uqs0jnqm.public.blob.vercel-storage.com/avatar-previews/PUHzIr1FTdih7EnH0pXlGzOeJp2D6XBv/one-shot_PUHzIr1FTdih7EnH0pXlGzOeJp2D6XBv_2891de34-9f0c-4b47-a7f5-091844dda047-cropped-voGwxO4kJP933OJIXuF8uMse9axWLB.png","Adam Stone":"https://newgxnc1uqs0jnqm.public.blob.vercel-storage.com/avatar-previews/PUHzIr1FTdih7EnH0pXlGzOeJp2D6XBv/one-shot_PUHzIr1FTdih7EnH0pXlGzOeJp2D6XBv_65aba6fd-25a5-4ac7-a600-667f48ffb368-cropped-xODya2gxxk3AyEepC2xPDUeJpmfuzE.png"};
const password=process.env.BOARDROOM_PASSWORD;if(!password||password.length<12)throw Error('BOARDROOM_PASSWORD must be at least 12 characters');
const compare=(a,b)=>{const x=Buffer.from(a),y=Buffer.from(b);return x.length===y.length&&timingSafeEqual(x,y)};

const liveScoreToolName='freddys_live_game_scores_v10';
const liveScoreToolState={status:'pending',toolId:null,attached:[],errors:[],checkedAt:null};
const apiAnam=async(method,path,payload)=>{
 const opts={method,headers:{authorization:'Bearer '+process.env.ANAM_API_KEY,accept:'application/json','content-type':'application/json'},signal:AbortSignal.timeout(12000)};
 if(payload!==undefined)opts.body=JSON.stringify(payload);
 const resp=await fetch('https://api.anam.ai/v1'+path,opts);
 const parsed=await resp.json().catch(()=>({}));
 if(!resp.ok)throw Error('Anam '+path+' HTTP '+resp.status+' '+String(parsed?.error?.code||parsed?.code||parsed?.error||'').slice(0,80));
 return parsed;
};
const provisionLiveAnamTool=async()=>{
 liveScoreToolState.checkedAt=new Date().toISOString();
 if(!process.env.ANAM_API_KEY){liveScoreToolState.status='no-anam-key';return}
 liveScoreToolState.status='checking';liveScoreToolState.errors=[];liveScoreToolState.attached=[];
 try{
  const existing=await apiAnam('GET','/tools?page=1&perPage=100');
  const listed=Array.isArray(existing.data)?existing.data:Array.isArray(existing.tools)?existing.tools:Array.isArray(existing)?existing:null;
  if(!listed)throw Error('Anam tool list response structure unrecognized; no tool created');
  let tool=listed.find(x=>x.name===liveScoreToolName && x.type==='SERVER_WEBHOOK');
  if(!tool){
   tool=await apiAnam('POST','/tools',{
    name:liveScoreToolName,
    description:'MANDATORY for sports questions about today, tonight, upcoming games, current matchups, scores, game status or schedules. Call this real-time read-only ESPN scoreboard feed before answering. Report actual retrievedAt time and games returned; the tool does NOT provide sportsbook lines, injuries, props, verified probabilities or Sharp Edge bets. If the league has no listed events, say no events returned, not that no games exist.',
    type:'SERVER_WEBHOOK',
    config:{url:'https://v10-voice-boardroom-production.up.railway.app/api/public-live-scores',method:'GET',awaitResponse:true,parameters:{type:'object',properties:{},additionalProperties:false}}
   });
  }
  if(!tool?.id)throw Error('Anam live tool missing id');
  liveScoreToolState.toolId=tool.id;
  for(const [role,id] of Object.entries(anamPersonaIds)){
   if(!id)continue;
   try{
    const persona=await apiAnam('GET','/personas/'+encodeURIComponent(id));
    const preserved=Array.isArray(persona.toolIds)?persona.toolIds:Array.isArray(persona.tools)?persona.tools.map(x=>x._toolId||x.id).filter(Boolean):null;
    if(!preserved)throw Error('Anam persona tool IDs missing; refusing overwrite');
    if(!preserved.includes(tool.id))await apiAnam('PUT','/personas/'+encodeURIComponent(id),{toolIds:[...preserved,tool.id]});
    liveScoreToolState.attached.push(role);
   }catch(e){liveScoreToolState.errors.push(role+': '+String(e.message||e).slice(0,140))}
  }
  liveScoreToolState.status=liveScoreToolState.errors.length?'partial':'connected';
  console.log('V10_LIVE_TOOL_SETUP',JSON.stringify({status:liveScoreToolState.status,toolId:liveScoreToolState.toolId,roles:liveScoreToolState.attached,errors:liveScoreToolState.errors}));
 }catch(e){liveScoreToolState.status='failed';liveScoreToolState.errors.push(String(e.message||e).slice(0,180));console.error('V10_LIVE_TOOL_SETUP_ERROR',JSON.stringify(liveScoreToolState.errors))}
};


const modelAnamToolName='freddys_model_research_v10';
const modelToolState={status:'pending',toolId:null,attached:[],errors:[]};
const provisionModelAnamTool=async()=>{
 if(!process.env.ANAM_API_KEY){modelToolState.status='no-anam-key';return}
 modelToolState.status='checking';modelToolState.errors=[];modelToolState.attached=[];
 try{
  const existing=await apiAnam('GET','/tools?page=1&perPage=100');
  const arr=Array.isArray(existing.data)?existing.data:Array.isArray(existing.tools)?existing.tools:Array.isArray(existing)?existing:null;
  if(!arr)throw Error('Unrecognized Anam tools listing');
  let tool=arr.find(x=>x.name===modelAnamToolName&&x.type==='SERVER_WEBHOOK');
  if(!tool)tool=await apiAnam('POST','/tools',{
   name:modelAnamToolName,type:'SERVER_WEBHOOK',
   description:'CALL when users ask about Freddy Picks AI model status, recent research performance, Sharp Edge, best bets, game probabilities, calibration, last 5/10 data availability, EV, CLV, or Champion-001. This returns authentic versioned GitHub NBA/NFL/NHL Elo research scorecards. They are NOT current betting odds or certified picks; never treat exploratory directional accuracy as a sportsbook hit rate. Cite timestamps, keep all unverified betting choices HOLD, and preserve frozen Champion-001.',
   config:{url:'https://v10-voice-boardroom-production.up.railway.app/api/public-model-research',method:'GET',awaitResponse:true,parameters:{type:'object',properties:{},additionalProperties:false}}
  });
  if(!tool?.id)throw Error('No Anam model tool ID');
  modelToolState.toolId=tool.id;
  for(const [role,id] of Object.entries(anamPersonaIds)){
   if(!id)continue;
   try{
    const persona=await apiAnam('GET','/personas/'+encodeURIComponent(id));
    const old=Array.isArray(persona.toolIds)?persona.toolIds:Array.isArray(persona.tools)?persona.tools.map(x=>x._toolId||x.id).filter(Boolean):null;
    if(!old)throw Error('Cannot preserve existing tool IDs');
    if(!old.includes(tool.id))await apiAnam('PUT','/personas/'+encodeURIComponent(id),{toolIds:[...old,tool.id]});
    modelToolState.attached.push(role);
   }catch(e){modelToolState.errors.push(role+': '+String(e.message||e).slice(0,100))}
  }
  modelToolState.status=modelToolState.errors.length?'partial':'connected';
  console.log('V10_MODEL_TOOL_SETUP',JSON.stringify(modelToolState));
 }catch(e){modelToolState.status='failed';modelToolState.errors.push(String(e.message||e).slice(0,140));console.error('V10_MODEL_TOOL_SETUP_ERROR',JSON.stringify(modelToolState))}
};


const dailyAnamToolName='freddys_daily_slates_v10';
const dailyAnamToolState={status:'pending',toolId:null,attached:[],errors:[]};
const provisionDailyAnamTool=async()=>{
 if(!process.env.ANAM_API_KEY){dailyAnamToolState.status='no-anam-key';return}
 dailyAnamToolState.status='checking';dailyAnamToolState.errors=[];dailyAnamToolState.attached=[];
 try{
  const available=await apiAnam('GET','/tools?page=1&perPage=100');
  const toolsList=Array.isArray(available.data)?available.data:Array.isArray(available.tools)?available.tools:Array.isArray(available)?available:null;
  if(!toolsList)throw Error('Missing Anam tools array');
  let tool=toolsList.find(t=>t.name===dailyAnamToolName&&t.type==='SERVER_WEBHOOK');
  if(!tool){
   tool=await apiAnam('POST','/tools',{
    name:dailyAnamToolName,type:'SERVER_WEBHOOK',
    description:'MANDATORY for any conversation about all games TODAY, scheduled league slates, daily boardroom audits, which games the analysts should debate, moneylines, spreads, overs/unders, player props, combinations, parlays, Sharp Edge and daily best bets. Returns the full Eastern-date ESPN schedule across eight sports with game time, status, scores, and per-market certification HOLD. Do not call any selection a certified bet unless authentic sportsbook odds, source-frozen probability and independent verification are supplied. Discuss one game at a time and call the host Freddy naturally.',
    config:{url:'https://v10-voice-boardroom-production.up.railway.app/api/public-daily-slate-summary',method:'GET',awaitResponse:true,parameters:{type:'object',properties:{},additionalProperties:false}}
   })
  }
  if(!tool?.id)throw Error('Tool ID unavailable');
  dailyAnamToolState.toolId=tool.id;
  for(const [role,id] of Object.entries(anamPersonaIds)){
   if(!id)continue;
   try{
    const current=await apiAnam('GET','/personas/'+encodeURIComponent(id));
    const prev=Array.isArray(current.toolIds)?current.toolIds:Array.isArray(current.tools)?current.tools.map(t=>t._toolId||t.id).filter(Boolean):null;
    if(!prev)throw Error('Refusing to replace an unknown tool list');
    if(!prev.includes(tool.id))await apiAnam('PUT','/personas/'+encodeURIComponent(id),{toolIds:[...prev,tool.id]});
    dailyAnamToolState.attached.push(role);
   }catch(e){dailyAnamToolState.errors.push(role+': '+String(e.message||e).slice(0,130))}
  }
  dailyAnamToolState.status=dailyAnamToolState.errors.length?'partial':'connected';
  console.log('V10_DAILY_ANAM_TOOL_SETUP',JSON.stringify(dailyAnamToolState))
 }catch(e){dailyAnamToolState.status='failed';dailyAnamToolState.errors.push(String(e.message||e).slice(0,150));console.error('V10_DAILY_ANAM_TOOL_ERROR',JSON.stringify(dailyAnamToolState))}
};


const sourceAnamToolName='freddys_source_readiness_v10';
const sourceAnamToolState={status:'pending',toolId:null,attached:[],errors:[]};
const provisionSourceAnamTool=async()=>{
 if(!process.env.ANAM_API_KEY){sourceAnamToolState.status='no-anam-key';return}
 sourceAnamToolState.status='checking';sourceAnamToolState.attached=[];sourceAnamToolState.errors=[];
 try{
  const list=await apiAnam('GET','/tools?page=1&perPage=100');
  const arr=Array.isArray(list.data)?list.data:Array.isArray(list.tools)?list.tools:Array.isArray(list)?list:null;
  if(!arr)throw Error('Anam tool list unavailable, not modifying personas');
  let tool=arr.find(x=>x.name===sourceAnamToolName&&x.type==='SERVER_WEBHOOK');
  if(!tool)tool=await apiAnam('POST','/tools',{
   name:sourceAnamToolName,type:'SERVER_WEBHOOK',
   description:'CALL this read-only tool whenever Freddy asks whether DraftKings, SharpAPI, SportsGameOdds, SportsDataIO, injury data, Champion-001 probabilities, player prop lines or Sharp Edge bets are connected, verified, fresh or ready. It returns GitHub workflow metadata only (run status/timestamps). Workflow success NEVER means source odds, injuries, native model probabilities or certified EV are available. Say HOLD for any unverified betting recommendation.',
   config:{url:'https://v10-voice-boardroom-production.up.railway.app/api/public-source-readiness',method:'GET',awaitResponse:true,parameters:{type:'object',properties:{},additionalProperties:false}}
  });
  if(!tool?.id)throw Error('Anam source-readiness tool missing id');
  sourceAnamToolState.toolId=tool.id;
  for(const [role,id] of Object.entries(anamPersonaIds)){
   if(!id)continue;
   try{
    const persona=await apiAnam('GET','/personas/'+encodeURIComponent(id));
    const previous=Array.isArray(persona.toolIds)?persona.toolIds:Array.isArray(persona.tools)?persona.tools.map(x=>x._toolId||x.id).filter(Boolean):null;
    if(!previous)throw Error('Existing tool IDs unavailable, preserving persona');
    if(!previous.includes(tool.id))await apiAnam('PUT','/personas/'+encodeURIComponent(id),{toolIds:[...previous,tool.id]});
    sourceAnamToolState.attached.push(role);
   }catch(e){sourceAnamToolState.errors.push(role+': '+String(e.message||e).slice(0,120))}
  }
  sourceAnamToolState.status=sourceAnamToolState.errors.length?'partial':'connected';
  console.log('V10_SOURCE_ANAM_TOOL_SETUP',JSON.stringify(sourceAnamToolState));
 }catch(e){sourceAnamToolState.status='failed';sourceAnamToolState.errors.push(String(e.message||e).slice(0,160));console.warn('V10_SOURCE_ANAM_TOOL_ERROR',JSON.stringify(sourceAnamToolState.errors))}
};

// Reflect the deployed build in installed web-app update checks without exposing secrets.
const appVersion=String(process.env.RAILWAY_GIT_COMMIT_SHA||process.env.GITHUB_SHA||('v10-start-'+Date.now().toString(36))).replace(/[^a-zA-Z0-9._-]/g,'').slice(0,80);
const respond=(res,status,data,headers={})=>{res.writeHead(status,{'content-type':'application/json','cache-control':'no-store',...headers});res.end(JSON.stringify(data))};
async function body(req){let s='';for await(const c of req){s+=c;if(s.length>50000)throw Error('Payload too large')}return JSON.parse(s||'{}')}
const html=`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#0b1732"><meta name="mobile-web-app-capable" content="yes"><link rel="manifest" href="/manifest.webmanifest"><link rel="icon" href="/app-icon.svg" type="image/svg+xml"><title>Freddy's V10 Sports Podcast Studio</title><style>body{font:16px system-ui;background:radial-gradient(circle at top,#182f58,#080e1c 70%);color:#eef2ff;margin:0;padding:18px}main{max-width:1250px;margin:auto}h1{font-size:24px}input,textarea,button{font:inherit;padding:12px;border-radius:10px;margin:6px 0}input,textarea{background:#202943;color:white;border:1px solid #566}button{background:#0e8bd6;color:white;border:0;cursor:pointer}button:disabled{opacity:.5}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.person{background:linear-gradient(150deg,#24395c,#101a2d);border:2px solid #334a69;border-radius:16px;overflow:hidden;text-align:center;position:relative;min-height:230px;display:flex;flex-direction:column;justify-content:flex-end}.person.speaking{border-color:#50e3b3;box-shadow:0 0 0 2px #50e3b355}.face{height:165px;display:flex;align-items:end;justify-content:center;background:radial-gradient(circle at 50% 15%,#48658e,#18243b 75%)}.face svg{height:160px;width:150px}.person strong{padding-top:8px}.person .muted{padding:5px 4px 12px}.live{position:absolute;top:8px;left:8px;background:#081629bd;border-radius:30px;padding:4px 8px;font-size:11px;color:#bce4ff}.toolbar{display:flex;gap:8px;flex-wrap:wrap}.toolbar button{flex:1}#question{box-sizing:border-box;width:100%}#status{color:#9ee3c6}.muted{color:#b9c5d7;font-size:13px}#log{background:#151d33;min-height:100px;padding:15px;border-radius:10px;white-space:pre-wrap}textarea{width:95%;height:70px}@media(max-width:600px){.grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:390px){.person{min-height:190px}.face{height:125px}.face svg{height:125px}} .studio{background:linear-gradient(135deg,#151c2c,#203c69 52%,#151b2d);border:2px solid #c69b48;border-radius:18px;padding:14px;margin:12px 0 18px;box-shadow:0 8px 30px #0008}.studio-head{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}.studio-sign{font-weight:900;letter-spacing:1px;color:#f5d58b}.memorabilia{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}.memorabilia span{border:1px solid #a17d43;background:#101a2d;padding:8px;border-radius:9px;font-size:13px}.person{background:linear-gradient(180deg,#22385a,#111927 85%)}.person .face{background:linear-gradient(135deg,#283c62,#192b45)}.person.talking .mouth{animation:talk .19s ease-in-out infinite alternate;transform-origin:81px 117px}@keyframes talk{from{transform:scaleY(.35)}to{transform:scaleY(2.4)}}@media(prefers-reduced-motion:reduce){.person.talking .mouth{animation:none}} .hybrid{display:grid;grid-template-columns:minmax(0,2fr) minmax(230px,1fr);gap:16px;margin:18px 0}.lounge{background:linear-gradient(130deg,#11182a,#243f68 50%,#111827);border:1px solid #bd8b48;border-radius:20px;padding:14px;position:relative;overflow:hidden}.lounge:before{content:"🏀  NEW YORK KNICKS  •  ⚾ YANKEES  •  👟 SNEAKERS  •  🎧 HIP-HOP  •  🏆";display:block;letter-spacing:1px;background:#101d32;padding:14px 8px;border-radius:10px;text-align:center;margin-bottom:12px;color:#f8bd62;font-weight:700;font-size:12px}.room-title{font-size:13px;letter-spacing:1px;color:#f7c878;font-weight:800;margin:0 0 12px}.lounge .grid{grid-template-columns:repeat(2,minmax(0,1fr))}.lounge .person{min-height:210px;border-radius:16px;background:linear-gradient(#324766,#171e2b);box-shadow:inset 0 -12px 0 #222b39}.remote{background:#0e1728;border:1px solid #536f95;border-radius:18px;padding:12px}.remote-grid{display:grid;grid-template-columns:1fr;gap:12px}.remote .person{min-height:190px;border:2px solid #5679a3}.remote .person:before{content:"REMOTE • VIDEO WINDOW";position:absolute;right:8px;top:8px;color:#cfe3ff;font-size:10px;z-index:2}.person.speaking{border-color:#56efbd}.person:focus-visible{outline:3px solid #ffbb65}.studio .memorabilia span{background:#192e4a}@media(max-width:760px){.hybrid{grid-template-columns:1fr}.remote-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.remote .person{min-height:185px}}@media(max-width:390px){.lounge .person,.remote .person{min-height:175px}.room-title{font-size:11px}}.podcast-stage{background:radial-gradient(ellipse at 50% 0,#344e76,#101726 75%);border:2px solid #b98c4c;border-radius:24px;padding:20px;margin:16px 0}.podcast-stage .grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.podcast-stage .person{min-height:230px;border:2px solid #657c99}.podcast-stage .room-title{text-align:center;font-size:18px}.stage-desk{background:linear-gradient(90deg,#2b1c18,#745039,#2b1c18);border-top:4px solid #d1a76c;border-radius:12px;text-align:center;padding:13px;font-weight:900;letter-spacing:2px;color:#f8ddb0;margin-top:12px}.stage-control{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin:12px 0}.podcast-stage .person.speaking{box-shadow:0 0 0 3px #54efb4aa,0 0 25px #54efb455}@media(max-width:650px){.podcast-stage .grid{grid-template-columns:repeat(2,minmax(0,1fr))}.podcast-stage{padding:10px}.podcast-stage .person{min-height:185px}}.live-wall{background:#0b1323;border:1px solid #bc945d;border-radius:18px;padding:14px;margin:14px 0}.live-wall-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.live-tile{background:#111e31;border:1px solid #526a8a;border-radius:12px;padding:8px}.live-tile video{display:block;width:100%;aspect-ratio:4/3;object-fit:contain;background:#080e18;border-radius:8px}.live-tile .muted{margin:6px 0}.live-wall .toolbar{margin:10px 0}@media(max-width:650px){.live-wall-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}.live-tile.on-air{border-color:#56efbd;box-shadow:0 0 0 2px #56efbd66}.live-tile.on-air:before{content:"ON AIR";display:block;color:#56efbd;font-size:11px;font-weight:800;letter-spacing:1px}.podcast-stage .person.talking{box-shadow:0 0 0 3px #56efbd}.v10-hero{background:linear-gradient(125deg,#142f51,#101929 60%,#302419);border:1px solid #c9a46b;border-radius:22px;padding:24px;margin-bottom:18px;box-shadow:0 18px 55px #0007}.v10-hero h1{font-size:clamp(26px,5vw,42px);margin:6px 0}.v10-eyebrow{color:#eac38a;font-size:12px;font-weight:900;letter-spacing:2px}.v10-hero p{color:#c8d7ea;margin:8px 0 16px}.v10-login{display:flex;flex-wrap:wrap;align-items:center;gap:10px}.v10-login input{flex:1;min-width:180px;max-width:340px}.v10-login button{background:#e5b76d;color:#101725;font-weight:800}.v10-quick{background:#101f33;border:1px solid #41658a;border-radius:16px;padding:16px;margin:16px 0}.v10-quick h2{margin:0 0 6px}.v10-quick textarea{box-sizing:border-box;width:100%;height:100px;margin:12px 0}.v10-quick button{font-weight:700}.v10-advanced-toggle{display:block;margin:16px 0;background:#233b5b;border:1px solid #8aadd2}.v10-advanced{display:none}.v10-advanced.is-open{display:block}.podcast-stage{box-shadow:0 20px 50px #0007}.podcast-stage .person{transition:border-color .2s,transform .2s}.podcast-stage .person.talking{transform:translateY(-3px)}.stage-control button{background:#243e61;border:1px solid #4d7096}.stage-control #record-shorts-start{background:#e5b76d;color:#111827;font-weight:900}.stage-control #record-stop{background:#a83749}.stage-control #roundtable{background:#137e74}.v10-advanced .live-wall,.v10-advanced #adam-live-panel,.v10-advanced #sports-data-panel{margin:16px 0}@media(max-width:650px){body{padding:9px}.v10-hero{padding:16px}.podcast-stage .grid{gap:7px}.podcast-stage .person{min-height:165px}.podcast-stage .person .face{height:120px}.podcast-stage .person .face svg{height:120px}.stage-control{justify-content:stretch}.stage-control button{flex:1 1 145px}.v10-quick .toolbar button{flex:1 1 100px}}.podcast-stage #people{grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.podcast-stage .v10-remote-roster{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.podcast-stage .person .face{height:150px;overflow:hidden}@media(max-width:700px){.podcast-stage #people{grid-template-columns:repeat(2,minmax(0,1fr))}.podcast-stage .person .face{height:120px}}
/* Shared V10 room: the same six-person podcast set across conversation and recording. */
.podcast-room-scene{position:relative;isolation:isolate;overflow:hidden;border-radius:18px;border:2px solid #bf945d;padding:13px 12px 16px;margin:10px 0 14px;color:#fff;background:radial-gradient(ellipse at 44% 32%,#2254a0 0%,#102243 35%,#0b0d1c 72%),repeating-linear-gradient(90deg,#25141c 0 12px,#0f1124 12px 25px);box-shadow:inset 0 0 50px #0009,0 15px 38px #02040a}
.podcast-room-scene:before{content:"";position:absolute;inset:0;pointer-events:none;z-index:-1;background:linear-gradient(140deg,transparent 24%,#ca6d2622 45%,transparent 70%),repeating-linear-gradient(180deg,#ffffff06 0px,#ffffff06 2px,transparent 2px,transparent 30px)}
.podcast-room-neon{border:2px solid #122b67;background:linear-gradient(135deg,#090e20,#081c3a);border-radius:10px;box-shadow:0 0 13px #1967ff99;padding:9px 14px;text-align:center;letter-spacing:2px;text-shadow:0 2px 2px #050a0f}
.podcast-room-neon strong{font-size:clamp(23px,3.2vw,43px);font-style:italic;color:#f5f7ff;display:block;line-height:1.1}
.podcast-room-neon em{color:#edb961;font-style:italic}
.podcast-room-neon span{font-size:clamp(10px,1.2vw,17px);color:#b9d5ff;font-weight:800}
.podcast-room-backwall{display:flex;align-items:center;justify-content:space-around;padding:18px 4px 6px;gap:10px;background:radial-gradient(ellipse at center,#1453ac95,#030b1a80 75%);border-radius:12px;margin-top:8px;min-height:90px}
.room-nyc-logo{font-weight:1000;font-style:italic;font-size:clamp(12px,2vw,24px);letter-spacing:.2px;text-shadow:0 2px 1px #000c}
.room-knicks{color:#ef873a}.room-yankees{color:#d9e8ff}
.room-nyc-center{text-align:center;color:#e6f0ff;text-shadow:0 0 12px #248dff}
.room-nyc-center strong{font-size:clamp(18px,3vw,37px);line-height:.9;font-weight:1000;font-style:italic;display:block}
.room-nyc-center span{font-size:clamp(7px,.9vw,12px);color:#e3b975;letter-spacing:1px}
.podcast-room-set{display:grid;grid-template-columns:minmax(0,4fr) minmax(180px,1.15fr);gap:11px;align-items:stretch}
.room-primary-table{min-width:0;display:flex;flex-direction:column;justify-content:flex-end;background:linear-gradient(180deg,#0f254030,#18274388);border:1px solid #be8b5440;border-radius:12px;padding:8px}
.room-subheading{font-weight:900;letter-spacing:1.5px;text-align:center;color:#ffcf88;font-size:12px;padding:4px}
.podcast-room-scene #people{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;align-items:stretch}
.podcast-room-scene .person{background:linear-gradient(180deg,#0c173ccc,#10233ee6);padding:7px 5px 9px;box-shadow:0 5px 9px #01040e99;border:2px solid #547aaa;border-radius:11px;text-align:center;min-width:0;cursor:pointer;transition:box-shadow .16s,border-color .16s,transform .16s}
.podcast-room-scene .person .live{display:block;font-size:9px;font-weight:750;color:#9fc2e3;min-height:18px}
.podcast-room-scene .person .face{height:clamp(95px,12vw,178px);border-radius:9px;position:relative;overflow:hidden;background:#11233e}
.podcast-room-scene .person .face img{border-radius:8px!important}
.podcast-room-scene .person strong{display:block;font-size:clamp(13px,1.6vw,21px);text-overflow:ellipsis;overflow:hidden;white-space:nowrap;text-transform:uppercase}
.podcast-room-scene .person .muted{font-size:clamp(9px,1vw,12px);line-height:1.25}
.podcast-room-scene .person.talking,.podcast-room-scene .person.speaking{border-color:#e9bc79;box-shadow:0 0 18px #f5b62b72;transform:translateY(-2px)}
.podcast-room-scene .person.talking{border-color:#44e4a6;box-shadow:0 0 19px #48f8bb88}
.room-table-edge{display:flex;align-items:center;justify-content:center;gap:12px;text-align:center;margin:10px 0 2px;padding:9px 4px;border-radius:7px;background:linear-gradient(#5e3d2a,#241b1a);border:1px solid #deac79;color:#e7c18d;box-shadow:0 8px 12px #0008;text-shadow:0 1px 1px #000}
.room-table-edge b{font-size:clamp(10px,1.3vw,16px);letter-spacing:.8px}
.room-remote-side{background:linear-gradient(165deg,#09142f,#123467);border:2px solid #5b92e8;border-radius:16px;padding:7px;min-width:0;box-shadow:0 0 12px #267adf66}
.room-remote-banner{font-weight:900;font-size:12px;color:#e9ecff;text-align:center;letter-spacing:.5px;padding:4px}
.room-camera-on,.room-signal{color:#36e995;text-shadow:0 0 9px #2ff6b7}
.podcast-room-scene .v10-remote-roster{display:grid;grid-template-columns:1fr;gap:8px;margin:0!important}
.podcast-room-scene .v10-remote-roster h3{display:none}
.podcast-room-scene .room-remote-side .person{padding:5px;min-height:0}
.podcast-room-scene .room-remote-side .person .face{height:clamp(92px,11vw,147px)}
.podcast-room-scene .room-remote-side .person .muted{font-size:10px}
.room-now-speaking{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:8px 12px;margin-top:12px;border:1px solid #416a9a;background:#081b36;border-radius:9px}
.room-now-speaking strong{color:#edbd7d;font-size:14px}.room-now-speaking span:last-child{font-size:11px;color:#adbbce}
.room-sport-shortcuts{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:5px;margin:10px 0}
.room-sport-shortcuts button{padding:9px 3px;border:1px solid #3e72b6;background:linear-gradient(#153c71,#091d3b);color:#fff;font-size:clamp(9px,1.04vw,13px);font-weight:850;border-radius:8px;margin:0;min-width:0}
.room-sport-shortcuts button:hover,.room-sport-shortcuts button:focus-visible{background:linear-gradient(#244e8d,#1d345e);outline:1px solid #e7be83}
.podcast-room-live-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:center}
.podcast-room-live-actions button{border:2px solid #e6bd7a;background:linear-gradient(#f4c879,#c08a4c);color:#10192d;font-weight:900}
.podcast-room-live-actions span{font-size:11px;color:#b9c9da}
@media(max-width:800px){.podcast-room-set{grid-template-columns:1fr}.podcast-room-scene .person .face{height:clamp(110px,23vw,195px)}.podcast-room-scene .v10-remote-roster{grid-template-columns:repeat(2,minmax(0,1fr))}.podcast-room-scene .room-remote-side .person .face{height:clamp(100px,26vw,190px)}.room-sport-shortcuts{grid-template-columns:repeat(6,minmax(0,1fr))}}
@media(max-width:490px){.podcast-room-scene{padding:8px}.podcast-room-scene #people{grid-template-columns:repeat(2,minmax(0,1fr))}.podcast-room-scene .person .face{height:132px}.podcast-room-scene .room-remote-side .person .face{height:122px}.room-now-speaking strong{font-size:12px}.room-sport-shortcuts{grid-template-columns:repeat(4,minmax(0,1fr))}.room-table-edge b{font-size:10px}.podcast-room-neon span{letter-spacing:.5px}}

.daily-slate-board{background:linear-gradient(145deg,#0d1a32,#132b47);border:1px solid #b18b5c;border-radius:14px;margin:15px 0;padding:13px;color:#e7eefb}
.daily-slate-top{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
.daily-slate-top strong{color:#eec381;font-size:17px}
.daily-slate-top span{font-size:12px;color:#bbd2ea}
.daily-slate-toolbar{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:10px 0}
.daily-slate-toolbar label{font-size:12px}.daily-slate-toolbar input{width:155px;max-width:100%;padding:7px;font-size:13px}
.daily-slate-toolbar button{font-weight:750;font-size:12px;padding:9px;background:#184879;border:1px solid #5b90cb;margin:0}
.daily-slate-toolbar button:hover,.daily-slate-toolbar button:focus-visible{background:#2963a0}
.daily-slate-counts{font-size:12px;color:#d2dbeb;line-height:1.6;padding:8px;background:#102541;border-radius:8px}
.daily-slate-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(270px,1.2fr);gap:10px;margin-top:11px}
.daily-slate-schedule,.daily-game-audit{background:#08162ba8;border:1px solid #355678;border-radius:10px;padding:10px;min-width:0}
.daily-slate-schedule strong,.daily-game-audit>strong{font-size:12px;color:#f0c985}
.daily-slate-games{max-height:360px;overflow-y:auto;margin-top:8px;padding:4px 2px}
.daily-slate-games button{display:block;width:100%;text-align:left;font-size:12px;background:#142a46;color:#e4edf7;margin:3px 0;padding:8px;border:1px solid #2b527e;border-radius:6px}
.daily-slate-games button.selected,.daily-slate-games button:focus-visible{border-color:#e9bc79;background:#245077}
.daily-slate-games .league-name{color:#f0c985;margin-top:10px;font-size:12px;font-weight:900;letter-spacing:1px}
#daily-game-review{white-space:pre-wrap;font-size:12px;line-height:1.55;overflow-wrap:anywhere;margin:8px 0;padding:9px;background:#11253e;border-radius:8px;min-height:150px}
.daily-consensus{border-top:1px solid #476887;padding-top:10px;margin-top:7px}
.daily-consensus strong{color:#f4c976}
.daily-consensus p{font-size:12px;line-height:1.6}
.daily-slate-warning{color:#cfdae9}
@media(max-width:800px){.daily-slate-grid{grid-template-columns:1fr}.daily-slate-games{max-height:245px}}

.odds-evidence-inbox{margin:13px 0 10px;padding:12px;border:1px solid #bb9767;border-radius:12px;background:linear-gradient(145deg,#0c233b,#111c2f)}
.odds-evidence-inbox strong{color:#f0c582}.odds-evidence-inbox p{font-size:12px;line-height:1.5;color:#bccfe3}
.odds-inbox-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.odds-inbox-fields label{font-size:12px;color:#bbd1e7;display:flex;flex-direction:column;gap:4px;min-width:0}
.odds-inbox-fields input,.odds-inbox-fields select{width:100%;min-width:0;box-sizing:border-box;margin:0;padding:8px;font-size:13px;background:#102744;color:white;border:1px solid #54749c;border-radius:7px}
#quote-preflight-result{font-size:12px;line-height:1.6;white-space:pre-wrap;overflow-wrap:anywhere;background:#06162a;padding:10px;border:1px solid #43648c;border-radius:9px}
@media(max-width:560px){.odds-inbox-fields{grid-template-columns:1fr}}

.podcast-room-scene .room-avatar-live-toggle{display:block;width:100%;font-size:clamp(9px,1vw,12px);line-height:1.2;margin:6px 0 3px;padding:7px 3px;background:linear-gradient(#12447b,#0b2d52);border:1px solid #4e85c4;color:#ecf4ff;border-radius:7px;min-width:0;cursor:pointer}
.podcast-room-scene .room-avatar-live-toggle:disabled{opacity:.58;cursor:wait}
.podcast-room-scene .room-avatar-live-status{display:block;font-size:10px;min-height:12px;color:#a1b5c8;line-height:1.2}
.podcast-room-scene .person.live-video-active{border-color:#45f3a7;box-shadow:0 0 16px #13e7af80}
.podcast-room-scene .person.live-video-active .room-avatar-live-status{color:#45f3a7;font-weight:bold}
.podcast-room-scene .room-anam-upgrade{font-size:11px;color:#f0c482;text-decoration:underline}
.podcast-room-scene .podcast-room-live-actions #room-start-live-all{background:#123e70;border-color:#4b89c8;color:white}
.podcast-room-scene .podcast-room-live-actions #room-stop-live-all{background:#2a3149;color:#e5ebf6;border-color:#7d8ba8}

.room-live-spotlight{margin:12px 0;border:2px solid #e3b06c;border-radius:17px;overflow:hidden;background:#040b1d;box-shadow:0 0 32px #4089ee7d}
.room-live-spotlight[hidden]{display:none!important}
.spotlight-heading{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:center;padding:11px 14px;background:linear-gradient(110deg,#091b3d,#164d8b);font-weight:900;color:#fff;letter-spacing:.5px}
.spotlight-heading strong{font-size:clamp(18px,2.6vw,30px)}
.spotlight-heading span:last-child{font-size:12px;color:#bde4fa}
.room-spotlight-stage{position:relative;display:flex;align-items:center;justify-content:center;width:100%;min-height:300px;height:min(69vh,690px);background:radial-gradient(circle,#253e60,#030713 78%);overflow:hidden}
.room-spotlight-stage>video,.room-spotlight-stage>img{display:block;width:100%;height:100%;object-fit:contain;object-position:center center;background:#030917}
.room-spotlight-stage>video{display:none}
.room-spotlight-actions{display:flex;align-items:center;justify-content:center;gap:9px;flex-wrap:wrap;padding:11px;background:#0b2241}
.room-spotlight-actions button{font-size:13px;font-weight:850;padding:12px 14px;margin:0;border-radius:9px;background:#22548c;border:1px solid #619ddb;color:white;touch-action:manipulation}
.room-spotlight-actions #room-spotlight-unmute{background:linear-gradient(#d3a15b,#aa762f);color:#0d1931;border-color:#f5d097}
.room-spotlight-actions label{min-width:145px;max-width:200px;font-size:12px;color:#e7efff;display:flex;flex-direction:column;gap:6px;font-weight:800}
.room-spotlight-actions input[type=range]{width:100%;accent-color:#e1b675}
#room-live-audio-status{margin:0;padding:9px 13px;color:#bdd3ef;font-size:12px}
.room-master-audio{display:flex;align-items:center;flex-wrap:wrap;gap:9px;margin:11px 0;padding:11px 13px;border:1px solid #628cb9;background:#0c2345;border-radius:11px;color:#edf2fb}
.room-master-audio strong{font-size:13px;color:#f1c481}
.room-master-audio label{display:flex;flex-direction:column;gap:5px;min-width:165px;font-size:12px}
.room-master-audio input[type=range]{width:100%;accent-color:#e9bc79}
.room-master-audio button{margin:0;background:#204675;color:white;font-size:12px;padding:9px 13px;border:1px solid #628db5}
.room-master-audio span:last-child{font-size:11px;color:#bbcadb}
.podcast-room-scene .person .face img,.podcast-room-scene .person .face video{object-fit:contain!important;object-position:center center;background:#051326}
@media(max-width:590px){.room-spotlight-stage{height:min(63vh,520px);min-height:275px}.spotlight-heading strong{font-size:16px}.room-spotlight-actions{gap:6px}.room-spotlight-actions button{font-size:11px;padding:11px 9px}.room-master-audio{gap:7px}}

/* Larger six-seat previews so full animated faces remain recognizable around the table. */
.podcast-room-scene .person .face{height:clamp(170px,16vw,250px);overflow:hidden;background:#07172d}
.podcast-room-scene .room-remote-side .person .face{height:clamp(145px,13vw,225px)}
.podcast-room-scene .person .face img,.podcast-room-scene .person .face video{max-width:100%;object-position:50% 35%!important}
@media(max-width:800px){.podcast-room-scene .person .face{height:clamp(160px,30vw,255px)}.podcast-room-scene .room-remote-side .person .face{height:clamp(150px,26vw,225px)}}
@media(max-width:490px){.podcast-room-scene .person .face{height:clamp(165px,42vw,235px)}.podcast-room-scene .room-remote-side .person .face{height:clamp(150px,36vw,220px)}}

/* Unified, app-like six-person studio. All names and live streams share ONE backdrop. */
body{padding:0;background:#040c1c}main{max-width:100%;padding:0 8px 14px}
.v10-hero{border-radius:0 0 17px 17px;position:sticky;top:0;z-index:25;padding:10px 15px!important;background:linear-gradient(105deg,#071328,#193658)!important;backdrop-filter:blur(9px)}
.podcast-room-scene{padding:10px;margin:7px auto 14px;max-width:1500px;border-radius:16px;border:1px solid #bc956b;background:radial-gradient(ellipse at 50% 20%,#26549a 0%,#071b3a 48%,#050c1a 90%);box-shadow:0 15px 45px #0008}
.podcast-room-set{display:block;width:100%}
.room-primary-table{width:100%;box-sizing:border-box;min-height:unset;padding:9px 5px 8px;display:block;background:linear-gradient(#061d3b33,#32251941);border:0;border-radius:10px}
.podcast-room-scene .room-remote-side,.podcast-room-scene #remote{display:none!important}
.podcast-room-scene #people{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:clamp(2px,.6vw,10px);align-items:end;width:100%;margin:0}
.podcast-room-scene #people .person{min-width:0;min-height:unset;display:flex;flex-direction:column;gap:2px;justify-content:flex-end;padding:2px 2px 9px;border:0!important;border-radius:0!important;transform:none!important;overflow:visible;background:transparent!important;box-shadow:none!important;outline:0;cursor:pointer}
.podcast-room-scene #people .person .face{order:0;position:relative;width:100%;height:clamp(128px,16vw,255px);overflow:hidden;background:transparent;border-radius:40% 40% 4px 4px / 12% 12% 4px 4px}
.podcast-room-scene #people .person .face img,.podcast-room-scene #people .person .face video{width:100%;height:100%;object-fit:cover!important;object-position:50% 30%!important;border-radius:inherit!important;mask-image:linear-gradient(to bottom,#000 0%,#000 82%,transparent 100%);-webkit-mask-image:linear-gradient(to bottom,#000 0%,#000 82%,transparent 100%)}
.podcast-room-scene #people .person strong{order:1;display:block;line-height:1.1;font-size:clamp(12px,1.5vw,21px);padding:7px 1px;text-transform:uppercase;color:white;border:1px solid #5477a6;border-radius:7px;background:#071735c9}
.podcast-room-scene #people .person .muted{display:none}
.podcast-room-scene #people .person .live{order:2;position:relative;top:auto;left:auto;display:block;background:none;padding:2px 0;margin:0;white-space:nowrap;font-size:clamp(7px,.8vw,11px)}
.podcast-room-scene #people .person .room-avatar-live-toggle{order:3;display:block;width:100%;margin:3px 0 0;padding:9px 2px;font-size:clamp(9px,1vw,13px);border-radius:8px}
.podcast-room-scene #people .person .room-avatar-live-status{order:4;display:block;min-height:15px;font-size:clamp(8px,.85vw,10px);line-height:1.2}
.podcast-room-scene #people .person.speaking strong,.podcast-room-scene #people .person.talking strong,.podcast-room-scene #people .person.live-video-active strong{border-color:#eeca8a;background:#245b90;box-shadow:0 0 18px #e3ae6688}
.podcast-room-scene #people .person.live-video-active .face{filter:drop-shadow(0 0 15px #43f0b888)}
.podcast-room-scene .room-table-edge{position:relative;z-index:2;display:flex;align-items:center;justify-content:center;min-height:42px;margin:0;border-radius:10px;background:linear-gradient(#806046,#30221e);box-shadow:0 10px 20px #0008}
.room-live-spotlight{max-width:1330px;margin:10px auto}
.room-name-control{background:linear-gradient(115deg,#08214a,#103767);border:1px solid #79b7e8;border-radius:13px;padding:12px;margin:10px 0;box-shadow:0 3px 18px #0005}
.name-control-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:6px}
.name-control-head strong{font-size:clamp(15px,1.8vw,21px);color:#f0c47c}
.name-control-head span{font-size:12px;color:#c2d8f1}
.name-control-actions{display:flex;flex-wrap:wrap;gap:7px;margin:7px 0}
.name-control-actions button,.name-control-text button{margin:0;padding:11px 14px;font-size:12px;font-weight:850;border:1px solid #86b4df;border-radius:9px;color:#f5f9ff;background:#1c5e9c}
.name-control-actions #room-voice-names{background:#e4ba79;color:#10213b;border-color:#ffdca3}
.name-control-text{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}
.name-control-text input{margin:0;padding:11px 13px;flex:1 1 250px;min-width:0;box-sizing:border-box}
.name-command-hint{margin:6px 0 0;font-size:11px;line-height:1.4;color:#bcd5ee}
@media(max-width:900px){.podcast-room-scene #people{grid-template-columns:repeat(3,minmax(0,1fr));gap:4px 8px}.podcast-room-scene #people .person .face{height:clamp(150px,28vw,275px)}.podcast-room-scene #people .person strong{font-size:clamp(14px,2.6vw,20px)}}
@media(max-width:480px){main{padding:0 4px 10px}.podcast-room-scene{padding:7px 4px 12px}.podcast-room-scene #people .person .face{height:clamp(130px,36vw,190px)}.podcast-room-scene #people .person strong{font-size:13px}.podcast-room-scene #people .person .room-avatar-live-toggle{font-size:10px}.podcast-room-scene #people .person .room-avatar-live-status{font-size:9px}.room-name-control{padding:9px}.name-control-actions button{flex:1 1 100px;padding:10px 5px}.room-nyc-logo{display:none}}
/* Keep the reference navy/gold studio, two-column controls and six portraits. Only collapse the sticky login overlay after authentication. */
.v10-hero.is-unlocked{position:relative!important;top:auto!important;z-index:1!important;backdrop-filter:none!important;padding:12px 15px!important;margin-bottom:9px!important;box-shadow:0 4px 18px #0005!important}
.v10-hero.is-unlocked .v10-login{display:none!important}
.v10-hero.is-unlocked h1{font-size:clamp(22px,4.8vw,32px);line-height:1.15;margin:5px 0!important}
.v10-hero.is-unlocked p{margin:6px 0!important}
.v10-hero.is-unlocked #avatar-readiness{font-size:11px;line-height:1.35;overflow-wrap:anywhere}
.v10-hero.is-unlocked #status{font-weight:700}
@media(max-width:650px){.v10-hero.is-unlocked{border-radius:0 0 17px 17px!important;padding:10px 12px!important}.v10-hero.is-unlocked .v10-eyebrow{font-size:11px}.v10-hero.is-unlocked h1{font-size:23px}.v10-hero.is-unlocked p{font-size:13px!important}}

.v10-cinematic{position:relative;width:100%;aspect-ratio:16/9;overflow:hidden;background:#071127;border:1px solid #d4a95c;border-radius:10px}
.v10-boardroom-art{display:block;width:100%;height:100%;object-fit:contain}
/* Place the only active video on the correct face within the original group image. */
.v10-chair-video-layer{position:absolute;inset:0;z-index:2;pointer-events:none;overflow:hidden}
.v10-chair-video{position:absolute;display:none;object-fit:cover;object-position:50% 28%;background:#07152d;border-radius:38% 38% 15% 15% / 18% 18% 12% 12%;-webkit-mask-image:radial-gradient(ellipse 73% 70% at 50% 47%,#000 58%,transparent 100%);mask-image:radial-gradient(ellipse 73% 70% at 50% 47%,#000 58%,transparent 100%);transform:translateZ(0)}
.v10-cinematic-hotspots{z-index:3}
.v10-live-label{z-index:4}
.v10-cinematic-hotspots{position:absolute;inset:0}
.v10-hotspot{position:absolute;display:block!important;margin:0!important;padding:0!important;min-height:0!important;min-width:0!important;opacity:0;background:transparent!important;border:0!important;cursor:pointer}
.v10-hotspot:focus-visible{opacity:1;outline:3px solid #efc77b;background:#f9d67e22!important}
.v10-live-label{position:absolute;top:5px;left:5px;max-width:95%;background:#07162adf;border:1px solid #b98b4c;border-radius:14px;padding:3px 8px;color:#eef8ff;font:800 clamp(8px,1vw,13px) system-ui;pointer-events:none}
.podcast-room-scene{padding:5px!important}
.podcast-room-scene>.podcast-room-neon,.podcast-room-scene>.podcast-room-backwall,.podcast-room-scene>.podcast-room-set,.podcast-room-scene>.room-master-audio{display:none!important}
.podcast-room-scene>.room-name-control{margin:6px 0!important;padding:9px!important}
.podcast-room-scene>.room-name-control .name-control-actions,.podcast-room-scene>.room-name-control .name-command-hint{display:none!important}
.v10-microphone-help .podcast-room-scene>.room-name-control .name-control-actions{display:flex!important}
.v10-microphone-help #room-voice-stop,.v10-microphone-help #room-everybody-talk{display:none!important}
.v10-microphone-help #room-voice-names{display:block!important;background:#eac07a;color:#08192d;font-size:12px}

.v10-hero.is-unlocked .v10-eyebrow,.v10-hero.is-unlocked h1,.v10-hero.is-unlocked>p:not(#status){display:none!important}
.v10-hero.is-unlocked{padding:5px 12px!important;margin-bottom:3px!important}
.v10-hero.is-unlocked #status{font-size:12px!important;margin:0!important}
.v10-hero.is-unlocked~.podcast-stage>.room-title,.v10-hero.is-unlocked~.podcast-stage>#live-score-quick,.v10-hero.is-unlocked~.podcast-stage>#analysts-live-data-status{display:none!important}
@media(max-width:650px){.podcast-stage{padding:7px!important;margin-top:3px!important}.v10-live-label{font-size:8px}}

/* Keep the on-air photograph visible, and make Android voice permission recoverable. */
.podcast-room-scene>.room-name-control .name-control-actions{display:flex!important}
.podcast-room-scene>.room-name-control .name-control-actions #room-voice-names{display:block!important;background:#e9bd7a!important;color:#10213b!important;font-weight:900!important}
.podcast-room-scene>.room-name-control .name-control-actions #room-voice-stop{display:block!important}
.podcast-room-scene>.room-name-control .name-control-actions #room-everybody-talk{display:none!important}
@media(max-width:530px){#v10-recovery-controls button{font-size:12px!important;padding:8px 5px!important}}
</style></head><body><main><section id="v10-app-update" aria-live="polite" hidden style="border:1px solid #e8ba76;border-radius:12px;padding:10px 12px;background:#16243c;color:#fff;margin-bottom:12px"><span id="v10-app-update-text">Checking app status</span><button type="button" id="v10-app-refresh" style="margin-left:9px;padding:8px 12px">Refresh app</button></section><header class="v10-hero"><div class="v10-eyebrow">FREDDY'S PICKS AI · V10</div><h1>🎙️ The 914 Sports Podcast Studio</h1><p>Private sports roundtable · Six analysts · Vertical Shorts recording</p><div class="v10-login"><input id="pass" type="password" placeholder="Enter your private studio password" autocomplete="current-password"><button id="unlock">Enter private studio</button></div><p id="status" aria-live="polite">Studio locked · Enter your existing boardroom password to continue.</p><p id="avatar-readiness" class="muted">Illustrated studio works separately from optional live Anam video.</p></header><section id="anam-panel" style="display:none;background:#111c32;padding:12px;border-radius:12px;margin:12px 0"><strong>Adam Stone · Live Anam Video</strong><p><button id="anam-start">Start selected analyst live video</button> <button id="anam-stop" disabled>End live video</button></p><video id="anam-video" autoplay playsinline style="width:100%;max-width:640px;border-radius:12px;background:#000"></video><p id="anam-status" class="muted">Ready</p></section><section class="podcast-stage"><div class="room-title">🎙️ THE 914 SPORTS ROUNDTABLE · ALL SIX AT ONE TABLE</div><p class="muted" style="padding:8px 12px">Tap any analyst portrait to select them. Type your question in the Host control desk, then tap Ask analyst. Original analyst portraits remain visible even without Anam live video. Cassidy retains her original V10 image and is now registered for Anam live video.</p><p class="muted" id="live-score-quick" aria-live="polite">Checking ESPN game scores and schedules after sign-in. Game scores refresh every 60 seconds while the boardroom is open. Live sportsbook odds and certified model picks are separate feeds.</p><p class="muted" id="analysts-live-data-status" aria-live="polite">Live analyst scoreboard connection status will appear here after sign-in.</p><div id="podcast-room-scene" class="podcast-room-scene" aria-label="Freddy's Picks AI V10 shared podcast room">
 <div id="v10-cinematic" class="v10-cinematic"><img src="https://d2ol7oe51mr4n9.cloudfront.net/user_3BDJnFoSlMTlWgomPBXmbowr4TM/01c379c2-18bb-4f22-9c6a-d5f0817aa643.png" class="v10-boardroom-art" loading="eager" alt="Original Freddy's Picks AI V10 boardroom with all six analysts"><div class="v10-cinematic-hotspots"><button class="v10-hotspot" type="button" style="left:2%;top:30%;width:18%;height:42%" data-v10-speaker="Bella" aria-label="Select Bella"></button><button class="v10-hotspot" type="button" style="left:21%;top:30%;width:18%;height:42%" data-v10-speaker="David" aria-label="Select David"></button><button class="v10-hotspot" type="button" style="left:40%;top:30%;width:18%;height:42%" data-v10-speaker="Cassidy" aria-label="Select Cassidy"></button><button class="v10-hotspot" type="button" style="left:59%;top:30%;width:18%;height:42%" data-v10-speaker="Roger" aria-label="Select Roger"></button><button class="v10-hotspot" type="button" style="left:79%;top:16%;width:20%;height:28%" data-v10-speaker="Sarah" aria-label="Select Sarah"></button><button class="v10-hotspot" type="button" style="left:79%;top:45%;width:20%;height:29%" data-v10-speaker="Adam Stone" aria-label="Select Adam Stone"></button><button class="v10-hotspot" type="button" style="left:1.7%;top:86%;width:6.5%;height:13%" data-v10-topic="NBA" aria-label="Select NBA"></button><button class="v10-hotspot" type="button" style="left:9.12%;top:86%;width:6.5%;height:13%" data-v10-topic="NFL" aria-label="Select NFL"></button><button class="v10-hotspot" type="button" style="left:16.54%;top:86%;width:6.5%;height:13%" data-v10-topic="MLB" aria-label="Select MLB"></button><button class="v10-hotspot" type="button" style="left:23.959999999999997%;top:86%;width:6.5%;height:13%" data-v10-topic="NHL" aria-label="Select NHL"></button><button class="v10-hotspot" type="button" style="left:31.38%;top:86%;width:6.5%;height:13%" data-v10-topic="NCAAF" aria-label="Select NCAAF"></button><button class="v10-hotspot" type="button" style="left:38.800000000000004%;top:86%;width:6.5%;height:13%" data-v10-topic="NCAAB" aria-label="Select NCAAB"></button><button class="v10-hotspot" type="button" style="left:46.22%;top:86%;width:6.5%;height:13%" data-v10-topic="MLS" aria-label="Select MLS"></button><button class="v10-hotspot" type="button" style="left:53.64%;top:86%;width:6.5%;height:13%" data-v10-topic="UCL" aria-label="Select UCL"></button><button class="v10-hotspot" type="button" style="left:61.2%;top:86%;width:7.1%;height:13%" data-v10-topic="SHARP EDGE" aria-label="Select SHARP EDGE"></button><button class="v10-hotspot" type="button" style="left:68.8%;top:86%;width:7.1%;height:13%" data-v10-topic="BEST BETS" aria-label="Select BEST BETS"></button><button class="v10-hotspot" type="button" style="left:76.4%;top:86%;width:7.1%;height:13%" data-v10-topic="PLAYER PROPS" aria-label="Select PLAYER PROPS"></button><button class="v10-hotspot" type="button" style="left:84%;top:86%;width:7.1%;height:13%" data-v10-topic="PARLAYS" aria-label="Select PARLAYS"></button><button class="v10-hotspot" type="button" style="left:91.6%;top:86%;width:7.1%;height:13%" data-v10-topic="LIVE DATA" aria-label="Select LIVE DATA"></button></div><div id="v10-live-label" class="v10-live-label" aria-live="polite">● PRIVATE BOARDROOM · SAY AN ANALYST NAME</div></div><div id="v10-chair-test" style="margin:7px 0;padding:9px;display:flex;gap:7px;flex-wrap:wrap;align-items:center;background:#0c2345;border:1px solid #5f8ab8;border-radius:9px">
<label for="v10-chair-select" style="font-size:12px">Live analyst in group picture</label>
<select id="v10-chair-select" aria-label="Choose analyst to show in group picture" style="min-width:115px;padding:8px;background:#102b4d;color:white;border:1px solid #91b5df;border-radius:6px"><option value="Cassidy">Cassidy</option><option value="Adam">Adam Stone</option><option value="Bella">Bella</option><option value="David">David</option><option value="Roger">Roger</option><option value="Sarah">Sarah</option></select>
<button type="button" id="v10-chair-test-start" style="padding:9px;background:#dfb36d;color:#071b38;border-radius:7px;font-weight:800">Test moving chair and voice</button>
<span id="v10-chair-test-status" role="status" aria-live="polite" style="flex-basis:100%;font-size:12px;color:#e1ecfc">Unlock studio, then test an analyst. Only one live video can run at a time.</span><span id="v10-live-mic-status" role="status" aria-live="polite" style="flex-basis:100%;font-size:12px;color:#ffda93">Microphone status: start a moving analyst and allow Chrome microphone access.</span>
</div><div id="v10-data-health" role="status" aria-live="polite" style="margin:5px 0 8px;padding:9px 10px;border:1px solid #477bb8;border-radius:9px;background:#081b33;color:#dfedff;font-size:12px;line-height:1.45">Continuous eight-sport refresh monitor · sign in to view timestamps.</div><div id="v10-recovery-controls" aria-label="Boardroom controls" style="display:flex;gap:7px;flex-wrap:wrap;margin:7px 0 10px;padding:8px;border:1px solid #5f8ab8;background:#0c2345;border-radius:10px">
<button id="v10-enable-mic" type="button" style="flex:1 1 110px;margin:0;padding:9px;background:#e9bb70;color:#10233c;font-weight:800">🎙 Enable voice</button>
<button id="v10-mic-test" type="button" style="flex:1 1 110px;margin:0;padding:9px;background:#146353;color:#fff;font-weight:800">🎤 Test microphone</button>\n<button id="v10-test-persona" type="button" style="flex:1 1 110px;margin:0;padding:9px;background:#174a79;color:#fff">Test Cassidy</button>
<button id="v10-replay-reply" type="button" style="flex:1 1 110px;margin:0;padding:9px;background:#174a79;color:#fff">🔊 Hear reply</button>
<span id="v10-recovery-status" role="status" style="flex-basis:100%;font-size:12px;color:#d4e6fc">Unlock studio first. Voice commands can require one microphone permission tap on Android Chrome.</span>
</div><div id="v10-source-health" role="status" aria-live="polite" style="margin:4px 0 8px;padding:8px 10px;background:#0a2138;border:1px solid #54749b;border-radius:8px;color:#e5d3b1;font-size:11px">Source checks: reading existing odds, injury and model collector workflows · No certified betting prices</div><div class="podcast-room-neon"><strong>FREDDY'S PICKS AI <em>V10</em></strong><span>LIVE BOARDROOM · NEW YORK SPORTS PODCAST</span></div>
 
<section id="room-live-spotlight" class="room-live-spotlight" hidden aria-label="Enlarged live analyst face">
 <div class="spotlight-heading"><strong><span class="room-camera-on">●</span> LIVE ON CAMERA · <span id="room-spotlight-person">SELECT AN ANALYST</span></strong><span id="room-spotlight-state">Waiting for Anam video</span></div>
 <div id="room-spotlight-stage" class="room-spotlight-stage">
  <img id="room-spotlight-photo" alt="Original cast portrait" src="/api/cast-portrait?member=Adam%20Stone" style="width:100%;height:100%;object-fit:contain">
  <video id="room-spotlight-video" autoplay muted playsinline style="display:none" aria-label="Enlarged live Anam analyst"></video>
 </div>
 <div class="room-spotlight-actions">
  <button type="button" id="room-spotlight-unmute">🔊 ENABLE LIVE AUDIO</button>
  <label for="room-live-volume">Live volume / boost <span id="room-live-volume-value">150%</span><input id="room-live-volume" type="range" min="0" max="200" step="10" value="150"></label>
  <button type="button" id="room-spotlight-fullscreen">⛶ FULL SCREEN</button>
  <button type="button" id="room-spotlight-close">Return to 6-person room</button>
 </div>
 <p id="room-live-audio-status" aria-live="polite">Tap ENABLE LIVE AUDIO to allow sound on your phone. Also check Android media volume and Bluetooth output.</p>
</section>
<div id="room-master-audio" class="room-master-audio" aria-label="Studio voice settings">
 <strong>🔊 STUDIO AUDIO</strong>
 <label for="room-voice-boost">Analyst voice boost <span id="room-voice-boost-value">140%</span>
  <input id="room-voice-boost" type="range" min="100" max="180" step="10" value="140">
 </label>
 <button id="room-audio-test" type="button">🔈 Test sound</button>
 <span id="room-voice-status">Voices boosted for the podcast. Audio may require a tap to start in Chrome.</span>
</div>
<div class="podcast-room-backwall" aria-hidden="true"><div class="room-nyc-logo room-knicks">NEW YORK<br>KNICKS 🏀</div><div class="room-nyc-center"><strong>FREDDY'S<br>PICKS AI</strong><span>DATA · SHARP EDGE · PARLAYS</span></div><div class="room-nyc-logo room-yankees">NY<br>YANKEES ⚾</div></div>
 <div id="room-voice-command" class="room-name-control" aria-label="Call an analyst by name">
 <div class="name-control-head"><strong>🎙️ HEY FREDDY · CALL AN ANALYST</strong><span id="name-command-status">Tap Voice Names and say “Cassidy” or “Adam, discuss today's games.”</span></div>
 <div class="name-control-actions"><button type="button" id="room-voice-names" disabled>🎤 Voice Names</button><button type="button" id="room-voice-stop" disabled>■ Stop listening</button><button type="button" id="room-everybody-talk" disabled>🎙️ Everyone join in</button></div>
 <div class="name-control-text"><input id="room-name-question" type="text" placeholder="Bella, what's today's NBA schedule?" aria-label="Speak to an analyst by name"><button id="room-name-send" disabled>Ask by name</button></div>
 <p class="name-command-hint">Call Bella, David, Cassidy, Roger, Sarah or Adam Stone by name. Say “everybody” to begin a group discussion. Use the microphone button to grant permission first.</p>
</div>
<div class="podcast-room-set">
  <div class="room-primary-table">
   <div class="room-subheading">🎙️ ALL SIX TOGETHER · ONE PODCAST ROOM</div><button id="restore-panel-members" type="button" style="display:block;margin:8px auto 12px;padding:10px 16px;background:#173c69;color:#fff;border:1px solid #e9bc79;border-radius:9px;font-weight:800">↻ Restore all six panel members</button>
   <section class="grid" id="people" aria-label="Six podcast members seated together"><div class="person" data-person="Bella" aria-label="Bella, Command Center Manager"><span class="live">● SAVED ANALYST</span><div class="face"><span style="position:absolute;inset:0;display:grid;place-items:center;font-weight:900;color:#e9bc79">Bella</span><img loading="eager" alt="Bella original portrait" src="/api/cast-portrait?member=Bella" style="position:relative;width:100%;height:100%;object-fit:cover;border-radius:12px"></div><strong>Bella</strong><span class="room-avatar-live-status">PANEL MEMBER RESTORED · live video available after sign-in</span></div><div class="person" data-person="David" aria-label="David, Sports Data Analyst"><span class="live">● SAVED ANALYST</span><div class="face"><span style="position:absolute;inset:0;display:grid;place-items:center;font-weight:900;color:#e9bc79">David</span><img loading="eager" alt="David original portrait" src="/api/cast-portrait?member=David" style="position:relative;width:100%;height:100%;object-fit:cover;border-radius:12px"></div><strong>David</strong><span class="room-avatar-live-status">PANEL MEMBER RESTORED · live video available after sign-in</span></div><div class="person" data-person="Cassidy" aria-label="Cassidy, Sharp Edge Analyst"><span class="live">● SAVED ANALYST</span><div class="face"><span style="position:absolute;inset:0;display:grid;place-items:center;font-weight:900;color:#e9bc79">Cassidy</span><img loading="eager" alt="Cassidy original portrait" src="/api/cast-portrait?member=Cassidy" style="position:relative;width:100%;height:100%;object-fit:cover;border-radius:12px"></div><strong>Cassidy</strong><span class="room-avatar-live-status">PANEL MEMBER RESTORED · live video available after sign-in</span></div><div class="person" data-person="Roger" aria-label="Roger, Parlay Builder"><span class="live">● SAVED ANALYST</span><div class="face"><span style="position:absolute;inset:0;display:grid;place-items:center;font-weight:900;color:#e9bc79">Roger</span><img loading="eager" alt="Roger original portrait" src="/api/cast-portrait?member=Roger" style="position:relative;width:100%;height:100%;object-fit:cover;border-radius:12px"></div><strong>Roger</strong><span class="room-avatar-live-status">PANEL MEMBER RESTORED · live video available after sign-in</span></div><div class="person" data-person="Sarah" aria-label="Sarah, Risk Manager"><span class="live">● SAVED ANALYST</span><div class="face"><span style="position:absolute;inset:0;display:grid;place-items:center;font-weight:900;color:#e9bc79">Sarah</span><img loading="eager" alt="Sarah original portrait" src="/api/cast-portrait?member=Sarah" style="position:relative;width:100%;height:100%;object-fit:cover;border-radius:12px"></div><strong>Sarah</strong><span class="room-avatar-live-status">PANEL MEMBER RESTORED · live video available after sign-in</span></div><div class="person" data-person="Adam Stone" aria-label="Adam Stone, Audit Engineer"><span class="live">● SAVED ANALYST</span><div class="face"><span style="position:absolute;inset:0;display:grid;place-items:center;font-weight:900;color:#e9bc79">Adam Stone</span><img loading="eager" alt="Adam Stone original portrait" src="/api/cast-portrait?member=Adam%20Stone" style="position:relative;width:100%;height:100%;object-fit:cover;border-radius:12px"></div><strong>Adam Stone</strong><span class="room-avatar-live-status">PANEL MEMBER RESTORED · live video available after sign-in</span></div></section>
   <div class="room-table-edge"><span>🎤</span><b>FREDDY'S PICKS AI · LIVE FROM THE 914</b><span>🎤</span></div>
  </div>
  <div id="remote" class="v10-remote-roster" hidden></div>
 </div>
 <div class="room-now-speaking" aria-live="polite"><span class="room-signal">●</span> <strong id="room-now-speaking">PODCAST ROOM READY</strong><span id="room-scene-capacity">Six analyst seats · live-video capacity checked after login</span></div><div id="room-transcript" aria-live="polite" style="background:#090e1eaa;border:1px solid #4d7198;border-radius:10px;padding:10px 14px;margin:7px 0;color:#dce6f7;font-size:13px">🎙️ Ask a question or start the six-person podcast to see the active discussion here.</div>
 <div id="room-sport-shortcuts" class="room-sport-shortcuts" aria-label="Sports discussion topics">
  <button type="button" data-room-action="NBA">🏀 NBA</button><button type="button" data-room-action="NFL">🏈 NFL</button><button type="button" data-room-action="MLB">⚾ MLB</button><button type="button" data-room-action="NHL">🏒 NHL</button><button type="button" data-room-action="NCAAF">🎓 NCAAF</button><button type="button" data-room-action="NCAAB">🏀 NCAAB</button><button type="button" data-room-action="MLS">⚽ MLS</button><button type="button" data-room-action="UCL">🏆 UCL</button><button type="button" data-room-action="SHARP EDGE">🎯 SHARP EDGE</button><button type="button" data-room-action="PLAYER PROPS">📊 PROPS</button><button type="button" data-room-action="PARLAYS">🎟️ PARLAYS</button><button type="button" data-room-action="LIVE DATA">📡 LIVE DATA</button>
 </div>
 
<section id="daily-slate-board" class="daily-slate-board" aria-label="Daily eight-sport schedule and game review">
 <div class="daily-slate-top"><strong>📅 FREDDY’S DAILY GAME-BY-GAME AUDIT</strong><span id="daily-slate-health">Sign in to load the eight-sport daily slate</span></div>
 <div class="daily-slate-toolbar">
  <label for="daily-slate-date">Eastern date</label><input id="daily-slate-date" type="date" aria-label="Sports slate date">
  <button id="daily-slate-today" type="button">Today</button>
  <button id="daily-slate-refresh" type="button">Refresh all 8 sports</button>
  <button id="daily-slate-review-all" type="button">Audit full day's game evidence</button>
 </div>
 <div id="daily-slate-counts" class="daily-slate-counts">Waiting for verified schedules</div>
 <div class="daily-slate-grid">
  <div class="daily-slate-schedule">
   <strong>All returned games · select any matchup</strong>
   <div id="daily-slate-games" class="daily-slate-games" role="list" aria-label="All games for selected date">Enter your studio password to load games.</div>
  </div>
  <div class="daily-game-audit">
   <strong>One-game analysis · Bella, David, Cassidy, Roger, Sarah & Adam</strong>
   <div id="daily-game-review" aria-live="polite">Choose a scheduled game. The analysts will distinguish verified facts from markets without prices.</div><div id="daily-game-form" style="font-size:12px;background:#0b2038;border:1px solid #335b82;border-radius:8px;padding:10px;margin:8px 0" aria-live="polite"><strong>Last 5 / Last 10 form</strong><p id="daily-game-form-status">Select a game and load completed-game form when available from ESPN.</p><div id="daily-game-form-result" style="white-space:pre-wrap;line-height:1.5"></div><button type="button" id="daily-game-form-load">Load last 5 / last 10</button></div>
   <div class="daily-slate-toolbar"><button id="daily-game-previous" type="button">← Previous</button><button id="daily-game-next" type="button">Next game →</button><button id="daily-game-discuss" type="button">🎙️ Six-person game review</button></div>
   
<section class="odds-evidence-inbox" aria-label="Source-locked sportsbook quote preflight">
 <strong>📊 SHARP EDGE · MARKET PREFLIGHT</strong>
 <p>Enter a price you observed yourself. This calculates break-even probability, not a certified prediction. No odds are fetched from DraftKings or submitted as bets.</p>
 <div class="odds-inbox-fields">
  <label>Market <select id="quote-market"><option value="moneyline">Moneyline</option><option value="spread">Spread</option><option value="total">Game total O/U</option><option value="player_points">Player points</option><option value="player_rebounds">Player rebounds</option><option value="player_assists">Player assists</option><option value="player_combo">Player combo PR/PA/RA/PRA</option></select></label>
  <label>Pick/side <input id="quote-selection" maxlength="110" placeholder="e.g. Atlanta ML / Over 225.5"></label>
  <label>Line <input id="quote-line" type="number" step="0.5" placeholder="e.g. 225.5"></label>
  <label>American odds <input id="quote-odds" type="number" step="1" placeholder="e.g. -110 or +145"></label>
  <label>Other side odds (optional) <input id="quote-opposing-odds" type="number" step="1" placeholder="-110"></label>
  <label>Your observed time (ET) <input id="quote-timestamp" type="datetime-local"></label>
 </div>
 <div class="daily-slate-toolbar"><button type="button" id="quote-checked-now">Set time I personally checked</button><button type="button" id="quote-preflight">Audit this quote</button><button type="button" id="quote-discuss" disabled>Discuss with all six</button></div>
 <div id="quote-preflight-result" aria-live="polite">Select a matchup above, enter a price, and run the evidence gate. Certified Champion-001 EV is unavailable, so no wager will be promoted.</div>
 <p class="daily-slate-warning">User-reported quotes are not verified bookmaker checkout prices. No-vig estimates require verified opposing market identity. Odds-implied probability is not the model's predicted probability.</p>
</section>
<div class="daily-consensus">
    <strong>🏆 TODAY'S BOARDROOM CONSENSUS</strong>
    <p id="daily-consensus-status">Awaiting today's full-slate review. No verified betting selection is authorized.</p>
    <div class="daily-slate-toolbar">
     <button type="button" id="daily-consensus-two">Debate 2-leg parlay</button>
     <button type="button" id="daily-consensus-five">Debate today's 5-leg parlay</button>
    </div>
    <p class="daily-slate-warning">Moneylines · spreads · totals · points/rebounds/assists · combinations · parlays. Without independently verified prices, native model probabilities and correlated-leg assessment, the correct conclusion is HOLD / NO PLAY—not five invented picks.</p>
   </div>
  </div>
 </div>
</section>
<div class="podcast-room-live-actions">
  <button id="room-start-live-all" type="button" disabled>📹 Start available live cameras</button><button id="room-stop-live-all" type="button" disabled>End live cameras</button><button id="room-start-conversation" type="button" disabled>🎙️ Talk to all six in this room</button><button id="room-host-mic" type="button" disabled>🎤 Speak to the room</button>
  <button id="room-start-video" type="button" disabled>🎬 Record this room</button>
  <span id="room-video-notice">Each seat has its own live Anam control. Original portraits remain visible until the video truly connects. Your provider account controls how many can stream simultaneously.</span><a class="room-anam-upgrade" href="https://lab.anam.ai/" target="_blank" rel="noopener noreferrer">Manage Anam video concurrency</a>
 </div>
<div id="group-video-frame" hidden style="margin:12px 0;background:#081323;border:1px solid #cbaa78;border-radius:16px;padding:12px"><div style="font-size:16px;font-weight:800;color:#e9bc79;margin-bottom:8px">ONE VIDEO · ALL SIX ANALYSTS</div><div id="group-video-preview" style="width:100%;background:#070d18;border-radius:10px;overflow:hidden"><p style="padding:14px;color:#c9d9ec">Your six-person studio video will appear here.</p></div><p class="muted">Every analyst appears in the same recorded frame. Active Anam video streams appear when the provider plan permits; remaining seats use original portraits. The moderated roundtable uses separate ElevenLabs speech, which is not automatically synchronized to each Anam stream.</p><button type="button" id="group-video-stop">Stop meeting &amp; save video</button> <a id="group-video-download" hidden style="color:#e9bc79;font-weight:800" download>Download saved group video</a></div></div><div class="stage-desk">FREDDY’S PICKS AI · PODCAST STUDIO</div><div id="model-research-display" style="margin:10px 0;background:#0b1729;border:1px solid #577399;border-radius:13px;padding:14px"><div style="font-size:17px;font-weight:800;color:#e9bc79">FREDDY’S PICKS AI · CONNECTED MODEL RESEARCH</div><p id="model-research-status" class="muted">Sign in to load authentic NBA / NFL / NHL research scores and certification status.</p><div id="model-research-cards" class="grid" style="grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:10px"></div><button type="button" id="model-research-refresh">Refresh model research</button><p class="muted">Model reports are historical pregame Elo research, not current sportsbook prices. Champion-001 is frozen. Certified EV remains HOLD.</p><p style="margin:8px 0"><a href="https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/v8-one-command.yml" target="_blank" rel="noopener noreferrer" style="color:#e9bc79;font-weight:700">Run NBA / Run All Sports / Run Sharp Edge · GitHub research workflow</a></p><p class="muted">Opens your GitHub workflow for an authenticated manual run. The boardroom automatically reads published research scorecards, not unverified picks from in-progress jobs.</p></div><p id="live-capacity-on-stage" class="muted" aria-live="polite">Anam live-avatar capacity will be checked after sign-in. Six original portraits remain visible even if only one live avatar can stream.</p><div class="stage-control"><label for="episode-title">Episode title</label><input id="episode-title" maxlength="90" placeholder="e.g. Knicks Game Night — Sharp Edge Roundtable" value="Freddy’s Picks AI · Sports Roundtable" style="min-width:260px;max-width:100%;padding:10px;border-radius:9px;background:#152640;color:#fff;border:1px solid #58708f"><button id="group-video-start" disabled style="background:#e9bc79;color:#10233a;font-weight:900;border:2px solid #f9dcb0">▶ START ALL 6 — ONE VIDEO</button><button id="roundtable" disabled>Ask the whole panel</button><button id="roundtable-stop">Stop discussion</button><button id="roundtable-reset">New episode / Clear discussion</button><button id="roundtable-export">Download episode transcript</button><button id="record-start" disabled>Record podcast audio</button><button id="record-video-start" disabled>Record podcast video</button><button id="record-shorts-start" disabled>Record vertical Short (9:16)</button><button id="record-stop" disabled>Stop & save audio</button></div><p class="muted" id="roundtable-status">Unlock to start a six-analyst discussion. Audio recording is opt-in and captures your microphone plus the moderated ElevenLabs audio, not independent Anam sessions.</p></section><section class="v10-quick"><h2>🎤 Host control desk</h2><p class="muted">Type your question or use the microphone, then ask the whole panel. Record vertical video using the gold button above.</p><textarea id="question" placeholder="Ask the analysts a question"></textarea><p class="toolbar"><button id="ask" disabled>Ask selected analyst</button> <button id="mic" disabled>🎤 Speak</button> <button id="stop">Stop / Interrupt</button></p><div id="log" aria-live="polite"></div></section><button class="v10-advanced-toggle" id="advanced-toggle" type="button" aria-expanded="false" aria-controls="advanced-panels">⚙ Advanced: live avatars and sports research</button><div id="advanced-panels" class="v10-advanced"><section class="live-wall"><h2>🎥 Live Podcast Video Wall</h2><p class="muted">Six analyst seats plus your host microphone. Your current Anam plan supports one live video session at a time; the other analysts stay visible as roster previews. Each live tile is an independent Anam session. Start available streams according to your verified plan capacity. The recorder combines active video tiles plus original cast portrait previews; this does not lip-sync the Anam video or route audio into its session.</p><div class="live-wall-grid" id="live-wall-grid"></div><div class="toolbar"><button id="live-wall-start" disabled>Start available live analysts</button><button id="live-wall-stop" disabled>End all live avatars</button><button id="live-host-mic" disabled>🎤 Host microphone</button></div><p class="muted" id="live-wall-status">Unlock the boardroom first. All six analysts are registered. The Anam plan supports one live-video conversation at a time; switch between them using the Connect buttons.</p></section><section id="adam-live-panel" style="border:1px solid #50779a;border-radius:14px;padding:12px;margin:14px 0"><strong>Live Anam analyst video</strong><p><label for="anam-analyst">Select analyst: </label><select id="anam-analyst"><option value="Adam">Adam Stone</option><option value="Bella">Bella</option><option value="Sarah">Sarah</option><option value="David">David</option><option value="Roger">Roger</option><option value="Cassidy">Cassidy</option></select></p><p class="muted">Separate Anam live-video conversation. Cassidy currently uses a temporary Anam voice; her original ElevenLabs voice remains assigned to the six-analyst moderated roundtable.</p><video id="adam-live-video" autoplay playsinline style="width:100%;max-width:500px;display:block;background:#090f1a;border-radius:12px;margin:10px 0"></video><button id="adam-live-start" disabled>Start selected analyst live video</button> <button id="adam-live-stop" disabled>End live video</button><p id="adam-live-status" class="muted">Unlock the boardroom to start.</p></section><section id="sports-data-panel" style="border:1px solid #50779a;border-radius:14px;padding:14px;margin:14px 0"><h2>Freddy's Picks AI · Data Command Center</h2><p class="muted">Read-only V10 research display. Champion-001 remains frozen. No odds, probabilities, CLV, EV, or Sharp Edge are certified without verified source data.</p><div class="toolbar"><button id="data-refresh" disabled>Refresh sports data</button><button id="data-nba" disabled>NBA</button><button id="data-nfl" disabled>NFL</button><button id="data-all" disabled>All sports</button><button id="data-artifacts" disabled>GitHub research artifacts</button><button id="data-runs" disabled>Workflow status</button><button id="data-snapshot" disabled>Signed research snapshot</button></div><button id="live-scores-refresh" type="button">Refresh live games · 8 sports</button><p id="live-scores-status" class="muted">Sign in to load live scores and schedules.</p><pre id="live-scores-results" style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:360px;overflow:auto;background:#0a1425;padding:12px;border-radius:10px">Live scoreboard pending.</pre><p id="data-status" class="muted">Unlock to check certified data feed.</p><pre id="data-results" style="white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto;background:#0a1425;padding:12px;border-radius:10px">HOLD · No independently verified model picks loaded.</pre><p class="muted">Supported research categories: moneylines, spreads, totals, player points/rebounds/assists, PR/PA/RA/PRA combos, injuries, last 5/10, back-to-backs, line movement, CLV and recalibration. A category is not live until its source is connected and validated.</p></section></div><p class="muted">AI responses require OpenAI API access. If ElevenLabs voice fails, device speech is used when supported. Speech recognition requires browser support and HTTPS.</p></main><script>(function(){const btn=document.getElementById('unlock'),input=document.getElementById('pass'),status=document.getElementById('status');let busy=false;async function enter(){if(busy)return;void window.v10UnlockStudioSound?.();const secret=input.value;if(!secret){status.textContent='Enter your existing private studio password first.';input.focus();return}busy=true;btn.disabled=true;status.textContent='Checking studio password…';const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),12000);try{const response=await fetch('/api/status',{headers:{'x-boardroom-password':secret},signal:abort.signal,cache:'no-store'});if(response.status===401){status.textContent='Incorrect studio password. Use the BOARDROOM_PASSWORD value in Railway.';return}if(!response.ok){status.textContent='Studio authentication error (HTTP '+response.status+').';return}const data=await response.json();window.__v10AnamPassword=()=>secret;document.querySelector('.v10-hero')?.classList.add('is-unlocked');if(typeof window.v10CompleteUnlock==='function'){await window.v10CompleteUnlock(secret,data)}else{const ids=['ask','roundtable','record-start','record-video-start','record-shorts-start','mic','live-host-mic','data-refresh','data-nba','data-nfl','data-all','data-artifacts','data-runs','data-snapshot'];for(const id of ids){const element=document.getElementById(id);if(element)element.disabled=!(id==='live-host-mic'||id.startsWith('data-')||data.aiConfigured)}const ap=document.getElementById('anam-panel');if(ap)ap.style.display='block';status.textContent='Unlocked · Basic studio mode (advanced controls unavailable).';const runtimeState=document.getElementById('avatar-readiness');if(runtimeState)runtimeState.textContent='Runtime loaded: '+(window.v10MainScriptLoaded?'yes':'no')+' · Full initialization: failed';const diagnostic=document.getElementById('avatar-readiness');if(diagnostic)diagnostic.textContent='Runtime downloaded: '+(window.v10RuntimeDownloaded?'yes':'no')+' · Script started: '+(window.v10RuntimeStarted?'yes':'no')+' · Startup error: '+(window.v10RuntimeInitError||'none captured')+' · Basic host controls available.';const roster=document.getElementById('people');const analysts=['Bella','David','Cassidy','Roger','Sarah','Adam Stone'];if(roster&&!roster.children.length){roster.innerHTML=analysts.map(n=>'<button type="button" class="person" data-person="'+n+'" style="min-height:75px">'+n+'</button>').join('')}let selected='Adam Stone';if(roster)roster.querySelectorAll('[data-person]').forEach(node=>node.addEventListener('click',()=>{selected=node.dataset.person;const ask=document.getElementById('ask');if(ask)ask.textContent='Ask '+selected}));const ask=document.getElementById('ask');if(ask){ask.disabled=!data.aiConfigured;ask.addEventListener('click',async()=>{const q=document.getElementById('question')?.value.trim(),log=document.getElementById('log');if(!q){if(log)log.textContent='Type a topic first.';return}ask.disabled=true;if(log)log.textContent='Asking '+selected+'…';try{const r=await fetch('/api/converse',{method:'POST',headers:{'content-type':'application/json','x-boardroom-password':secret},body:JSON.stringify({speaker:selected,question:q})});const d=await r.json();if(log)log.textContent=r.ok?selected+': '+d.reply:'Conversation unavailable: '+(d.error||r.status)}catch(e){if(log)log.textContent='Connection failed: '+e.message}finally{ask.disabled=false}})};}input.value=''}catch(e){status.textContent=e.name==='AbortError'?'Connection timed out. Try again in Chrome.':'Unable to sign in: '+e.message}finally{clearTimeout(timer);busy=false;btn.disabled=false}}btn.addEventListener('click',enter);input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();enter()}});window.addEventListener('error',function(e){const message=String(e.message||'unknown').slice(0,120);const diagnostic=document.getElementById('avatar-readiness');if(diagnostic)diagnostic.textContent='JavaScript diagnostic: '+message;if(status.textContent.includes('locked')||status.textContent.includes('Starting'))status.textContent='Studio script error: '+message});})();</script><script>
window.v10RuntimeStarted=true;
try{

document.getElementById('advanced-toggle').addEventListener('click',()=>{const p=document.getElementById('advanced-panels'),open=p.classList.toggle('is-open');document.getElementById('advanced-toggle').setAttribute('aria-expanded',String(open))});const names=['Bella','David','Cassidy','Roger','Sarah','Adam Stone'];let token='',controller=null,audio=null,selected='Adam Stone',audioCtx=null,raf=0;
const el=x=>document.getElementById(x),say=s=>{el('log').textContent+=s+'\\n'};
const roles=['Command Center Manager','Sports Data Analyst','Sharp Edge Analyst','Parlay Builder','Risk Manager','Audit Engineer'];
const skins=['#9b6047','#b77a54','#d49b74','#c38b66','#e2aa83','#b77a56'],hair=['#201c23','#151a24','#29202b','#30231b','#1a1820','#171b21'];
const outfits=[['NYC hoodie','#222b3d'],['Yankees varsity jacket','#172e55'],['Mets streetwear','#f26d21'],['Jets hoodie','#175b3b'],['Giants jacket','#234d94'],['Rangers streetwear','#c62d3b'],['Bills varsity jacket','#1c4d9a'],['Brooklyn bomber','#70436d'],['NYC denim jacket','#476b89'],['Streetwear tracksuit','#343b4c']];
let meetingNumber=0;try{meetingNumber=Number(localStorage.getItem('v10MeetingWardrobe')||'0')||0}catch(e){}
const outfitFor=i=>outfits[(meetingNumber*3+i*7)%outfits.length];
const startWardrobeMeeting=()=>{meetingNumber++;try{localStorage.setItem('v10MeetingWardrobe',String(meetingNumber))}catch(e){};if((window.v10LiveCameraCount?.()||0)===0)renderParticipants();};
const avatar=i=>'<svg viewBox="0 0 160 170" aria-hidden="true"><ellipse cx="80" cy="168" rx="75" ry="53" fill="'+outfitFor(i)[1]+'"/><rect x="66" y="114" width="28" height="31" rx="11" fill="'+skins[i]+'"/><ellipse cx="80" cy="76" rx="46" ry="57" fill="'+skins[i]+'"/><path d="M35 78 Q19 14 79 15 Q139 10 125 82 L115 51 Q81 37 45 54Z" fill="'+hair[i]+'"/><path d="M53 81 Q63 75 71 81 M90 81 Q100 75 109 81" stroke="#241c1b" stroke-width="3" fill="none" stroke-linecap="round"/><circle cx="63" cy="84" r="3" fill="#21191a"/><circle cx="99" cy="84" r="3" fill="#21191a"/><path d="M81 87 L77 105 L86 105" stroke="#8a5947" stroke-width="2" fill="none"/><ellipse class="mouth" cx="81" cy="117" rx="13" ry="3" fill="#743f3b"/></svg>';
const originalPortraits={Bella:'https://lab.anam.ai/api/avatars/410bd990-d7ca-4054-bf5b-ce862d249a8a/image/landscape?v=5644338a60533ba4',David:'https://lab.anam.ai/api/avatars/fa2b8027-f776-4485-820f-a79cf8412b6f/image/landscape?v=796ec28c55013c8e',Cassidy:'data:image/webp;base64,UklGRj4IAABXRUJQVlA4IDIIAACwKACdASpkAG4APu1mp04ppaOiL7iuYTAdiWwAwrm62F9ku1tHTy74VeLuPxytvv5q/Od8+PflZVLqRs0O5SA8v/TqNKegQkR/47rM4pOeZYPBo8S3ushCvNxSqJa3xIXD/tKdip2ampfIJ5WC1nUGUl9x5RO8ueKCxRiKgfAxG4PqDMDk42+O0KWoOznX9LzOGEIBR1YWYp+UK1FG7DwWNZ+e9IbmkXSsXG0/dkVS3yqIqV5VyyuzkEgjfAwcVP4OySWFbaqi/UHTWxQLyGk5rYG62FVHHMyG0GXChpszfrZIfkXMy8nMyTdU84BiRS2tisB3oh9ixLNB0GXSlIH3tR8zu+zvPAZCEI7ACv+o7AZG2IEVjv5Ho/uOn3PCRFHcyOK1Vx78SgeNZS+DtS6sDIl/J3K6H0nR9pEIAfIlNswoKUxSHyEmsro27CAAAP76cJAoiYsAEZftaK+V+TxflZ76HA/vL4zoEtFPvG+X5DLNNvqkqGWWZF90ILnckxbZkculliWefXoIWu3QH3hG3Kvmd7ozwuZaTt1byQxXtIHLUdKAkbnDdb7/zagtW1mPUARWKEp+9DVsKINe8FDU3xtrZ3ZVPR6Nj5WzsIP0odPtA5tPhY/WUY4XtqB5yBAZBrhD9NA9LWP1wpyqKcyAeI1MrdXsMffVq0DTUThiXDOp/nLA+02o5WIPr9fK4dIgQcob2wsWjp5DptqNBg9WAle3TtSc9oDW6hYRmflEh3X+CyMHaCcRmaU/PDaGCu4rBZ9XytK3oqD+T31TuohQCkZaXikuqgjQhvGV4KG1yuZdy2TVhe8V9h25PlG7ZTmcx26dRHlN7j1JVfJ0HM2wk49ZpcR3x8AQ9aRlCLZHP+ItDyQqTGGlBwmUF0F0XDKPNtiAEHR2u8+YkQu7H92o77aeljUFK8IlI6IyvU4gB5drf8o9SNqa2H3reG6NnvLeCXgi5HXyATXPiu8vSRFBqva4OWoMWkkNhI3MFtidxyXf8umP92MgJvzrocnMLjnsiGryFUyRkQk/XuvlVS7jsWQ2CtAQAMgoNHhkn5TjmBcT56s9FwzstkTOYjLsEn3r2rSKn4uSSp7JR7tQOmc1+cfpnbBF22MgF4sicLKe9lBYb3DSHmNUmWHq+RBKdDSzwA+GPcWPTC/3qBxrg+KzeY9FmNqG51m4Pvq8er1OMjuQxIB4Wg0xq8BQO3vluQihYEx1pgpvvvn87Ca7Zd01zhRPTDDxGij/Yk0q8TdjCWXefXVKduke6aHM6RnjgPngyiZbuj6gADzcShpY2ufdMk6VMZshBJvii+RwepnVpNPz0jFcXkaep+2kYZj58RcM8va+p1fi1Wjsqimkv+Fh0sNhZ8CZmYpXlRW5fAvoAxsWPS/29F+0tBsY3ygfgs8PPDT2BynOg3aqEPVeRLPyg370LC4odHJiPaut3Y5bqiuPTJ52fxJyBArTNCBKKdbTke7OEPWwnYPBYcgomCB/1jli8zn0iHxKD3SZ3k9a9k0spF7tuZFswLbgvRDU9jZLLFCmSQMr0gN+NZUoQVdSnJE2BCMkGppnngb1k+hgxRbKX7UKiRkgfsBZtgtaF4D8tPyWwFFV2FzD5FnzKLwqQuhODkW7yWm4m81DTtnjmbtPZg/DLyLbVz7smJU9GTnUFR+aR3CjOohq8I/N29QkL2k4OtOgkPvfYonhhYl7/gN0LYi0Ovetp1JZnSjanzJ2NrJz17YF+1LaMCJ6IMz8uGL2+u2x+Pn6uIgOiURE9REFtzYdapY+XDgKq6gOhnouzcxyKWl7YCIOlsNyNFd6hQSTAHhX9xdAtcq4KnPnSbkMjhPQJwB1CXgcyjiSAPegUpLA5RuzOTS8K9ZHRM7vm8IoCU5fV0C7mJRskUGJka6XUMu/GZ9wBJrdnOkDvtQ6bEZpdkCjWF83Gbg6GtP+Lp1hU011jagHUf1B+U5oVme4b8ezxOjwTBJRxij1qi6y48NFAQ4ybVghP1mBoSINo8nxqxRWF0w9fUe09IesEJBbWwY13jWtnpjqhsYZ9KkN5mayY8zMg6nRfujxupHIxf3o5m/qXUPcftPY9xEHJU8zJpxi7nsaySsibXAvBCUxxsMZbvcqA57PLwnPnr7wgnW4MLxME3imhLucHzrTM6AK42duwFtEU+OoR5EXvR3kSKOYSbfgZDPG0YTtp+sUIz42+fBlaej2L1h+8pkMauFWMJZSTgNh12JmEvSh0BB9rw1mwBP9cnMEiLqVd11gNNui3jQyzr7IZmRHbEKbMB+avM1eBe2HoqpLoOrJO8RgH5jSPv7fS1SX0c9DdDuSi4ZPHjB76yuw+Q/qi83Go2xBRtQ/sIRbjMRekbAAGfbCL/m70vrnJ8t0Pm/VNYDolhVjOlb2ufiKau9ffUUzECjn6104rjcjFlw5fuR7zZSKN8AAj0U8ZpxFOtRLnR6vEEN2GzxC0SHI76m9IladfNK9E6NrnWeMvcsm77ebpsLNOw88tTp1ezcEIfH2omE8HNW/oleRKRC2StKJMf6Y/ogL7hYyN2aTdB/mkbtn/n00MVyzQfvf7jdHaEVShSPOhhCDOTX8OH17NRQ086OGUz1EcrVEZ++QPaQQbtvCyjdds2Q5wneLe0kcZw5winiA8D/aFJcKLdPJ0rpftm2Evs84gOgiAVFtQWEsx4Ja9YZIe52rJR6cLTpYIYzJSgNWt/CnKi7y5W/OU9h43DWVAmEgKx9o+B8OpCV1B9tCxov8cCzAhLAFnQBD/iQo4NQj3A1cZD1LeJlN4rWFQPF+AAAA',Roger:'https://lab.anam.ai/api/avatars/2a900f85-6f8e-4070-825e-07ac8a55b7c4/image/landscape?v=9d541cb91b5cbe8e',Sarah:'https://lab.anam.ai/api/avatars/2891de34-9f0c-4b47-a7f5-091844dda047/image/landscape?v=1bf91cf0fc6c7230','Adam Stone':'https://lab.anam.ai/api/avatars/65aba6fd-25a5-4ac7-a600-667f48ffb368/image/landscape?v=7ef6178679dd4ea1'};
const participantMarkup=(n,i)=>'<div class="person" data-person="'+n+'" role="button" tabindex="0"><span class="live">● ORIGINAL CAST PREVIEW</span><div class="face"><img alt="'+n+' original cast portrait" src="/api/cast-portrait?member='+encodeURIComponent(n)+'" style="width:100%;height:100%;object-fit:cover;border-radius:14px" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><span hidden>'+avatar(i)+'</span><video id="room-video-'+(n==='Adam Stone'?'Adam':n)+'" muted autoplay playsinline style="display:none;position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:8px"></video></div><strong>'+n+'</strong><div class="muted">'+roles[i]+' · '+outfitFor(i)[0]+'</div><button type="button" class="room-avatar-live-toggle" data-live-persona="'+(n==='Adam Stone'?'Adam':n)+'" aria-label="Start or stop '+n+' live Anam video">📹 Go live</button><span class="room-avatar-live-status" id="room-live-status-'+(n==='Adam Stone'?'Adam':n)+'">PREVIEW · not streaming</span></div>';
const renderParticipants=()=>{el('people').innerHTML=names.map((n,i)=>participantMarkup(n,i)).join('');el('remote').innerHTML='';document.querySelectorAll('.person').forEach(p=>{p.onclick=()=>highlight(p.dataset.person);p.onkeydown=e=>{if(e.key==='Enter')highlight(p.dataset.person)}});window.v10RebindLiveSeatControls?.();highlight(selected)};
const highlight=n=>{selected=n;document.querySelectorAll('.person').forEach(p=>p.classList.toggle('speaking',p.dataset.person===n));el('ask').textContent='Ask '+n;window.v10FocusLiveAnalyst?.(n);const label=el('room-now-speaking');if(label&&!document.querySelector('.person.talking'))label.textContent='SELECTED: '+n.toUpperCase()+' · READY TO DISCUSS';};
renderParticipants();
const restorePanelMembers=()=>{const activeCount=window.v10LiveCameraCount?.()||0;if(activeCount>0){el('room-scene-capacity').textContent='Live video running · stop cameras before repairing cast layout';return false;}renderParticipants();const ok=names.every(n=>document.querySelector('.person[data-person="'+n+'"]'));el('room-scene-capacity').textContent=ok?'Full original panel restored: Bella · David · Cassidy · Roger · Sarah · Adam Stone':'Roster repair incomplete · refresh this page';return !!ok;};
el('restore-panel-members').onclick=restorePanelMembers;
// Reuse the shared Anam stream; this legacy button must not consume another session.
el('anam-start').onclick=async()=>{
 el('anam-start').disabled=true;el('anam-status').textContent='Switching main camera to Adam Stone…';
 try{
  if(!window.v10EnsureLiveCamera)throw Error('Camera controls are loading');
  await window.v10EnsureLiveCamera('Adam Stone');
  el('anam-status').textContent='Adam Stone live in the main boardroom; call another name to switch.';
  el('anam-stop').disabled=false
 }catch(e){el('anam-status').textContent='Camera unavailable: '+String(e.message||e).slice(0,140)}
 finally{el('anam-start').disabled=false}
};
el('anam-stop').onclick=async()=>{
 el('anam-stop').disabled=true;await window.v10StopLiveWall?.();
 el('anam-status').textContent='Boardroom live camera ended'
};
// Live Anam sessions are cleaned up by the active camera module on pagehide.




const updateModelBoard=async()=>{
 const status=el('model-research-status'),root=el('model-research-cards');
 status.textContent='Reading saved model research from GitHub…';root.replaceChildren();
 try{
  const resp=await fetch('/api/model-research',{headers:{'x-boardroom-password':token},cache:'no-store'});
  const board=await resp.json();if(!resp.ok)throw Error(board.error||'HTTP '+resp.status);window.v10BoardSnapshot=board;
  const names=['NBA','NFL','NHL'];
  status.textContent='Read-only V8 research · '+board.fetchedAt+' · '+Object.keys(board.models||{}).length+'/3 research scorecards available · Certified bets 0 / HOLD';
  for(const sport of names){
   const x=board.models?.[sport],card=document.createElement('div');
   card.style.cssText='padding:12px;border:1px solid #5d7796;background:#14253b;border-radius:12px';
   const title=document.createElement('strong');title.textContent=sport;title.style.color='#e9bc79';card.appendChild(title);
   const lines=x?[
    x.gradedResearchGames+' graded pregame research games',
    (x.researchAccuracy==null?'Directional accuracy: insufficient sample':'Research directional accuracy: '+(x.researchAccuracy*100).toFixed(1)+'%'),
    'Brier: '+(x.researchBrier==null?'withheld':x.researchBrier.toFixed(4)),
    'Report: '+(x.generatedAt||'timestamp unavailable'),
    'Source: '+x.modelVersion,
    'HOLD · no certified positive EV'
   ]:['Research report not available','HOLD · source must be checked'];
   for(const text of lines){const p=document.createElement('div');p.textContent=text;p.style.cssText='font-size:12px;line-height:1.5;color:#d0dfed;overflow-wrap:anywhere;margin-top:4px';card.appendChild(p)}root.appendChild(card);
  }
  if(board.errors?.length){const msg=document.createElement('p');msg.textContent='Source warnings: '+board.errors.map(x=>x.sport+' '+x.error).join('; ');msg.className='muted';root.appendChild(msg)}
 }catch(e){status.textContent='Model report unavailable: '+e.message+' · No predictions certified';root.replaceChildren()}
};
el('model-research-refresh').onclick=updateModelBoard;
const refreshSnapshot=async()=>{el('data-status').textContent='Checking signed GitHub delivery…';try{const r=await fetch('/api/research-snapshot',{headers:{'x-boardroom-password':token}});const d=await r.json();if(!r.ok)throw Error(d.error||'Snapshot request failed');if(!d.snapshot){el('data-status').textContent='No signed GitHub delivery received since server startup';el('data-results').textContent='HOLD · Run the V10 Research Bridge workflow from GitHub Actions. No certified picks available.';return}el('data-status').textContent='Signed GitHub delivery received · run '+d.snapshot.runId+' · '+d.snapshot.receivedAt;el('data-results').textContent=JSON.stringify(d.snapshot,null,2)+'\\nHOLD · No certified picks.'}catch(e){el('data-status').textContent='Snapshot unavailable';el('data-results').textContent='HOLD · '+e.message}};el('data-snapshot').onclick=refreshSnapshot;
const refreshRuns=async()=>{el('data-status').textContent='Checking recent GitHub workflow runs…';try{const r=await fetch('/api/research-runs',{headers:{'x-boardroom-password':token}});const d=await r.json();if(!r.ok){el('data-status').textContent='Workflow status unavailable ('+(d.providerStatus||d.error)+')';el('data-results').textContent='HOLD · GitHub access may require a read-only token.';return}el('data-status').textContent='GitHub Actions · '+d.runs.length+' recent runs · not prediction certification';el('data-results').textContent=JSON.stringify(d.runs,null,2)||'No runs found'}catch(e){el('data-status').textContent='Workflow status error';el('data-results').textContent='HOLD · '+e.message}};
el('data-runs').onclick=refreshRuns;
const refreshArtifacts=async()=>{el('data-status').textContent='Checking GitHub Actions artifact metadata…';try{const r=await fetch('/api/research-artifacts',{headers:{'x-boardroom-password':token}});const d=await r.json();if(!r.ok){el('data-status').textContent='GitHub artifact metadata unavailable ('+(d.providerStatus||d.error)+')';el('data-results').textContent='HOLD · No research artifacts imported; certified picks remain zero.';return}el('data-status').textContent='GitHub Actions · '+d.artifacts.length+' recent artifact records · metadata only · 0 certified predictions';el('data-results').textContent=d.artifacts.length?JSON.stringify(d.artifacts,null,2):'No artifacts found. HOLD · No certified picks.'}catch(e){el('data-status').textContent='GitHub connection failed';el('data-results').textContent='HOLD · '+e.message}};
el('data-artifacts').onclick=refreshArtifacts;
const refreshLiveScores=async()=>{const status=el('live-scores-status'),out=el('live-scores-results');status.textContent='Refreshing ESPN public scoreboards…';try{const r=await fetch('/api/live-scoreboards',{headers:{'x-boardroom-password':token},cache:'no-store'});const j=await r.json();if(!r.ok)throw Error(j.error||r.status);window.v10ScoreboardSnapshot={retrievedAt:j.retrievedAt,leagues:j.sports?.length||0};status.textContent='ESPN scoreboard · '+j.retrievedAt+' · '+j.sports.length+'/8 leagues responding · Not betting odds';el('live-score-quick').textContent='ESPN public game scores/schedules updated '+j.retrievedAt+' · '+j.sports.length+'/8 leagues responding. Scores auto-refresh every 60 seconds. No DraftKings live odds, player-prop prices, or certified Champion-001 picks connected.';out.textContent=j.sports.map(s=>s.sport+' · '+s.events.length+' games\\n'+(s.events.length?s.events.map(e=>e.name+' | '+e.shortStatus+' | '+(e.competitors||[]).map(c=>c.team+': '+(c.score||'-')).join(' · ')).join('\\n'):'No events returned')).join('\\n\\n')+'\\n'+j.errors.map(e=>'Unavailable: '+e.sport+' '+e.error).join('\\n')}catch(e){status.textContent='Live scoreboard unavailable: '+e.message;el('live-score-quick').textContent='ESPN scoreboard unavailable: '+e.message+' · Betting feeds remain HOLD';out.textContent='No current scores verified.'}};el('live-scores-refresh').onclick=refreshLiveScores;let scoreboardAutoRefresh=null;const startScoreboardAutoRefresh=()=>{if(scoreboardAutoRefresh)return;scoreboardAutoRefresh=setInterval(()=>{if(token&&!document.hidden)void refreshLiveScores()},60000)};
const refreshSportsData=async(scope='ALL')=>{const status=el('data-status'),results=el('data-results');status.textContent='Checking read-only certified picks feed…';results.textContent='HOLD · Awaiting verified data';try{const r=await fetch('/api/certified-picks',{headers:{'x-boardroom-password':token}});const d=await r.json();if(!r.ok){status.textContent='Certified model feed unavailable ('+(d.error||r.status)+')';results.textContent='HOLD · 0 certified predictions. Connect a verified read-only Champion-001 feed to populate the board. Research data cannot be substituted for native model probabilities.';return}const payload=d.data;const arr=Array.isArray(payload)?payload:Array.isArray(payload?.picks)?payload.picks:Array.isArray(payload?.predictions)?payload.predictions:null;const filtered=arr?arr.filter(x=>scope==='ALL'||String(x.sport||x.league||'').toUpperCase()===scope):null;status.textContent='Read-only feed received · V10 has NOT independently certified its contents';results.textContent=JSON.stringify(filtered??payload,null,2).slice(0,24000);if(filtered?.length===0)results.textContent='HOLD · No '+scope+' entries in configured feed.'}catch(e){status.textContent='Data connection error';results.textContent='HOLD · '+e.message}};
for(const [id,scope] of [['data-refresh','ALL'],['data-nba','NBA'],['data-nfl','NFL'],['data-all','ALL']])el(id).onclick=()=>refreshSportsData(scope);

const refreshSourceHealth=async()=>{
 if(!token||document.hidden)return;
 const display=el('v10-source-health');if(!display)return;
 try{
  const r=await fetch('/api/source-readiness',{headers:{'x-boardroom-password':token},cache:'no-store'});
  if(!r.ok)throw Error('HTTP '+r.status);
  const j=await r.json();const parts=(j.collectors||[]).map(x=>x.key+': '+(x.lastConclusion||x.lastStatus||x.coverage||'unknown')+(x.ageHours==null?'':' ('+x.ageHours+'h)'));
  display.textContent='SOURCE AUDIT '+(j.status||'unavailable')+' · '+(parts.join(' | ')||'No confirmed workflow runs')+' · GitHub run success ≠ authenticated odds or props · CHAMPION/EV HOLD';
 }catch(e){display.textContent='Source audit unavailable: '+String(e.message||e).slice(0,90)+' · odds / Champion / EV still HOLD'}
};
const refreshContinuousHealth=async()=>{
 if(!token||document.hidden)return;
 const display=el('v10-data-health');if(!display)return;
 try{
  const r=await fetch('/api/data-health',{headers:{'x-boardroom-password':token},cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);
  const h=await r.json();window.v10ContinuousDataStatus=h;
  const score=h.scores||{},slate=h.slate||{},research=h.research||{};
  const age=score.ageSeconds==null?'not fetched':score.ageSeconds+'s';
  const stamp=score.fetchedAt?new Date(score.fetchedAt).toLocaleTimeString('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit',second:'2-digit'}):'pending';
  const warning=(score.errors||[]).length?' · SOURCE WARNINGS: '+score.errors.map(x=>x.sport).join(', '):'';
  display.textContent='● CONTINUOUS SERVER '+(h.mode==='CONTINUOUS'?'RUNNING':'STARTING')+' · '+(score.leaguesReturned??0)+'/8 sports · '+(score.liveGames||[]).length+' games shown live · Score age '+age+' · Last '+stamp+' ET · Daily slate '+(slate.gamesReturned??0)+' games · Research '+Object.keys(research.reportGeneratedAt||{}).join('/')+' · BETTING ODDS/PROPS/CHAMPION: NOT VERIFIED · HOLD'+warning;
 }catch(e){display.textContent='Live data monitor not available ('+String(e.message||e).slice(0,80)+') · No certified bet';}
};
let continuousHealthTimer=null;
const startContinuousHealth=()=>{if(continuousHealthTimer)return;void refreshContinuousHealth();void refreshSourceHealth();continuousHealthTimer=setInterval(()=>{void refreshContinuousHealth();void refreshSourceHealth()},30000)};

window.v10MainScriptLoaded=true;const initializeAuthenticatedStudio=async(d)=>{if(el('people').querySelectorAll('.person').length!==6)restorePanelMembers();void fetch('/api/anam-concurrency',{headers:{'x-boardroom-password':token},cache:'no-store'}).then(async r=>{const info=await r.json();const line=r.ok?'ANAM LIVE VIDEO: '+info.limit+' of 6 simultaneous sessions permitted on this account'+(info.limit<6?' · Other analyst seats use original previews until the plan is upgraded':' · All six video streams can be started'): 'Anam live capacity not verified: '+(info.error||r.status);el('live-capacity-on-stage').textContent=line;el('room-scene-capacity').textContent=line}).catch(e=>{el('live-capacity-on-stage').textContent='Anam live capacity not verified · no simultaneous six-video claim'});try{startWardrobeMeeting()}catch(e){console.warn('Wardrobe initialization',e)}el('anam-panel').style.display='none';el('status').textContent='Unlocked · AI '+(d.aiConfigured?'configured':'missing')+' · ElevenLabs '+(d.elevenLabsConfigured?'connected':'missing');const liveFeed=d.liveAnamScores||{};el('analysts-live-data-status').textContent=liveFeed.status==='connected'?'LIVE GAME DATA CONNECTED TO ALL SIX ANALYSTS · ESPN game scores and schedules · DraftKings odds, player props and certified picks still unverified':liveFeed.status==='partial'?'Live data connection incomplete: '+(liveFeed.connectedAnalysts||[]).join(', ')+' connected. Retry after setup.':'ESPN scoreboard available in Research; direct Anam analyst connection '+(liveFeed.status||'not confirmed')+'.';try{const rr=await fetch('/api/diagnostics',{headers:{'x-boardroom-password':token}});if(rr.ok){const dd=await rr.json();el('avatar-readiness').textContent='Diagnostics · AI '+(dd.ai.configured?'configured':'missing')+' · Voice '+(dd.voice.configured?'configured':'missing')+' · Anam '+(dd.anam.configured?'configured':'missing')+' · Certified picks '+(dd.certifiedPicks.configured?'feed configured':'HOLD: feed missing')}}catch(e){}for(const id of ['ask','roundtable','group-video-start','room-start-conversation','room-host-mic','room-start-video','room-voice-names','room-name-send','room-everybody-talk','record-start','record-video-start','record-shorts-start','mic'])el(id).disabled=!d.aiConfigured;el('live-wall-start').disabled=!d.anamConfigured;el('room-start-live-all').disabled=!d.anamConfigured;el('adam-live-start').disabled=!d.anamConfigured;el('live-host-mic').disabled=false;for(const id of ['data-refresh','data-nba','data-nfl','data-all','data-artifacts','data-runs','data-snapshot'])el(id).disabled=false;startContinuousHealth();void updateModelBoard();void refreshLiveScores();startScoreboardAutoRefresh();void loadDailySlate();beginDailyRefresh();for(const [analyst,ready] of Object.entries(d.anamAnalysts||{})){const b=el('live-toggle-'+analyst),status=el('live-status-'+analyst);if(b&&!ready){b.disabled=true;b.textContent='Live persona pending';const roomBtn=document.querySelector('.room-avatar-live-toggle[data-live-persona="'+analyst+'"]');if(roomBtn){roomBtn.disabled=true;roomBtn.title='This persona is not yet configured';}if(status)status.textContent=analyst==='Cassidy'?'Original portrait preserved · Live approval pending':'Live persona not connected'}}if(d.sportsFeedConfigured)void refreshSportsData('ALL');else{el('data-status').textContent='Certified picks feed not configured · research and schedules remain available';el('data-results').textContent='HOLD · Native Champion-001 probabilities unavailable. No automated request will be made until the feed is configured.';}try{const a=await fetch('/api/avatar-provider',{headers:{'x-boardroom-password':token}});if(a.ok){const p=await a.json();el('avatar-readiness').textContent='Anam live selector: '+(p.anamReady?'configured':'not configured')+' · Linked: '+Object.entries(d.anamAnalysts||{}).filter(([name,ready])=>ready).map(([name])=>name).join(', ')+' · Missing live personas: '+Object.entries(d.anamAnalysts||{}).filter(([name,ready])=>!ready).map(([name])=>name).join(', ')}}catch(e){el('avatar-readiness').textContent='Optional live avatar status unavailable; illustrated preview remains available'}};
window.v10CompleteUnlock=async(secret,d)=>{token=secret;window.__v10AnamPassword=()=>token;await initializeAuthenticatedStudio(d);void window.v10HandsFreeStart?.()};
const clearTalking=()=>{document.querySelectorAll('.person').forEach(p=>p.classList.remove('talking'));cancelAnimationFrame(raf)};
const browserSpeak=(speaker,message)=>{const synth=window.speechSynthesis;if(!synth||!window.SpeechSynthesisUtterance){say('Browser speech unavailable on this device');return}try{synth.cancel();const utterance=new SpeechSynthesisUtterance(message);utterance.lang='en-US';utterance.rate=0.96;utterance.volume=1;const voices=synth.getVoices();const english=voices.filter(v=>v.lang?.toLowerCase().startsWith('en'));if(english.length)utterance.voice=english[Math.max(0,names.indexOf(speaker))%english.length];const active=[...document.querySelectorAll('.person')].find(p=>p.dataset.person===speaker);utterance.onstart=()=>active?.classList.add('talking');utterance.onend=clearTalking;utterance.onerror=()=>{clearTalking();say('Browser speech could not play')};synth.speak(utterance);say('Using device voice fallback for '+speaker)}catch(e){clearTalking();say('Browser speech unavailable: '+e.message)}};el('stop').onclick=()=>{controller?.abort();audio?.pause();clearTalking();window.speechSynthesis?.cancel();say('Interrupted')};
el('ask').onclick=async()=>{void window.v10UnlockStudioSound?.();controller?.abort();audio?.pause();clearTalking();controller=new AbortController();const q=el('question').value.trim();if(!q)return;say('You: '+q);try{let r=await fetch('/api/converse',{method:'POST',headers:{'content-type':'application/json','x-boardroom-password':token},body:JSON.stringify({speaker:selected,question:q}),signal:controller.signal});let d=await r.json();if(!r.ok)throw Error((d.category||d.error||'AI error')+(d.providerStatus?' (provider HTTP '+d.providerStatus+')':'')+(d.providerCode?' ['+d.providerCode+']':''));say(selected+': '+d.reply);let v=await fetch('/api/voice',{method:'POST',headers:{'content-type':'application/json','x-boardroom-password':token},body:JSON.stringify({speaker:selected,text:d.reply}),signal:controller.signal});if(v.ok){let blob=await v.blob();audio=new Audio(URL.createObjectURL(blob));connectPodcastAudio(audio);const active=document.querySelector('.person[data-person="'+selected+'"]');audio.onended=()=>{clearTalking();URL.revokeObjectURL(audio.src)};audio.onerror=clearTalking;await audio.play();active?.classList.add('talking')}else {let e=await v.json().catch(()=>({}));say('ElevenLabs unavailable: '+(e.category||e.error||v.status));browserSpeak(selected,d.reply)}}catch(e){if(e.name!=='AbortError')say('Error: '+e.message)}};
let roundtableActive=false,panelSession=0,panelMic=null;const episodeHistory=[];const stopPanel=()=>{setPanelSpeaker(null);window.v10SetPanelMode?.(false);roundtableActive=false;panelSession++;controller?.abort();audio?.pause();clearTalking();window.speechSynthesis?.cancel();try{panelMic?.abort()}catch{}el('roundtable-status').textContent='Discussion interrupted · ready for your next question';el('roundtable').disabled=false};el('roundtable-stop').onclick=stopPanel;
const setPanelSpeaker=speaker=>{document.querySelectorAll('.live-tile').forEach(t=>t.classList.remove('on-air'));document.querySelectorAll('.person').forEach(t=>t.classList.remove('talking'));podcastSpeaker=speaker||'';const roomStatus=el('room-now-speaking');if(roomStatus)roomStatus.textContent=speaker?'ON AIR: '+speaker.toUpperCase()+" · FREDDY'S PICKS AI V10":'PODCAST ROOM READY · SIX ANALYSTS';if(!speaker)return;const key=speaker==='Adam Stone'?'Adam':speaker;const tile=document.getElementById('live-'+key)?.closest('.live-tile');tile?.classList.add('on-air');document.querySelector('.person[data-person="'+speaker+'"]')?.classList.add('talking')};
window.v10IsRecording=()=>!!podcastRecording;
window.v10IsVoiceConversationActive=()=>!!roundtableActive||!!nameListening||!!nameSpeaking;
let podcastRecorder=null,podcastStream=null,podcastAudioContext=null,podcastMix=null,podcastMic=null,podcastChunks=[],podcastRecording=false,podcastVideo=false,podcastCanvas=null,podcastDrawTimer=null,podcastVideoStream=null,podcastSpeaker='',podcastCaption='',podcastCaptionBy='',podcastVertical=false,podcastCues=[],podcastStartedAt=0;const recordStart=el('record-start'),recordStop=el('record-stop'),videoStart=el('record-video-start'),shortsStart=el('record-shorts-start'),groupVideoStart=el('group-video-start'),groupVideoStop=el('group-video-stop');const groupCastImages=names.map(n=>{const im=new Image();im.src='/api/cast-portrait?member='+encodeURIComponent(n);return im});recordStart.addEventListener('pointerdown',()=>{podcastVideo=false;podcastVertical=false});recordStart.onclick=async()=>{if(podcastRecording)return;if(!window.MediaRecorder||!navigator.mediaDevices?.getUserMedia){el('roundtable-status').textContent='Audio recording unsupported in this browser';return}recordStart.disabled=true;videoStart.disabled=true;shortsStart.disabled=true;try{podcastMic=await navigator.mediaDevices.getUserMedia({audio:true,video:false});podcastAudioContext=new (window.AudioContext||window.webkitAudioContext)();podcastMix=podcastAudioContext.createMediaStreamDestination();const micSource=podcastAudioContext.createMediaStreamSource(podcastMic);micSource.connect(podcastMix);await podcastAudioContext.resume();const type=['audio/webm;codecs=opus','audio/webm','audio/mp4'].find(x=>MediaRecorder.isTypeSupported(x));if(podcastVideo){podcastCanvas=document.createElement('canvas');podcastCanvas.width=1280;podcastCanvas.height=720;podcastCanvas.style.cssText='display:block;width:100%;height:auto;aspect-ratio:16/9;background:#061020';el('group-video-preview').replaceChildren(podcastCanvas);el('group-video-frame').hidden=false;const ctx=podcastCanvas.getContext('2d');const draw=()=>{ctx.fillStyle='#0c1528';ctx.fillRect(0,0,1280,720);ctx.fillStyle='#e9bc79';ctx.font='bold 42px sans-serif';ctx.fillText('FREDDY’S PICKS AI · PODCAST STUDIO',65,78);ctx.font='24px sans-serif';ctx.fillStyle='#cad9ed';ctx.fillText('914 SPORTS ROUNDTABLE · SIX ANALYSTS + HOST',65,118);const episodeTitle=(el('episode-title')?.value||'SPORTS ROUNDTABLE').trim().slice(0,65);ctx.fillStyle='#ffffff';ctx.font='bold 25px sans-serif';ctx.fillText(episodeTitle,65,151);
const seats=['Bella','David','Cassidy','Roger','Sarah','Adam Stone'];
const drawFace=(n,idx,x,y,w,h)=>{
 const live=document.getElementById('room-video-'+(n==='Adam Stone'?'Adam':n));
 const im=groupCastImages[idx];
 ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();
 let image=null,iw=0,ih=0;
 if(live&&live.style.display!=='none'&&live.readyState>=2&&live.videoWidth){image=live;iw=live.videoWidth;ih=live.videoHeight}
 else if(im.complete&&im.naturalWidth){image=im;iw=im.naturalWidth;ih=im.naturalHeight}
 if(image){const scale=Math.max(w/iw,h/ih),dw=iw*scale,dh=ih*scale;ctx.drawImage(image,x+(w-dw)/2,y+(h-dh)/2,dw,dh)}
 else{ctx.fillStyle='#253e65';ctx.fillRect(x,y,w,h);ctx.fillStyle='#e8b874';ctx.font='bold 70px sans-serif';ctx.fillText(n[0],x+w/3,y+h/2)}
 ctx.restore()
};
ctx.fillStyle='#061632';ctx.fillRect(18,158,1245,397);
ctx.fillStyle='#174c85';ctx.fillRect(18,160,1245,6);
ctx.fillStyle='#ebc58c';ctx.font='bold 22px sans-serif';ctx.fillText('● ALL SIX ANALYSTS · ONE STUDIO ROOM',40,193);
ctx.fillStyle='#0b2045';ctx.fillRect(24,208,1233,322);
seats.forEach((n,i)=>{
 const x=34+i*206,w=197,h=277,y=210,active=podcastSpeaker===n;
 if(active){ctx.fillStyle='#164d60';ctx.fillRect(x-2,y-2,w+4,h+4)}
 drawFace(n,i,x,y,w,h);
 ctx.fillStyle='#07192dda';ctx.fillRect(x,459,w,31);
 ctx.fillStyle=active?'#56f0b6':'#ffffff';ctx.font='bold 22px sans-serif';
 ctx.fillText(n==='Adam Stone'?'ADAM':n.toUpperCase(),x+7,482);
 ctx.font='bold 12px sans-serif';ctx.fillStyle='#c9dbee';ctx.fillText(roles[i].toUpperCase().slice(0,24),x+7,506);
 if(active){ctx.fillStyle='#50f0b4';ctx.beginPath();ctx.arc(x+w-13,225,7,0,Math.PI*2);ctx.fill()}
});
ctx.fillStyle='#725137';ctx.fillRect(28,526,1223,33);
ctx.fillStyle='#e1b67a';ctx.fillRect(28,526,1223,4);
ctx.fillStyle='#f6d1a0';ctx.font='bold 18px sans-serif';ctx.fillText('🎙 FREDDY’S PICKS AI · LIVE FROM THE 914 · SHARED PODCAST TABLE',274,548);
ctx.fillStyle='#d9b57c';ctx.font='bold 24px sans-serif';ctx.fillText('HOST: FREDDY · PRIVATE PODCAST RECORDING',65,667);const modelSummary=window.v10BoardSnapshot;ctx.fillStyle='#a4c9e8';ctx.font='16px sans-serif';ctx.fillText(modelSummary?.models?'MODEL RESEARCH (NOT CERTIFIED) · '+['NBA','NFL','NHL'].map(n=>n+': '+(modelSummary.models[n]?.gradedResearchGames??'N/A')+' graded').join(' · ')+' · SHARP EDGE HOLD':'MODEL RESEARCH UNAVAILABLE · SHARP EDGE HOLD',65,699);if(podcastRecording){const elapsed=Math.max(0,Math.floor((performance.now()-podcastStartedAt)/1000));const clock=String(Math.floor(elapsed/3600)).padStart(2,'0')+':'+String(Math.floor(elapsed%3600/60)).padStart(2,'0')+':'+String(elapsed%60).padStart(2,'0');ctx.fillStyle='#ef5d6c';ctx.beginPath();ctx.arc(1044,58,9,0,Math.PI*2);ctx.fill();ctx.fillStyle='#ffffff';ctx.font='bold 21px sans-serif';ctx.fillText('REC  '+clock,1065,65)}if(podcastCaption){ctx.fillStyle='#07101be8';ctx.fillRect(55,554,1170,70);ctx.fillStyle='#52efbc';ctx.font='bold 18px sans-serif';ctx.fillText(podcastCaptionBy.toUpperCase(),76,579);ctx.fillStyle='#fff';ctx.font='22px sans-serif';const words=podcastCaption.split(' ');let line='',lines=[];for(const word of words){const trial=line?line+' '+word:word;if(ctx.measureText(trial).width>1090){lines.push(line);line=word}else line=trial}if(line)lines.push(line);ctx.fillText(lines[0]||'',76,607);if(lines.length>1){ctx.fillStyle='#07101be8';ctx.fillRect(55,624,1170,34);ctx.fillStyle='#fff';ctx.fillText(lines[1],76,649)}}};draw();let outputCanvas=podcastCanvas;if(podcastVertical){outputCanvas=document.createElement('canvas');outputCanvas.width=720;outputCanvas.height=1280;const vctx=outputCanvas.getContext('2d');const drawPortrait=(c,i,cx,cy,scale)=>{c.save();c.translate(cx,cy);c.scale(scale,scale);c.fillStyle=outfitFor(i)[1];c.beginPath();c.ellipse(0,107,102,78,0,0,Math.PI*2);c.fill();c.fillStyle=skins[i];c.fillRect(-17,53,34,43);c.beginPath();c.ellipse(0,-1,65,78,0,0,Math.PI*2);c.fill();c.fillStyle=hair[i];c.beginPath();c.moveTo(-65,5);c.bezierCurveTo(-83,-112,70,-112,65,8);c.lineTo(47,-42);c.quadraticCurveTo(0,-62,-48,-32);c.closePath();c.fill();c.strokeStyle='#241c1b';c.lineWidth=4;c.beginPath();c.moveTo(-39,0);c.quadraticCurveTo(-27,-7,-15,0);c.moveTo(15,0);c.quadraticCurveTo(27,-7,39,0);c.stroke();c.fillStyle='#21191a';c.beginPath();c.arc(-25,7,4,0,Math.PI*2);c.arc(25,7,4,0,Math.PI*2);c.fill();c.strokeStyle='#8a5947';c.lineWidth=3;c.beginPath();c.moveTo(0,11);c.lineTo(-4,34);c.lineTo(8,34);c.stroke();c.fillStyle='#743f3b';c.beginPath();c.ellipse(0,52,18,podcastSpeaker===names[i]?4+Math.abs(Math.sin(performance.now()/115+i))*12:4,0,0,Math.PI*2);c.fill();c.restore()};const renderVertical=()=>{vctx.fillStyle='#081326';vctx.fillRect(0,0,720,1280);vctx.fillStyle='#e9bc79';vctx.font='bold 34px sans-serif';vctx.fillText('FREDDY’S PICKS AI',38,84);vctx.fillStyle='#c9dbed';vctx.font='22px sans-serif';vctx.fillText('914 SPORTS · PODCAST SHORTS',38,124);const title=(el('episode-title')?.value||'Sports Roundtable').slice(0,39);vctx.fillStyle='#ffffff';vctx.font='bold 24px sans-serif';vctx.fillText(title,38,178);const seats=['Bella','David','Cassidy','Roger','Sarah','Adam Stone'];const roles=['COMMAND CENTER','SPORTS DATA','SHARP EDGE','PARLAY BUILDER','RISK MANAGER','AUDIT ENGINEER'];const idx=seats.indexOf(podcastSpeaker);const focused=idx>=0?idx:0;const n=seats[focused];vctx.fillStyle='#16354b';vctx.fillRect(34,220,652,540);vctx.strokeStyle='#52efbc';vctx.lineWidth=5;vctx.strokeRect(34,220,652,540);vctx.fillStyle='#52efbc';vctx.font='bold 23px sans-serif';vctx.fillText(podcastSpeaker?'● ON AIR':'● PANEL READY',62,266);drawPortrait(vctx,focused,360,434,1.45);vctx.textAlign='center';vctx.fillStyle='#ffffff';vctx.font='bold 45px sans-serif';vctx.fillText(n,360,636);if(podcastSpeaker===n){const bounce=14+Math.abs(Math.sin(performance.now()/135))*18;vctx.fillStyle='#52efbc';for(let bar=0;bar<7;bar++){const h=bounce*(.55+.45*Math.abs(Math.sin(performance.now()/170+bar)));vctx.fillRect(295+bar*21,710-h,12,h)}}vctx.fillStyle='#c9dbed';vctx.font='22px sans-serif';vctx.fillText(roles[focused],360,679);vctx.textAlign='left';vctx.fillStyle='#a9bdd3';vctx.font='19px sans-serif';vctx.fillText('THE PANEL',38,806);seats.forEach((person,i)=>{const x=38+(i%3)*222,y=828+Math.floor(i/3)*96;vctx.fillStyle=podcastSpeaker===person?'#236357':'#1b304b';vctx.fillRect(x,y,206,78);drawPortrait(vctx,i,x+38,y+34,.28);vctx.fillStyle='#ffffff';vctx.font='bold 19px sans-serif';vctx.fillText(person,x+70,y+35);vctx.font='14px sans-serif';vctx.fillStyle='#b5cbe0';vctx.fillText(roles[i].length>15?roles[i].slice(0,14)+'…':roles[i],x+70,y+60)});vctx.fillStyle='#0c1727';vctx.fillRect(30,1060,660,152);vctx.fillStyle='#52efbc';vctx.font='bold 18px sans-serif';vctx.fillText((podcastCaptionBy||'FREDDY').toUpperCase(),50,1095);vctx.fillStyle='#ffffff';vctx.font='21px sans-serif';const words=(podcastCaption||'Six analysts. One sports roundtable.').split(/\\s+/);let line='',y=1130,lines=0;for(const word of words){const next=line?line+' '+word:word;if(vctx.measureText(next).width>605&&line){vctx.fillText(line,50,y);lines++;y+=30;line=word;if(lines>=2)break}else line=next}if(lines<3&&line){while(vctx.measureText(line).width>605&&line.length>3)line=line.slice(0,-4)+'…';vctx.fillText(line,50,y)};vctx.fillStyle='#e9bc79';vctx.font='17px sans-serif';vctx.fillText('FREDDY’S PICKS AI · PRIVATE STUDIO',38,1250)};renderVertical();podcastDrawTimer=setInterval(()=>{draw();renderVertical()},250)}else podcastDrawTimer=setInterval(draw,250);podcastVideoStream=outputCanvas.captureStream(10);const combined=new MediaStream([...podcastVideoStream.getVideoTracks(),...podcastMix.stream.getAudioTracks()]);const vt=['video/webm;codecs=vp8,opus','video/webm','video/mp4;codecs=avc1.42E01E,mp4a.40.2','video/mp4'].find(x=>MediaRecorder.isTypeSupported(x));if(!vt)throw Error('Video recording not supported in this browser');podcastRecorder=new MediaRecorder(combined,{mimeType:vt})}else podcastRecorder=new MediaRecorder(podcastMix.stream,type?{mimeType:type}:undefined);podcastChunks=[];podcastRecorder.ondataavailable=e=>{if(e.data.size)podcastChunks.push(e.data)};podcastRecorder.onerror=e=>{el('roundtable-status').textContent='Recording error: '+(e.error?.message||'Browser recorder failure');if(podcastRecorder?.state==='recording')podcastRecorder.stop()};podcastRecorder.onstop=()=>{const blob=new Blob(podcastChunks,{type:podcastRecorder.mimeType||'audio/webm'});if(blob.size){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='freddys-v10-'+(el('episode-title')?.value||'episode').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,45)+'-'+new Date().toISOString().slice(0,10)+(podcastVideo?(blob.type.includes('mp4')?'.mp4':'.webm'):blob.type.includes('mp4')?'.m4a':'.webm');document.body.appendChild(a);a.click();a.remove();if(podcastVideo){if(window.v10GroupVideoURL)URL.revokeObjectURL(window.v10GroupVideoURL);window.v10GroupVideoURL=url;const dl=el('group-video-download');dl.href=url;dl.download=a.download;dl.hidden=false}else setTimeout(()=>URL.revokeObjectURL(url),30000)}if(podcastVideo&&podcastCues.length){const fmt=ms=>{const n=Math.max(0,Math.floor(ms));const h=String(Math.floor(n/3600000)).padStart(2,'0'),m=String(Math.floor(n%3600000/60000)).padStart(2,'0'),sec=String(Math.floor(n%60000/1000)).padStart(2,'0'),mil=String(n%1000).padStart(3,'0');return h+':'+m+':'+sec+'.'+mil};const vtt='WEBVTT\\n\\n'+podcastCues.filter(c=>Number.isFinite(c.start)).map((c,i)=>(i+1)+'\\n'+fmt(c.start)+' --> '+fmt(c.end||Math.max(c.start+300,performance.now()-podcastStartedAt))+'\\n'+c.speaker+': '+c.text.replace(/\\s+/g,' ')+'\\n').join('\\n');const vttUrl=URL.createObjectURL(new Blob([vtt],{type:'text/vtt'}));const link=document.createElement('a');link.href=vttUrl;link.download='freddys-v10-episode-'+new Date().toISOString().slice(0,10)+'.vtt';document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(vttUrl),30000)}podcastMic?.getTracks().forEach(t=>t.stop());podcastVideoStream?.getTracks().forEach(t=>t.stop());if(podcastDrawTimer)clearInterval(podcastDrawTimer);podcastDrawTimer=null;void podcastAudioContext?.close();podcastRecording=false;podcastVideo=false;podcastVertical=false;recordStart.disabled=false;videoStart.disabled=false;shortsStart.disabled=false;recordStop.disabled=true;recordStop.textContent='Stop & save audio';el('roundtable-status').textContent='Recording stopped · file downloads requested. Check your browser downloads.'};podcastCues=[];podcastStartedAt=performance.now();podcastRecorder.start(1000);podcastRecording=true;recordStop.disabled=false;recordStop.textContent=podcastVideo?'Stop & save video':'Stop & save audio';el('roundtable-status').textContent='● Recording '+(podcastVideo?'podcast video':'podcast audio')+' · Stop & save to download.'}catch(e){podcastMic?.getTracks().forEach(t=>t.stop());void podcastAudioContext?.close();recordStart.disabled=false;videoStart.disabled=false;shortsStart.disabled=false;if(podcastDrawTimer)clearInterval(podcastDrawTimer);podcastDrawTimer=null;podcastVideoStream?.getTracks().forEach(t=>t.stop());podcastRecording=false;podcastVideo=false;podcastVertical=false;recordStop.disabled=true;recordStop.textContent='Stop & save audio';el('roundtable-status').textContent='Recording unavailable: '+e.message}};videoStart.onclick=async()=>{podcastVideo=true;podcastVertical=false;await recordStart.onclick()};shortsStart.onclick=async()=>{podcastVideo=true;podcastVertical=true;await recordStart.onclick()};recordStop.onclick=()=>{if(podcastRecorder?.state==='recording'){recordStop.disabled=true;el('roundtable-status').textContent='Finalizing recording and preparing downloads…';podcastRecorder.stop()}};
let voiceBoost=1.4,voiceBoostContext=null;
const voiceNodes=new Set();
const voiceBoostInput=el('room-voice-boost'),voiceBoostLabel=el('room-voice-boost-value'),voiceAudioStatus=el('room-voice-status');
const unlockStudioSound=()=>{
 try{
  const Ctx=window.AudioContext||window.webkitAudioContext;
  if(!Ctx)throw Error('Web Audio unsupported');
  if(!voiceBoostContext||voiceBoostContext.state==='closed')voiceBoostContext=new Ctx();
  void voiceBoostContext.resume().catch(()=>{voiceAudioStatus.textContent='Audio paused by browser. Tap Test sound or Start conversation again.'});
  return voiceBoostContext
 }catch(e){voiceAudioStatus.textContent='Device audio unavailable: '+e.message;return null}
};
window.v10UnlockStudioSound=unlockStudioSound;
voiceBoostInput.oninput=()=>{
 voiceBoost=Math.max(1,Math.min(1.8,Number(voiceBoostInput.value)/100));
 voiceBoostLabel.textContent=Math.round(voiceBoost*100)+'%';
 for(const node of voiceNodes)node.gain.value=voiceBoost;
 voiceAudioStatus.textContent='Studio voices at '+Math.round(voiceBoost*100)+'% gain with dynamic limiting. Phone media volume still controls output.'
};
el('room-audio-test').onclick=()=>{
 const context=unlockStudioSound();if(!context)return;
 try{
  const oscillator=context.createOscillator(),gain=context.createGain();
  oscillator.type='sine';oscillator.frequency.value=440;gain.gain.value=0.001;
  oscillator.connect(gain);gain.connect(context.destination);
  const at=context.currentTime;
  gain.gain.setValueAtTime(0.001,at);
  gain.gain.exponentialRampToValueAtTime(0.11,at+0.035);
  gain.gain.exponentialRampToValueAtTime(0.001,at+0.35);
  oscillator.start(at);oscillator.stop(at+0.38);
  oscillator.onended=()=>{oscillator.disconnect();gain.disconnect()};
  voiceAudioStatus.textContent='Audio test played. If silent, raise Android media volume or check Bluetooth/output device.'
 }catch(e){voiceAudioStatus.textContent='Audio test failed: '+e.message}
};
const connectPodcastAudio=element=>{
 element.muted=false;element.volume=1;
 const context=podcastRecording&&podcastAudioContext?.state!=='closed'?podcastAudioContext:unlockStudioSound();
 if(!context)return;
 try{
  void context.resume().catch(()=>{voiceAudioStatus.textContent='Voice playback blocked. Tap Test sound, then retry the conversation.'});
  const source=context.createMediaElementSource(element);
  const boost=context.createGain();boost.gain.value=voiceBoost;voiceNodes.add(boost);
  const limiter=context.createDynamicsCompressor();
  limiter.threshold.value=-16;limiter.knee.value=20;limiter.ratio.value=8;limiter.attack.value=0.004;limiter.release.value=0.17;
  source.connect(boost);boost.connect(limiter);limiter.connect(context.destination);
  if(podcastRecording&&context===podcastAudioContext&&podcastMix)limiter.connect(podcastMix);
  const cleanup=()=>{voiceNodes.delete(boost);try{source.disconnect();boost.disconnect();limiter.disconnect()}catch{}};
  element.addEventListener('ended',cleanup,{once:true});
  element.addEventListener('error',cleanup,{once:true})
 }catch(e){voiceAudioStatus.textContent='Using normal speaker volume: '+e.message}
};
const speakPanel=async(speaker,reply,signal)=>{setPanelSpeaker(speaker);const v=await fetch('/api/voice',{method:'POST',headers:{'content-type':'application/json','x-boardroom-password':token},body:JSON.stringify({speaker,text:reply}),signal});if(!v.ok){say('ElevenLabs response unavailable for '+speaker+'; tap Hear reply to use phone voice.');const status=el('v10-recovery-status');if(status)status.textContent='Voice stream unavailable; tap Hear reply to use device speech';return}const url=URL.createObjectURL(await v.blob());try{audio=new Audio(url);connectPodcastAudio(audio);const active=document.querySelector('.person[data-person="'+speaker+'"]');await new Promise(resolve=>{let cue=null;const finish=()=>{if(cue)cue.end=Math.max(cue.start+300,performance.now()-podcastStartedAt);resolve()};audio.onended=finish;audio.onerror=finish;audio.play().then(()=>{active?.classList.add('talking');if(podcastRecording&&podcastVideo){cue={speaker,text:reply,start:Math.max(0,performance.now()-podcastStartedAt),end:0};podcastCues.push(cue)}}).catch(finish)})}finally{setPanelSpeaker(null);clearTalking();URL.revokeObjectURL(url)}};
const startPanel=async(q)=>{if(!q)return;stopPanel();roundtableActive=true;window.v10SetPanelMode?.(true);const session=panelSession;el('roundtable').disabled=true;el('roundtable-status').textContent='Panel discussion in progress · host can interrupt';say('You to the panel: '+q);podcastCaptionBy='Freddy';podcastCaption=q;el('room-transcript').textContent='HOST QUESTION: '+q;const remarks=[];episodeHistory.push({speaker:'Freddy',reply:q});if(episodeHistory.length>24)episodeHistory.splice(0,episodeHistory.length-24);for(const speaker of names){if(!roundtableActive||session!==panelSession)break;highlight(speaker);controller=new AbortController();el('roundtable-status').textContent='Speaking: '+speaker+' · Stop discussion to interrupt';try{const context=episodeHistory.slice(-9,-1).map(x=>x.speaker+': '+x.reply).join('\\n').slice(0,2500);const question='Host topic: '+q+'\\nEarlier panel remarks:\\n'+(context||'None yet')+'\\nRespond directly to Freddy and previous analysts naturally, with real personality and useful insight, in roughly 40 to 85 spoken words. Sometimes address him as Freddy, but do not repeat his name mechanically. Critique another analyst politely when appropriate. Do not invent live odds, injuries, model probabilities or certified bets. If no five-leg parlay is verified, agree on HOLD rather than manufacturing five picks.';const r=await fetch('/api/converse',{method:'POST',headers:{'content-type':'application/json','x-boardroom-password':token},body:JSON.stringify({speaker,question}),signal:controller.signal});const d=await r.json();if(!r.ok)throw Error(d.category||d.error||'Analyst unavailable');if(session!==panelSession)break;podcastCaptionBy=speaker;podcastCaption=d.reply;el('room-transcript').textContent=speaker.toUpperCase()+': '+d.reply;remarks.push({speaker,reply:d.reply});episodeHistory.push({speaker,reply:d.reply});if(episodeHistory.length>24)episodeHistory.shift();say(speaker+': '+d.reply);await speakPanel(speaker,d.reply,controller.signal)}catch(e){if(e.name!=='AbortError')say(speaker+' unavailable: '+e.message)}}if(session===panelSession){roundtableActive=false;window.v10SetPanelMode?.(false);setPanelSpeaker(null);el('roundtable').disabled=false;podcastCaption='';el('roundtable-status').textContent='Discussion complete · ask another topic or use host mic'}};
el('roundtable-export').onclick=()=>{if(!episodeHistory.length){el('roundtable-status').textContent='No episode transcript to export yet';return}const lines=['Freddy’s Picks AI V10 · Podcast Episode Transcript','Exported: '+new Date().toISOString(),'Research and betting claims are not independently certified.','',...episodeHistory.map((x,i)=>(i+1)+'. '+x.speaker+': '+x.reply)];const blob=new Blob([lines.join('\\n\\n')],{type:'text/plain;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='freddys-v10-podcast-'+new Date().toISOString().slice(0,10)+'.txt';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);el('roundtable-status').textContent='Transcript download requested · saved locally by your browser'};



/* Date-scoped eight-league boardroom analyst queue; no fictional bets. */
let currentSlate=null,dailyGames=[],dailySelected=0,dailyReviewed=new Set(),dailyScanActive=false,dailyPinned=false,dailyRefreshTimer=null;
const dailyFormCache=new Map(),dailyFormReviewed=new Set();
const easternTodayClient=()=>{
 const v=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()).filter(x=>x.type!=='literal').map(x=>[x.type,x.value]));
 return v.year+'-'+v.month+'-'+v.day
};
const escapeSlateText=v=>String(v==null?'':v).slice(0,160);
const setDailyConsensus=()=>{
 const status=el('daily-consensus-status');if(!status)return;
 const reviewed=dailyReviewed.size,total=dailyGames.length;
 const certified=0;
 status.textContent='DAILY CONSENSUS · '+reviewed+'/'+total+' schedule/market readiness checks · '+[...dailyFormReviewed].filter(k=>k.startsWith(currentSlate?.dateEastern+':')).length+' L5/L10 team-form requests · Certified 2-leg: NO PLAY (0/2) · Certified 5-leg: NO PLAY (0/5) · All markets HOLD until independently verified prices, native Champion-001 probabilities, and prop/correlation evidence are available.';
};

const formatDailyForm=data=>{
 if(!data)return 'No completed-game form fetched';
 const entries=[];
 for(const t of data.teams||[]){
  const five=t.last5Record||{},ten=t.last10Record||{};
  entries.push(t.team+' · '+t.status+' · ESPN retrieved '+(t.fetchedAt||'unknown'));
  if(t.error)entries.push('  Source error: '+t.error);
  entries.push('  LAST 5: '+(five.games||0)+' available: '+(five.wins||0)+'W / '+(five.losses||0)+'L / '+(five.ties||0)+'T');
  entries.push('  LAST 10: '+(ten.games||0)+' available: '+(ten.wins||0)+'W / '+(ten.losses||0)+'L / '+(ten.ties||0)+'T');
  for(const g of (t.last5||[]))entries.push('  '+g.dateEastern+' vs '+g.opponent+' · '+g.result+' '+(g.teamScore==null?'score unavailable':g.teamScore+'–'+g.opponentScore));
 }
 entries.push('Research-only form; no betting probabilities, injuries, live quotes or certified positive EV.');
 return entries.join('\\n')
};
const displayDailyForm=()=>{
 const game=dailyGames[dailySelected],root=el('daily-game-form-result'),st=el('daily-game-form-status');
 if(!game){root.textContent='';st.textContent='No game selected';el('daily-game-form-load').disabled=true;return}
 el('daily-game-form-load').disabled=false;
 const cached=dailyFormCache.get(currentSlate.dateEastern+':'+game.sport+':'+game.id);
 st.textContent=cached?'Verified ESPN team schedule response · '+cached.verifiedAt:'Last 5/10 unavailable until requested · no assumptions';
 root.textContent=cached?formatDailyForm(cached):'';
};
const loadSelectedDailyForm=async()=>{
 const game=dailyGames[dailySelected],day=currentSlate?.dateEastern;
 if(!game||!day||!token)return null;
 const key=day+':'+game.sport+':'+game.id;
 if(dailyFormCache.has(key)){displayDailyForm();return dailyFormCache.get(key)}
 el('daily-game-form-status').textContent='Checking ESPN completed-game team schedules…';
 el('daily-game-form-load').disabled=true;
 try{
  const r=await fetch('/api/game-form?'+new URLSearchParams({date:day,sport:game.sport,gameId:game.id}),{headers:{'x-boardroom-password':token},cache:'no-store'});
  const v=await r.json();if(!r.ok)throw Error(v.error||'ESPN schedule error');
  dailyFormCache.set(key,v);dailyFormReviewed.add(key);
  if(dailyGames[dailySelected]?.id===game.id)displayDailyForm();
  setDailyConsensus();return v
 }catch(e){if(dailyGames[dailySelected]?.id===game.id){el('daily-game-form-status').textContent='Last 5/10 provider unavailable: '+e.message;el('daily-game-form-result').textContent='No form-based betting conclusions supported.'}return null}
 finally{el('daily-game-form-load').disabled=false}
};
el('daily-game-form-load').onclick=()=>void loadSelectedDailyForm();

const renderDailySelected=()=>{
 const root=el('daily-game-review');root.textContent='';
 if(!dailyGames.length){root.textContent='No listed games for this date, or the sports feeds failed. Choose another date or refresh.';setDailyConsensus();return}
 const g=dailyGames[dailySelected];if(!g){root.textContent='Game not selected';return}
 const teams=g.teams.map(x=>x.team+(x.score==null?'':' ('+x.score+')')+' ['+(x.homeAway||'')+']').join(' vs ');
 const dataAge=currentSlate?.retrievedAt||'unknown';
 root.textContent=[
  'GAME '+(dailySelected+1)+' OF '+dailyGames.length+' · '+g.sport,
  g.name||teams, 'New York time: '+g.startEastern, 'Game status: '+(g.shortStatus||g.status),
  'Teams / scores: '+(teams||'Not provided'),
  'ESPN retrieved: '+dataAge,
  'MONEYLINE: '+g.review.moneyline,
  'SPREAD: '+g.review.spread,
  'TOTAL O/U: '+g.review.total,
  'PLAYER PROPS: '+g.review.playerProps,
  'COMBOS (P/R/A etc.): '+g.review.combos,
  'PREGAME PREDICTION: Champion-001 probability not independently authenticated.',
  'DECISION: HOLD · Insufficient evidence for a certified bet.'
 ].join('\\n');
 for(const b of el('daily-slate-games').querySelectorAll('[data-daily-index]'))b.classList.toggle('selected',Number(b.dataset.dailyIndex)===dailySelected);
 displayDailyForm();clearQuoteOnGameChange();setDailyConsensus()
};
const renderDailyGames=()=>{
 const box=el('daily-slate-games');box.replaceChildren();
 if(!currentSlate)return;
 if(!dailyGames.length){box.textContent='No events returned for this date. Results depend on provider schedule coverage.';return}
 const bySport=new Map();
 dailyGames.forEach((g,i)=>{if(!bySport.has(g.sport))bySport.set(g.sport,[]);bySport.get(g.sport).push({g,i})});
 for(const sport of ['NBA','NFL','MLB','NHL','NCAAF','NCAAB','MLS','UCL']){
  const games=bySport.get(sport)||[];
  const name=document.createElement('div');name.className='league-name';name.textContent=sport+' · '+games.length+' scheduled/reported';box.appendChild(name);
  for(const {g,i} of games){
   const b=document.createElement('button');b.type='button';b.dataset.dailyIndex=String(i);
   b.textContent=(i+1)+'. '+escapeSlateText(g.name)+' · '+escapeSlateText(g.startEastern)+' · '+escapeSlateText(g.shortStatus||g.status);
   b.onclick=()=>{dailySelected=i;renderDailySelected()};
   box.appendChild(b);
  }
 }
};
const renderDailySlate=()=>{
 const d=currentSlate;if(!d)return;
 const count=d.sports.map(x=>x.sport+': '+x.games.length).join(' · ');
 el('daily-slate-counts').textContent='Eastern date '+d.dateEastern+' · '+d.gameCount+' games returned · '+d.leaguesReturned+'/8 leagues · '+count+' · Review status: '+dailyReviewed.size+' checked / '+d.gameCount+' · All uncertified markets HOLD';
 el('daily-slate-health').textContent='Updated '+d.retrievedAt+' · '+d.errors.length+' errors · '+(d.potentiallyIncomplete.length?'Provider may truncate: '+d.potentiallyIncomplete.join(', '):'No 500-game cap reached');
 renderDailyGames();renderDailySelected()
};
const loadDailySlate=async(silent=false)=>{
 if(!token)return;
 const requestDay=el('daily-slate-date').value||easternTodayClient();
 if(!silent)el('daily-slate-health').textContent='Loading every returned game from 8 league sources…';
 try{
  const r=await fetch('/api/daily-slate?date='+encodeURIComponent(requestDay),{headers:{'x-boardroom-password':token},cache:'no-store'});
  const v=await r.json();if(!r.ok)throw Error(v.error||'HTTP '+r.status);
  if(el('daily-slate-date').value!==requestDay)return;
  const oldSelection=dailyGames[dailySelected]?.id;
  const isNew=currentSlate?.dateEastern!==v.dateEastern;
  currentSlate=v;dailyGames=v.sports.flatMap(x=>x.games).sort((a,b)=>(Date.parse(a.startUTC)||0)-(Date.parse(b.startUTC)||0)||a.sport.localeCompare(b.sport));
  if(isNew)dailyReviewed=new Set();
  const sameIdx=dailyGames.findIndex(g=>g.id===oldSelection);
  dailySelected=sameIdx>=0?sameIdx:0;
  renderDailySlate();
  if(v.errors.length){el('daily-slate-health').textContent+=' · FEED WARNINGS: '+v.errors.map(x=>x.sport).join(', ')}
 }catch(e){el('daily-slate-health').textContent='Daily schedule fetch failed: '+e.message+' · existing data, if any, is not refreshed'}
};
const auditEntireDailySlate=async()=>{
 if(!currentSlate||dailyScanActive)return;
 dailyScanActive=true;el('daily-slate-review-all').disabled=true;
 try{
  let missingSchedule=0;
  for(let i=0;i<dailyGames.length;i++){
   const g=dailyGames[i];if(!g.startUTC||g.teams.length<2)missingSchedule++;
   dailyReviewed.add(g.sport+':'+g.id);
   if(i%6===0||i===dailyGames.length-1){
    el('daily-slate-health').textContent='Auditing every game · '+(i+1)+'/'+dailyGames.length+' · missing time/team fields: '+missingSchedule+' · betting markets HOLD';
    await new Promise(resolve=>setTimeout(resolve,0));
   }
  }
  el('daily-slate-counts').textContent+=' · Completed source completeness and market-readiness checks for all '+dailyGames.length+' returned games. Individual team-form and expert discussions require separate review. '+missingSchedule+' games have missing core schedule fields. Zero certified sportsbook selections.';
  setDailyConsensus();
 }finally{dailyScanActive=false;el('daily-slate-review-all').disabled=false}
};
const discussSelectedDailyGame=async()=>{
 if(!token){el('daily-slate-health').textContent='Sign in to join a conversation';return}
 const g=dailyGames[dailySelected];if(!g){el('daily-slate-health').textContent='No game selected';return}
 dailyReviewed.add(g.sport+':'+g.id);renderDailySelected();
 const form=await loadSelectedDailyForm();
 const formContext=form?JSON.stringify({fetchedAt:form.verifiedAt,source:form.source,teams:(form.teams||[]).map(t=>({team:t.team,status:t.status,last5Record:t.last5Record,last10Record:t.last10Record,last5:t.last5,error:t.error}))}).slice(0,3400):'Team form was unavailable; do not infer last 5/10 results.';
 const question='Freddy wants the full six-analyst panel to discuss one scheduled game: '+g.sport+' '+g.name+' (event '+g.id+'), '+g.startEastern+', verified ESPN status '+g.shortStatus+', teams/scores '+g.teams.map(x=>x.team+' '+(x.score??'N/A')).join(' vs ')+'. One analyst at a time: Bella coordination; David schedule, form and missing last-5/10; Cassidy strict price/probability/EV certification; Roger cautious moneyline, spread, total, props/combo/parlay review; Sarah correlation, bankroll and injuries; Adam source audit. Speak to Freddy like a friend, respond to one another naturally, and ask clarifying follow-ups where useful. Historical team form evidence (when available) from ESPN: '+formContext+'. These descriptive last-5/last-10 team results are not model win probabilities, player prop projections or injury status. We have NO verified DraftKings market prices or native Champion-001 probabilities. Do not invent a pick, a percentage or sportsbook quotation; HOLD until verifiable.';
 void startPanel(question)
};
const debateDailyParlay=async(legs)=>{
 if(!token||!currentSlate)return;
 await auditEntireDailySlate();
 const draft='Freddy requests the entire six-person boardroom to come together and reach ONE consensus for '+legs+' parlay legs from all '+dailyGames.length+' games on the '+currentSlate.dateEastern+' Eastern slate. Consider moneylines, spreads, totals, player points/rebounds/assists, combinations and correlated markets. Discuss each analyst’s independent role, challenged assumptions, market timing, injuries, line values and last 5/10 coverage. Current verified price count is 0 and certified Champion-001 EV count is 0. Consequently do not invent matchups, legs, market prices, probabilities or a winning parlay. The agreed outcome today is NO PLAY/HOLD unless a fully verified feed supplies the necessary independent evidence. Address Freddy conversationally and do not repeat generic disclaimers unnecessarily.';
 el('daily-consensus-status').textContent=legs+'-LEG PANEL MEETING STARTING · '+dailyGames.length+' schedule records audited · No supported wagers; certification HOLD';
 void startPanel(draft)
};
el('daily-slate-date').value=easternTodayClient();
el('daily-slate-today').onclick=()=>{dailyPinned=false;el('daily-slate-date').value=easternTodayClient();void loadDailySlate()};
el('daily-slate-date').onchange=()=>{dailyPinned=true;void loadDailySlate()};
el('daily-slate-refresh').onclick=()=>void loadDailySlate();
el('daily-slate-review-all').onclick=()=>void auditEntireDailySlate();
el('daily-game-previous').onclick=()=>{if(!dailyGames.length)return;dailySelected=(dailySelected+dailyGames.length-1)%dailyGames.length;renderDailySelected()};
el('daily-game-next').onclick=()=>{if(!dailyGames.length)return;dailySelected=(dailySelected+1)%dailyGames.length;renderDailySelected()};
el('daily-game-discuss').onclick=discussSelectedDailyGame;
el('daily-consensus-two').onclick=()=>void debateDailyParlay(2);
el('daily-consensus-five').onclick=()=>void debateDailyParlay(5);
const beginDailyRefresh=()=>{
 if(dailyRefreshTimer)return;
 dailyRefreshTimer=setInterval(()=>{
  if(!token||document.hidden)return;
  const today=easternTodayClient();
  if(!dailyPinned&&today!==el('daily-slate-date').value){el('daily-slate-date').value=today;dailyReviewed=new Set();currentSlate=null}
  void loadDailySlate(true)
 },300000)
};


let quoteObservedAt=null,quoteDisplayAt=null,latestQuoteAudit=null,lastQuoteGameKey='';
const quoteBox=el('quote-preflight-result'),quoteWhen=el('quote-timestamp');
el('quote-checked-now').onclick=()=>{
 const now=new Date();
 quoteDisplayAt=new Intl.DateTimeFormat('sv-SE',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(now).replace(' ','T');
 quoteWhen.value=quoteDisplayAt;quoteObservedAt=now.toISOString();
 quoteBox.textContent='Freddy, your self-reported Eastern observation time is recorded. This does not authenticate the sportsbook price.';
};
quoteWhen.oninput=()=>{if(quoteWhen.value!==quoteDisplayAt){quoteObservedAt=null;quoteDisplayAt=null}};
const clearQuoteOnGameChange=()=>{
 const g=dailyGames[dailySelected],key=g?g.sport+':'+g.id:'';
 if(key!==lastQuoteGameKey){lastQuoteGameKey=key;latestQuoteAudit=null;el('quote-discuss').disabled=true;quoteBox.textContent=g?'Selected '+g.name+' · Report a price to check break-even arithmetic and evidence gaps.':'Select a game before auditing a price.'}
};
el('quote-preflight').onclick=async()=>{
 if(!token){quoteBox.textContent='Sign in first';return}
 const g=dailyGames[dailySelected],market=el('quote-market').value,selection=el('quote-selection').value.trim(),odds=el('quote-odds').value.trim(),line=el('quote-line').value.trim(),opposite=el('quote-opposing-odds').value.trim();
 if(!g||!currentSlate){quoteBox.textContent='Select a scheduled game first';return}
 if(!selection||!odds||(market!=='moneyline'&&!line)){quoteBox.textContent='Enter a pick, quoted American price, and the line for non-moneyline markets.';return}
 const q={date:currentSlate.dateEastern,sport:g.sport,gameId:g.id,market,selection,americanOdds:Number(odds),observedAt:quoteDisplayAt===quoteWhen.value?quoteObservedAt:null};
 if(market!=='moneyline')q.line=Number(line);
 if(opposite)q.opposingOdds=Number(opposite);
 el('quote-preflight').disabled=true;el('quote-discuss').disabled=true;
 quoteBox.textContent='Checking the reported market against the verified fixture…';
 try{
  const resp=await fetch('/api/odds-preflight',{method:'POST',headers:{'content-type':'application/json','x-boardroom-password':token},body:JSON.stringify(q),cache:'no-store'});
  const d=await resp.json();if(!resp.ok)throw Error(d.reason||d.error||'Audit failed');
  latestQuoteAudit=d;
  const a=d.arithmetic;
  quoteBox.textContent=[
   'GAME: '+d.event.gameName+' · '+d.event.startEastern,
   'USER-REPORTED PICK: '+d.observation.selection+' · '+d.observation.market+' · '+a.americanOdds,
   'BREAK-EVEN: '+a.breakEvenPercent.toFixed(2)+'% (market arithmetic, NOT model probability)',
   'ILLUSTRATIVE NO-VIG: '+(a.pairedNoVigProbability==null?'not applicable / unverified':(a.pairedNoVigProbability*100).toFixed(2)+'% (unverified sides)'),
   'REPORTED AGE: '+(d.observation.ageSeconds??'unknown')+' seconds',
   'DRAFTKINGS CHECKOUT: UNVERIFIED',
   'CHAMPION-001 WIN PROBABILITY: UNAVAILABLE',
   'CERTIFIED SHARP EDGE / EV: UNAVAILABLE',
   'FINAL DECISION: HOLD · NO BET PROMOTED'
  ].join(String.fromCharCode(10));
  el('quote-discuss').disabled=false
 }catch(e){latestQuoteAudit=null;quoteBox.textContent='HOLD · '+String(e.message||e)}
 finally{el('quote-preflight').disabled=false}
};
el('quote-discuss').onclick=()=>{
 const d=latestQuoteAudit;if(!d||!token)return;
 const topic='Freddy wants all six of you to discuss his USER-REPORTED '+d.observation.market+' '+d.observation.selection+' in '+d.event.gameName+' at American odds '+d.arithmetic.americanOdds+'. Break-even is '+d.arithmetic.breakEvenPercent+'%, but this is not the Champion-001 prediction or a verified DraftKings checkout. Bella moderates, David reviews actual matchup form, Cassidy evaluates missing EV evidence, Roger considers parlay eligibility, Sarah reviews correlation and downside, and Adam audits sources. Talk naturally with Freddy and each other. The responsible outcome is HOLD / NO PLAY until independent certification.';
 void startPanel(topic)
};

const roomActionPrompts={
 NBA:'RUN NBA. Have all six analysts discuss todays authenticated NBA schedule, scores, model research and injuries when verified. Include moneyline, spreads, totals, points/rebounds/assists and last five/ten status. Do not invent DraftKings odds or probabilities; HOLD when unverified.',
 NFL:'RUN NFL. Have the six-person panel examine authenticated NFL games, scores and schedule; discuss model forward-research record and available player/game market evidence. Unverified props and Sharp Edge remain HOLD.',
 MLB:'RUN MLB. Review ESPN MLB games and standings when available, data source timestamps and model readiness. Do not invent odds or certified predictions.',
 NHL:'RUN NHL. Discuss verified NHL games, scoreboard and historical Elo forward-research sample, showing risks and missing line data. HOLD unverified EV.',
 NCAAF:'RUN NCAAF. Discuss the verified ESPN college football schedule, results and what source data is needed for a certified model prediction.',
 NCAAB:'RUN NCAAB. Discuss verified college basketball schedule, scores and research readiness, separating facts from projections.',
 MLS:'RUN MLS. Check the ESPN MLS soccer schedule and scores, clarify provider data coverage and avoid unverified probabilities.',
 UCL:'RUN UCL. Discuss verified UEFA Champions League schedule, results and readiness; hold unverified sportsbook markets.',
 'SHARP EDGE':'Run Sharp Edge with all six analysts. Require exact timestamped sportsbook price and independent model probability for EV. Show what is certified and put unverified selections on HOLD.',
 'PLAYER PROPS':'Run verified player props audit across sports, including points, rebounds, assists and combinations, last 5/10, injuries and exact prop price sources when available. HOLD for missing evidence.',
 PARLAYS:'Have Roger and all other analysts discuss parlay correlation, joint probabilities and exact-source market integrity. Do not fabricate independent win probabilities or label unverified legs best bets.',
 'LIVE DATA':'Have all six analysts check the real ESPN scoreboard feed first; discuss today’s verified games, game times and scores with source freshness. Distinguish ESPN data from DraftKings odds and certified model predictions.'
};
for(const button of document.querySelectorAll('[data-room-action]')){
 button.onclick=()=>{
  const topic=roomActionPrompts[button.dataset.roomAction];if(!topic)return;
  el('question').value=topic;
  if(!token){el('room-now-speaking').textContent='ENTER YOUR STUDIO PASSWORD TO START A GROUP CONVERSATION';return}
  el('room-now-speaking').textContent='STARTING '+button.dataset.roomAction+' · ALL SIX ANALYSTS';
  void startPanel(topic)
 }
}
el('room-start-conversation').onclick=()=>{void window.v10UnlockStudioSound?.();if(!token)return;const prompt=el('question').value.trim()||'Welcome to Freddy’s Picks AI V10 podcast room. All six analysts introduce yourselves. Discuss today’s verified sports schedule and latest dated research model status; HOLD unverifiable betting markets.';void startPanel(prompt)};
el('room-start-video').onclick=()=>{if(!token)return;void groupVideoStart.onclick()};el('room-host-mic').onclick=()=>{if(!token){el('room-now-speaking').textContent='SIGN IN TO USE YOUR MICROPHONE';return}el('room-voice-names').click();document.getElementById('podcast-room-scene')?.scrollIntoView({behavior:'smooth',block:'nearest'})};
groupVideoStart.onclick=async()=>{
 if(!token){el('roundtable-status').textContent='Enter your private studio password first.';return}
 if(podcastRecording||roundtableActive){el('roundtable-status').textContent='A meeting is already active. Stop & save the current video before starting another.';return}
 groupVideoStart.disabled=true;
 el('group-video-frame').hidden=false;
 let liveCapacity=1;try{liveCapacity=await window.v10ReadLiveCapacity?.()||1}catch{}try{const result=await window.v10StartLiveWall?.();const connected=result?.connected||0;el('live-capacity-on-stage').textContent='ANAM CAMERAS: '+connected+' / 6 live · provider allows '+liveCapacity+' at once';el('roundtable-status').textContent='Six-person podcast video starting · '+connected+' real Anam stream(s), '+(6-connected)+' original cast previews';}catch(e){el('roundtable-status').textContent='Live streams unavailable: '+e.message+' · All six original cast portraits remain visible'}
 const topic=el('question').value.trim()||'Welcome to the 914 Sports Podcast Studio. Introduce yourselves, then discuss current verified ESPN games, schedules and the latest dated V8 NBA, NFL and NHL forward-model research results. State research accuracy separately from real-money betting results. Keep DraftKings odds, props, Champion-001 native probabilities and uncertified Sharp Edge picks on HOLD.';
 await videoStart.onclick();
 if(!podcastRecording){groupVideoStart.disabled=false;el('roundtable-status').textContent='Group video could not begin. Check microphone permission and WebM recorder support.';return}
 el('group-video-frame').scrollIntoView({behavior:'smooth',block:'nearest'});
 try{await startPanel(topic)}finally{groupVideoStart.disabled=false}
};
groupVideoStop.onclick=()=>{
 stopPanel();
 if(podcastRecorder?.state==='recording')recordStop.click();
 else el('roundtable-status').textContent='No group video recording is active.';
 void window.v10StopLiveWall?.();
};
el('roundtable').onclick=()=>{void window.v10UnlockStudioSound?.();return startPanel(el('question').value.trim())};el('roundtable-reset').onclick=()=>{stopPanel();episodeHistory.length=0;podcastCaption='';podcastCaptionBy='';el('log').textContent='';el('question').value='';el('roundtable-status').textContent='New episode ready · previous discussion context cleared'};

/* Name-call voice mode. Chrome SpeechRecognition needs a user tap and microphone permission.
 * Handle one utterance at a time and pause recognition while a persona speaks to prevent feedback. */
let nameListening=false,nameRecognition=null,nameSpeaking=false,nameMicErrors=0,nameSessionId=0;
let lastAnalystAnswer=null;
const nameStatus=el('name-command-status'),nameStart=el('room-voice-names'),nameStop=el('room-voice-stop');
const namedPersonas=[
 ['adam stone','Adam Stone'],['cassidy','Cassidy'],['bella','Bella'],
 ['david','David'],['roger','Roger'],['sarah','Sarah'],['adam','Adam Stone']
];
const setNameStatus=message=>{nameStatus.textContent=message;el('room-now-speaking').textContent=message;const x=el('v10-live-label');if(x)x.textContent=message.slice(0,100)};
const resolveNameCommand=utterance=>{
 const text=String(utterance||'').trim().slice(0,600);
 const lower=text.toLowerCase();
 if(lower.includes('everyone')||lower.includes('everybody')||lower.includes('all six')||lower.includes('whole panel'))
  return {speaker:'ALL',question:text.replace(/everyone|everybody|all six|whole panel/ig,'').trim()};
 for(const [alias,speaker] of namedPersonas){
  const at=lower.indexOf(alias);if(at<0)continue;
  const left=at?lower[at-1]:' ',right=lower[at+alias.length]||' ';
  if(' abcdefghijklmnopqrstuvwxyz'.includes(left)&&left!==' '||'abcdefghijklmnopqrstuvwxyz'.includes(right))continue;
  let question=(text.slice(0,at)+' '+text.slice(at+alias.length)).trim();
  question=question.replace(/^(hey|hi|yo|hello|ask|talk to|can you|could you|please|go ahead|okay|ok)[,!? ]*/i,'').replace(/^[,.:!? ]+/,'').trim();
  return {speaker,question,goLive:lower.includes('go live')||lower.includes('live camera')}
 }
 return {speaker:null,question:text};
};
const answerOneName=async(speaker,question)=>{
 stopPanel();highlight(speaker);
 // One active Anam stream on Free; calling a new name closes the previous video first.
 let liveReady=false,liveFailure='';
 if(window.v10EnsureLiveCamera){
  try{liveReady=await window.v10EnsureLiveCamera(speaker)}
  catch(e){liveFailure=String(e.message||e).slice(0,140)}
 }
 const actualQuestion=question&&question.trim()?question.trim():'Freddy just called your name. Say hello Freddy, respond naturally like a real podcast teammate, and ask what sports matchup he wants to discuss. One or two short sentences.';
 const prompt='Freddy is talking directly to '+speaker+' in the shared six-person podcast studio. Please answer this spoken request naturally as '+speaker+', without a formal report. '+actualQuestion;
 setNameStatus(speaker+' is listening to Freddy…');
 if(!liveReady)window.v10SetPanelMode?.(true);
 controller=new AbortController();
 try{
  const response=await fetch('/api/converse',{method:'POST',headers:{'content-type':'application/json','x-boardroom-password':token},body:JSON.stringify({speaker,question:prompt}),signal:controller.signal});
  const data=await response.json();if(!response.ok)throw Error(data.category||data.error||'Analyst unavailable');
  say('Freddy: '+(question||speaker));say(speaker+': '+data.reply);lastAnalystAnswer={speaker,reply:data.reply};const summary=el('v10-recovery-status');if(summary)summary.textContent=speaker+' answered: '+String(data.reply).slice(0,240);
  el('room-transcript').textContent=speaker.toUpperCase()+': '+data.reply;
  podcastCaptionBy=speaker;podcastCaption=data.reply;
  setNameStatus('🎙️ '+speaker+' is speaking to Freddy');
  if(liveReady&&window.v10TalkLive){
   try{
    await window.v10TalkLive(speaker,data.reply);
    setNameStatus('📹 '+speaker+' live video replied · call another name to switch camera');
    return
   }catch(e){liveFailure=String(e.message||e).slice(0,140)}
  }
  window.v10SetPanelMode?.(true);
  await speakPanel(speaker,data.reply,controller.signal);
  setNameStatus(speaker+' finished · '+(liveFailure?'live video unavailable ('+liveFailure+'); voice fallback used':'call another name or ask a follow-up'))
 }catch(e){
  if(e.name!=='AbortError'){const message=speaker+' could not answer: '+String(e.message||e).slice(0,140);setNameStatus(message);const summary=el('v10-recovery-status');if(summary)summary.textContent=message}
 }finally{window.v10SetPanelMode?.(false)}
};
const runNameCommand=async spoken=>{
 if(!token){setNameStatus('Unlock your private podcast room first');return}
 const cmd=resolveNameCommand(spoken);
 if(!cmd.speaker){setNameStatus('Say Bella, David, Cassidy, Roger, Sarah, or Adam Stone.');return}
 if(cmd.speaker==='ALL'){
  const q=cmd.question||'Freddy is here in the podcast room. Each of the six analysts greet him briefly, then begin a natural sports conversation using the verified game schedule and model evidence.';
  setNameStatus('All six analysts are joining the podcast conversation…');
  await startPanel(q);
  return
 }
 if(cmd.goLive){
  highlight(cmd.speaker);
  setNameStatus('Connecting the live Anam camera for '+cmd.speaker+'…');
  if(window.v10EnsureLiveCamera)await window.v10EnsureLiveCamera(cmd.speaker);
  else setNameStatus('Anam video control has not finished loading; use the in-room camera button');
  return
 }
 await answerOneName(cmd.speaker,cmd.question)
};
window.v10SpeakToName=name=>runNameCommand(name);
window.v10RunVoiceCommand=runNameCommand;
const recoveryStatus=el('v10-recovery-status');
el('v10-enable-mic').onclick=()=>{
 void window.v10UnlockStudioSound?.();
 if(!token){recoveryStatus.textContent='Unlock your studio password first';return}
 if(nameListening){recoveryStatus.textContent='Voice listener is already enabled. Say Bella, David, Cassidy, Roger, Sarah or Adam Stone.';return}
 nameStart.click();recoveryStatus.textContent='Microphone start requested. Approve Chrome microphone permission if prompted.';
};
el('v10-test-persona').onclick=async()=>{
 void window.v10UnlockStudioSound?.();
 if(!token){recoveryStatus.textContent='Unlock the studio first';return}
 recoveryStatus.textContent='Testing Cassidy: requesting a short analyst reply…';
 const resumed=nameListening;
 if(resumed){nameSpeaking=true;endNameMic()}
 try{lastAnalystAnswer=null;await runNameCommand('Cassidy');recoveryStatus.textContent=lastAnalystAnswer?.speaker==='Cassidy'?'Cassidy replied: '+lastAnalystAnswer.reply.slice(0,220)+' · Tap Hear reply if audio is silent.':'No Cassidy AI response received. Check the on-screen error and retry once.'}
 catch(e){recoveryStatus.textContent='Cassidy test failed: '+String(e.message||e).slice(0,140)}
 finally{nameSpeaking=false;if(resumed&&nameListening)window.setTimeout(listenForName,600)}
};
el('v10-replay-reply').onclick=()=>{
 void window.v10UnlockStudioSound?.();
 if(!lastAnalystAnswer){recoveryStatus.textContent='No answer to replay. Tap Test Cassidy or call an analyst first.';return}
 recoveryStatus.textContent='Playing last answer with your phone speaker…';
 browserSpeak(lastAnalystAnswer.speaker,lastAnalystAnswer.reply);
};

window.v10HandsFreeStart=()=>{if(!token)return false;if(!nameListening){nameMicErrors=0;nameSessionId++;nameListening=true;updateMicUI();listenForName()}return nameListening};
window.v10HandsFreeStop=()=>{nameListening=false;nameSessionId++;endNameMic();updateMicUI()};
document.querySelectorAll('[data-v10-speaker]').forEach(b=>b.addEventListener('click',()=>{void runNameCommand(b.dataset.v10Speaker)}));
document.querySelectorAll('[data-v10-topic]').forEach(b=>b.addEventListener('click',()=>{const t=b.dataset.v10Topic;const x=[...document.querySelectorAll('[data-room-action]')].find(q=>q.dataset.roomAction===t);if(x)x.click();else void runNameCommand('Cassidy, discuss '+t+' based on verified information.')}));
const endNameMic=()=>{
 const mic=nameRecognition;nameRecognition=null;
 if(mic)try{mic.abort()}catch{}
};
const updateMicUI=()=>{
 nameStart.textContent=nameListening?'🎤 Hands-free listening':'🎤 Enable microphone';
 nameStop.disabled=!nameListening
};
const listenForName=()=>{
 if(!nameListening||nameSpeaking||nameRecognition||!token)return;
 const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!Recognition){nameListening=false;document.body.classList.add('v10-microphone-help');updateMicUI();setNameStatus('This browser does not support voice recognition. Use the Ask by name field or open in Chrome.');return}
 const recognizer=new Recognition();nameRecognition=recognizer;
 recognizer.lang='en-US';recognizer.continuous=false;recognizer.interimResults=false;recognizer.maxAlternatives=1;
 const session=nameSessionId;let handled=false;
 recognizer.onresult=event=>{
  if(!nameListening||session!==nameSessionId||handled)return;
  handled=true;nameSpeaking=true;
  const utterance=String(event.results?.[0]?.[0]?.transcript||'').trim();
  el('room-name-question').value=utterance;
  setNameStatus('Freddy said: '+utterance);
  Promise.resolve(runNameCommand(utterance)).catch(e=>setNameStatus('Name command failed: '+String(e.message||e))).finally(()=>{
   nameSpeaking=false;
   if(nameListening&&session===nameSessionId)window.setTimeout(listenForName,500)
  })
 };
 recognizer.onerror=event=>{
  if(session!==nameSessionId)return;
  const why=String(event.error||'unknown');
  if(why==='not-allowed'||why==='service-not-allowed'||why==='audio-capture'){
   nameListening=false;nameSessionId++;document.body.classList.add('v10-microphone-help');updateMicUI();setNameStatus('Microphone permission required. Tap Enable microphone once, or type an analyst name below.')
  }else if(why==='no-speech')setNameStatus('No voice detected. Speak close to your phone, or tap Ask by name.');
  else {nameMicErrors++;setNameStatus('Microphone: '+why+(nameMicErrors>2?' · Tap Voice Names to retry.':''));if(nameMicErrors>2){nameListening=false;updateMicUI()}}
 };
 recognizer.onend=()=>{
  if(nameRecognition===recognizer)nameRecognition=null;
  if(nameListening&&!nameSpeaking&&session===nameSessionId)window.setTimeout(listenForName,800)
 };
 try{recognizer.start();document.body.classList.remove('v10-microphone-help');setNameStatus('🎤 Listening · Say Bella, David, Cassidy, Roger, Sarah, Adam or Everybody')}
 catch(e){nameRecognition=null;nameListening=false;document.body.classList.add('v10-microphone-help');updateMicUI();setNameStatus('Chrome may need a microphone tap. Tap Enable microphone once: '+String(e.message||e))}
};
nameStart.onclick=()=>{
 if(!token){setNameStatus('Enter your studio password first');return}
 if((window.v10LiveCameraCount?.()||0)>0){setNameStatus('Live Anam microphone is on. Call an analyst name to switch chairs.');return}
 if(nameListening){nameListening=false;nameSessionId++;endNameMic();updateMicUI();setNameStatus('Voice-name listening paused');return}
 void window.v10UnlockStudioSound?.();
 document.body.classList.remove('v10-microphone-help');nameMicErrors=0;nameSessionId++;nameListening=true;updateMicUI();listenForName()
};
nameStop.onclick=()=>{nameListening=false;nameSessionId++;endNameMic();updateMicUI();setNameStatus('Voice-name mode stopped')};
el('room-name-send').onclick=()=>{
 const phrase=el('room-name-question').value.trim();
 if(!phrase){setNameStatus('Type a name or question first');return}
 void window.v10UnlockStudioSound?.();
 const wasListening=nameListening;
 if(wasListening){nameSpeaking=true;endNameMic()}
 void runNameCommand(phrase).finally(()=>{nameSpeaking=false;if(wasListening&&nameListening)window.setTimeout(listenForName,500)})
};
el('room-name-question').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();el('room-name-send').click()}};
el('room-everybody-talk').onclick=()=>{void window.v10UnlockStudioSound?.();void runNameCommand('Everybody, what verified games and model evidence should we discuss today?')};
updateMicUI();
window.v10HostMic=()=>{const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){el('roundtable-status').textContent='Browser speech recognition unavailable; type your topic';return}stopPanel();panelMic=new SR();panelMic.lang='en-US';panelMic.interimResults=false;panelMic.onresult=e=>{const q=e.results[0][0].transcript;el('question').value=q;el('roundtable-status').textContent='Host: '+q;void startPanel(q)};panelMic.onerror=e=>{if(e.error!=='aborted')el('roundtable-status').textContent='Microphone: '+e.error};panelMic.start();el('roundtable-status').textContent='Listening to host · speech interrupts current panel'};
el('mic').onclick=()=>{stopPanel();const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){say('Browser speech recognition unavailable');return}const sr=new SR();sr.lang='en-US';sr.onresult=e=>{el('question').value=e.results[0][0].transcript;el('ask').click()};sr.onerror=e=>say('Mic: '+e.error);sr.start()};

}catch(v10InitError){const diagnostic=document.getElementById('avatar-readiness');if(diagnostic)diagnostic.textContent='Studio initialization error: '+String(v10InitError&&v10InitError.message||v10InitError).slice(0,200);const status=document.getElementById('status');if(status)status.textContent='Studio script failed: '+String(v10InitError&&v10InitError.message||v10InitError).slice(0,140);window.v10RuntimeInitError=String(v10InitError&&v10InitError.message||v10InitError);console.error('V10_STUDIO_INIT_ERROR',v10InitError)}
</script><script type="module">


const liveNames=['Adam','Bella','David','Cassidy','Roger','Sarah'];
const wall=document.getElementById('live-wall-grid');
const active=new Map(),busy=new Set();
const showLiveMic=text=>{const node=document.getElementById('v10-live-mic-status');if(node)node.textContent=text};
const namedLiveCommand=text=>{
 const m=/^(?:(?:hey|hi|yo|hello|okay|ok|please|switch to|ask|talk to|go to)\\s+)*(adam stone|cassidy|bella|david|roger|sarah|adam)\\b[\\s,:!?-]*(.*)$/i.exec(String(text||'').trim());
 if(!m)return null;
 const name=m[1].toLowerCase();
 return {speaker:name.startsWith('adam')?'Adam':name[0].toUpperCase()+name.slice(1),question:m[2].trim()};
};
let sdkPromise=null,planLimit=1,connectingAll=false,focused='Adam',moderatedPanel=false;
const wallStatus=document.getElementById('live-wall-status'),
 startAll=document.getElementById('live-wall-start'),
 stopAll=document.getElementById('live-wall-stop'),
 roomStartAll=document.getElementById('room-start-live-all'),
 roomStopAll=document.getElementById('room-stop-live-all');
const memberLabel=n=>n==='Adam'?'Adam Stone':n;
// Stream onto the group image rather than the legacy portrait tiles further down the page.
const cinematic=document.getElementById('v10-cinematic');
const chairLayer=document.createElement('div');chairLayer.className='v10-chair-video-layer';chairLayer.id='v10-chair-video-layer';
const chairPositions={
 Bella:{left:'2%',top:'29%',width:'18%',height:'44%'},
 David:{left:'21%',top:'29%',width:'18%',height:'44%'},
 Cassidy:{left:'40%',top:'29%',width:'18%',height:'44%'},
 Roger:{left:'59%',top:'29%',width:'18%',height:'44%'},
 Sarah:{left:'79%',top:'15%',width:'20%',height:'30%'},
 Adam:{left:'79%',top:'45%',width:'20%',height:'31%'}
};
if(cinematic){cinematic.insertBefore(chairLayer,cinematic.querySelector('.v10-cinematic-hotspots'));for(const [name,position] of Object.entries(chairPositions)){const video=document.createElement('video');video.id='v10-chair-video-'+name;video.className='v10-chair-video';video.autoplay=true;video.muted=true;video.playsInline=true;video.setAttribute('playsinline','');video.setAttribute('aria-label',memberLabel(name)+' moving live video in group photo');Object.assign(video.style,position);chairLayer.appendChild(video)}}
const roomVideo=n=>document.getElementById('v10-chair-video-'+n)||document.getElementById('room-video-'+n);
const preview=n=>document.getElementById('live-preview-'+n);
const wallVideo=n=>document.getElementById('live-'+n);
const roomSeat=n=>document.querySelector('.person[data-person="'+memberLabel(n)+'"]');

const spotlight=document.getElementById('room-live-spotlight'),
 spotlightVideo=document.getElementById('room-spotlight-video'),
 spotlightPhoto=document.getElementById('room-spotlight-photo'),
 spotlightPerson=document.getElementById('room-spotlight-person'),
 spotlightState=document.getElementById('room-spotlight-state'),
 liveSoundButton=document.getElementById('room-spotlight-unmute'),
 liveSoundStatus=document.getElementById('room-live-audio-status'),
 liveVolumeInput=document.getElementById('room-live-volume'),
 liveVolumeValue=document.getElementById('room-live-volume-value');
let liveVolume=1.5,soundEnabled=false,spotlightHiddenByUser=false,liveAudioContext=null;
const liveBoostNodes=new Map();
const unlockLiveAudio=()=>{
 try{
  const Ctx=window.AudioContext||window.webkitAudioContext;
  if(!Ctx)return null;
  if(!liveAudioContext||liveAudioContext.state==='closed')liveAudioContext=new Ctx();
  void liveAudioContext.resume().catch(()=>{
   liveSoundStatus.textContent='Android paused live audio. Tap ENABLE LIVE AUDIO again to resume sound.'
  });
  return liveAudioContext
 }catch(e){return null}
};
const installLiveBoost=n=>{
 if(liveBoostNodes.has(n))return true;
 const v=roomVideo(n)||wallVideo(n);
 const audioTracks=v?.srcObject?.getAudioTracks?.()||[];
 if(!audioTracks.length||typeof MediaStream==='undefined')return false;
 const ctx=unlockLiveAudio();if(!ctx)return false;
 try{
  const audioStream=new MediaStream(audioTracks);
  const source=ctx.createMediaStreamSource(audioStream),gain=ctx.createGain(),limiter=ctx.createDynamicsCompressor();
  gain.gain.value=0;limiter.threshold.value=-17;limiter.knee.value=18;limiter.ratio.value=8;
  limiter.attack.value=0.004;limiter.release.value=0.18;
  source.connect(gain);gain.connect(limiter);limiter.connect(ctx.destination);
  liveBoostNodes.set(n,{source,gain,limiter});
  v.muted=true;return true
 }catch(e){liveSoundStatus.textContent='Live voice booster unavailable; browser will use normal speaker audio.';return false}
};
const stopLiveBoost=n=>{
 const nodes=liveBoostNodes.get(n);if(!nodes)return;
 try{nodes.gain.gain.value=0;nodes.source.disconnect();nodes.gain.disconnect();nodes.limiter.disconnect()}catch{}
 liveBoostNodes.delete(n)
};
const defaultPhoto=n=>'/api/cast-portrait?member='+encodeURIComponent(memberLabel(n));
const showBigFace=n=>{
 if(!active.has(n)||spotlightHiddenByUser)return;
 const source=roomVideo(n)||wallVideo(n);
 spotlight.hidden=false;
 spotlightPerson.textContent=memberLabel(n).toUpperCase();
 spotlightPhoto.alt=memberLabel(n)+' original cast portrait';
 spotlightPhoto.src=defaultPhoto(n);
 spotlightState.textContent='LIVE CAMERA CONNECTED · FULL-FACE VIEW';
 let stream=source?.srcObject||null;
 if(!stream&&source&&typeof source.captureStream==='function')try{stream=source.captureStream()}catch{}
 if(stream&&typeof stream.getVideoTracks==='function'&&stream.getVideoTracks().length){
  spotlightVideo.srcObject=stream;spotlightVideo.muted=true;spotlightVideo.volume=0;
  spotlightVideo.style.display='block';spotlightPhoto.style.display='none';
  void spotlightVideo.play().catch(()=>{
   spotlightVideo.style.display='none';spotlightPhoto.style.display='block';
   spotlightState.textContent='Live stream active in analyst seat; video enlargement blocked by browser'
  })
 }else{
  spotlightVideo.style.display='none';spotlightPhoto.style.display='block';
  spotlightState.textContent='Live session started · waiting for video frames'
 }
};
const hideBigFace=()=>{
 spotlight.hidden=true;spotlightVideo.pause();spotlightVideo.srcObject=null;
 spotlightVideo.style.display='none';spotlightPhoto.style.display='block'
};
const displayLiveSound=()=>{
 const video=roomVideo(focused)||wallVideo(focused);
 const isPlaying=!!active.has(focused);
 const hasAudio=!!video?.srcObject?.getAudioTracks?.().length;
 liveSoundButton.textContent=soundEnabled?'🔇 MUTE LIVE AUDIO':'🔊 ENABLE LIVE AUDIO';
 liveVolumeValue.textContent=Math.round(liveVolume*100)+'%';
 if(!isPlaying)liveSoundStatus.textContent='Start a live analyst, then use ENABLE LIVE AUDIO. Check your phone media volume and connected Bluetooth device.';
 else if(moderatedPanel)liveSoundStatus.textContent='Live Anam audio is temporarily muted during the six-person ElevenLabs roundtable to prevent overlapping voices.';
 else if(!soundEnabled)liveSoundStatus.textContent='Live video connected, sound muted. Tap ENABLE LIVE AUDIO to hear the analyst.';
 else if(!hasAudio)liveSoundStatus.textContent='Live video connected but its media element has no incoming audio track. Check Anam voice configuration and browser permissions.';
 else liveSoundStatus.textContent=memberLabel(focused)+(liveBoostNodes.has(focused)?' live audio boosted to ':' live audio at browser volume ')+Math.round(liveVolume*100)+'% · Raise Android media volume or check Bluetooth if still quiet.';
};
liveVolumeInput.oninput=()=>{
 liveVolume=Math.max(0,Math.min(2,Number(liveVolumeInput.value)/100));
 if(liveVolume===0)soundEnabled=false;
 else if(active.size)soundEnabled=true;
 adjustFocus();displayLiveSound()
};
liveSoundButton.onclick=()=>{
 void window.v10UnlockStudioSound?.();
 unlockLiveAudio();
 soundEnabled=!soundEnabled;
 const v=roomVideo(focused)||wallVideo(focused);
 if(v&&!liveBoostNodes.has(focused)){v.volume=Math.min(1,liveVolume);v.muted=!soundEnabled}
 adjustFocus();displayLiveSound()
};
document.getElementById('room-spotlight-close').onclick=()=>{
 spotlightHiddenByUser=true;hideBigFace()
};
document.getElementById('room-spotlight-fullscreen').onclick=async()=>{
 const node=document.getElementById('room-spotlight-stage');
 try{
  if(document.fullscreenElement){await document.exitFullscreen();return}
  if(node.requestFullscreen){await node.requestFullscreen();return}
  const v=spotlightVideo;if(typeof v.webkitEnterFullscreen==='function')v.webkitEnterFullscreen();
  else spotlightState.textContent='Use your phone landscape orientation for the largest video'
 }catch(e){spotlightState.textContent='Full screen unavailable here. Rotate your phone to landscape.'}
};

const captureLimit=()=>active.size+' of 6 cameras LIVE · Anam concurrency limit '+planLimit+(planLimit<6?' · Upgrade to 6+ for all simultaneous streams':'');
function updateCapacityUI(){
 const text=captureLimit()+(planLimit===1?' · Say Bella, David, Cassidy, Roger, Sarah, or Adam to switch the moving video.':'');
 wallStatus.textContent=text;
 const cap=document.getElementById('room-scene-capacity');
 if(cap)cap.textContent=text;
 stopAll.disabled=active.size===0;
 if(roomStopAll)roomStopAll.disabled=active.size===0;
 if(roomStartAll)roomStartAll.textContent=planLimit>=6?'📹 Start all six live cameras':planLimit===1?'📹 Start one live camera · call names to switch':'📹 Start '+planLimit+' live cameras';
}
function setLiveState(n,isLive,message){
 const seat=roomSeat(n);
 seat?.classList.toggle('live-video-active',isLive);
 const label=seat?.querySelector('.live');if(label)label.textContent=isLive?'● LIVE ANAM VIDEO':'● ORIGINAL CAST PREVIEW';
 const roomButton=seat?.querySelector('.room-avatar-live-toggle');
 if(roomButton){roomButton.textContent=isLive?'■ End live':'📹 Go live';roomButton.disabled=busy.has(n)}
 const roomStatus=document.getElementById('room-live-status-'+n);
 if(roomStatus)roomStatus.textContent=message||(isLive?'LIVE STREAMING':'PREVIEW · not streaming');
 const wallState=document.getElementById('live-status-'+n);if(wallState)wallState.textContent=message||(isLive?'LIVE · Anam video connected':'Portrait preview · not streaming');
 const wallButton=document.getElementById('live-toggle-'+n);
 if(wallButton){wallButton.textContent=isLive?'End live: '+n:'Go live: '+n;wallButton.disabled=busy.has(n)}
 const groupLabel=document.getElementById('v10-live-label'),onCamera=[...active.keys()][0];
 if(groupLabel)groupLabel.textContent=onCamera?'● '+memberLabel(onCamera).toUpperCase()+' LIVE · IN THE GROUP PHOTO':'● PRIVATE BOARDROOM · SAY AN ANALYST NAME';
 updateCapacityUI()
}
function adjustFocus(){
 for(const name of liveNames){
  const v=roomVideo(name)||wallVideo(name);
  if(v&&active.has(name)){
   const boost=liveBoostNodes.get(name);
   if(boost){
    boost.gain.gain.value=soundEnabled&&!moderatedPanel&&focused===name?liveVolume:0;
    v.muted=true
   }else{
    v.muted=!soundEnabled||moderatedPanel||focused!==name;
    v.volume=Math.min(1,liveVolume)
   }
   void v.play().catch(()=>{
    const st=document.getElementById('room-live-status-'+name);
    if(st&&focused===name)st.textContent='Connected but playback blocked · tap ENABLE LIVE AUDIO'
   })
  }
 }
 spotlightVideo.muted=true;
 displayLiveSound()
}
const focusLive=n=>{
 const key=n==='Adam Stone'?'Adam':n;
 if(!liveNames.includes(key))return;
 focused=key;
 if(active.has(key))showBigFace(key);
 adjustFocus()
};
window.v10FocusLiveAnalyst=focusLive;
window.v10SetPanelMode=on=>{moderatedPanel=!!on;adjustFocus()};
wall.innerHTML=liveNames.map(n=>'<div class="live-tile" data-analyst="'+n+'"><strong>'+memberLabel(n)+'</strong><div style="position:relative"><img id="live-preview-'+n+'" src="/api/cast-portrait?member='+encodeURIComponent(memberLabel(n))+'" alt="'+memberLabel(n)+' original preview" style="width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:8px"><video id="live-'+n+'" autoplay muted playsinline style="display:none"></video></div><p class="muted" id="live-status-'+n+'">Preview · not streaming</p><button type="button" id="live-toggle-'+n+'">Go live: '+n+'</button></div>').join('')+'<div class="live-tile"><strong>Freddy · Host</strong><div style="min-height:100px;display:grid;place-items:center;font-size:44px">🎙️</div><p class="muted">Host microphone · browser permission required</p></div>';
async function refreshCapacity(){
 const pass=window.__v10AnamPassword?.();if(!pass)throw Error('Unlock the studio first');
 const r=await fetch('/api/anam-concurrency',{headers:{'x-boardroom-password':pass},cache:'no-store'});
 const data=await r.json();if(!r.ok)throw Error(data.error||'Anam capacity unavailable');
 planLimit=Math.max(1,Math.min(6,Number(data.limit)||1));updateCapacityUI();return planLimit
}
/* Local microphone diagnostics. Invoked directly by a click before any network/session awaits
   so Chrome on Android can request user permission. Nothing is recorded or uploaded. */
let micPermissionPending=null;
const probeBrowserMic=async(measure=false)=>{
 if(!navigator.mediaDevices?.getUserMedia)throw Error('Microphone unavailable. Open the HTTPS boardroom in Android Chrome.');
 let stream=null,ctx=null;
 try{
  stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
  const track=stream.getAudioTracks()[0];
  if(!track||track.readyState!=='live'||!track.enabled)throw Error('No active microphone audio track was returned.');
  if(!measure)return {trackActive:true,level:null};
  const Audio=window.AudioContext||window.webkitAudioContext;
  if(!Audio)return {trackActive:true,level:null};
  ctx=new Audio();await ctx.resume();
  const source=ctx.createMediaStreamSource(stream),analyser=ctx.createAnalyser();analyser.fftSize=1024;source.connect(analyser);
  const bytes=new Uint8Array(analyser.fftSize);let peak=0;
  for(let i=0;i<24;i++){
   analyser.getByteTimeDomainData(bytes);
   let sum=0;for(let j=0;j<bytes.length;j++){const x=(bytes[j]-128)/128;sum+=x*x}
   peak=Math.max(peak,Math.sqrt(sum/bytes.length));
   await new Promise(resolve=>setTimeout(resolve,125));
  }
  return {trackActive:true,peakLevel:Math.round(peak*10000)/100,levelDetected:peak>=0.012};
 }finally{stream?.getTracks().forEach(track=>track.stop());if(ctx)void ctx.close().catch(()=>{})}
};
const ensureMicPermission=()=>{
 if(!micPermissionPending)micPermissionPending=probeBrowserMic(false).finally(()=>{micPermissionPending=null});
 return micPermissionPending
};
const micCheckButton=document.getElementById('v10-mic-test');
if(micCheckButton)micCheckButton.onclick=async()=>{
 if(micCheckButton.disabled)return;
 micCheckButton.disabled=true;showLiveMic('Checking microphone: speak out loud for three seconds. Browser audio stays on this device.');
 try{
  const result=await probeBrowserMic(true);
  showLiveMic(result.levelDetected===true
    ?'Microphone permission GRANTED and voice level detected ('+result.peakLevel+'%). Now start an Anam live camera and ask a question; this test does not prove Anam received it.'
    :result.levelDetected===false
    ?'Microphone permission GRANTED but little speech level detected. Raise your voice, unmute the phone microphone, and retry. Level test does not prove Anam received audio.'
    :'Microphone permission GRANTED with active audio track; level meter unavailable. Start an Anam camera and check Heard: transcript.');
 }catch(e){showLiveMic('Microphone BLOCKED: '+String(e.name||'error')+' · '+String(e.message||e).slice(0,140)+'. Allow microphone access for this site in Chrome, then retry.')}
 finally{micCheckButton.disabled=false}
};

async function connect(n){
 if(active.has(n))return true;
 if(busy.has(n))return false;
 if(active.size>=planLimit)throw Error('Anam permits '+planLimit+' concurrent stream(s); select another seat to switch.');
 const target=roomVideo(n)||wallVideo(n);
 if(!target)throw Error('Missing video element for '+n);
 busy.add(n);setLiveState(n,false,'Connecting to Anam video provider…');
 let client=null;
 try{
  const pass=window.__v10AnamPassword?.();if(!pass)throw Error('Enter your private studio password');
  const r=await fetch('/api/anam-session',{method:'POST',headers:{'content-type':'application/json','x-boardroom-password':pass},body:JSON.stringify({analyst:n})});
  const d=await r.json();if(!r.ok)throw Error((d.error||'Session refused')+(d.providerStatus?' · provider HTTP '+d.providerStatus:''));
  const sdk=await(sdkPromise||=import('https://esm.sh/@anam-ai/js-sdk@latest'));
  // The prior setting disabled all input microphone audio in Anam.
  client=sdk.createClient(d.sessionToken,{disableInputAudio:false});
  const heardIds=new Set();
  if(sdk.AnamEvent&&typeof client.addListener==='function'){
   client.addListener(sdk.AnamEvent.MIC_PERMISSION_PENDING,()=>showLiveMic('Allow Chrome microphone permission.'));
   client.addListener(sdk.AnamEvent.MIC_PERMISSION_GRANTED,()=>showLiveMic('Microphone permitted · connecting '+memberLabel(n)+'…'));
   client.addListener(sdk.AnamEvent.MIC_PERMISSION_DENIED,e=>showLiveMic('Microphone denied: '+String(e||'check Chrome site permissions').slice(0,100)));
   client.addListener(sdk.AnamEvent.INPUT_AUDIO_STREAM_STARTED,()=>showLiveMic('🎤 '+memberLabel(n)+' microphone active · speak naturally.'));
   client.addListener(sdk.AnamEvent.USER_SPEECH_STARTED,()=>showLiveMic('🎤 '+memberLabel(n)+' hears you speaking…'));
   client.addListener(sdk.AnamEvent.MESSAGE_HISTORY_UPDATED,messages=>{
    if(!Array.isArray(messages))return;
    const msg=messages[messages.length-1];
    if(msg?.role!=='user'||!msg.id||heardIds.has(msg.id))return;
    heardIds.add(msg.id);
    const spoken=String(msg.content||'').trim();
    showLiveMic('🎤 Heard: '+spoken.slice(0,120));
    const cmd=namedLiveCommand(spoken);
    if(!cmd||cmd.speaker===n)return;
    showLiveMic('Switching camera to '+memberLabel(cmd.speaker)+'…');
    void ensureLiveCamera(cmd.speaker).then(()=>{
     const next=active.get(cmd.speaker);
     const question=cmd.question.replace(/^(?:go live|live camera|come live|join live)[.!? ]*/i,'').trim();
     if(question&&next&&typeof next.sendUserMessage==='function')next.sendUserMessage(question);
    }).catch(e=>showLiveMic('Switch failed: '+String(e?.message||e).slice(0,120)));
   });
  }
  // Avoid competing browser SpeechRecognition and Anam microphone capture on Android.
  window.v10HandsFreeStop?.();
  target.muted=true;
  await client.streamToVideoElement(target.id);
  if(typeof client.setInputAudioEnabled==='function')await client.setInputAudioEnabled(true);
  else if(typeof client.unmuteInputAudio==='function')await client.unmuteInputAudio();
  const mic=typeof client.getInputAudioState==='function'?client.getInputAudioState():null;
  if(mic?.permissionState==='denied')showLiveMic('Mic permission denied · allow access in Chrome, then reconnect.');
  else if(mic?.isMuted)showLiveMic('Anam mic muted · reconnect to retry.');
  else showLiveMic('🎤 '+memberLabel(n)+' audio track '+(mic?.permissionState==='granted'?'permission granted':'status unknown')+' · speak now; wait for a Heard: confirmation to verify recognition.');
  installLiveBoost(n);
  active.set(n,client);
  target.style.display='block';
  const wv=wallVideo(n),pv=preview(n);
  if(wv&&target!==wv){
   let mirrored=target.srcObject;
   if(!mirrored&&typeof target.captureStream==='function')try{mirrored=target.captureStream()}catch{}
   if(mirrored){wv.srcObject=mirrored;wv.muted=true;wv.style.display='block';if(pv)pv.style.display='none';void wv.play().catch(()=>{})}
  }else if(pv)pv.style.display='none';
  busy.delete(n);setLiveState(n,true,'LIVE · original '+memberLabel(n)+' avatar');
  if(active.size===1)focused=n;
  spotlightHiddenByUser=false;if(focused===n)showBigFace(n);adjustFocus();return true
 }catch(e){
  if(client)try{await client.stopStreaming()}catch{}
  busy.delete(n);active.delete(n);
  showLiveMic('Camera or microphone failed: '+String(e?.message||e).slice(0,120));
  target.srcObject=null;target.style.display='none';
  setLiveState(n,false,'Camera unavailable: '+String(e.message||e));
  throw e
 }
}
async function disconnect(n){
 if(busy.has(n))return;
 busy.add(n);
 const client=active.get(n);active.delete(n);
 stopLiveBoost(n);
 try{await client?.stopStreaming()}catch{}
 for(const video of [roomVideo(n),wallVideo(n)]){
  if(video){try{video.pause()}catch{}video.srcObject=null;video.style.display='none'}
 }
 if(preview(n))preview(n).style.display='block';
 if(!active.size)showLiveMic('Microphone disconnected · select a chair to talk.');
 busy.delete(n);setLiveState(n,false,'PREVIEW · live session ended');
 if(focused===n){focused=active.keys().next().value||'Adam'}
 if(active.size)showBigFace(focused);else hideBigFace();adjustFocus()
}
async function toggleMember(n){
 if(busy.has(n))return;
 soundEnabled=liveVolume>0;unlockLiveAudio();void window.v10UnlockStudioSound?.();
 const button=roomSeat(n)?.querySelector('.room-avatar-live-toggle');
 if(button)button.disabled=true;
 try{
  if(active.has(n)){
   // Serialize manual stop with pending name-triggered camera transitions.
   const stopTask=liveSwitchQueue.then(async()=>{if(active.has(n))await disconnect(n)});
   liveSwitchQueue=stopTask.catch(()=>{});await stopTask;
  }else await ensureLiveCamera(n);
 }catch(e){setLiveState(n,false,'Unable to connect: '+String(e.message||e))}
 finally{if(button)button.disabled=false;updateCapacityUI()}
}
const rebindSeats=()=>{for(const n of liveNames){const rb=roomSeat(n)?.querySelector('.room-avatar-live-toggle');if(rb)rb.onclick=e=>{e.stopPropagation();soundEnabled=liveVolume>0;void toggleMember(n)};if(active.has(n))setLiveState(n,true,'LIVE · '+memberLabel(n)+' camera')}};
for(const n of liveNames){const wb=document.getElementById('live-toggle-'+n);if(wb)wb.onclick=()=>{soundEnabled=liveVolume>0;void toggleMember(n)}}
window.v10RebindLiveSeatControls=rebindSeats;rebindSeats();
// Serialize automatic swaps so repeated voice commands never consume multiple slots.
let liveSwitchQueue=Promise.resolve();
const ensureLiveCamera=name=>{
 const n=name==='Adam Stone'?'Adam':name;
 if(!liveNames.includes(n))return Promise.reject(Error('Unknown analyst '+name));
 if(active.size===0)window.v10HandsFreeStop?.();
 const micReady=active.size===0?ensureMicPermission():Promise.resolve();
 const task=liveSwitchQueue.then(async()=>{
  await micReady;
  if(active.has(n)){focusLive(n);return true}
  await refreshCapacity();
  // One live session on Anam Free: close any previous stream before requesting a new one.
  for(const previous of [...active.keys()]){
   wallStatus.textContent='Switching camera from '+memberLabel(previous)+' to '+memberLabel(n)+'…';
   await disconnect(previous);
  }
  soundEnabled=liveVolume>0;unlockLiveAudio();
  for(let attempt=0;attempt<3;attempt++){
   try{await connect(n);focusLive(n);return true}
   catch(e){
    const transient=/provider HTTP 429|concurren|capacity|session limit/i.test(String(e?.message||e));
    if(!transient||attempt===2)throw e;
    wallStatus.textContent='Releasing the previous Anam camera before switching to '+memberLabel(n)+'…';
    await new Promise(resolve=>setTimeout(resolve,1000*(attempt+1)));
   }
  }
  return false
 });
 liveSwitchQueue=task.catch(()=>{});
 return task
};
window.v10EnsureLiveCamera=ensureLiveCamera;
// This recovery test exercises the moving chair, Anam video and lip-synced voice
// without requiring microphone recognition or an AI response.
const chairTestButton=document.getElementById('v10-chair-test-start');
const chairTestStatus=document.getElementById('v10-chair-test-status');
if(chairTestButton)chairTestButton.onclick=async()=>{
 const selected=document.getElementById('v10-chair-select')?.value||'Cassidy';
 chairTestButton.disabled=true;
 chairTestStatus.textContent='Connecting '+memberLabel(selected)+' in the group picture…';
 try{
  await ensureLiveCamera(selected);
  chairTestStatus.textContent=memberLabel(selected)+' live in the group picture. Checking spoken reply…';
  await window.v10TalkLive(selected,'Freddy, I am here at the sports boardroom table, and I am ready to talk.');
  chairTestStatus.textContent=memberLabel(selected)+' live in the group picture and voice test sent. If only a separate box moves, report that result.';
 }catch(e){
  chairTestStatus.textContent=memberLabel(selected)+' camera or speech failed: '+String(e?.message||e).slice(0,165);
 }finally{chairTestButton.disabled=false}
};
window.v10TalkLive=async(name,reply)=>{
 const n=name==='Adam Stone'?'Adam':name;
 const client=active.get(n);
 if(!client||typeof client.talk!=='function'||(typeof client.isStreaming==='function'&&!client.isStreaming()))throw Error('Live camera is not connected');
 soundEnabled=liveVolume>0;
 focusLive(n);
 adjustFocus();
 await client.talk(String(reply||'').slice(0,4000));
 return true
};
async function startAvailable(){
 if(connectingAll)return {limit:planLimit,connected:active.size};
 connectingAll=true;startAll.disabled=true;if(roomStartAll)roomStartAll.disabled=true;
 const permission=active.size===0?ensureMicPermission():Promise.resolve();
 try{
  await permission;
  await refreshCapacity();
  for(const name of liveNames){
   if(active.size>=planLimit)break;
   if(active.has(name))continue;
   try{await connect(name)}catch(e){setLiveState(name,false,'Unavailable: '+String(e.message||e));break}
  }
  return {limit:planLimit,connected:active.size}
 }catch(e){wallStatus.textContent='Unable to start live cameras: '+String(e.message||e);return {limit:planLimit,connected:active.size,error:String(e.message||e)}}
 finally{connectingAll=false;startAll.disabled=false;if(roomStartAll)roomStartAll.disabled=false;updateCapacityUI()}
}
async function stopAllCameras(){for(const name of liveNames)if(active.has(name))await disconnect(name);updateCapacityUI()}
window.v10StartLiveWall=startAvailable;window.v10StopLiveWall=stopAllCameras;
window.v10ReadLiveCapacity=refreshCapacity;
window.v10ActivateLiveCamera=toggleMember;window.v10LiveCameraCount=()=>active.size;
startAll.onclick=()=>{soundEnabled=liveVolume>0;unlockLiveAudio();void startAvailable()};stopAll.onclick=()=>void stopAllCameras();
if(roomStartAll)roomStartAll.onclick=()=>{soundEnabled=liveVolume>0;unlockLiveAudio();void window.v10UnlockStudioSound?.();void startAvailable()};
if(roomStopAll)roomStopAll.onclick=()=>void stopAllCameras();
document.getElementById('live-host-mic').onclick=()=>window.v10HostMic?.();
updateCapacityUI();displayLiveSound();
window.addEventListener('pagehide',()=>{for(const client of active.values())void client.stopStreaming()});
</script><script type="module">
const start=document.getElementById('adam-live-start'),stop=document.getElementById('adam-live-stop'),status=document.getElementById('adam-live-status');
start.addEventListener('click',async()=>{
 start.disabled=true;status.textContent='Switching the shared boardroom camera…';
 try{
  const selected=document.getElementById('anam-analyst').value;
  if(!window.v10EnsureLiveCamera)throw Error('Camera controls have not loaded');
  await window.v10EnsureLiveCamera(selected);
  status.textContent=(selected==='Adam'?'Adam Stone':selected)+' live in the main boardroom · spoken names switch the same camera';
  stop.disabled=false
 }catch(e){status.textContent='Live camera unavailable: '+String(e.message||e).slice(0,135)}
 finally{start.disabled=false}
});
stop.addEventListener('click',async()=>{
 stop.disabled=true;await window.v10StopLiveWall?.();status.textContent='Shared live camera ended'
});
</script><script>
(function(){
 'use strict';
 const bar=document.getElementById('v10-app-update');
 const message=document.getElementById('v10-app-update-text');
 const button=document.getElementById('v10-app-refresh');
 const current=document.querySelector('meta[name="v10-app-version"]')?.getAttribute('content')||'';
 let newer='',lastError='',checking=false;
 const show=(msg,allowRefresh)=>{
  if(!bar||!message||!button)return;
  bar.hidden=false;message.textContent=msg;button.hidden=!allowRefresh
 };
 const clear=()=>{if(bar)bar.hidden=true};
 const reload=()=>window.location.reload();
 if(button)button.addEventListener('click',reload);
 function inUse(){
  // The user should never lose an active podcast or switch because of an update.
  return (window.v10LiveCameraCount?.()||0)>0 ||
   window.v10IsRecording?.()===true ||
   window.v10IsVoiceConversationActive?.()===true ||
   !!document.querySelector('input:focus,textarea:focus');
 }
 async function check(){
  if(checking||document.hidden)return;
  checking=true;
  try{
   const response=await fetch('/api/app-version',{cache:'no-store',signal:(typeof AbortSignal.timeout==='function'?AbortSignal.timeout(6500):undefined)});
   if(!response.ok)throw Error('Server status '+response.status);
   const data=await response.json();
   if(typeof data.version!=='string'||!data.version)throw Error('Version missing');
   lastError='';
   if(current&&data.version!==current)newer=data.version;
   if(newer){
    show(inUse()?'Update available. Finish your live conversation or recording, then tap Refresh app.':'A new V10 update is available. Tap Refresh app to install the latest boardroom changes.',true)
   }else clear();
  }catch(e){
   lastError=String(e?.message||e).slice(0,80);
   if(newer)show('Update ready, but the network is unstable. Refresh after your conversation.',true);
   else show(navigator.onLine===false?'Offline: live analysts require an internet connection. The app will recheck when you reconnect.':'Boardroom connection is interrupted. Checking again automatically; you can refresh when ready.',true)
  }finally{checking=false}
 }
 window.addEventListener('online',()=>{void check()});
 window.addEventListener('offline',()=>show('Offline: live camera and sports-data requests require internet. The app will retry after reconnecting.',false));
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)void check()});
 setInterval(()=>{void check()},60000);
 if(navigator.onLine===false)show('Offline: reconnect to access live studio features.',false);
 else void check();
})();
</script></body></html>`;
const bootMarker="const btn=document.getElementById('unlock'),input=document.getElementById('pass'),status=document.getElementById('status');let busy=false;";
const mainScriptTag=[...html.matchAll(/<script>[\s\S]*?<\/script>/g)].map(m=>m[0]).find(t=>t.includes('window.v10CompleteUnlock=async'));if(!mainScriptTag)throw Error('V10 main script not found');const mainScriptSource=mainScriptTag.slice('<script>'.length,-'</script>'.length);new Script(mainScriptSource,{filename:'studio-runtime.js'});const pageHtml=html.replace('</head>','<meta name="v10-app-version" content="'+appVersion+'"></head>'); // HTML and API expose the same deployed revision; browsers fetch fresh HTML on open.
const server=http.createServer(async(req,res)=>{const pathname=new URL(req.url||'/', 'http://localhost').pathname;console.log('V10_REQUEST',req.method,pathname);if(req.method==='GET'&&pathname==='/studio-runtime.js'){res.writeHead(200,{'content-type':'application/javascript; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'});return res.end(mainScriptSource)}
if(req.method==='GET'&&pathname==='/manifest.webmanifest')return respond(res,200,{name:"Freddy's Picks AI V10 · Sports Podcast Room",short_name:"Freddy's V10",description:"Private six-person sports analysis and voice podcast studio",start_url:"/",scope:"/",display:"standalone",background_color:"#050d1e",theme_color:"#0b1732",icons:[{src:"/app-icon.svg",sizes:"any",type:"image/svg+xml",purpose:"any"}]}, {'content-type':'application/manifest+json'});
if(req.method==='GET'&&pathname==='/app-icon.svg'){res.writeHead(200,{'content-type':'image/svg+xml','cache-control':'public, max-age=86400','x-content-type-options':'nosniff'});return res.end('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192"><rect width="192" height="192" rx="36" fill="#071b38"/><circle cx="96" cy="85" r="67" fill="#184e85" stroke="#d6ac6b" stroke-width="7"/><text x="96" y="99" fill="#fff" font-size="54" font-weight="900" text-anchor="middle" font-family="Arial,sans-serif">V10</text><text x="96" y="162" fill="#ffca83" font-size="18" font-weight="bold" text-anchor="middle" font-family="Arial,sans-serif">FREDDY</text></svg>')}
if(req.method==='GET'&&pathname==='/api/app-version')return respond(res,200,{version:appVersion,service:'v10-voice-boardroom',updatePolicy:'Reload when idle; never restart an active video or recording automatically.'});
if(req.method==='GET'&&pathname==='/healthz')return respond(res,200,{online:true,service:'v10-voice-boardroom',version:appVersion});if(req.method==='GET'&&pathname==='/favicon.ico'){res.writeHead(204,{'cache-control':'public, max-age=86400'});return res.end()}if(req.method==='GET'&&pathname==='/connection-check'){res.writeHead(200,{'content-type':'text/html; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff'});return res.end('<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V10 Connection Check</title><body style="font:18px system-ui;background:#0d1930;color:white;padding:24px;max-width:650px;margin:auto"><h1>Freddy&#39;s V10 is reachable</h1><p>Your browser reached the Railway studio server successfully. This page does not require your password.</p><p><a style="color:#ffca76" href="/">Open the private podcast studio</a></p><p>If the studio fails after this page opens, the issue is likely within the main page or its browser compatibility.</p></body></html>')};if((pathname==='/'||pathname==='/index.html')&&req.method==='GET'){res.writeHead(200,{'content-type':'text/html; charset=utf-8','x-v10-app':'podcast-studio','cache-control':'no-store','content-security-policy':"default-src 'self'; script-src 'self' 'unsafe-inline' https://esm.sh; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://lab.anam.ai https://d2ol7oe51mr4n9.cloudfront.net; connect-src 'self' https: wss:; media-src 'self' blob:"});return res.end(pageHtml)}
if((req.method==='GET'||req.method==='POST')&&pathname==='/api/public-live-scores'){const feed=await loadPublicScoreboards();console.log('V10_LIVE_SCORE_REQUEST',JSON.stringify({method:req.method,leagues:feed.items.length,errors:feed.errors.length,at:new Date(feed.at).toISOString(),eventCount:feed.items.reduce((n,x)=>n+x.events.length,0)}));const sports=feed.items.map(x=>({sport:x.sport,events:x.events.slice(0,12).map(e=>({name:e.name,date:e.date,status:e.status,shortStatus:e.shortStatus,competitors:e.competitors}))}));return respond(res,200,{source:'ESPN public scoreboard',retrievedAt:new Date(feed.at).toISOString(),available:feed.items.length>0,leaguesResponding:feed.items.length,leagueErrors:feed.errors,sports,oddsAvailable:false,injuryFeedAvailable:false,championModelProbabilityAvailable:false,certifiedPicks:0,limit:'Game scores/schedules only. No authenticated sportsbook odds, player props, injuries or independently verified model probabilities.'})}
if(req.method==='GET'&&pathname==='/api/cast-portrait'){const name=new URL(req.url,'http://localhost').searchParams.get('member')||'';const id=castPortraitIds[name];if(!id)return respond(res,404,{error:'UNKNOWN_CAST_MEMBER'});try{let upstream=await fetch('https://lab.anam.ai/api/avatars/'+id+'/image/landscape',{signal:AbortSignal.timeout(8500)});let mime=upstream.headers.get('content-type')||'';if(!upstream.ok||!/^image\/(png|jpeg|webp)/.test(mime)){upstream=await fetch(castPortraitSources[name],{signal:AbortSignal.timeout(8500)});mime=upstream.headers.get('content-type')||'';}if(!upstream.ok||!/^image\/(png|webp|jpeg)/.test(mime))return respond(res,502,{error:'CAST_PORTRAIT_NOT_AVAILABLE'});const bytes=Buffer.from(await upstream.arrayBuffer());if(bytes.length>4000000)return respond(res,502,{error:'CAST_PORTRAIT_TOO_LARGE'});res.writeHead(200,{'content-type':mime,'cache-control':'public, max-age=1800','x-content-type-options':'nosniff'});return res.end(bytes)}catch(e){console.warn('V10_CAST_PORTRAIT',name,String(e.message||e).slice(0,100));return respond(res,502,{error:'CAST_PORTRAIT_FETCH_FAILED'})}}

if(req.method==='GET'&&pathname==='/api/public-data-health')return respond(res,200,continuousFeedStatus());
if(req.method==='GET'&&pathname==='/api/public-source-readiness')return respond(res,200,await refreshV10Sources());
if(req.method==='GET'&&pathname==='/api/public-model-research'){const report=await modelBoardFor();return respond(res,200,report)}
if(req.method==='GET'&&pathname==='/api/public-daily-slate-summary'){
 try{
  const board=await dailySlateLoad();
  return respond(res,200,{dateEastern:board.dateEastern,timezone:board.timezone,retrievedAt:board.retrievedAt,source:board.source,
   gameCount:board.gameCount,leaguesReturned:board.leaguesReturned,errors:board.errors,potentiallyIncomplete:board.potentiallyIncomplete,
   sports:board.sports.map(row=>({sport:row.sport,count:row.games.length,games:row.games.map(g=>({id:g.id,name:g.name,time:g.startEastern,status:g.shortStatus||g.status,score:g.teams.map(t=>({team:t.team,score:t.score}))}))})),
   marketEvidence:{independentlyCertifiedChampion001Predictions:0,authenticatedSportsbookPrices:0,verifiedPlayerPropPrices:0,verifiedTotalsAndSpreads:0,correlatedComboProbabilities:0},
   twoLegConsensus:'NO PLAY / HOLD',fiveLegConsensus:'NO PLAY / HOLD',
   instructions:'Debate all listed games one by one and discuss data needs. Public ESPN schedules do not certify betting odds, expected value, sportsbook best bets or 2/5 leg parlays.'})
 }catch(e){return respond(res,502,{error:'DAILY_SLATE_UNAVAILABLE',message:String(e.message||e).slice(0,130)})}
}
if(req.method==='GET'&&pathname==='/api/public-daily-slate'){const requested=new URL(req.url,'http://localhost').searchParams.get('date')||easternDate();if(requested!==easternDate())return respond(res,400,{error:'ONLY_TODAY_PUBLIC_TOOL_SUPPORTED'});try{const board=await dailySlateLoad(requested);return respond(res,200,board)}catch(e){return respond(res,502,{error:'DAILY_SLATE_FETCH_FAILED',message:String(e.message||e).slice(0,130)})}}
if(!compare(String(req.headers['x-boardroom-password']||''),password))return respond(res,401,{error:'UNAUTHORIZED'});
if(req.url==='/api/anam/session-token'&&req.method==='POST'){if(!process.env.ANAM_API_KEY||!process.env.ANAM_ADAM_PERSONA_ID)return respond(res,503,{error:'ANAM_NOT_CONFIGURED'});try{const upstream=await fetch('https://api.anam.ai/v1/auth/session-token',{method:'POST',headers:{authorization:'Bearer '+process.env.ANAM_API_KEY,'content-type':'application/json'},body:JSON.stringify({personaConfig:{personaId:process.env.ANAM_ADAM_PERSONA_ID}})});if(!upstream.ok){let detail={};try{const raw=await upstream.text();const parsed=JSON.parse(raw);detail={code:String(parsed?.error?.code||parsed?.code||''),message:String(parsed?.error?.message||parsed?.message||'').slice(0,160)}}catch{}console.error('ANAM_SESSION_PROVIDER_FAILURE',JSON.stringify({status:upstream.status,code:detail.code,message:detail.message}));return respond(res,502,{error:'ANAM_SESSION_UNAVAILABLE',providerStatus:upstream.status,providerCode:detail.code||undefined})}const data=await upstream.json();if(!data.sessionToken)return respond(res,502,{error:'ANAM_SESSION_TOKEN_MISSING'});return respond(res,200,{sessionToken:data.sessionToken})}catch{return respond(res,502,{error:'ANAM_NETWORK_ERROR'})}}
if(req.url==='/api/avatar-provider'&&req.method==='GET')return respond(res,200,{provider:'LiveAvatar',anamReady:!!(process.env.ANAM_API_KEY&&process.env.ANAM_ADAM_PERSONA_ID),mode:'LITE',configured:!!process.env.LIVEAVATAR_API_KEY,streamingEnabled:false,avatarIdsConfigured:Object.fromEntries(Object.keys(people).map(n=>[n,!!process.env['LIVEAVATAR_AVATAR_'+n.toUpperCase().replace(/[^A-Z0-9]/g,'_')]])),reason:'Real-time streaming requires provider credentials, six approved avatar IDs, and client WebRTC integration'});
if(req.url==='/api/anam-session'&&req.method==='POST'){const request=await body(req).catch(()=>({}));const analyst=typeof request.analyst==='string'?request.analyst:'Adam';if(!Object.hasOwn(anamPersonaIds,analyst))return respond(res,400,{error:'UNKNOWN_ANALYST'});const selectedPersonaId=anamPersonaIds[analyst];if(!process.env.ANAM_API_KEY||!selectedPersonaId)return respond(res,503,{error:'ANAM_NOT_CONFIGURED'});try{const a=await fetch('https://api.anam.ai/v1/auth/session-token',{method:'POST',headers:{'authorization':'Bearer '+process.env.ANAM_API_KEY,'content-type':'application/json'},body:JSON.stringify({personaConfig:{personaId:selectedPersonaId}}),signal:AbortSignal.timeout(12000)});const j=await a.json().catch(()=>({}));if(!a.ok)return respond(res,502,{error:'ANAM_SESSION_FAILED',providerStatus:a.status});const sessionToken=j.sessionToken||j.session_token;if(!sessionToken)return respond(res,502,{error:'ANAM_TOKEN_MISSING'});return respond(res,200,{sessionToken})}catch{return respond(res,502,{error:'ANAM_UNREACHABLE'})}}


if(req.method==='POST'&&pathname==='/api/odds-preflight'){
 try{return respond(res,200,await auditOddsPreflight(await body(req)))}
 catch(e){return respond(res,400,{error:'ODDS_PREFLIGHT_REJECTED',reason:String(e.message||e).slice(0,180),decision:'HOLD'})}
}
if(req.method==='GET'&&pathname==='/api/game-form'){
 const q=new URL(req.url,'http://localhost').searchParams,date=q.searchParams.get('date')||easternDate(),sport=q.searchParams.get('sport')||'',gameId=q.searchParams.get('gameId')||'';
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Object.hasOwn(scoreboardSources,sport)||!/^[0-9a-z_-]{1,36}$/i.test(gameId))return respond(res,400,{error:'INVALID_GAME_FORM_SCOPE'});
 try{return respond(res,200,await selectedGameForm(date,sport,gameId))}
 catch(e){return respond(res,502,{error:'FORM_FETCH_UNAVAILABLE',details:String(e.message||e).slice(0,140)})}
}
if(req.method==='GET'&&pathname==='/api/daily-slate'){const requested=new URL(req.url,'http://localhost').searchParams.get('date')||easternDate();if(!/^\d{4}-\d{2}-\d{2}$/.test(requested))return respond(res,400,{error:'INVALID_DATE'});if(Math.abs((Date.parse(requested+'T12:00:00Z')-Date.parse(easternDate()+'T12:00:00Z'))/86400000)>14)return respond(res,400,{error:'DATE_OUTSIDE_SUPPORTED_WINDOW'});try{return respond(res,200,await dailySlateLoad(requested))}catch(e){return respond(res,502,{error:'DAILY_SLATE_UNAVAILABLE',message:String(e.message||e).slice(0,130)})}}
if(req.method==='GET'&&pathname==='/api/model-research'){const report=await modelBoardFor();return respond(res,200,report)}
if(req.method==='GET'&&pathname==='/api/anam-concurrency'){
 if(!process.env.ANAM_API_KEY)return respond(res,503,{error:'ANAM_UNCONFIGURED'});
 try{
  const a=await apiAnam('GET','/sessions/concurrency');
  return respond(res,200,{provider:'Anam',limit:Number(a.limit)||1,active:Number(a.active)||0,canStartSession:!!a.canStartSession,
   allSixSimultaneousPossible:Number(a.limit)>=6,requiredSessionsForAllLive:6,note:'Anam concurrency is shared across your account. Session creation may still return 429.'});
 }catch(e){return respond(res,502,{error:'ANAM_CAPACITY_UNAVAILABLE',note:String(e.message||e).slice(0,120)})}
}
if(req.url==='/api/status'&&req.method==='GET')return respond(res,200,{online:true,aiConfigured:!!process.env.OPENAI_API_KEY,elevenLabsConfigured:!!process.env.ELEVENLABS_API_KEY,anamConfigured:!!(process.env.ANAM_API_KEY&&anamPersonaId),anamAnalysts:Object.fromEntries(Object.entries(anamPersonaIds).map(([name,id])=>[name,!!id])),sportsFeedConfigured:!!process.env.CERTIFIED_PICKS_FEED_URL,liveAnamScores:{status:liveScoreToolState.status,connectedAnalysts:liveScoreToolState.attached,errors:liveScoreToolState.errors},modelResearchTool:{status:modelToolState.status,connectedAnalysts:modelToolState.attached,errors:modelToolState.errors},dailySlateTool:{status:dailyAnamToolState.status,connectedAnalysts:dailyAnamToolState.attached,errors:dailyAnamToolState.errors},sourceReadinessTool:{status:sourceAnamToolState.status,connectedAnalysts:sourceAnamToolState.attached,errors:sourceAnamToolState.errors},participants:Object.keys(people)});
try{if(req.url==='/api/research-push'&&req.method==='POST'){const secret=process.env.RESEARCH_PUSH_SECRET;if(!secret||secret.length<32)return respond(res,503,{error:'RESEARCH_PUSH_NOT_CONFIGURED'});const chunks=[];let size=0;for await(const chunk of req){size+=chunk.length;if(size>32768)return respond(res,413,{error:'PAYLOAD_TOO_LARGE'});chunks.push(chunk)}const raw=Buffer.concat(chunks);const stamp=Number(req.headers['x-research-timestamp']);const signature=String(req.headers['x-research-signature']||'');if(!Number.isFinite(stamp)||Math.abs(Date.now()-stamp)>300000||!/^sha256=[a-f0-9]{64}$/.test(signature))return respond(res,401,{error:'INVALID_RESEARCH_SIGNATURE'});const expected='sha256='+createHmac('sha256',secret).update(String(stamp)+'.').update(raw).digest('hex');if(!compare(expected,signature))return respond(res,401,{error:'INVALID_RESEARCH_SIGNATURE'});let data;try{data=JSON.parse(raw.toString('utf8'))}catch{return respond(res,400,{error:'INVALID_JSON'})}if(data?.schemaVersion!==1||typeof data.runId!=='number'||typeof data.createdAt!=='string'||!Array.isArray(data.reports)||data.reports.length>25||data.reports.some(x=>typeof x.name!=='string'||typeof x.summary!=='string'||x.summary.length>2000))return respond(res,400,{error:'INVALID_RESEARCH_SCHEMA'});if(Date.parse(data.createdAt)>Date.now()+300000||Date.parse(data.createdAt)<Date.now()-86400000||!Number.isFinite(Date.parse(data.createdAt)))return respond(res,400,{error:'STALE_RESEARCH_REPORT'});globalThis.v10ResearchSnapshot={receivedAt:new Date().toISOString(),runId:data.runId,createdAt:data.createdAt,reports:data.reports.map(x=>({name:x.name.slice(0,120),summary:x.summary.slice(0,2000)})),certifiedPredictions:0,certified:false};return respond(res,200,{accepted:true,runId:data.runId,certifiedPredictions:0})}
if(req.url==='/api/data-health'&&req.method==='GET')return respond(res,200,continuousFeedStatus());
if(req.url==='/api/source-readiness'&&req.method==='GET')return respond(res,200,await refreshV10Sources());
if(req.url==='/api/analyst-knowledge'&&req.method==='GET')return respond(res,200,{model:'Freddys Picks AI V10',guide:v10ModelGuide,researchAvailable:!!globalThis.v10ResearchSnapshot,reportCount:globalThis.v10ResearchSnapshot?.reports?.length||0,researchCreatedAt:globalThis.v10ResearchSnapshot?.createdAt||null,certifiedPredictions:0,source:'V9/V10 methodology and signed V10 research bridge',note:'No live odds or verified Champion-001 probabilities without separately configured and validated feeds'});
if(req.url==='/api/live-scoreboards'&&req.method==='GET'){const data=await loadPublicScoreboards();return respond(res,200,{source:'ESPN public scoreboard',retrievedAt:new Date(data.at).toISOString(),sports:data.items,errors:data.errors,certified:false,oddsAvailable:false,note:'Live or scheduled scores and games only; no verified betting edge'})}
if(req.url==='/api/research-snapshot'&&req.method==='GET')return respond(res,200,{source:'GitHub Actions signed push',readOnly:true,certifiedPredictions:0,certified:false,snapshot:globalThis.v10ResearchSnapshot||null,note:'Ephemeral snapshot; HOLD for unverified predictions and odds'});
if(req.url==='/api/research-runs'&&req.method==='GET'){try{const headers={'accept':'application/vnd.github+json','user-agent':'freddys-v10-readonly','x-github-api-version':'2022-11-28'};if(process.env.GITHUB_READ_TOKEN)headers.authorization='Bearer '+process.env.GITHUB_READ_TOKEN;const upstream=await fetch('https://api.github.com/repos/frederickwalker66-cmyk/Freddy-s-sports-data/actions/runs?per_page=20',{headers,signal:AbortSignal.timeout(8000)});if(!upstream.ok)return respond(res,502,{error:'GITHUB_WORKFLOW_RUNS_UNAVAILABLE',providerStatus:upstream.status,tokenConfigured:!!process.env.GITHUB_READ_TOKEN});const j=await upstream.json();return respond(res,200,{source:'GitHub Actions',readOnly:true,certifiedPredictions:0,runs:(Array.isArray(j.workflow_runs)?j.workflow_runs:[]).map(r=>({id:r.id,name:r.name,branch:r.head_branch,status:r.status,conclusion:r.conclusion,createdAt:r.created_at,updatedAt:r.updated_at,url:r.html_url,certified:false})),note:'Workflow success is not proof of accurate predictions or certified EV'})}catch{return respond(res,502,{error:'GITHUB_WORKFLOW_RUNS_UNREACHABLE'})}}
if(req.url==='/api/research-artifacts'&&req.method==='GET'){try{const url='https://api.github.com/repos/frederickwalker66-cmyk/Freddy-s-sports-data/actions/artifacts?per_page=30';const headers={'accept':'application/vnd.github+json','user-agent':'freddys-v10-readonly','x-github-api-version':'2022-11-28'};if(process.env.GITHUB_READ_TOKEN)headers.authorization='Bearer '+process.env.GITHUB_READ_TOKEN;const response=await fetch(url,{headers,signal:AbortSignal.timeout(8000)});if(!response.ok)return respond(res,502,{error:'GITHUB_ARTIFACT_METADATA_UNAVAILABLE',providerStatus:response.status,tokenConfigured:!!process.env.GITHUB_READ_TOKEN});const data=await response.json();const artifacts=(Array.isArray(data.artifacts)?data.artifacts:[]).map(a=>({id:a.id,name:a.name,createdAt:a.created_at,updatedAt:a.updated_at,expiresAt:a.expires_at,expired:!!a.expired,sizeBytes:a.size_in_bytes,workflowRunId:a.workflow_run?.id,branch:a.workflow_run?.head_branch,source:'GitHub Actions artifact metadata',certified:false}));return respond(res,200,{source:'GitHub Actions',readOnly:true,certifiedPredictions:0,metadataOnly:true,totalCount:data.total_count??artifacts.length,artifacts})}catch{return respond(res,502,{error:'GITHUB_ARTIFACT_METADATA_UNREACHABLE'})}}
if(req.url==='/api/diagnostics'&&req.method==='GET')return respond(res,200,{service:'Freddys V10',login:'authenticated',ai:{configured:!!process.env.OPENAI_API_KEY,liveProviderTest:'not_run',note:'Provider billing, quota and credentials require an authenticated upstream test'},voice:{configured:!!process.env.ELEVENLABS_API_KEY,liveProviderTest:'not_run'},anam:{configured:!!(process.env.ANAM_API_KEY&&process.env.ANAM_ADAM_PERSONA_ID),liveProviderTest:'not_run'},certifiedPicks:{configured:!!process.env.CERTIFIED_PICKS_FEED_URL,verifiedPredictions:0,certification:'HOLD'},recording:{browserDependent:true,serverTest:'not_run'},privacy:{passwordConfigured:true,secretValuesExposed:false}});
if(req.url==='/api/certified-picks'&&req.method==='GET'){const raw=process.env.CERTIFIED_PICKS_FEED_URL;if(!raw)return respond(res,503,{error:'CERTIFIED_PICKS_FEED_NOT_CONFIGURED',certifiedPredictions:0});let u;try{u=new URL(raw);if(u.protocol!=='https:'||u.username||u.password||u.port||!u.hostname.includes('.'))throw Error('bad url')}catch{return respond(res,503,{error:'CERTIFIED_PICKS_FEED_INVALID'})}const ctrl=new AbortController();const timeout=setTimeout(()=>ctrl.abort(),6000);try{const upstream=await fetch(u,{headers:{accept:'application/json',...(process.env.CERTIFIED_PICKS_FEED_TOKEN?{authorization:'Bearer '+process.env.CERTIFIED_PICKS_FEED_TOKEN}:{})},signal:ctrl.signal});if(!upstream.ok)return respond(res,502,{error:'CERTIFIED_PICKS_FEED_UNAVAILABLE',providerStatus:upstream.status});const content=await upstream.text();if(content.length>250000)return respond(res,502,{error:'CERTIFIED_PICKS_FEED_TOO_LARGE'});let payload;try{payload=JSON.parse(content)}catch{return respond(res,502,{error:'CERTIFIED_PICKS_FEED_NOT_JSON'})}return respond(res,200,{source:'configured_read_only_feed',verifiedByV10:false,data:payload})}catch{return respond(res,502,{error:'CERTIFIED_PICKS_FEED_UNREACHABLE'})}finally{clearTimeout(timeout)}}
if(req.url==='/api/converse'&&req.method==='POST'){
 if(!process.env.OPENAI_API_KEY)return respond(res,503,{error:'OPENAI_NOT_CONFIGURED'});
 const request=await body(req);
 if(!people[request.speaker]||typeof request.question!=='string'||request.question.length>3000)return respond(res,400,{error:'INVALID_REQUEST'});
 const began=Date.now(),role=people[request.speaker][1];
 const greeting=/Freddy just called your name|say hello and confirm that you can respond/i.test(request.question) || /^(hello|hi|hey|yo|whats up|are you there)[!?. ]*$/i.test(request.question.trim());
 let live='No sports data requested for this greeting.',slate='No daily slate required.',model='Research evidence was not requested.',source='No market-source audit required.';
 if(!greeting){
  const results=await Promise.allSettled([liveScoreboardContext(),minimalDailyForModels(),modelBoardFor(),refreshV10Sources()]);
  live=results[0].status==='fulfilled'?results[0].value:'Score feed unavailable; do not infer scores';
  slate=results[1].status==='fulfilled'?results[1].value:'Daily slate unavailable';
  model=results[2].status==='fulfilled'?JSON.stringify(results[2].value).slice(0,2300):'Research data unavailable';
  source=results[3].status==='fulfilled'?JSON.stringify(results[3].value).slice(0,1300):'Source workflow status unavailable';
 }
 const instructions='You are '+request.speaker+', '+role+', in the private Freddy’s Picks AI V10 sports boardroom. Reply naturally to the host Freddy. Answer his exact question clearly in 1–4 conversational sentences. Do not invent odds, injury facts, verified Champion-001 probabilities, certified Sharp Edge bets or player prop markets. If discussing bets without authenticated prices and model-derived EV say HOLD. For a greeting, say a short friendly greeting and ask what to analyze. For sports questions use time-stamped source data only, and distinguish real ESPN scores/schedules from sportsbook odds. '+(greeting?'No sports data requested.':'SOURCE EVIDENCE: LIVE '+String(live).slice(0,4600)+' DAILY '+String(slate).slice(0,3300)+' RESEARCH '+model+' WORKFLOW STATUS '+source+' CHAMPION_001 is frozen, odds and props uncertified.');
 const payload={model:process.env.OPENAI_MODEL||'gpt-4o-mini',max_tokens:170,messages:[{role:'system',content:instructions},{role:'user',content:request.question}]};
 let upstream;
 try{upstream=await fetch('https://api.openai.com/v1/chat/completions',{method:'POST',headers:{authorization:'Bearer '+process.env.OPENAI_API_KEY,'content-type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(22000)})}
 catch(err){console.warn('V10_CONVERSE_TIMEOUT_OR_NETWORK',JSON.stringify({speaker:request.speaker,elapsedMs:Date.now()-began,error:String(err.name||'network')}));return respond(res,504,{error:'ANALYST_RESPONSE_TIMEOUT',message:'Analyst did not respond in time. Try again.',retryable:true})}
 let result={};try{result=await upstream.json()}catch(e){return respond(res,502,{error:'ANALYST_INVALID_PROVIDER_RESPONSE',retryable:true})}
 if(!upstream.ok){console.warn('V10_AI_PROVIDER_FAILURE',JSON.stringify({status:upstream.status,code:result?.error?.code||null}));return respond(res,502,{error:'AI_PROVIDER_ERROR',providerStatus:upstream.status,category:upstream.status===429?'OPENAI_QUOTA_OR_RATE_LIMIT':upstream.status===401?'INVALID_OPENAI_CREDENTIAL':'OPENAI_UPSTREAM_FAILURE',retryable:upstream.status>=500||upstream.status===429})}
 const reply=String(result.choices?.[0]?.message?.content||'').trim();
 if(!reply)return respond(res,502,{error:'EMPTY_ANALYST_REPLY',retryable:true});
 console.log('V10_CONVERSE_COMPLETE',JSON.stringify({speaker:request.speaker,greeting,elapsedMs:Date.now()-began,characters:reply.length}));
 return respond(res,200,{speaker:request.speaker,reply});
}
if(req.url==='/api/voice'&&req.method==='POST'){if(!process.env.ELEVENLABS_API_KEY)return respond(res,503,{error:'ELEVENLABS_NOT_CONFIGURED'});const d=await body(req);if(!people[d.speaker]||typeof d.text!=='string'||d.text.length>2000)return respond(res,400,{error:'INVALID_REQUEST'});let v;try{v=await fetch('https://api.elevenlabs.io/v1/text-to-speech/'+people[d.speaker][0],{method:'POST',headers:{'xi-api-key':process.env.ELEVENLABS_API_KEY,'content-type':'application/json',accept:'audio/mpeg'},body:JSON.stringify({text:d.text,model_id:'eleven_multilingual_v2',voice_settings:{...voiceProfiles[d.speaker],use_speaker_boost:true}}),signal:AbortSignal.timeout(15000)})}catch(err){console.warn('V10_VOICE_TIMEOUT_OR_NETWORK',JSON.stringify({speaker:d.speaker,reason:String(err.name||'network')}));return respond(res,504,{error:'VOICE_PROVIDER_TIMEOUT',fallback:'browser_speech'})}if(!v.ok){console.error('V10_VOICE_PROVIDER_FAILURE',JSON.stringify({status:v.status,speaker:d.speaker}));return respond(res,502,{error:'VOICE_PROVIDER_ERROR',providerStatus:v.status,category:v.status===401?'INVALID_ELEVENLABS_CREDENTIAL':v.status===429?'ELEVENLABS_QUOTA_OR_RATE_LIMIT':'ELEVENLABS_UPSTREAM_FAILURE'});}res.writeHead(200,{'content-type':'audio/mpeg','cache-control':'no-store'});return res.end(Buffer.from(await v.arrayBuffer()))}
return respond(res,404,{error:'NOT_FOUND'})}catch(e){return respond(res,500,{error:'SERVER_ERROR'})}});
server.listen(Number(process.env.PORT||3000),'0.0.0.0',()=>{
 if(Math.abs(oddsPreflightMath(150).breakEvenProbability-0.4)>1e-12||Math.abs(oddsPreflightMath(-110).breakEvenProbability-110/210)>1e-12||Math.abs(oddsPreflightMath(-200).breakEvenProbability-2/3)>1e-12)throw Error('ODDS_PREFLIGHT_MATH_SELFTEST_FAILED');console.log('V10_ODDS_PREFLIGHT_MATH_SELFTEST',JSON.stringify({plus150:oddsPreflightMath(150).breakEvenPercent,minus110:oddsPreflightMath(-110).breakEvenPercent,minus200:oddsPreflightMath(-200).breakEvenPercent,source:'USER_REPORTED_ONLY',certifiedEV:0}));
 launchContinuousFeed();
 void refreshV10Sources();
 void provisionLiveAnamTool().then(()=>provisionModelAnamTool()).then(()=>provisionDailyAnamTool()).then(()=>provisionSourceAnamTool());
 void dailySlateLoad().then(async board=>{console.log('V10_DAILY_SLATE_CHECK',JSON.stringify({date:board.dateEastern,leagues:board.leaguesReturned,count:board.gameCount,errors:board.errors}));const test=board.sports.find(x=>x.sport==='NBA')?.games.find(x=>x.teams.length===2);if(test){const form=await selectedGameForm(board.dateEastern,'NBA',test.id);console.log('V10_FORM_SMOKE',JSON.stringify({league:'NBA',gameId:test.id,teams:form.teams.map(x=>({name:x.team,status:x.status,last5:x.last5Record,last10:x.last10Record,error:x.error}))}))}}).catch(e=>console.error('V10_DAILY_SLATE_CHECK_ERROR',String(e.message||e).slice(0,130)));
 const slateRefresh=setInterval(()=>{void dailySlateLoad().catch(e=>console.warn('V10_DAILY_SLATE_REFRESH',String(e.message||e).slice(0,100)))},600000);slateRefresh.unref();
 void modelBoardFor().then(board=>console.log('V10_MODEL_REPORT_CHECK',JSON.stringify({status:board.status,leagues:Object.keys(board.models),errors:board.errors,graded:Object.fromEntries(Object.entries(board.models).map(([k,v])=>[k,v.gradedResearchGames]))}))).catch(e=>console.error('V10_MODEL_REPORT_ERROR',String(e.message||e).slice(0,180)));
 void loadPublicScoreboards().then(feed=>console.log('V10_LIVE_ESPN_CHECK',JSON.stringify({leagues:feed.items.length,events:feed.items.map(x=>({sport:x.sport,count:x.events.length})),errors:feed.errors}))).catch(e=>console.error('V10_LIVE_ESPN_CHECK_ERROR',String(e.message||e).slice(0,160)));
 void Promise.all(Object.keys(castPortraitIds).map(async member=>{
  try{
   const resp=await fetch('http://127.0.0.1:'+String(process.env.PORT||3000)+'/api/cast-portrait?member='+encodeURIComponent(member),{signal:AbortSignal.timeout(15000)});
   return {member,status:resp.status,type:resp.headers.get('content-type'),bytes:(await resp.arrayBuffer()).byteLength}
  }catch(e){return {member,error:String(e.message||e).slice(0,100)}}
 })).then(status=>console.log('V10_GROUP_CAST_TEST',JSON.stringify(status)));
});
