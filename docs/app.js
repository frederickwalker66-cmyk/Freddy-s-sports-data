"use strict";

const $ = (id) => document.getElementById(id);
const TZ = "America/New_York";
const repo = "https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data";
const leagueInfo = [
  ["nba","🏀","NBA","Pro basketball"],
  ["nfl","🏈","NFL","Pro football"],
  ["nhl","🏒","NHL","Pro hockey"],
  ["mlb","⚾","MLB","Pro baseball"],
  ["ncaaf","🏟️","NCAAF","College football"],
  ["ncaab","🏀","NCAAB","College basketball"],
  ["mls","⚽","MLS","Major League Soccer"],
  ["uefa_champions_league","🏆","UEFA UCL","Champions League"]
];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
}
function number(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
function displayNum(value) {
  return number(value) !== null ? Number(value).toLocaleString("en-US") : "—";
}
function dateText(utc, opts={}) {
  if (!utc || Number.isNaN(Date.parse(utc))) return "Not available";
  try {
    return new Intl.DateTimeFormat("en-US", {
      timeZone: TZ, month:"short", day:"numeric", hour:"numeric",minute:"2-digit",
      timeZoneName:"short", ...opts
    }).format(new Date(utc));
  } catch {
    return "Not available";
  }
}
function dateOnly(value) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return "—";
  const [year,month,day] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("en-US",{month:"short",day:"numeric",year:"numeric"})
    .format(new Date(Date.UTC(year,month-1,day,12)));
}
function sourceAge(utc) {
  if (!utc || Number.isNaN(Date.parse(utc))) return null;
  return Math.round((Date.now() - Date.parse(utc)) / 60000);
}
function stateBadge(status, period, clock) {
  if (status === "post") return ["FINAL","final"];
  if (status === "in") return [period ? "Q"+period+(clock ? " · "+clock : ""):"IN PROGRESS",""];
  return ["PREGAME","pre"];
}
function teamAbbrev(name) {
  const chunks = String(name || "").split(/\s+/);
  const tail = chunks[chunks.length-1] || "?";
  return tail.slice(0,3).toUpperCase();
}

