"""#111-115: fail-closed SportsDataIO quantitative-field trust inventory.

A successful HTTP fetch validates transport/schema, NOT real-data entitlement.
Official SportsDataIO says Free Trial and Dev Key feeds can scramble scores,
stats and odds while retaining schedule/team/player identities. This module
never tries to reverse-engineer scores, never discovers the secret/key tier,
and never promotes publisher payloads to native Challenger model features.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import re

DOC_URL = "https://sportsdata.io/help/scrambled-data"
SOURCE_STATUS = "provider_numeric_data_unverified_may_be_scrambled"
SCHEDULE_STATUS = "provider_schedule_identity_candidate_not_independently_matched"
MAX_DEPTH = 8
MAX_SCALARS = 50000
MAX_TEXT = 8192
SUSPECT_TOKENS = (
    "score","point","stat","rebound","assist","goal","hit","run","yard",
    "rating","percent","percentage","probability","odds","price","line",
    "total","spread","over","under","payout","money","projection","fantasy",
    "minute","second","period","quarter","possession","turnover","streak",
    "rank","win","loss","draw","xg","expected","strikeout","walk","save",
    "shot","fieldgoal","free throw","freethrow","threepoint",
)
ID_FIELDS = ("GameID", "HomeTeam", "AwayTeam", "DateTimeUTC",
             "DateTime", "HomeTeamID", "AwayTeamID")


def inventory(payload):
    """Inventory names/shape only. Never return potentially scrambled values."""
    if not isinstance(payload,dict):
        raise ValueError("sportsdataio_game_payload_not_an_object")
    queue=[(payload,0)]
    fields=Counter()
    numeric_fields=Counter()
    numeric_count=0
    items=0
    while queue:
        obj,depth=queue.pop()
        if depth>MAX_DEPTH:
            raise ValueError("overly_nested_sportsdataio_data")
        if isinstance(obj,dict):
            if len(obj)>250:
                raise ValueError("unbounded_sportsdataio_object")
            for key,val in obj.items():
                if not isinstance(key,str) or len(key)>128:
                    raise ValueError("unsafe_provider_field_name")
                fields[key]+=1
                queue.append(((key,val),depth+1))
        elif isinstance(obj,list):
            if len(obj)>10000:
                raise ValueError("unbounded_sportsdataio_array")
            queue.extend((x,depth+1) for x in obj)
        elif isinstance(obj,tuple) and len(obj)==2 and isinstance(obj[0],str):
            key,val=obj
            # Numeric GameID / TeamIDs are identifiers, NOT safely validated stats.
            if type(val) in (int,float) and key not in ID_FIELDS:
                numeric_count+=1
                numeric_fields[key]+=1
            queue.append((val,depth+1))
        elif isinstance(obj,str):
            if len(obj)>MAX_TEXT:
                raise ValueError("oversized_sportsdataio_string")
            items+=1
        elif type(obj) in (int,float,bool) or obj is None:
            items+=1
        else:
            raise ValueError("unexpected_sportsdataio_value")
        if items>MAX_SCALARS:
            raise ValueError("unbounded_sportsdataio_payload")
    labels=sorted(k for k in numeric_fields if any(
        token in re.sub(r"[^a-z0-9]","",k.casefold()) for token in SUSPECT_TOKENS
    ))
    # Only names are exposed; never emit the provider's numerical values.
    return {
        "raw_field_count":sum(fields.values()),
        "numeric_non_identifier_values_present":numeric_count,
        "numeric_field_names_research_only":sorted(numeric_fields),
        "score_stats_odds_related_numeric_names":labels,
    }


def classify_record(record):
    if (not isinstance(record,dict)
            or record.get("source")!="sportsdataio"
            or record.get("league") not in (
                "nba","nfl","mlb","nhl","ncaaf","ncaab","mls")
            or record.get("qualified_for_challenger_backtest") is not False
            or record.get("certified_prediction") is not False
            or record.get("champion_001_modified") is not False):
        raise ValueError("unsafe_source_or_model_promotion")
    payload=record.get("provider_payload")
    details=inventory(payload)
    candidate_fields=[key for key in ("GameID","HomeTeam","AwayTeam",
                                       "DateTimeUTC","DateTime")
                      if key in payload and payload[key] is not None]
    # Even Schedule candidates require clock/team crosswalk to ESPN/NBA before use.
    # No numeric provider score/stat/odds is trusted without external audit.
    return {
        "league":record["league"],
        "schedule_identity_candidate_fields_present":candidate_fields,
        "schedule_identity_status":SCHEDULE_STATUS,
        "quantitative_field_source_status":SOURCE_STATUS,
        "observed_numeric_nonidentifier_values":details[
            "numeric_non_identifier_values_present"],
        "observed_score_stats_odds_numeric_names":details[
            "score_stats_odds_related_numeric_names"],
        "original_provider_payload_preserved_separately":True,
        "provider_account_license_or_real_data_tier_authenticated":False,
        "data_source_ok_for_training":False,
        "stats_ok_for_native_model_features":False,
        "odds_ok_for_verified_ev":False,
        "qualified_for_challenger_backtest":False,
        "certified_prediction":False,
        "bet_ready":False,
        "champion_001_modified":False,
    }


def summarize(records):
    if not isinstance(records,list):
        raise ValueError("expected_list_of_validated_provider_records")
    leagues=Counter()
    uncertain=Counter()
    numeric=0
    schedule=0
    for r in records:
        item=classify_record(r)
        lg=item["league"]
        leagues[lg]+=1
        numeric+=item["observed_numeric_nonidentifier_values"]
        uncertain[lg]+=int(item["observed_numeric_nonidentifier_values"]>0)
        schedule+=int(len(item["schedule_identity_candidate_fields_present"])>=3)
    return {
        "stage":"challenger_115_sportsdataio_ingestion_provider_quality_quarantine",
        "research_records_checked":sum(leagues.values()),
        "by_league":dict(sorted(leagues.items())),
        "records_with_unverified_numeric_fields_by_league":dict(sorted(uncertain.items())),
        "numeric_non_identifier_values_not_authenticated_for_models":numeric,
        "schedule_identity_candidates_present_not_independently_matched":schedule,
        "provider_quantitative_data_status":SOURCE_STATUS,
        "provider_schedule_candidate_status":SCHEDULE_STATUS,
        "documentation_url":DOC_URL,
        "provider_key_plan_independently_known":False,
        "provider_real_unscrambled_data_entitlement_authenticated":False,
        "original_raw_provider_values_retained_for_debugging":True,
        "new_training_eligible_rows":0,
        "new_certified_challenger_predictions":0,
        "new_certified_champion_predictions":0,
        "verified_direct_draftkings_checkout_prices":0,
        "positive_ev_selections":0,
        "automated_wagers_placed":0,
        "champion_001_modified":False,
        "release_decision":"PROVIDER_QUANTITATIVE_SOURCE_NOT_AUTHENTICATED",
    }
