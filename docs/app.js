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
refresh();
setInterval(refresh, 120000);
