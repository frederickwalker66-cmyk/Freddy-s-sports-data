"""NBA league-operated versus ESPN historical player boxscore research comparison.

Consumes ONLY previously quarantined NBA official-final game identity receipts.
Comparing retrospective boxscores does NOT establish player availability before
tipoff, bookmaker prop grading, independently timestamped features, or a bet.
No automatic training, forecasts, Champion modification, or sportsbook calls.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.request import Request, urlopen

from challenger_nba_player_boxes import parse_summary, SUMMARY_BASE
from challenger_nba_official_final_crosscheck import RESEARCH_STATUS
from challenger_nba_schedule_clock import nba_team_name
from challenger_prospective_outcome_validation import instant

NBA_BOX_URL = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{}.json"
MAX_GAMES = 3
MAX_BYTES = 4_000_000
MARKETS = ("points", "rebounds", "assists", "steals", "blocks")
SCHEMA = "challenger_nba_player_two_publisher_research_review_only"


def canonical(value):
    if not isinstance(value, str):
        return ""
    base = unicodedata.normalize("NFKD", value)
    clean = "".join(c for c in base if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", clean.casefold()).split())


def official_url(game_id):
    if not isinstance(game_id, str) or not re.fullmatch(r"\d{10}", game_id):
        raise ValueError("invalid_nba_official_box_game_id")
    return NBA_BOX_URL.format(game_id)


def fetch_json_bytes(url):
    if (not isinstance(url, str) or
            not (url.startswith("https://cdn.nba.com/static/json/liveData/boxscore/boxscore_")
                 and url == official_url(url.rsplit("_", 1)[-1].replace(".json", ""))
                 or url.startswith(SUMMARY_BASE) and url[len(SUMMARY_BASE):].isdigit())):
        raise ValueError("untrusted_nba_player_source_url")
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "FreddysPicksPlayerResearch/1.0",
    })
    with urlopen(req, timeout=18) as response:
        raw = response.read(MAX_BYTES+1)
    if len(raw) > MAX_BYTES:
        raise ValueError("source_exceeds_nba_boxscore_byte_limit")
    return raw


def validate_crosscheck(row, observed):
    if (not isinstance(row, dict)
            or row.get("crosscheck_status") != RESEARCH_STATUS
            or row.get("training_row_qualified") is not False
            or row.get("independent_feature_asof_verified") is not False
            or row.get("independent_source_receipt_authenticated") is not False
            or row.get("independent_bookmaker_settlement_verified") is not False
            or row.get("certified_prediction") is not False
            or row.get("bet_ready") is not False
            or row.get("champion_001_modified") is not False):
        raise ValueError("unqualified_or_invalid_nba_game_crosscheck")
    nba_id = row.get("official_nba_game_id")
    official_url(nba_id)
    eid = row.get("espn_research_event_id")
    if not isinstance(eid, str) or not eid.isdigit():
        raise ValueError("invalid_espn_game_identity")
    name_home, name_away = nba_team_name(row.get("home_team")), nba_team_name(row.get("away_team"))
    if not name_home or not name_away or name_home == name_away:
        raise ValueError("ambiguous_nba_game_teams")
    score = row.get("official_nba_score")
    if (not isinstance(score, dict) or type(score.get("home")) is not int
            or type(score.get("away")) is not int
            or not 0 <= score["home"] <= 250 or not 0 <= score["away"] <= 250
            or score["home"] == score["away"]
            or score != row.get("espn_published_score")):
        raise ValueError("nba_official_score_not_confirmed")
    checked_at = instant(row.get("source_checked_at_utc"))
    if checked_at > observed:
        raise ValueError("future_nba_game_source_check")
    return nba_id, eid, name_home, name_away


def choose_games(rows, observed, limit=MAX_GAMES):
    if (not isinstance(rows, list) or type(limit) is not int or not 1 <= limit <= MAX_GAMES
            or not isinstance(observed, datetime) or observed.tzinfo is None):
        raise ValueError("invalid_nba_player_review_plan")
    seen_e, seen_o, chosen = set(), set(), []
    for row in rows:
        if not isinstance(row, dict) or row.get("crosscheck_status") != RESEARCH_STATUS:
            continue
        nba, eid, _, _ = validate_crosscheck(row, observed)
        if nba in seen_o or eid in seen_e:
            raise ValueError("duplicate_or_conflicting_nba_game_id_crosswalk")
        seen_o.add(nba)
        seen_e.add(eid)
        chosen.append(row)
    return sorted(chosen, key=lambda x: (x["official_nba_start_utc"], x["official_nba_game_id"]),
                  reverse=True)[:limit]


def decode_source(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise ValueError("invalid_nba_original_bytes")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("invalid_nba_json_source")
    return obj


def _played(value):
    if value in ("1", 1, True):
        return True
    if value in ("0", 0, False):
        return False
    raise ValueError("nba_official_played_status_missing")


def parse_nba_official(payload, crosscheck):
    """Check the exact official game, score, team identities and player statuses."""
    if not isinstance(payload, dict) or not isinstance(payload.get("game"), dict):
        raise ValueError("nba_official_boxscore_missing_game")
    g = payload["game"]
    if (str(g.get("gameId")) != crosscheck["official_nba_game_id"]
            or g.get("gameStatus") not in (3, "3")):
        raise ValueError("nba_game_identity_or_final_status_invalid")
    result, ids = {}, set()
    for side in ("home", "away"):
        team = g.get(side+"Team")
        if not isinstance(team, dict):
            raise ValueError("nba_official_team_missing")
        team_name = nba_team_name(str(team.get("teamCity", "")) + " " +
                                  str(team.get("teamName", "")))
        if team_name != nba_team_name(crosscheck[side+"_team"]):
            raise ValueError("official_nba_team_mismatch")
        if team.get("score") != crosscheck["official_nba_score"][side]:
            raise ValueError("nba_official_boxscore_score_mismatch")
        team_id = team.get("teamId")
        if type(team_id) not in (str, int) or not str(team_id).isdigit() or str(team_id) in ids:
            raise ValueError("invalid_official_nba_team_id")
        ids.add(str(team_id))
        players = team.get("players")
        if not isinstance(players, list) or not 1 <= len(players) <= 32:
            raise ValueError("official_nba_player_array_missing_or_oversized")
        by_name, by_id = {}, set()
        for player in players:
            if not isinstance(player, dict):
                raise ValueError("invalid_nba_official_player_object")
            pid = player.get("personId")
            pn = canonical(player.get("name"))
            if (not str(pid).isdigit() or not pn or pn in by_name
                    or str(pid) in by_id):
                raise ValueError("duplicate_or_unknown_official_player_identity")
            by_id.add(str(pid))
            played = _played(player.get("played"))
            stats = player.get("statistics")
            if played and not isinstance(stats, dict):
                raise ValueError("missing_official_player_stats")
            extracted = {}
            if played:
                for m, field in (("points","points"), ("rebounds","reboundsTotal"),
                                 ("assists","assists"), ("steals","steals"), ("blocks","blocks")):
                    n = stats.get(field)
                    if type(n) is not int or not 0 <= n <= 100:
                        raise ValueError("invalid_nba_official_player_stat")
                    extracted[m] = n
            by_name[pn] = {"official_player_id": str(pid), "played": played,
                           "stats": extracted}
        result[side] = {"team_id": str(team_id), "players": by_name}
    return result


def compare_player_rows(espn, official, crosscheck):
    """Compare exact same-game same-side name only; never fill missing from odds."""
    if (not isinstance(espn, list) or not espn
            or not isinstance(official, dict)):
        raise ValueError("missing_two_source_nba_player_evidence")
    ids, output = set(), []
    by_side = {"home": {}, "away": {}}
    for row in espn:
        if not isinstance(row, dict) or row.get("event_id") != crosscheck["espn_research_event_id"]:
            raise ValueError("wrong_espn_player_game")
        pid, tid = row.get("player_id"), row.get("team_id")
        if not isinstance(pid, str) or not pid.isdigit() or not isinstance(tid, str) or not tid.isdigit():
            raise ValueError("invalid_espn_player_or_team_id")
        if pid in ids:
            raise ValueError("duplicate_espn_player_across_teams")
        ids.add(pid)
        side = None
        for s in ("home", "away"):
            if tid == crosscheck["_espn_team_ids"][s]:
                side = s
        if side is None:
            raise ValueError("espn_player_team_not_in_matchup")
        name = canonical(row.get("player_name"))
        if not name or name in by_side[side]:
            raise ValueError("missing_or_duplicate_espn_player_name")
        by_side[side][name] = row
    for side in ("home", "away"):
        for pn, e in by_side[side].items():
            matched = official[side]["players"].get(pn)
            item = {
                "record_type": SCHEMA, "league": "nba",
                "espn_event_id": crosscheck["espn_research_event_id"],
                "nba_official_game_id": crosscheck["official_nba_game_id"],
                "team_side": side, "player_name": e["player_name"],
                "espn_player_id": e["player_id"],
                "nba_official_person_id": matched["official_player_id"] if matched else None,
                "espn_did_not_play": e["did_not_play"],
                "nba_official_played": matched["played"] if matched else None,
                "espn_postgame_minutes": e["minutes"],
                "stat_agreement": None,
                "es_submitted_points": e["points"],
                "source_observation_is_postgame": True,
                "independent_pregame_player_availability_verified": False,
                "independent_pregame_minutes_projection_verified": False,
                "historical_bookmaker_prop_settlement_verified": False,
                "qualified_for_player_prop_training": False,
                "model_player_prop_probability": None,
                "certified_prediction": False, "bet_ready": False,
                "champion_001_modified": False,
            }
            if matched is None:
                status = "no_exact_cross_provider_player_name_match"
            elif e["did_not_play"] is True and matched["played"] is False:
                status = "two_source_dnp_agreement_research_only"
            elif e["did_not_play"] is not False or matched["played"] is not True:
                status = "two_source_participation_disagreement"
            else:
                disagreements = [m for m in MARKETS
                                 if type(e.get(m)) is not int or
                                 e[m] != matched["stats"][m]]
                item["stat_agreement"] = {
                    m: e[m] == matched["stats"][m] if type(e.get(m)) is int else False
                    for m in MARKETS}
                status = ("two_source_player_stats_agree_research_only"
                          if not disagreements else "two_source_player_stats_disagree")
            item["crosscheck_status"] = status
            output.append(item)
    return output


def compare_one(crosscheck, espn_bytes, nba_bytes, observed):
    validate_crosscheck(crosscheck, observed)
    a, b = decode_source(espn_bytes), decode_source(nba_bytes)
    espn_rows = parse_summary(a, crosscheck["espn_research_event_id"],
                              observed.astimezone(timezone.utc).isoformat())
    competition = a["header"]["competitions"][0]
    espn_ids = {}
    for side in ("home", "away"):
        matches = [x for x in competition["competitors"]
                   if isinstance(x, dict) and x.get("homeAway") == side]
        if len(matches) != 1:
            raise ValueError("ambiguous_espn_competitor_side")
        team = matches[0].get("team")
        if not isinstance(team, dict) or not str(team.get("id")).isdigit():
            raise ValueError("missing_espn_team_id")
        if nba_team_name(team.get("displayName")) != nba_team_name(crosscheck[side+"_team"]):
            raise ValueError("mismatched_espn_game_team")
        espn_ids[side] = str(team["id"])
    if espn_ids["home"] == espn_ids["away"]:
        raise ValueError("same_espn_team_id_both_sides")
    trusted = dict(crosscheck)
    trusted["_espn_team_ids"] = espn_ids
    official = parse_nba_official(b, crosscheck)
    rows = compare_player_rows(espn_rows, official, trusted)
    return rows


def run(crosschecks, fetcher=fetch_json_bytes, now=None, max_games=MAX_GAMES):
    now = now or datetime.now(timezone.utc)
    selected = choose_games(crosschecks, now, max_games)
    results, diagnostics, raws, reasons = [], [], {}, Counter()
    for row in selected:
        espn_id, nba_id = row["espn_research_event_id"], row["official_nba_game_id"]
        try:
            a = fetcher(SUMMARY_BASE + espn_id)
            b = fetcher(official_url(nba_id))
            compared = compare_one(row, a, b, now)
            # Preserve untouched original source bytes; never make the game
            # pass by imputing missing individual values or guessing names.
            raws[espn_id] = {"espn": a, "nba": b}
            results.extend(compared)
            status = "two_sources_parsed_for_player_review_only"
        except (ValueError, TypeError, KeyError, OSError, TimeoutError,
                json.JSONDecodeError, OverflowError, UnicodeError) as exc:
            status = "blocked_" + type(exc).__name__
        diagnostics.append({"espn_event_id": espn_id, "official_nba_game_id": nba_id,
                            "state": status})
        reasons[status] += 1
    report = {
        "stage": "challenger_nba_two_publisher_player_boxscore_review_only",
        "observed_at_utc": now.astimezone(timezone.utc).isoformat(),
        "official_nba_boxscore_source": NBA_BOX_URL,
        "espn_summary_source": SUMMARY_BASE,
        "games_checked": len(selected), "games_with_two_parseable_sources":
            reasons["two_sources_parsed_for_player_review_only"],
        "player_rows_for_manual_review": len(results),
        "statuses": dict(sorted(reasons.items())),
        "player_statuses": dict(sorted(Counter(x["crosscheck_status"] for x in results).items())),
        "game_diagnostics": diagnostics,
        "original_byte_hashes": {event: {source: hashlib.sha256(raw).hexdigest()
                                         for source, raw in files.items()}
                                for event, files in raws.items()},
        "independently_verified_pregame_player_availability": 0,
        "qualified_prop_training_observations": 0,
        "trained_player_prop_probability_models": 0,
        "certified_champion_001_predictions": 0,
        "certified_challenger_001_predictions": 0,
        "positive_ev_player_props": 0,
        "bet_ready_selections": 0, "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": ("Two retrospective boxscores can corroborate a player's result "
                    "but do NOT establish pregame injury/activity, minutes forecast, "
                    "bookmaker void/push/OT settlement, sportsbook price, "
                    "or a trained prop probability."),
    }
    return results, report, raws


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--official-crosschecks", required=True)
    p.add_argument("--output-dir", default="prospective_validation")
    p.add_argument("--max-games", type=int, default=MAX_GAMES)
    args = p.parse_args(argv)
    src = Path(args.official_crosschecks)
    if not src.is_file():
        raise FileNotFoundError("missing_nba_official_score_crosscheck_file")
    rows = [json.loads(s) for s in src.read_text(encoding="utf8").splitlines() if s.strip()]
    compared, report, originals = run(rows, max_games=args.max_games)
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    (folder/"nba_player_two_source_review.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in compared), encoding="utf8")
    (folder/"nba_player_two_source_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf8")
    if originals:
        root = folder/"nba_player_original_source_bytes"
        root.mkdir(parents=True, exist_ok=True)
        for eid, srcs in sorted(originals.items()):
            for source, raw in sorted(srcs.items()):
                file = root/(eid+"_"+source+".json")
                if file.exists():
                    raise FileExistsError("refusing_to_overwrite_nba_player_source_bytes")
                file.write_bytes(raw)
    print(json.dumps({"nba_games_reviewed": report["games_checked"],
                      "player_rows_for_manual_review": report["player_rows_for_manual_review"],
                      "qualified_prop_training_observations": 0, "certified_player_props": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
