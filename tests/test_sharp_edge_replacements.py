from datetime import datetime, timedelta, timezone
from research.sharp_edge_replacements import Candidate, evaluate, replace_passes

NOW = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)


def candidate(**overrides):
    values = dict(selection_id="prop-a", market="assists_over", american_odds=-110,
                  model_probability=.60, model_id="Champion-001",
                  model_verified=True, odds_verified=True,
                  odds_timestamp=NOW-timedelta(minutes=2),
                  evaluation_timestamp=NOW, injury_verified=True,
                  matchup_verified=True, minutes_verified=True,
                  calibrated=True, correlation_group="game-a")
    values.update(overrides)
    return Candidate(**values)


def test_verified_take():
    result = evaluate(candidate())
    assert result["decision"] == "TAKE"
    assert result["ev"] > .03


def test_no_native_probability_means_hold():
    assert evaluate(candidate(model_verified=False))["decision"] == "HOLD"
    assert evaluate(candidate(model_probability=None))["decision"] == "HOLD"
    assert evaluate(candidate(model_id="market_implied"))["decision"] == "HOLD"


def test_stale_odds_and_started_game_hold():
    assert evaluate(candidate(odds_timestamp=NOW-timedelta(minutes=30)))["decision"] == "HOLD"
    assert evaluate(candidate(game_started=True))["decision"] == "HOLD"


def test_negative_edge_pass():
    assert evaluate(candidate(model_probability=.40))["decision"] == "PASS"


def test_only_replaces_pass_with_take():
    original = [{"selection_id": "bad-a", "decision": "PASS"},
                {"selection_id": "lean-b", "decision": "LEAN"}]
    output = replace_passes(original, [candidate(), candidate(selection_id="prop-b",
                            model_verified=False, correlation_group="game-b")])
    assert output["board"][0]["selection_id"] == "prop-a"
    assert output["board"][0]["decision"] == "TAKE"
    assert output["board"][1]["selection_id"] == "lean-b"
    assert output["betting_status"].startswith("HOLD")


def test_no_forced_filler_and_correlation_block():
    original = [{"selection_id": "bad-a", "decision": "PASS"},
                {"selection_id": "bad-b", "decision": "PASS"}]
    output = replace_passes(original, [candidate()])
    assert output["board"][0]["decision"] == "TAKE"
    assert output["board"][1]["decision"] == "HOLD"
    assert output["board"][1]["replacement_pending"] is True


def test_existing_correlated_leg_blocks_candidate():
    original = [{"selection_id": "bad-a", "decision": "PASS"},
                {"selection_id": "existing", "decision": "LEAN", "correlation_group": "game-a"}]
    output = replace_passes(original, [candidate()])
    assert output["board"][0]["decision"] == "HOLD"
