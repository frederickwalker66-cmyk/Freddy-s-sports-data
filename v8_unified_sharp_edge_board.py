"""Single all-sports, all-market V8 Sharp Edge view from already vetted research.

Never convert archived prices, forecasts, or historical hit rates into certified
Champion-001 probabilities or independently verified expected value.
No network calls, wagers, paid provider actions or model changes are made.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import math
from pathlib import Path

LEAGUES = ("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls", "uefa_champions_league")
COMBOS = {
    "player_points_+_rebounds": "PR",
    "player_points_+_assists": "PA",
    "player_rebounds_+_assists": "RA",
    "player_points_+_rebounds_+_assists": "PRA",
    "player_points+rebounds": "PR",
    "player_points+assists": "PA",
    "player_rebounds+assists": "RA",
    "player_points+rebounds+assists": "PRA",
    "player_passing_+_rushing_yards": "Pass+Rush yards",
    "player_rushing_+_receiving_yards": "Rush+Receive yards",
}
FIELDS = ("Sport", "Game", "Player", "Category", "Market / side", "Line",
          "Book label", "Odds", "Source time UTC", "Age min",
          "Research p%", "Champion p%", "No-vig market %", "Break-even %",
          "Sharp edge pp", "EV ROI%", "Sharp handle %", "CLV%", "Status")


def _num(v):
    return v if type(v) in (int, float) and math.isfinite(v) else None


def _pct(v, *, fraction=False):
    x = _num(v)
    if x is None:
        return None
    x = x * 100 if fraction else x
    return round(x, 2) if 0 <= x <= 100 else None


def _break_even(odds):
    x = _num(odds)
    if x is None or abs(x) < 100:
        return None
    return round(100 * (-x / (100 - x) if x < 0 else 100 / (100 + x)), 2)


def _age(at, clock):
    if not isinstance(at, str):
        return None
    try:
        t = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        return None
    minutes = (clock - t.astimezone(timezone.utc)).total_seconds() / 60
    return round(minutes, 1) if minutes >= 0 else None


def _base(league, game, *, player=None, category=None, market=None,
          selection=None, line=None, odds=None, source=None, at=None, now=None,
          research=None, no_vig=None, break_even=None, note=""):
    # Native certified probability/edge/EV fields deliberately remain None.
    return {
        "league": league, "game": game, "player": player,
        "category": category, "market": market, "selection": selection,
        "line": line, "source_book_label": source,
        "american_odds": odds, "source_timestamp_utc": at,
        "source_age_minutes": _age(at, now) if now is not None else None,
        "research_model_probability_percent": _pct(research),
        "verified_champion_001_probability_percent": None,
        "no_vig_market_probability_percent": _pct(no_vig),
        "break_even_probability_percent": (_pct(break_even) if break_even is not None
                                           else _break_even(odds)),
        "sharp_edge_percentage_points": None, "expected_roi_percent": None,
        "verified_sharp_handle_percent": None, "verified_clv_percent": None,
        "source_class": "research_only_unverified_checkout",
        "decision": "HOLD", "notes": note,
    }


def _is_combo(stat):
    if stat in COMBOS:
        return True
    return False


def _valid(bundle):
    if (not isinstance(bundle, dict)
            or bundle.get("champion_001_modified") is not False
            or bundle.get("certified_positive_ev_bets") != 0):
        raise ValueError("unified_board_requires_uncertified_frozen_source")
    scope = bundle.get("requested_leagues")
    if (not isinstance(scope, list) or not scope
            or any(lg not in LEAGUES for lg in scope)
            or len(scope) != len(set(scope))):
        raise ValueError("unified_board_invalid_league_scope")
    return scope


def build(bundle):
    """Every eligible source market side, forecast and NBA fixture in one table."""
    scope = _valid(bundle)
    now = datetime.fromisoformat(bundle["checked_at_utc"].replace("Z", "+00:00"))
    if now.tzinfo is None:
        raise ValueError("unified_board_invalid_clock")
    now = now.astimezone(timezone.utc)
    sharp = bundle.get("sharp_edge_research") or {}
    rows = []
    games = sharp.get("research_only_game_line_examples") or []
    props = sharp.get("research_only_player_market_examples") or []
    forecasts = bundle.get("research_only_pregame_predictions") or []
    if any(not isinstance(x, list) or len(x) > 20000
           for x in (games, props, forecasts)):
        raise ValueError("unified_board_source_budget_exceeded")

    for g in games:
        if not isinstance(g, dict) or g.get("league") not in scope:
            raise ValueError("unified_board_invalid_game_quote")
        lg = g["league"]
        match = str(g.get("away_team") or "?") + " @ " + str(g.get("home_team") or "?")
        if "paired_primary_markets" in g:
            if g.get("verified_sportsbook_checkout") is not False:
                raise ValueError("unified_board_game_checkout_claim")
            for market, q in sorted(g["paired_primary_markets"].items()):
                if (not isinstance(q, dict)
                        or q.get("bookmaker_checkout_price_verified") is not False
                        or q.get("native_model_probability_verified") is not False):
                    raise ValueError("unified_board_untrusted_game_pair")
                if market not in ("moneyline", "point_spread", "total_points"):
                    raise ValueError("unified_board_unknown_game_market")
                labels = ("over", "under") if market == "total_points" else ("home", "away")
                for n, side in enumerate(labels):
                    prefix = "first" if n == 0 else "second"
                    name = (side.upper() if market == "total_points"
                            else str(g.get("home_team") if n == 0 else g.get("away_team")))
                    rows.append(_base(
                        lg, match, category=market.upper().replace("_", " "),
                        market=market, selection=name,
                        line=q.get("home_or_over_line" if n == 0 else "away_or_under_line"),
                        odds=q.get("home_or_over_odds" if n == 0 else "away_or_under_odds"),
                        source="DraftKings-labelled SharpAPI archive",
                        at=q.get("provider_quote_utc"), now=now,
                        no_vig=q.get(prefix+"_side_no_vig_market_percent"),
                        break_even=q.get(prefix+"_side_break_even_percent"),
                        note="Original provider-event identity and executable price not independently verified."))
        else:
            if (g.get("bookmaker_checkout_price_verified") is not False
                    or g.get("independent_model_probability_verified") is not False):
                raise ValueError("unified_board_untrusted_soccer_pair")
            odds=g.get("american_odds_by_outcome") or {}
            shares=g.get("normalized_no_vig_market_shares") or {}
            if set(odds) != set(shares) or set(odds) not in (
                    {"home","draw","away"}, {"over","under"}):
                raise ValueError("unified_board_soccer_missing_outcomes")
            for side in ("home", "draw", "away", "over", "under"):
                if side not in odds:
                    continue
                rows.append(_base(
                    lg, match, category=("SOCCER 1X2" if side in ("home", "draw", "away")
                                         else "TOTALS"),
                    market=g.get("market"), selection=side.upper(),
                    line=g.get("goal_total_line"), odds=odds[side],
                    source="DraftKings-labelled SharpAPI archive",
                    at=g.get("provider_quote_utc"), now=now,
                    no_vig=_pct(shares[side], fraction=True),
                    note="Soccer 90-minute settlement scope and checkout not independently verified."))

    for p in props:
        if not isinstance(p, dict) or p.get("league") not in scope:
            raise ValueError("unified_board_invalid_prop")
        if (p.get("player_identity_independently_verified") is not False
                or p.get("active_player_independently_verified") is not False
                or p.get("bet_ready") is not False):
            raise ValueError("unified_board_prop_unverified_identity_promotion")
        lg=p["league"]
        stat=str(p.get("prop_stat") or "unknown")
        category="COMBO" if _is_combo(stat) else "PLAYER PROP"
        match=str(p.get("away_team") or "?")+" @ "+str(p.get("home_team") or "?")
        for side in ("over", "under"):
            prefix="first" if side == "over" else "second"
            rows.append(_base(
                lg, match, player=p.get("player_name"), category=category,
                market=COMBOS.get(stat, stat), selection=side.upper(),
                line=p.get("line"), odds=p.get(side+"_american_odds"),
                source="DraftKings-labelled SharpAPI archive",
                at=p.get("last_capture_utc"), now=now,
                no_vig=p.get(prefix+"_side_no_vig_market_percent"),
                break_even=p.get(prefix+"_side_break_even_percent"),
                note="Source player/team assignment, current availability and checkout not verified."))

    for f in forecasts:
        if not isinstance(f, dict) or f.get("league") not in scope:
            raise ValueError("unified_board_invalid_research_forecast")
        if (f.get("native_Champion_001_model_probability") is not None
                or f.get("market_specific_verified_expected_value") is not None
                or f.get("verified_live_sportsbook_quote") is not False):
            raise ValueError("unified_board_untrusted_forecast_promotion")
        lg=f["league"]
        match=str(f.get("away_team") or "?")+" @ "+str(f.get("home_team") or "?")
        note=("Uncalibrated independent research only; no matched market price."
              + (" NFL p is conditional on no tie." if lg == "nfl" else "")
              + (" NHL regulation/OT settlement unverified." if lg == "nhl" else ""))
        for side in ("home", "away"):
            p=f.get(side+"_win_research_rule_probability")
            if _num(p) is not None:
                rows.append(_base(
                    lg, match, category="RESEARCH FORECAST",
                    market="home/away win (research only)", selection=side.upper(),
                    source="Uncalibrated research rule, NOT Champion-001",
                    at=f.get("original_forecast_recorded_utc"), now=now,
                    research=_pct(p,fraction=True), note=note))

    # NBA original scheduled events remain visible when no quote is available.
    for fixture in bundle.get("research_game_schedule") or []:
        if not isinstance(fixture, dict) or fixture.get("league") not in scope:
            raise ValueError("unified_board_invalid_fixture")
        match=str(fixture.get("away_team") or "?")+" @ "+str(fixture.get("home_team") or "?")
        if fixture.get("league")=="nba":
            rows.append(_base(
                "nba",match,category="SCHEDULE",
                market="Game fixture (not a priced selection)",
                source="ESPN date-scoped schedule research", now=now,
                at=fixture.get("source_timestamp_utc"),
                note="Official active roster and exact betting markets unavailable or separate."))

    covered={r["league"] for r in rows}
    for lg in scope:
        if lg not in covered:
            rows.append(_base(
                lg,"No eligible source markets",category="COVERAGE",
                market="No independently validated current quote / player prop",
                now=now,note="No price is not a 0% event probability. Check collector coverage."))
    if len(rows) > 50000:
        raise ValueError("unified_board_result_budget_exceeded")
    rank={lg:i for i,lg in enumerate(LEAGUES)}
    rows.sort(key=lambda x:(rank[x["league"]],x["game"],x["category"] or "",
                            x["player"] or "",x["market"] or "",x["selection"] or ""))
    byleague={lg:Counter(r["category"] for r in rows if r["league"]==lg)
              for lg in scope}
    return {
        "report_type":"FREDDYS_V8_ONE_DISPLAY_ALL_MARKETS_RESEARCH_ONLY",
        "command":bundle.get("user_command"),
        "checked_at_utc":now.isoformat(), "requested_leagues":scope,
        "displayed_rows":len(rows), "rows":rows,
        "category_counts_by_league":{lg:dict(by_league[lg]) for lg in scope},
        "independently_verified_champion_probability_rows":0,
        "certified_positive_ev_bets":0,"champion_001_modified":False,
        "qualified_sharp_handle_rows":0, "verified_entry_close_clv_rows":0,
        "betting_decision":"PASS_NO_CERTIFIED_EDGE_HOLD_ALL_UNVERIFIED_MARKETS",
        "source_scope":"Only supported, received and parsed archived markets; never all bookmaker markets or all active players.",
        "notice":"No-vig and break-even % are sportsbook PRICE mathematics, not native model predictions. Research p is uncalibrated and may not match a priced market. N/A never means 0%.",
    }


def _cell(v, kind=None):
    x=_num(v)
    if x is None:
        return "N/A" if v is None else str(v).replace("|","/").replace("\n"," ")[:120]
    if kind=="percent":
        return f"{x:.2f}%"
    if kind=="pp":
        return f"{x:+.2f} pp"
    return str(int(x)) if x == int(x) else str(x)


def _table(r):
    return [
        r["league"].upper(),r["game"],r["player"],r["category"],
        (str(r["market"] or "")+" / "+str(r["selection"] or "")).strip(" /"),
        r["line"],r["source_book_label"],r["american_odds"],
        r["source_timestamp_utc"],r["source_age_minutes"],
        _cell(r["research_model_probability_percent"],"percent"),
        _cell(r["verified_champion_001_probability_percent"],"percent"),
        _cell(r["no_vig_market_probability_percent"],"percent"),
        _cell(r["break_even_probability_percent"],"percent"),
        _cell(r["sharp_edge_percentage_points"],"pp"),
        _cell(r["expected_roi_percent"],"percent"),
        _cell(r["verified_sharp_handle_percent"],"percent"),
        _cell(r["verified_clv_percent"],"percent"),r["decision"]]


def render_markdown(board, limit=None):
    lines=[
        "# Freddy's Picks V8 — ONE DISPLAY / SHARP EDGE",
        "**All sports · All available game markets · Player props · Combos · EV & probabilities**",
        f"**Command:** {board.get('command')} · **As of:** {board['checked_at_utc']}",
        "**Certified positive-EV bets: 0 · Champion-001 probabilities: N/A · Betting decision: HOLD / PASS · Stakes: $0.**",
        f"**Source scope:** {board['source_scope']}",
        f"**Probability rule:** {board['notice']}",
        f"**Rows available:** {board['displayed_rows']}; full searchable table: ONE_DISPLAY_SHARP_EDGE.html (download from this run).",
        "",
        "| "+" | ".join(FIELDS)+" |",
        "| "+" | ".join(["---"]*len(FIELDS))+" |",
    ]
    rows=board["rows"] if limit is None else board["rows"][:limit]
    for x in rows:
        lines.append("| "+" | ".join(_cell(v) for v in _table(x))+" |")
    if limit is not None and len(board["rows"])>len(rows):
        lines.append(f"**Preview {len(rows)} of {len(board['rows'])} rows. Open ONE_DISPLAY_SHARP_EDGE.html or .json for all available markets.**")
    return "\n".join(lines)+"\n"


def render_html(board):
    """One offline searchable table with complete source-side rows, no external JS."""
    data=json.dumps(board["rows"],ensure_ascii=False,allow_nan=False)
    # Do not allow third-party provider strings to terminate the JSON script.
    safe=data.replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
    title=escape("Freddy's Picks AI V8 — All Sports Sharp Edge")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{font:14px system-ui,Arial,sans-serif;color:#15253d;background:#f5f7fa}}
body{{margin:0;padding:20px}}h1{{font-size:23px;margin:0 0 6px}}
small,.muted{{color:#45556b}}.stats{{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}}
.stat{{background:white;border:1px solid #d3dbe7;border-radius:9px;padding:10px 14px}}
.stat b{{display:block;font-size:19px}}.notice{{background:#fff5d9;border-left:4px solid #ae7800;padding:12px;border-radius:5px;margin:10px 0}}
.controls{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:15px 0}}
label{{display:grid;gap:4px;font-weight:600}}input,select{{font:inherit;border:1px solid #a3b1c4;border-radius:7px;padding:10px;min-height:40px;background:white}}
#search{{min-width:min(340px,85vw)}}.frame{{overflow-x:auto;border:1px solid #c7d1df;border-radius:8px;background:white;max-width:100%}}
table{{border-collapse:collapse;white-space:nowrap;font-size:12px;width:100%}}
th,td{{padding:9px 10px;border-bottom:1px solid #e5eaf0;text-align:left}}
th{{position:sticky;top:0;background:#e9eff7;z-index:1}}td.na{{color:#637188}}
tbody tr:hover{{background:#eff7ff}}.pill{{border-radius:4px;background:#fff1d0;color:#744800;padding:3px 6px;font-weight:700}}
footer{{padding:12px 0;color:#43516a}}button{{font:inherit;padding:10px;border-radius:7px;border:1px solid #92a0b5;background:white;cursor:pointer}}
</style></head><body>
<h1>Freddy's Picks AI V8 · One Sharp Edge Display</h1>
<p class="muted">Every supported sport and every eligible archived market row available to this run, in one place. Generated {escape(board['checked_at_utc'])} UTC.</p>
<div class="stats"><div class="stat">Market rows<b>{board['displayed_rows']}</b></div>
<div class="stat">Sports<b>{len(board['requested_leagues'])}</b></div>
<div class="stat">Certified +EV<b>0</b></div><div class="stat">Champion p verified<b>0</b></div></div>
<div class="notice"><b>HOLD / PASS — no independently certified Sharp Edge.</b> N/A = unavailable, not a 0% probability. Market % is price math, not a native forecast. Archived book labels are not live checkout prices. Player identity and active status are unverified.</div>
<div class="controls">
<label>Find team, game, player or line<input id="search" type="search" placeholder="Search any player, team, stat, line"></label>
<label>Sport<select id="sport"><option value="">All eight sports</option></select></label>
<label>Market<select id="market"><option value="">All markets & combos</option></select></label>
<label>Status<select id="status"><option value="">All statuses</option><option value="HOLD">HOLD</option><option value="PASS">PASS</option></select></label>
<button id="reset" type="button">Clear filters</button>
</div>
<p id="shown" aria-live="polite"></p>
<div class="frame"><table><thead><tr id="head"></tr></thead><tbody id="body"></tbody></table></div>
<footer>Scope: eligible archived snapshots, scheduled NBA research games and available forecasts. Unsupported/absent markets are clearly marked; not every currently active player or sportsbook market is in the source. No wagers and no model modifications.</footer>
<script id="dataset" type="application/json">{safe}</script>
<script>
(function(){{
'use strict';
const data=JSON.parse(document.getElementById('dataset').textContent);
const headers={json.dumps(FIELDS)};
const root=document;
const sport=root.getElementById('sport'), market=root.getElementById('market');
const status=root.getElementById('status'),search=root.getElementById('search');
const tbody=root.getElementById('body'),shown=root.getElementById('shown');
const th=root.getElementById('head');
const COLS=['league','game','player','category','market_side','line','source_book_label','american_odds','source_timestamp_utc','source_age_minutes','research_model_probability_percent','verified_champion_001_probability_percent','no_vig_market_probability_percent','break_even_probability_percent','sharp_edge_percentage_points','expected_roi_percent','verified_sharp_handle_percent','verified_clv_percent','decision'];
headers.forEach(function(s){{const cell=root.createElement('th');cell.textContent=s;th.appendChild(cell);}});
const choices=function(sel,values){{[...new Set(values)].filter(Boolean).sort().forEach(function(v){{const opt=root.createElement('option');opt.value=v;opt.textContent=v;sel.appendChild(opt);}});}};
choices(sport,data.map(x=>x.league));choices(market,data.map(x=>x.category));
function pct(v){{return typeof v==='number'?v.toFixed(2)+'%':'N/A';}}
function format(key,v){{
 if(key.endsWith('_percent')||key==='research_model_probability_percent')return pct(v);
 if(key==='sharp_edge_percentage_points')return typeof v==='number'?v.toFixed(2)+' pp':'N/A';
 if(v===null||v===undefined||v==='')return 'N/A';
 return String(v);
}}
function update(){{
 const q=search.value.toLowerCase().trim();
 const rows=data.filter(function(x){{
  return (!sport.value||x.league===sport.value)
  &&(!market.value||x.category===market.value)
  &&(!status.value||x.decision===status.value)
  &&(!q||[x.league,x.game,x.player,x.category,x.market,x.selection,String(x.line||'')].join(' ').toLowerCase().includes(q));
 }});
 tbody.replaceChildren();
 const frag=root.createDocumentFragment();
 rows.forEach(function(row){{
  const tr=root.createElement('tr');
  const item=Object.assign({{}},row,{{market_side:String(row.market||'')+' / '+String(row.selection||'')}});
  COLS.forEach(function(key){{
   const td=root.createElement('td');
   td.textContent=format(key,item[key]);
   if(item[key]==null)td.className='na';
   if(key==='decision'){{const tag=root.createElement('span');tag.className='pill';tag.textContent=item[key];td.replaceChildren(tag);}}
   tr.appendChild(td);
  }});frag.appendChild(tr);
 }});
 tbody.appendChild(frag);
 shown.textContent='Showing '+rows.length+' of '+data.length+' source rows.';
}}
[sport,market,status,search].forEach(el=>el.addEventListener('input',update));
root.getElementById('reset').addEventListener('click',function(){{sport.value='';market.value='';status.value='';search.value='';update();}});
update();
}})();
</script></body></html>"""


def save(board, directory):
    out=Path(directory)
    out.mkdir(parents=True,exist_ok=True)
    (out/"ONE_DISPLAY_SHARP_EDGE.json").write_text(json.dumps(board,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    (out/"ONE_DISPLAY_SHARP_EDGE.md").write_text(render_markdown(board),encoding="utf-8")
    (out/"ONE_DISPLAY_SHARP_EDGE_SUMMARY.md").write_text(render_markdown(board,limit=80),encoding="utf-8")
    (out/"ONE_DISPLAY_SHARP_EDGE.html").write_text(render_html(board),encoding="utf-8")
