"""Read-only, fail-closed latest source-observed season L5/L10 dashboard.

No external data collection here. Reads completed GitHub season snapshot
artifacts, never derives prop probabilities or calls sportsbook endpoints.
Partial source days and failed player vectors remain explicit missing data.
"""
from __future__ import annotations
import json
from pathlib import Path
from historical_outcomes import LEAGUES
from v8_all_sports_season_form import season_anchor

LIMIT_BYTES=65_000_000


def _read(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>LIMIT_BYTES:
        raise ValueError("season_artifact_missing_or_oversized")
    return json.loads(path.read_text(encoding="utf-8"))


def review(root):
    root=Path(root)
    results={}
    for lg in LEAGUES:
        folder=root/lg
        if not folder.is_dir():
            results[lg]={"status":"NOT_YET_COLLECTED",
                         "season_source_coverage_complete":False,
                         "team_last5_complete":0,"team_last10_complete":0,
                         "player_last5_complete":0,"player_last10_complete":0}
            continue
        try:
            score=_read(folder/"SEASON_COVERAGE.json")
            team=_read(folder/"TEAM_LAST5_LAST10.json")
            player=_read(folder/"player_boxes"/"PLAYER_BOX_COVERAGE.json")
            stats=_read(folder/"player_boxes"/"PLAYER_LAST5_LAST10.json")
            if (any(v.get("league")!=lg for v in (score,team,player,stats))
                    or any(v.get("champion_001_modified") is not False
                           for v in (score,team,player,stats))
                    or any(v.get("certified_positive_ev_bets")!=0
                           for v in (score,team,player,stats))
                    or score["source_days_confirmed_total"]>
                       score["source_days_expected"]
                    or stats.get("bookmaker_prop_price_and_player_crosswalk_verified")
                           is not False):
                raise ValueError("season_artifact_claims_untrusted")
            teams=team["teams"]
            if not isinstance(teams,dict):
                raise ValueError("season_teams_not_object")
            results[lg]={
                "status":("SCORES_AND_PLAYER_SOURCE_COMPLETE" if
                          score["source_coverage_complete"]
                          and player["player_boxscore_event_coverage_complete"]
                          else "INCOMPLETE_SOURCE_COVERAGE"),
                "season_anchor_not_official_opening_date":
                    score["conservative_collection_anchor_et"],
                "source_days_confirmed":score["source_days_confirmed_total"],
                "source_days_expected":score["source_days_expected"],
                "published_score_final_games":score["retained_published_final_results"],
                "regular_season_teams_observed":team["teams_in_published_history"],
                "team_last5_complete":sum(x["last5"]["complete_window"]
                                           for x in teams.values()),
                "team_last10_complete":sum(x["last10"]["complete_window"]
                                            for x in teams.values()),
                "player_boxscore_games":player["regular_season_boxscore_events_with_player_rows"],
                "players_observed":stats["player_ids_observed"],
                "player_last5_complete":stats["players_with_complete_last5"],
                "player_last10_complete":stats["players_with_complete_last10"],
                "source_days_full":score["source_coverage_complete"],
                "player_boxscore_events_full":
                    player["player_boxscore_event_coverage_complete"],
                "market_line_settlement_and_pricing_verified":False,
                "independently_calibrated_model_features":False,
            }
        except (ValueError,KeyError,TypeError,AttributeError,OSError) as exc:
            results[lg]={"status":"HOLD_INVALID_OR_MISSING_SAVED_SEASON_ARTIFACT",
                         "source_error_class":type(exc).__name__,
                         "team_last5_complete":0,"team_last10_complete":0,
                         "player_last5_complete":0,"player_last10_complete":0}
    return {
        "report_type":"FREDDY_V8_EIGHT_LEAGUE_SEASON_L5_L10_SOURCE_COVERAGE",
        "by_league":results,
        "complete_leagues":sum(x["status"]=="SCORES_AND_PLAYER_SOURCE_COMPLETE"
                               for x in results.values()),
        "independently_certified_player_prop_expected_values":0,
        "independently_certified_game_prop_expected_values":0,
        "independent_bookmaker_price_and_line_receipts":0,
        "season_day_anchors_are_conservative_not_official_openers":True,
        "champion_001_modified":False,"certified_positive_ev_bets":0,
    }