function gameCard(game) {
  const pb = number(game.pregame_home_probability_pct);
  const validPb = pb !== null && pb > 0 && pb < 100;
  const winner = validPb ? (pb >= 50 ? game.home : game.away) : null;
  const wProb = validPb ? (pb >= 50 ? pb : 100-pb) : null;
  const [tag,cls] = stateBadge(game.status,game.period,game.clock);
  const scoreAway = number(game.away_score) !== null ? String(game.away_score) : "—";
  const scoreHome = number(game.home_score) !== null ? String(game.home_score) : "—";
  const pace = number(game.pace_total);
  const paceLine = pace !== null && game.status === "in"
    ? '<div class="pace-note">Uncalibrated final-regulation scoring pace: <strong>'
      +escapeHtml(pace.toFixed(1))+' total · '+escapeHtml(game.pace_away?.toFixed(1) ?? "—")
      +'–'+escapeHtml(game.pace_home?.toFixed(1) ?? "—")+'</strong></div>' : "";
  const forecast = validPb
    ? '<span class="game-prob">Research lean: <b>'+escapeHtml(winner) + " "
      +escapeHtml(wProb.toFixed(1))+'%</b></span>'
    : '<span class="game-prob">Research probability: <b>N/A</b></span>';
  return '<article class="game-card">'
    + '<div class="game-head"><span class="game-league">NBA · GAME '+escapeHtml(game.id)+'</span>'
    + '<span class="game-time">'+escapeHtml(dateText(game.start_et,{timeZoneName:undefined,month:undefined,day:undefined}))+'</span></div>'
    + '<div class="game-teams"><div class="game-team"><span class="team-label">'
    + '<span class="team-bubble">'+escapeHtml(teamAbbrev(game.away))+'</span>'
    + '<span class="team-name">'+escapeHtml(game.away)+'</span></span>'
    + '<span class="team-score">'+escapeHtml(scoreAway)+'</span></div>'
    + '<div class="game-team"><span class="team-label"><span class="team-bubble">'
    +escapeHtml(teamAbbrev(game.home))+'</span><span class="team-name">'
    +escapeHtml(game.home)+'</span></span><span class="team-score">'
    +escapeHtml(scoreHome)+'</span></div></div>'
    + '<div class="game-footer">'+forecast+'<span class="status-mini '+cls+'">'
    +escapeHtml(tag)+'</span></div>'+paceLine+'</article>';
}
function updateBoard(data) {
  const games = Array.isArray(data.games) ? data.games : [];
  const observed = data.live_observed_at_utc;
  const age = sourceAge(observed);
  const fresh = data.live_source_status === "SOURCE_OBSERVED" && age !== null && age >= -2 && age <= 180;
  $("source-state").classList.toggle("stale", !fresh);
  $("source-state").lastChild.textContent = fresh ? " PUBLISHED SCOREBOARD" : " DATA NOT CURRENT";
  $("board-state").textContent = fresh ? "PUBLIC GAME STATES" : "AWAITING FRESH DATA";
  $("board-observed").textContent = fresh ? "Observed "+dateText(observed)+" · snapshot, not a stream"
    : "No current source timestamp; older observations withheld";
  $("nba-date").textContent = dateOnly(data.reference_date_eastern);
  $("stat-games").textContent = fresh ? displayNum(games.length) : "—";
  if (fresh && games.length) {
    $("games").innerHTML = games.map(gameCard).join("");
  } else {
    $("games").innerHTML = '<div class="empty-card"><strong>NBA scoreboard not yet published for this period.</strong>'
      + '<p>Reports show N/A until the source refreshes. No games or probabilities are fabricated.</p></div>';
  }
  $("published-at").textContent = dateText(data.generated_at_utc);
  $("reference-date").textContent = dateOnly(data.reference_date_eastern);
}
function updateMarkets(data) {
  const m = data.market || {};
  $("stat-game-markets").textContent = displayNum(m.paired_game_markets);
  $("stat-props").textContent = displayNum(m.paired_prop_markets);
  $("stat-ev").textContent = "0";
  $("cover-game-label").textContent = displayNum(m.paired_game_markets)+" paired groups";
  $("cover-prop-label").textContent = displayNum(m.paired_prop_markets)+" paired groups";
  const g = number(m.paired_game_markets) ?? 0;
  const p = number(m.paired_prop_markets) ?? 0;
  $("cover-game-bar").style.width = g > 0 ? "100%" : "0%";
  $("cover-prop-bar").style.width = p > 0 ? "100%" : "0%";
  // Bars indicate presence of research matching, not percentage market coverage.
  $("odds-receipt").textContent = m.odds_receipt_utc
    ? dateText(m.odds_receipt_utc) : "Unavailable";
  const referenceCurrent = m.paired_market_reference_current === true;
  $("paired-readiness").textContent = !referenceCurrent
    ? "N/A — current source evidence missing or stale"
    : (g+p>0 ? (g+p)+" recent research pairs" : "No recent matched markets");
  const evidence = m.price_evidence_state || "NO_VERIFIED_PRICE_RECEIPT";
  const reason = evidence === "STALE_OR_MISSING_MODEL_REPORT"
    ? "The model research snapshot is old or missing."
    : evidence === "STALE_OR_MISSING_PRICE_RECEIPT"
      ? "The archived odds receipt is older than two hours or missing."
      : "Recent aggregator reference only; checkout remains unverified.";
  $("market-explanation").textContent = reason+
    " Source state: "+evidence.replaceAll("_"," ")+
    ". No authenticated sportsbook checkout, independently certified model EV, or sharp-money data.";
}
function updateLeagues(data) {
  const leagues = data.leagues || {};
  $("league-grid").innerHTML = leagueInfo.map(([key,icon,title,desc])=>{
    const val = leagues[key] || {};
    const exists = val.status === "SUCCESS_RESEARCH_ONLY";
    const recent = exists && val.research_freshness === "RECENT_RESEARCH";
    const forecast = number(val.forecasts);
    const status = recent ? "RECENT RESEARCH" : exists ? "ARCHIVED RESEARCH" : "NO CURRENT SYNC";
    const l5 = number(val.player_last5);
    const slate = data.slates?.[key] || {};
    const games = slate.status === "ESPN_SCHEDULE_OBSERVED"
      ? String(slate.game_count)+" GAMES"
      : slate.status === "NO_GAMES_LISTED" ? "NO GAMES LISTED" : "SCHEDULE N/A";
    return '<article class="league-card"><div class="league-head">'
      + '<span class="league-icon" aria-hidden="true">'+icon+'</span>'
      + '<span class="league-status '+(recent?"ready":"")+'">'+status+'</span></div>'
      + '<h3>'+escapeHtml(title)+'</h3><p>'+escapeHtml(desc)+'</p><div class="league-slate">'+escapeHtml(games)+'</div>'
      + '<div class="league-foot"><span>Rule forecasts <strong>'
      + escapeHtml(forecast === null ? "N/A" : String(forecast))
      +'</strong></span><span>Player L5 <strong>'
      +escapeHtml(l5 === null ? "N/A" : String(l5))+'</strong></span></div></article>';
  }).join("");
}
function updateModel(data) {
  const model = data.model || {};
  $("model-calibration").textContent = "RESEARCH ONLY";
  const n = number(model.graded_forecasts);
  const total = number(model.forward_forecasts);
  $("calibration-description").textContent =
    "Forward game grading: "+(n===null?"N/A":n)+(total===null?"":"/"+total)
    +". Champion-001 source/model authentication, exact-market calibration, "+
    "executable bookmaker prices and verified CLV are not established.";
  const valid = (url) => typeof url === "string" && url.startsWith(repo+"/actions/runs/")
    && /^https:\/\/github\.com\/frederickwalker66-cmyk\/Freddy-s-sports-data\/actions\/runs\/\d+$/.test(url);
  const latest = data.sources?.run_nba;
  if (valid(latest)) $("link-latest-run").href = latest;
}
function update(data) {
  if (!data || data.schema !== "freddys-picks-ai-public-v1") {
    throw new Error("Published report has an unexpected format");
  }
  updateBoard(data);
  updateMarkets(data);
  updateLeagues(data);
  updateModel(data);
  updateTerminal(data);
}
let refreshing = false;
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  const button = $("refresh-button");
  button.disabled = true;
  try {
    const response = await fetch("./data/dashboard.json?_="+Date.now(),
      {cache:"no-store",headers:{"Accept":"application/json"}});
    if (!response.ok) throw new Error("The published snapshot is not available");
    const data = await response.json();
    update(data);
  } catch(err) {
    $("source-state").classList.add("stale");
    $("source-state").lastChild.textContent = " SOURCE UNAVAILABLE";
    $("board-state").textContent = "AWAITING PUBLICATION";
    $("games").innerHTML = '<div class="empty-card"><strong>The dashboard is online, but data has not synchronized.</strong>'
      +'<p>Check the latest GitHub Actions run or refresh after the first successful publish.</p></div>';
    console.warn("Freddy's Picks AI public snapshot unavailable:", String(err));
  } finally {
    button.disabled = false;
    refreshing = false;
  }
}
$("refresh-button").addEventListener("click", refresh);
document.querySelectorAll(".nav-item").forEach(el=>{
  el.addEventListener("click",()=>{
    document.querySelectorAll(".nav-item").forEach(link=>link.classList.remove("active"));
    el.classList.add("active");
  });
});


