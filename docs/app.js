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

function terminalGameTable(data) {
  const lg=terminalState.league;
  const q=($("terminal-search").value||"").trim().toLowerCase();
  const sports=lg==="all"?leagueInfo.map(x=>x[0]):[lg];
  const slates=data.slates||{};
  const selected=sports.flatMap(s=>{
    const slate=slates[s]||{};
    const games=Array.isArray(slate.games)?slate.games:[];
    return games.filter(g=>(s+" "+g.away+" "+g.home).toLowerCase().includes(q))
      .map(g=>({sport:s,game:g,observed:slate.as_of_utc}));
  }).sort((a,b)=>{
    return String(a.game.start_et||"").localeCompare(String(b.game.start_et||""))
      || a.sport.localeCompare(b.sport) || String(a.game.id).localeCompare(String(b.game.id));
  });
  const rows=selected.map(({sport,game:g,observed})=>{
    const modelFresh=terminalAge(data.leagues?.[sport]?.as_of_utc)!==null
      && terminalAge(data.leagues?.[sport]?.as_of_utc)<=180;
    const scheduleFresh=terminalAge(observed)!==null && terminalAge(observed)<=180;
    const pb=number(g.research_home_probability_pct);
    const usable=modelFresh&&scheduleFresh&&pb!==null&&pb>0&&pb<100;
    const homeLean=usable&&pb>=50;
    const pct=usable?(homeLean?pb:100-pb):null;
    const lean=usable?(homeLean?g.home:g.away):"N/A";
    const research=usable?'<div class="terminal-lean">'+escapeHtml(lean)
        +'<small>Uncalibrated rule</small>'
        +'<div class="terminal-bar"><span style="width:'+pct.toFixed(1)+'%"></span></div></div>'
      :'<span class="terminal-na">N/A</span>';
    const gameTime=g.start_et?dateText(g.start_et,{month:undefined,day:undefined,timeZoneName:undefined}):"TBD";
    return terminalRow([
      '<span class="terminal-sport-pill">'+escapeHtml(leagueInfo.find(x=>x[0]===sport)?.[2]||sport)+'</span>',
      '<div class="terminal-team-cell"><strong>'+escapeHtml(g.away)+' @ '+escapeHtml(g.home)+'</strong><small>'
        +escapeHtml(gameTime)+' ET · '+escapeHtml(g.status==="scheduled"?"Scheduled · research snapshot":"Observed")+'</small></div>',
      research,
      usable?'<strong>'+pct.toFixed(1)+'%</strong> <small class="terminal-na">research</small>':'<span class="terminal-na">N/A</span>',
      '<span class="terminal-na">N/A</span>',
      '<span class="terminal-na">N/A</span>',
      '<span class="terminal-gate-chip">HOLD</span>'
    ]);
  });
  const statusLines=sports.map(s=>{
    const slate=slates[s]||{};
    const title=leagueInfo.find(x=>x[0]===s)?.[2]||s;
    const status=slate.status==="ESPN_SCHEDULE_OBSERVED"
      ?displayNum(slate.game_count)+" ESPN-listed game(s)"
      :slate.status==="NO_GAMES_LISTED"?"0 games listed by ESPN"
      :slate.status==="MATCHUPS_UNVERIFIED"?"Unverified source identity"
      :"Schedule not current";
    return '<span class="terminal-slate-source"><b>'+escapeHtml(title)+'</b> '+escapeHtml(status)+'</span>';
  }).join("");
  const text=q?"No games match this search.":"No eligible, source-observed matchups in this selection.";
  const table=terminalTable(
    ["League","Matchup / ET","Research lean","Rule p%","ML / Spread / O-U","Champion p / EV","Sharp status"],
    rows.length?rows:[terminalEmptyRow(7,text)]);
  return terminalBlock(
    "Game markets · "+(lg==="all"?"ALL EIGHT LEAGUES":terminalLeague()[2]),
    "Observed ESPN fixture snapshots · not authenticated sportsbook lines",
    '<div class="terminal-slate-sources">'+statusLines+'</div>'+table+
    '<div class="terminal-info">Matches and kickoff/tipoff originate from the archived ESPN schedule preflight; third-party research only. '
    +'Odds, spreads, totals, bookmaker IDs, official lineup confirmation, independently calibrated game probabilities, sharp handle and EV: '
    +'<strong>N/A until separately validated.</strong> No verified fixture is silently replaced with a predicted game.</div>');
}


