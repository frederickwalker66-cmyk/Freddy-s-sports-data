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
    return '<article class="league-card"><div class="league-head">'
      + '<span class="league-icon" aria-hidden="true">'+icon+'</span>'
      + '<span class="league-status '+(recent?"ready":"")+'">'+status+'</span></div>'
      + '<h3>'+escapeHtml(title)+'</h3><p>'+escapeHtml(desc)+'</p>'
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
const terminalState = {league:"nba",tab:"all",compact:false,data:null};
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
  return leagueInfo.find(i=>i[0]===terminalState.league) || leagueInfo[0];
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
  const isNBA=terminalState.league==="nba";
  const gdata=Array.isArray(data.games)?data.games:[];
  const q=($("terminal-search").value||"").toLowerCase().trim();
  const filtered=isNBA?gdata.filter(g=>(g.away+" "+g.home).toLowerCase().includes(q)):[];
  const l=data.leagues?.nba||{};
  const leagueFresh=terminalAge(l.as_of_utc)!==null && terminalAge(l.as_of_utc)<=180;
  const rows=filtered.map(g=>{
    const p=number(g.pregame_home_probability_pct);
    const usable=leagueFresh&&p!==null&&p>0&&p<100;
    const homeLean=usable&&p>=50;
    const pct=usable?(homeLean?p:100-p):null;
    const lean=usable?(homeLean?g.home:g.away):"N/A";
    const hint=usable?'<div class="terminal-lean">'+escapeHtml(lean)+'<small>Rule research · uncalibrated</small><div class="terminal-bar"><span style="width:'+Math.max(0,Math.min(100,pct)).toFixed(1)+'%"></span></div></div>':'<span class="terminal-na">N/A · research stale</span>';
    return terminalRow([
      '<div class="terminal-team-cell"><strong>'+escapeHtml(g.away)+' @ '+escapeHtml(g.home)+'</strong><small>'+escapeHtml(dateText(g.start_et,{month:undefined,day:undefined,timeZoneName:undefined}))+' ET · '+escapeHtml(g.status==="post"?"FINAL":g.status==="in"?"IN PROGRESS":"PREGAME")+'</small></div>',
      hint,
      usable?'<b>'+escapeHtml(pct.toFixed(1))+'%</b> <small class="terminal-na">research only</small>':'<span class="terminal-na">N/A</span>',
      '<span class="terminal-na">N/A</span>',
      '<span class="terminal-na">N/A</span>',
      '<span class="terminal-na">N/A</span>',
      '<span class="terminal-gate-chip">HOLD</span>'
    ]);
  });
  const label=isNBA?"NBA public game slate":terminalLeague()[2]+" event-level slate unavailable in public feed";
  const subtitle=isNBA?"Research lean ≠ Champion forecast":"No verified exact-match games";
  const table=terminalTable(["Game / Start ET","Uncalibrated lean","Rule %","ML / Spread / O-U","Champion p / EV","Sharp flow / CLV","Decision"],rows.length?rows:[terminalEmptyRow(7,isNBA?"No matching NBA teams in this published slate.":"Public JSON has league research counts but no independently verified upcoming event-level slate for this sport.")]);
  return terminalBlock("Game markets · "+label,subtitle,table
    +'<div class="terminal-info">All current sportsbook lines, authenticated checkout prices and verified game-market EV: <strong>N/A</strong>. Historical or external prices are not silently reused. <a target="_blank" rel="noopener noreferrer" href="https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/v8-one-command.yml">Run game-market research ↗</a></div>');
}
function terminalProps(data,combos=false) {
  const conf=terminalGroups[terminalState.league]||{props:[],combos:[]};
  const cats=combos?conf.combos:conf.props;
  const name=combos?"Combination markets":"Player props";
  const val=data.leagues?.[terminalState.league]||{};
  const p=combos?null:data.market?.paired_prop_markets;
  let body='<div class="terminal-pill-list">'+cats.map(x=>'<span>'+escapeHtml(x)+'</span>').join('')+'</div>';
  body+='<div class="terminal-market-cards">'+[
    ['Verified exact markets',p===null?"N/A":displayNum(p),'Current executable quotes required'],
    ['Player L5 available',displayNum(val.player_last5),'Historical records, not picks'],
    ['Player L10 available',displayNum(val.player_last10),'Historical records, not probabilities']
  ].map(([lab,num,note])=>'<article><span>'+escapeHtml(lab)+'</span><strong>'+escapeHtml(num)+'</strong><small>'+escapeHtml(note)+'</small></article>').join('')+'</div>';
  body+='<div class="terminal-no-source"><strong>WATCH / HOLD — no qualified player-specific selection.</strong><p>Exact player, opponent, side, stat line, offered sportsbook price, source timestamp, active/injury status, calibrated model probability and same-game correlation are not all published together. Empty coverage is <b>N/A</b>, not a zero-percent chance.</p></div>';
  return terminalBlock(name,combos?"Correlated legs require executable joint prices":"Overs, unders and alt-lines require real offers",body);
}
function terminalAudit(data) {
  const m=data.market||{},mod=data.model||{};
  const odds=terminalAge(m.odds_receipt_utc);
  const stale=odds===null||odds>120;
  const pairs=m.paired_market_reference_current===true && !stale;
  const fields=[
    ["Champion-001","FROZEN · original executable not independently authenticated"],
    ["Odds receipt",m.odds_receipt_utc?dateText(m.odds_receipt_utc)+" · "+terminalAgeText(m.odds_receipt_utc)+" old":"N/A"],
    ["Exact market matching",pairs?"Recent research pairs only; no checkout":"N/A · stale or missing"],
    ["Price execution","N/A · no direct sportsbook checkout"],
    ["Native model probability","N/A · original frozen model unavailable"],
    ["Professional handle / tickets","N/A · no independently sourced sharp flow"],
    ["Certified EV & CLV","0 +EV selections · CLV N/A"],
    ["Stake","$0 shadow research · no wagers"]
  ];
  const grid='<div class="terminal-audit-grid">'+fields.map(([label,value])=>'<div><span>'+escapeHtml(label)+'</span><strong class="'+(/N\/A|FROZEN/.test(value)?"hold":"")+'">'+escapeHtml(value)+'</strong></div>').join('')+'</div>';
  return terminalBlock("Sharp Edge · evidence audit","Fail-closed until price + model + settlement prove value",grid
    +'<div class="terminal-info">Source state: '+escapeHtml(m.price_evidence_state||"NOT VERIFIED")
    +'. Archived quote records: '+escapeHtml(displayNum(m.archived_quotes))
    +'. Model calibration status: '+escapeHtml(mod.calibration_status||"N/A")
    +'. <a target="_blank" rel="noopener noreferrer" href="https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions">View GitHub workflow receipts ↗</a></div>');
}
function renderTerminal() {
  const d=terminalState.data;
  if(!d)return;
  const v=d.leagues?.[terminalState.league]||{};
  const age=terminalAge(v.as_of_utc);
  const n=Array.isArray(d.games)?d.games.length:null;
  $("t-games").textContent=displayNum(n);
  $("t-market-pairs").textContent=displayNum(d.market?.paired_game_markets);
  $("t-prop-pairs").textContent=displayNum(d.market?.paired_prop_markets);
  $("t-certified").textContent=displayNum(d.market?.certified_positive_ev);
  $("t-research-age").textContent=terminalAgeText(v.as_of_utc);
  $("t-odds-age").textContent=terminalAgeText(d.market?.odds_receipt_utc);
  $("terminal-sync").textContent="Published "+dateText(d.generated_at_utc)+" · static snapshot";
  $("terminal-decision").textContent=d.model?.betting_state==="HOLD"?"HOLD":"NOT CERTIFIED";
  $("terminal-leagues").querySelectorAll("button").forEach(b=>{
    const a=b.dataset.league===terminalState.league;b.classList.toggle("active",a);b.setAttribute("aria-pressed",String(a));
  });
  $("terminal-tabs").querySelectorAll("button").forEach(b=>{
    const a=b.dataset.tab===terminalState.tab;b.classList.toggle("active",a);b.setAttribute("aria-selected",String(a));b.tabIndex=a?0:-1;
  });
  $("terminal-search").disabled=terminalState.league!=="nba";
  $("terminal-search").placeholder=terminalState.league==="nba"?"Search NBA teams…":"NBA search only";
  const parts=[];
  const tab=terminalState.tab;
  const blockGame=terminalGameTable(d),blockProp=terminalProps(d),blockCombo=terminalProps(d,true),blockSharp=terminalAudit(d);
  if(tab==="all"||tab==="games")parts.push(blockGame);
  if(tab==="all"||tab==="props")parts.push(blockProp);
  if(tab==="all"||tab==="combos")parts.push(blockCombo);
  if(tab==="all"||tab==="sharp")parts.push(blockSharp);
  const lTitle=terminalLeague()[2],lcount=displayNum(v.forecasts);
  const header='<div class="terminal-meta"><strong>'+escapeHtml(lTitle)+'</strong> · '+escapeHtml(lcount)+' uncalibrated research-rule forecasts · '+escapeHtml(age!==null&&age<=180?"recent research":"archived or unsynced research")+' · no certified +EV</div>';
  $("terminal-body").innerHTML=header+'<div class="terminal-stack">'+parts.join("")+'</div>';
}
function updateTerminal(data){
  terminalState.data=data;
  if(!$("terminal-leagues").dataset.ready){
    $("terminal-leagues").innerHTML=leagueInfo.map(([k,emoji,name])=>'<button type="button" data-league="'+escapeHtml(k)+'">'+emoji+' '+escapeHtml(name)+'</button>').join("");
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