/* Custom unified, source-aware sports terminal. Never substitute market prices for a native model. */
const terminalState = {league:"all",tab:"all",compact:false,data:null};
const terminalGroups = {
  nba:{props:["Points","Rebounds","Assists","3-pointers","Steals","Blocks","Stocks"],combos:["Points + rebounds","Points + assists","Rebounds + assists","PRA"]},
  nfl:{props:["Passing yards","Rush yards","Receiving yards","Receptions","Touchdowns","Pass attempts"],combos:["Pass + rush","Same-game markets"]},
  nhl:{props:["Shots on goal","Goals","Assists","Points","Blocked shots","Goalie saves"],combos:["Goals + assists","Same-game markets"]},
  mlb:{props:["Hits","Total bases","RBIs","Runs","Home runs","Pitcher strikeouts"],combos:["Batter combinations","First-five markets"]},
  ncaaf:{props:["Pass yards","Rush yards","Receptions","Touchdowns"],combos:["QB pass + rush","Same-game markets"]},
  ncaab:{props:["Points","Rebounds","Assists","3-pointers","Blocks"],combos:["PR","PA","RA","PRA"]},
  mls:{props:["Goals","Shots","Shots on target","Assists","Saves"],combos:["Same-game markets"]},
  uefa_champions_league:{props:["Goals","Shots","Shots on target","Assists","Saves"],combos:["Same-game markets"]}
};
function terminalAge(utc) {
  const n=sourceAge(utc);
  return n!==null && n>=0 ? n : null;
}
function terminalAgeText(utc) {
  const m=terminalAge(utc);
  if(m===null)return "N/A";
  return m<60?m+"m":(m/60).toFixed(1)+"h";
}
function terminalLeague() {
  return terminalState.league==="all"?["all","🌐","ALL SPORTS","All eight leagues"]:
    leagueInfo.find(i=>i[0]===terminalState.league) || leagueInfo[0];
}
function terminalBlock(title,subtitle,body) {
  return '<section class="terminal-block"><div class="terminal-block-head"><h3>'+escapeHtml(title)+'</h3><small>'+escapeHtml(subtitle)+'</small></div>'+body+'</section>';
}
function terminalTable(headers,rows) {
  return '<div class="terminal-table-scroll"><table class="terminal-table"><thead><tr>'
    +headers.map(s=>'<th scope="col">'+escapeHtml(s)+'</th>').join('')
    +'</tr></thead><tbody>'+rows.join('')+'</tbody></table></div>';
}
function terminalRow(values) { return '<tr>'+values.map(s=>'<td>'+s+'</td>').join('')+'</tr>'; }
function terminalEmptyRow(count,text) {
  return '<tr><td colspan="'+count+'" class="terminal-no-source">'+escapeHtml(text)+'</td></tr>';
}


