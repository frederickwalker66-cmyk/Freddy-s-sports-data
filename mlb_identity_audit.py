"""Read-only MLB candidate ID reconciliation; NEVER certify SharpAPI IDs.

Exact name+team matching provides manual-review candidates, not independent
proof that provider ID and official MLB ID represent the same person.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import unicodedata


def norm(value):
    if not isinstance(value, str):
        return ""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def valid_id(x):
    return not isinstance(x, bool) and isinstance(x, (int, str)) and bool(str(x).strip())


def build_roster_index(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("teams"), list):
        raise ValueError("missing MLB team roster evidence")
    by_name = {}
    for team in payload["teams"]:
        if not isinstance(team, dict) or not norm(team.get("team_name")):
            raise ValueError("invalid MLB team roster evidence")
        name = norm(team["team_name"])
        for player in team.get("players", []):
            pid = player.get("official_player_id") if isinstance(player, dict) else None
            pname = norm(player.get("player_name")) if isinstance(player, dict) else ""
            if not pname or not valid_id(pid):
                continue
            by_name.setdefault(pname, []).append({
                "team_name": team["team_name"],
                "official_team_id": team.get("team_id"),
                "official_player_id": pid, "player_name": player["player_name"],
                "source_url": team.get("source_url")})
    return by_name


def reconcile(odds, roster_evidence):
    index = build_roster_index(roster_evidence)
    candidates = []
    reasons = Counter()
    counts = Counter()
    for row in odds:
        if not isinstance(row, dict) or row.get("league") != "mlb" or row.get("is_player_prop") is not True:
            continue
        counts["mlb_player_prop_records"] += 1
        pname = norm(row.get("player_name"))
        if not pname:
            reasons["missing_player_name"] += 1
            continue
        if not valid_id(row.get("player_id")):
            reasons["missing_provider_player_id"] += 1
            continue
        opponents = {norm(row.get("home_team")), norm(row.get("away_team"))}
        if not all(opponents):
            reasons["missing_event_teams"] += 1
            continue
        found = [p for p in index.get(pname, []) if norm(p["team_name"]) in opponents]
        # A candidate is ambiguous unless exactly one official player matches.
        if len(found) == 0:
            reasons["no_exact_official_match_in_game"] += 1
        elif len(found) > 1:
            reasons["ambiguous_official_match"] += 1
        else:
            p = found[0]
            candidates.append({"event_id": row.get("event_id"),
                               "provider_player_id": str(row["player_id"]),
                               "official_player_id_candidate": p["official_player_id"],
                               "official_team_id": p["official_team_id"],
                               "player_name": p["player_name"],
                               "official_team_name": p["team_name"],
                               "odds_timestamp": row.get("timestamp"),
                               "source_url": p["source_url"],
                               "status": "manual_review_required_not_verified"})
    counts["exact_match_review_candidates"] = len(candidates)
    counts["unresolved_prop_records"] = counts["mlb_player_prop_records"] - len(candidates)
    return {"mode": "mlb_official_id_research_crosswalk_candidates",
            "counts": dict(counts),
            "reasons": dict(sorted(reasons.items())),
            "candidates": candidates,
            "crosswalk_independently_verified": False,
            "bet_ready_selections": 0,
            "certified_champion_001_predictions": 0,
            "champion_001_modified": False}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--odds", required=True)
    p.add_argument("--mlb-rosters", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args(argv)
    roster = json.loads(Path(a.mlb_rosters).read_text(encoding="utf-8"))
    with Path(a.odds).open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    result = reconcile(rows, roster)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"counts": result["counts"], "reasons": result["reasons"],
                      "crosswalk_independently_verified": False,
                      "bet_ready_selections": 0}, indent=2))


if __name__ == "__main__":
    main()