function terminalProps(data,combos=false) {
  const all=terminalState.league==="all";
  const selected=all?leagueInfo.map(x=>x[0]):[terminalState.league];
  const name=combos?"Combination markets":"Player props";
  const cards=selected.map(lg=>{
    const conf=terminalGroups[lg]||{props:[],combos:[]};
    const cats=combos?conf.combos:conf.props;
    const meta=data.leagues?.[lg]||{};
    const market=data.market_by_league?.[lg]||{};
    const title=leagueInfo.find(x=>x[0]===lg)?.[2]||lg.toUpperCase();
    return '<article class="terminal-sport-card"><div class="terminal-card-title"><strong>'
      +escapeHtml(title)+'</strong><span class="terminal-gate-chip">HOLD</span></div>'
      +'<div class="terminal-card-metrics"><div><span>Exact paired props</span><b>'
      +escapeHtml(combos?"N/A":displayNum(market.paired_prop_markets))+'</b></div>'
      +'<div><span>Historical player L5 / L10</span><b>'
      +escapeHtml(displayNum(meta.player_last5))+' / '+escapeHtml(displayNum(meta.player_last10))+'</b></div></div>'
      +'<div class="terminal-pill-list">'+cats.map(x=>'<span>'+escapeHtml(x)+'</span>').join("")+'</div>'
      +'<p>Current player, market side and threshold: <b>N/A</b> · matched available price: <b>N/A</b> · certified EV: <b>N/A</b>.</p></article>';
  }).join("");
  return terminalBlock(
    name+" · "+(all?"ALL EIGHT LEAGUES":terminalLeague()[2]),
    combos?"Combined propositions require verified joint prices and dependence":"Player overs, unders and alternatives require exact market receipts",
    '<div class="terminal-sport-grid">'+cards+'</div>'
    +'<div class="terminal-info">These are supported research categories and genuine historical L5/L10 coverage counts, '
    +'NOT listed player wagers or available sportsbook lines. '
    +'Absent player-specific markets are intentionally shown as N/A rather than manufactured.</div>');
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
  const details= '<div class="terminal-audit-grid">'
    +'<div><span>FROZEN CHAMPION-001</span><strong>Original executable not independently authenticated</strong></div>'
    +'<div><span>BET-READY PROBABILITY</span><strong class="hold">N/A · independent calibration missing</strong></div>'
    +'<div><span>PROVIDER DIRECT CHECKOUT</span><strong class="hold">N/A · original sportsbook price not verified</strong></div>'
    +'<div><span>REAL SPORTSBOOK CLV & SHARP HANDLE</span><strong class="hold">N/A · audited receipts unavailable</strong></div></div>';
  return terminalBlock(
    "Sharp Edge audit · "+(all?"ALL EIGHT LEAGUES":terminalLeague()[2]),
    "Each sport has its OWN timestamp and pricing gate · no NBA quote substitution",
    table+details+'<div class="terminal-info">All league betting decisions: <strong>HOLD / PASS</strong>. '
    +'Historical archive counts are not current market coverage. '
    +'Verified +EV selections: <strong>0</strong>. Shadow stake: <strong>$0</strong>. '
    +'<a href="https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions" target="_blank" rel="noopener noreferrer">Source workflow history ↗</a></div>');
}


function renderTerminal() {
  const d=terminalState.data;
  if(!d)return;
  const lg=terminalState.league;
  const selected=lg==="all"?leagueInfo.map(x=>x[0]):[lg];
  const slates=d.slates||{}, markets=d.market_by_league||{};
  const allCount=selected.every(k=>typeof slates[k]?.game_count==="number");
  const tracked=allCount?selected.reduce((sum,k)=>sum+slates[k].game_count,0):null;
  const paired=(key)=>{
    const values=selected.map(k=>markets[k]?.[key]);
    return values.every(x=>typeof x==="number"&&Number.isFinite(x))
      ?values.reduce((sum,x)=>sum+x,0):null;
  };
  const ages=selected.map(k=>terminalAge(d.leagues?.[k]?.as_of_utc));
  const currentAge=ages.length&&ages.every(x=>x!==null)?Math.max(...ages):null;
  const quoteAges=selected.map(k=>terminalAge(markets[k]?.odds_receipt_utc));
  const quoteAge=quoteAges.length&&quoteAges.every(x=>x!==null)?Math.max(...quoteAges):null;
  $("t-games").textContent=displayNum(tracked);
  $("t-market-pairs").textContent=displayNum(paired("paired_game_markets"));
  $("t-prop-pairs").textContent=displayNum(paired("paired_prop_markets"));
  $("t-certified").textContent="0";
  $("t-research-age").textContent=currentAge===null?"N/A":currentAge<60?currentAge+"m":(currentAge/60).toFixed(1)+"h";
  $("t-odds-age").textContent=quoteAge===null?"N/A":quoteAge<60?quoteAge+"m":(quoteAge/60).toFixed(1)+"h";
  $("terminal-sync").textContent="Published "+dateText(d.generated_at_utc)+" · source snapshot";
  $("terminal-decision").textContent="HOLD";
  $("terminal-leagues").querySelectorAll("button").forEach(b=>{
    const a=b.dataset.league===lg;b.classList.toggle("active",a);b.setAttribute("aria-pressed",String(a));
  });
  $("terminal-tabs").querySelectorAll("button").forEach(b=>{
    const a=b.dataset.tab===terminalState.tab;b.classList.toggle("active",a);b.setAttribute("aria-selected",String(a));b.tabIndex=a?0:-1;
  });
  $("terminal-search").disabled=false;
  $("terminal-search").placeholder=lg==="all"?"Search any team or league…":"Search "+terminalLeague()[2]+" teams…";
  const parts=[],tab=terminalState.tab;
  if(tab==="all"||tab==="games")parts.push(terminalGameTable(d));
  if(tab==="all"||tab==="props")parts.push(terminalProps(d));
  if(tab==="all"||tab==="combos")parts.push(terminalProps(d,true));
  if(tab==="all"||tab==="sharp")parts.push(terminalAudit(d));
  const leagueTitle=terminalLeague()[2];
  const forecastCount=selected.reduce((sum,k)=>sum+(number(d.leagues?.[k]?.forecasts)||0),0);
  const status='<div class="terminal-meta"><strong>'+escapeHtml(leagueTitle)+'</strong> · '
    +escapeHtml(displayNum(tracked))+' source-listed games today · '
    +escapeHtml(String(forecastCount))+' research rule forecast rows (not certified) · '
    +'0 certified +EV · <span class="hold-text">HOLD</span></div>';
  $("terminal-body").innerHTML=status+'<div class="terminal-stack">'+parts.join("")+'</div>';
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
setInterval(refresh, 120000);