function terminalAmerican(v) {
  if(typeof v!=="number"||!Number.isInteger(v)||Math.abs(v)<100||Math.abs(v)>99999)return "N/A";
  return (v>0?"+":"")+String(v);
}
function terminalPublicMarket(g) {
  const q=g?.market_reference;
  if(!q||q.direct_checkout_verified!==false)return null;
  return q;
}
function terminalGameTable(data) {
  const lg=terminalState.league;
  const q=($("terminal-search").value||"").trim().toLowerCase();
  const sports=lg==="all"?leagueInfo.map(x=>x[0]):[lg];
  const slates=data.slates||{}, publicLeagues=data.public_hourly_board||{};
  const view=sports.flatMap(s=>{
    const original=slates[s]||{};
    const published=publicLeagues[s]||{};
    const usePublic=(published.status==="ESPN_PUBLIC_OBSERVED" || published.status==="NO_GAMES_LISTED")
      && terminalAge(published.observed_at_utc)!==null && terminalAge(published.observed_at_utc)<=100;
    const games=usePublic
      ? (Array.isArray(published.games)?published.games:[])
      : (Array.isArray(original.games)?original.games:[]);
    const researchById=new Map((original.games||[]).map(g=>[String(g.id),g]));
    return games
      .filter(g=>(s+" "+g.away+" "+g.home).toLowerCase().includes(q))
      .map(g=>({
        sport:s,game:g,
        observed:usePublic?published.observed_at_utc:original.as_of_utc,
        publicSource:usePublic,
        research:usePublic?researchById.get(String(g.id)):g,
      }));
  }).sort((a,b)=>String(a.game.start_et||"").localeCompare(String(b.game.start_et||""))
      || a.sport.localeCompare(b.sport) || String(a.game.id).localeCompare(String(b.game.id)));
  const rows=view.map(({sport,game:g,observed,publicSource,research:rg})=>{
    const modelFresh=terminalAge(data.leagues?.[sport]?.as_of_utc)!==null
      && terminalAge(data.leagues?.[sport]?.as_of_utc)<=180;
    const scheduleFresh=terminalAge(observed)!==null
      && terminalAge(observed)<=(publicSource?100:180);
    const pb=number(rg?.research_home_probability_pct);
    const validPair=rg&&String(rg.id)===String(g.id)&&rg.home===g.home&&rg.away===g.away;
    const usable=modelFresh&&scheduleFresh&&validPair&&pb!==null&&pb>0&&pb<100;
    const homeLean=usable&&pb>=50;
    const pct=usable?(homeLean?pb:100-pb):null;
    const lean=usable?(homeLean?g.home:g.away):"N/A";
    const research=usable?'<div class="terminal-lean">'+escapeHtml(lean)
      +'<small>Uncalibrated research</small><div class="terminal-bar"><span style="width:'+pct.toFixed(1)+'%"></span></div></div>'
      :'<span class="terminal-na">N/A</span>';
    const time=g.start_et?dateText(g.start_et,{month:undefined,day:undefined,timeZoneName:undefined}):"TBD";
    const score=(g.status==="in"||g.status==="post")
       && number(g.away_score)!==null&&number(g.home_score)!==null
      ? ' · '+escapeHtml(String(g.away_score))+'–'+escapeHtml(String(g.home_score)):"";
    const type=g.status==="post"?"FINAL":g.status==="in"?"IN PROGRESS":"PREGAME";
    const quote=publicSource?terminalPublicMarket(g):null;
    const market=quote
      ? '<div class="terminal-priced"><strong>'+escapeHtml(quote.provider||"ESPN-labelled")
        +'</strong><span class="terminal-muted">Observed '+escapeHtml(terminalAgeText(observed))
        +' ago · book posted time N/A</span></div>'
      :'<span class="terminal-na">Market N/A</span>';
    const ml=quote&&(quote.moneyline_away!==null||quote.moneyline_home!==null)
      ?'<div class="terminal-price"><b>ML</b> '+escapeHtml(terminalAmerican(quote.moneyline_away))
        +' / '+escapeHtml(terminalAmerican(quote.moneyline_home))+'</div>' : "";
    const spread=quote?.spread_details
      ?'<div class="terminal-price"><b>ESPN LINE</b> '+escapeHtml(quote.spread_details)+'</div>':"";
    const total=number(quote?.total)!==null
      ?'<div class="terminal-price"><b>TOTAL</b> '+escapeHtml(String(quote.total))
       +(quote.over_price!==null||quote.under_price!==null
         ?' ('+escapeHtml(terminalAmerican(quote.over_price))+' / '+escapeHtml(terminalAmerican(quote.under_price))+')':"")
       +'</div>':"";
    const changed = g.reference_change?.source_retrieval_differences_only===true
      && g.reference_change.provider===quote?.provider?g.reference_change:null;
    const changeParts=[];
    if(changed) {
      if(typeof changed.previous_total==="number" && typeof changed.current_total==="number"
          && changed.previous_total!==changed.current_total) {
        changeParts.push('TOTAL '+changed.previous_total+' → '+changed.current_total);
      }
      if(changed.previous_line && changed.current_line
          && changed.previous_line!==changed.current_line) {
        changeParts.push('LINE '+changed.previous_line+' → '+changed.current_line);
      }
    }
    const changeHtml=changeParts.length?'<div class="terminal-movement"><strong>OBSERVED CHANGE</strong> '
        +escapeHtml(changeParts.join(' · '))+'<small>ESPN retrieved snapshots · not sharp flow or CLV</small></div>':"";
    const sourceRows=(data.fresh_provider_markets?.leagues?.[sport]?.rows||[])
      .filter(x=>x.public_game_id===String(g.id)&&x.category==="game"
        &&terminalAge(x.quote_observed_at_utc)!==null&&terminalAge(x.quote_observed_at_utc)<=60);
    const filteredMarket=sourceRows.filter(x=>x.is_alternate_line!==true).slice(0,8);
    const providerLines=filteredMarket.map(x=>{
      const label=x.market==="moneyline"?"ML":x.market==="point_spread"?"SPREAD":"TOTAL";
      const line=typeof x.line==="number"?" "+String(x.line):"";
      return '<div class="terminal-price"><b>'+label+'</b> '
        +escapeHtml(x.side.toUpperCase()+line+' '+terminalAmerican(x.american_odds))
        +'</div>';
    }).join("");
    const marketCell=(quote?market+ml+spread+total+changeHtml:market)
      +(providerLines?'<div class="terminal-provider-reference">'
        +'<b>Recent SharpAPI · DraftKings-labelled (not checkout)</b>'
        +providerLines
        +'<small>Provider quote age '+escapeHtml(terminalAgeText(filteredMarket[0].quote_observed_at_utc))
        +'</small></div>':"");
    const recordString=(g.away_record||g.home_record)
      ?'<small>Season record: '+escapeHtml(g.away_abbr||"Away")+' '+escapeHtml(g.away_record||"N/A")
       +' · '+escapeHtml(g.home_abbr||"Home")+' '+escapeHtml(g.home_record||"N/A")+'</small>'
      :"";
    const venueString=g.venue?'<small>Venue: '+escapeHtml(g.venue)+'</small>':"";
    const networks=Array.isArray(g.broadcasts)&&g.broadcasts.length
      ?'<small>TV: '+escapeHtml(g.broadcasts.join(", "))+'</small>':"";
    return terminalRow([
      '<span class="terminal-sport-pill">'+escapeHtml(leagueInfo.find(x=>x[0]===sport)?.[2]||sport)+'</span>',
      '<div class="terminal-team-cell"><strong>'+escapeHtml(g.away)+' @ '+escapeHtml(g.home)
        +'</strong><small>'+escapeHtml(time)+' ET · '+escapeHtml(type)+score+'</small>'+recordString+venueString+networks+'</div>',
      marketCell,
      research,
      usable?'<b>'+pct.toFixed(1)+'%</b><small class="terminal-muted">rule only</small>':'<span class="terminal-na">N/A</span>',
      '<span class="terminal-na">N/A</span>',
      '<span class="terminal-gate-chip">HOLD</span>'
    ]);
  });
  const sourceStatus=sports.map(s=>{
    const original=slates[s]||{}, published=publicLeagues[s]||{};
    const title=leagueInfo.find(x=>x[0]===s)?.[2]||s;
    let state;
    if((published.status==="ESPN_PUBLIC_OBSERVED"||published.status==="NO_GAMES_LISTED")
        && terminalAge(published.observed_at_utc)!==null&&terminalAge(published.observed_at_utc)<=100){
      state=displayNum(published.game_count)+" games · "+displayNum(published.line_reference_count)+" line refs · "+terminalAgeText(published.observed_at_utc)+" ago";
    }else if(typeof original.game_count==="number"){
      state=displayNum(original.game_count)+" fixtures · live source N/A";
    }else{
      state="No current public source";
    }
    return '<span class="terminal-slate-source"><b>'+escapeHtml(title)+'</b> '+escapeHtml(state)+'</span>';
  }).join("");
  const msg=q?"No games match this team or league.":"No current source-observed games for these sports.";
  const table=terminalTable(
    ["League","Game / Score (ET)","Public ML / Spread / Total","Research lean","Rule p%","Champion p / EV","Bet status"],
    rows.length?rows:[terminalEmptyRow(7,msg)]);
  return terminalBlock("All-sport game markets · "+(lg==="all"?"EIGHT LEAGUES":terminalLeague()[2]),
    "Best-effort ESPN source snapshots · hourly requested · no sportsbook checkout",
    '<div class="terminal-slate-sources">'+sourceStatus+'</div>'+table
    +'<div class="terminal-info">Market columns display only source-labelled ESPN references when published. '
    +'ML = away/home prices when explicitly provided. ESPN LINE may be a spread or headline moneyline (especially NHL); it is not necessarily a verified spread. TOTAL price pair = over/under when available. Observation time is when ESPN was fetched, '
    +'<strong>not the bookmaker quote time.</strong> In-play source fields are not automatically executable live betting lines. '
    +'Historical reference changes are source-observed comparisons—not sharp-money action, CLV, or verified executable line movement. '+
    'Certified Sharp Edge / EV, authenticated DraftKings checkout and professional sharp-money percentages remain N/A.</div>');
}


function terminalProps(data,combos=false) {
  const isAll=terminalState.league==="all";
  const selected=isAll?leagueInfo.map(i=>i[0]):[terminalState.league];
  const category=combos?"combo":"prop";
  const title=combos?"Player combos & combined markets":"Player props · overs & unders";
  const search=($("terminal-search").value||"").trim().toLowerCase();
  const provider=data.fresh_provider_markets||{};
  const cards=selected.map(lg=>{
    const league=provider.leagues?.[lg]||{};
    const conf=terminalGroups[lg]||{props:[],combos:[]};
    const examples=combos?conf.combos:conf.props;
    const sourceRows=(Array.isArray(league.rows)?league.rows:[]).filter(x=>x.category===category);
    const rows=sourceRows.filter(x=>(
      [lg,x.player,x.home,x.away,x.market,x.market_label].join(" ").toLowerCase().includes(search)));
    const label=leagueInfo.find(i=>i[0]===lg)?.[2]||lg.toUpperCase();
    const bodyRows=rows.slice(0,35).map(x=>{
      const line=typeof x.line==="number"?String(x.line):"N/A";
      return terminalRow([
        '<span class="terminal-team-cell"><strong>'+escapeHtml(x.player||"N/A")+'</strong><small>'
          +escapeHtml(x.away)+' @ '+escapeHtml(x.home)+'</small></span>',
        '<strong>'+escapeHtml(x.market_label||x.market)+'</strong>'
          +(x.is_alternate_line?'<small class="terminal-muted">Alternate threshold</small>':""),
        '<strong>'+escapeHtml(x.side.toUpperCase())+' '+escapeHtml(line)+'</strong>',
        '<strong>'+escapeHtml(terminalAmerican(x.american_odds))+'</strong>',
        '<small class="terminal-muted">'+escapeHtml(terminalAgeText(x.quote_observed_at_utc))
         +' old · aggregator-labelled</small>',
        '<span class="terminal-gate-chip">HOLD</span>'
      ]);
    });
    const explain=rows.length>35?
      '<div class="terminal-info">Showing first 35 of '+rows.length+' source-stamped quotes. Select this sport or search a player to narrow results.</div>':"";
    const sourceState=league.status==="RECENT_AGGREGATOR_QUOTES_NOT_CHECKOUT"
      ? rows.length+' market sides captured'
      : 'NO CURRENT PROVIDER QUOTES';
    const marketTable=rows.length
      ?terminalTable(["Player / Game","Market","Over / Under","Odds","Quote age","Decision"],bodyRows)
      :'<div class="terminal-no-source"><strong>Current '+escapeHtml(category)+' prices: N/A</strong>'
        +'<p>No recent, matchup-checked sportsbook-aggregator quotes for '+escapeHtml(label)+'. '
        +'The ESPN scoreboard does not publish player props or PRA prices. Historical quotes are hidden.</p></div>';
    return '<section class="terminal-block terminal-prop-league"><div class="terminal-block-head">'
      +'<h3>'+escapeHtml(label)+'</h3><small>'+escapeHtml(sourceState)+'</small></div>'
      +marketTable+explain
      +'<div class="terminal-pill-list">'+examples.map(t=>'<span>'+escapeHtml(t)+'</span>').join("")+'</div></section>';
  });
  return terminalBlock(title+" · "+(isAll?"ALL EIGHT LEAGUES":terminalLeague()[2]),
    "Only real source-stamped player prices when accessible · never yesterday's odds",
    '<div class="terminal-props-stack">'+cards.join("")+'</div>'
      +'<div class="terminal-info">Raw market rows are not calibrated picks, player availability verification, '
      +'or settled sportsbook prices. They remain HOLD even when recently observed. '
      +'<a target="_blank" rel="noopener noreferrer" href="https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/collect-sharpapi.yml">'
      +'View provider collection status ↗</a> · More leagues and extra provider calls may use paid quota.</div>');
}

function terminalAudit(data) {
  const m=data.market_by_league||{};
  const all=terminalState.league==="all";
  const selected=all?leagueInfo.map(x=>x[0]):[terminalState.league];
  const rows=selected.map(lg=>{
    const row=m[lg]||{};
    const status=row.price_evidence_state==="RECENT_AGGREGATOR_REFERENCE_ONLY_NO_CHECKOUT"
      ?"AGGREGATOR · NOT CHECKOUT":row.price_evidence_state==="STALE_OR_MISSING_MODEL_REPORT"
      ?"MODEL STALE":"MISSING / STALE ODDS";
    return terminalRow([
      '<span class="terminal-sport-pill">'+escapeHtml(leagueInfo.find(x=>x[0]===lg)?.[2]||lg)+'</span>',
      escapeHtml(displayNum(row.archived_quotes))+' <small class="terminal-na">archived</small>',
      escapeHtml(row.odds_receipt_utc?terminalAgeText(row.odds_receipt_utc):"N/A"),
      escapeHtml(displayNum(row.paired_game_markets))+' / '+escapeHtml(displayNum(row.paired_prop_markets)),
      '<span class="terminal-na">'+escapeHtml(status)+'</span>',
      '<span class="terminal-na">N/A</span>',
      '<span class="terminal-gate-chip">HOLD</span>'
    ]);
  });
  const table=terminalTable(
    ["League","Source quote archive","Quote age","Current game / prop pairs","Source quality","True CLV / sharp flow","Betting"],
    rows);
  const providerNow=data?.fresh_provider_markets?.leagues||{};
  const extra='<div class="terminal-info"><b>Fresh provider rows by league:</b> '+selected.map(k=>{
    const o=providerNow[k]||{};
    return escapeHtml((leagueInfo.find(x=>x[0]===k)?.[2]||k)+': '+String((o.game||0)+(o.prop||0)+(o.combo||0)));
  }).join(' · ')+' — all aggregator-only / HOLD. </div>';
  const details= '<div class="terminal-audit-grid">'
    +'<div><span>FROZEN CHAMPION-001</span><strong>Original executable not independently authenticated</strong></div>'
    +'<div><span>BET-READY PROBABILITY</span><strong class="hold">N/A · independent calibration missing</strong></div>'
    +'<div><span>PROVIDER DIRECT CHECKOUT</span><strong class="hold">N/A · original sportsbook price not verified</strong></div>'
    +'<div><span>REAL SPORTSBOOK CLV & SHARP HANDLE</span><strong class="hold">N/A · audited receipts unavailable</strong></div></div>';
  return terminalBlock(
    "Sharp Edge audit · "+(all?"ALL EIGHT LEAGUES":terminalLeague()[2]),
    "Each sport has its OWN timestamp and pricing gate · no NBA quote substitution",
    table+extra+details+'<div class="terminal-info">All league betting decisions: <strong>HOLD / PASS</strong>. '
    +'Historical archive counts are not current market coverage. '
    +'Verified +EV selections: <strong>0</strong>. Shadow stake: <strong>$0</strong>. '
    +'<a href="https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions" target="_blank" rel="noopener noreferrer">Source workflow history ↗</a></div>');
}




function terminalData(data) {
  const lg=terminalState.league;
  const selected=lg==="all"?leagueInfo.map(x=>x[0]):[lg];
  const rows=selected.map(k=>{
    const label=leagueInfo.find(x=>x[0]===k)?.[2]||k;
    const counts=data.leagues?.[k]||{};
    const publicData=data.public_hourly_board?.[k]||{};
    const status=publicData.status==="ESPN_PUBLIC_OBSERVED"||publicData.status==="NO_GAMES_LISTED";
    const games=status?publicData.games||[]:[];
    const completeTeamRecords=games.filter(g=>g.home_record&&g.away_record).length;
    const sampleHistory=games.filter(g=>Array.isArray(g.reference_history)&&g.reference_history.length>1).length;
    const form=[displayNum(counts.team_last5),displayNum(counts.team_last10)].join(" / ");
    const player=[displayNum(counts.player_last5),displayNum(counts.player_last10)].join(" / ");
    const rowStatus=status
      ?'ESPN observed '+terminalAgeText(publicData.observed_at_utc)+' ago'
      :'Public scoreboard unavailable';
    return terminalRow([
      '<span class="terminal-sport-pill">'+escapeHtml(label)+'</span>',
      '<b>'+escapeHtml(displayNum(publicData.game_count))+'</b>',
      '<b>'+escapeHtml(String(completeTeamRecords))+'</b>',
      '<b>'+escapeHtml(displayNum(publicData.line_reference_count))+'</b>',
      '<b>'+escapeHtml(String(sampleHistory))+'</b>',
      '<span class="terminal-muted">'+escapeHtml(form)+'</span>',
      '<span class="terminal-muted">'+escapeHtml(player)+'</span>',
      '<span class="terminal-muted">'+escapeHtml(rowStatus)+'</span>'
    ]);
  });
  const table=terminalTable(
    ["League","Games","2-team records","ESPN line refs","Observed changes","Team L5 / L10","Player L5 / L10","Source"],
    rows);
  const nextRows=[];
  selected.forEach(k=>{
    const next=data.slates?.[k]?.next_games;
    if(!Array.isArray(next))return;
    const name=leagueInfo.find(x=>x[0]===k)?.[2]||k;
    next.slice(0,6).forEach(g=>{
      if(!g.away||!g.home||!g.start_et)return;
      nextRows.push(terminalRow([
        '<span class="terminal-sport-pill">'+escapeHtml(name)+'</span>',
        '<span>'+escapeHtml(g.away)+' @ '+escapeHtml(g.home)+'</span>',
        '<span>'+escapeHtml(dateText(g.start_et,{timeZoneName:undefined}))+'</span>',
        '<span class="terminal-na">ESPN source-matched · no verified odds</span>'
      ]));
    });
  });
  const future=terminalTable(["League","Next fixture","Eastern time","Source status"],
    nextRows.length?nextRows:[terminalEmptyRow(4,
      "No independently source-matched upcoming game entries in the current seven-day preflight.")]);
  return terminalBlock("Source data & season-form coverage",
    "Observed scores, W–L records, verified source identity and historical data coverage",
    table+'<div class="terminal-info">L5 / L10 values are counts of complete HISTORICAL source records '
      +'already collected, not team recent averages or calibrated winning probabilities. '
      +'Observed changes are comparisons between ESPN pulls, not professional sharp action. '
      +'No injury or active-roster status is implied.</div>')
    +terminalBlock("Next upcoming fixtures",
      "Displayed only when a source-hash-matched future ESPN schedule record is available",
      future);
}

function renderTerminal() {
  const d=terminalState.data;
  if(!d)return;
  const lg=terminalState.league;
  const selected=lg==="all"?leagueInfo.map(x=>x[0]):[lg];
  const slates=d.slates||{}, markets=d.market_by_league||{}, publicLeagues=d.public_hourly_board||{};
  const matchedCounts=selected.map(k=>{
    const p=publicLeagues[k]||{},s=slates[k]||{};
    if((p.status==="ESPN_PUBLIC_OBSERVED"||p.status==="NO_GAMES_LISTED")
        && terminalAge(p.observed_at_utc)!==null&&terminalAge(p.observed_at_utc)<=100)
      return p.game_count;
    return s.game_count;
  });
  const tracked=matchedCounts.every(x=>typeof x==="number")
    ?matchedCounts.reduce((a,b)=>a+b,0):null;
  const references=selected.map(k=>{
    const p=publicLeagues[k]||{};
    return ((p.status==="ESPN_PUBLIC_OBSERVED"||p.status==="NO_GAMES_LISTED")
      &&terminalAge(p.observed_at_utc)!==null&&terminalAge(p.observed_at_utc)<=100)
      ?p.line_reference_count:null;
  });
  const activeSources=references.filter(x=>typeof x==="number").length;
  const refCount=activeSources?references.reduce((sum,x)=>sum+(number(x)||0),0):null;
  const ages=selected.map(k=>terminalAge(d.leagues?.[k]?.as_of_utc));
  const modelAge=ages.length&&ages.every(x=>x!==null)?Math.max(...ages):null;
  const observedAges=selected.flatMap(k=>{
    const p=publicLeagues[k]||{};
    return typeof p.line_reference_count==="number"&&p.line_reference_count>0
      ?[terminalAge(p.observed_at_utc)]:[];
  }).filter(x=>x!==null);
  const lineAge=observedAges.length?Math.max(...observedAges):null;
  $("t-games").textContent=displayNum(tracked);
  $("t-market-pairs").textContent=displayNum(refCount);
  const currentProps=selected.reduce((sum,k)=>{
    const row=d.fresh_provider_markets?.leagues?.[k]||{};
    return sum+(row.prop||0)+(row.combo||0);
  },0);
  $("t-prop-pairs").textContent=currentProps?String(currentProps):"N/A";
  $("t-certified").textContent="0";
  $("t-research-age").textContent=modelAge===null?"N/A":modelAge<60?modelAge+"m":(modelAge/60).toFixed(1)+"h";
  $("t-odds-age").textContent=lineAge===null?"N/A":lineAge<60?lineAge+"m":(lineAge/60).toFixed(1)+"h";
  $("terminal-sync").textContent="ESPN observed "+activeSources+"/"+selected.length+" selected sports · site published "+dateText(d.generated_at_utc);
  $("terminal-decision").textContent="HOLD";
  $("terminal-leagues").querySelectorAll("button").forEach(b=>{
    const a=b.dataset.league===lg;b.classList.toggle("active",a);b.setAttribute("aria-pressed",String(a));
  });
  $("terminal-tabs").querySelectorAll("button").forEach(b=>{
    const a=b.dataset.tab===terminalState.tab;b.classList.toggle("active",a);
    b.setAttribute("aria-selected",String(a));b.tabIndex=a?0:-1;
  });
  $("terminal-search").disabled=false;
  $("terminal-search").placeholder=lg==="all"?"Search teams, players, markets…":"Search "+terminalLeague()[2]+" teams or players…";
  const parts=[],tab=terminalState.tab;
  if(tab==="all"||tab==="games")parts.push(terminalGameTable(d));
  if(tab==="all"||tab==="data")parts.push(terminalData(d));
  if(tab==="all"||tab==="props")parts.push(terminalProps(d));
  if(tab==="all"||tab==="combos")parts.push(terminalProps(d,true));
  if(tab==="all"||tab==="sharp")parts.push(terminalAudit(d));
  const totalResearch=selected.reduce((sum,k)=>sum+(number(d.leagues?.[k]?.forecasts)||0),0);
  const caption='<div class="terminal-meta"><strong>'+escapeHtml(terminalLeague()[2])+'</strong> · '
      +escapeHtml(displayNum(tracked))+' source-listed games · '
      +escapeHtml(String(totalResearch))+' research-rule forecast rows · '
      +'public reference sources '+activeSources+'/'+selected.length+' · <span class="hold-text">0 certified +EV / HOLD</span></div>';
  $("terminal-body").innerHTML=caption+'<div class="terminal-stack">'+parts.join("")+'</div>';
}

function updateTerminal(data){
  terminalState.data=data;
  if(!$("terminal-leagues").dataset.ready){
    $("terminal-leagues").innerHTML='<button type="button" data-league="all">🌐 ALL SPORTS</button>'+leagueInfo.map(([k,emoji,name])=>'<button type="button" data-league="'+escapeHtml(k)+'">'+emoji+' '+escapeHtml(name)+'</button>').join("");
    $("terminal-leagues").dataset.ready="true";
  }
  renderTerminal();
}
$("terminal-leagues").addEventListener("click",e=>{
  const b=e.target.closest("button[data-league]");
  if(!b)return;terminalState.league=b.dataset.league;
  $("terminal-search").value="";renderTerminal();
});
$("terminal-tabs").addEventListener("click",e=>{
  const b=e.target.closest("button[data-tab]");
  if(!b)return;terminalState.tab=b.dataset.tab;renderTerminal();
});
$("terminal-search").addEventListener("input",()=>renderTerminal());
$("terminal-density").addEventListener("click",()=>{
  terminalState.compact=!terminalState.compact;
  $("terminal").classList.toggle("terminal-compact",terminalState.compact);
  $("terminal-density").setAttribute("aria-pressed",String(terminalState.compact));
  $("terminal-density").textContent=terminalState.compact?"Comfort view":"Compact view";
});

refresh();
setInterval(refresh, 60000);
