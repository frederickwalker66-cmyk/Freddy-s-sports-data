"""Research-only TikTok strategy filters. No changes to frozen Champion-001."""
from dataclasses import dataclass
from math import prod
from typing import Optional

@dataclass(frozen=True)
class ThreePointCandidate:
    player: str
    opponent: str
    line: float
    last5_hits: int
    last10_hits: int
    last5_games: int
    last10_games: int
    opponent_3pm_allowed_rank: Optional[int]  # 1 = most allowed
    player_3pm_rank: Optional[int]  # 1 = most made
    minutes_verified: bool
    injury_verified: bool
    odds_american: Optional[int] = None
    native_probability: Optional[float] = None
    odds_timestamp: Optional[str] = None
    source: Optional[str] = None
    dfs_ownership_percent: Optional[float] = None

def implied_probability(odds: int) -> float:
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    return (-odds)/(-odds+100) if odds < 0 else 100/(odds+100)

def evaluate(c: ThreePointCandidate) -> dict:
    if not (0 <= c.last5_hits <= c.last5_games <= 5 and 0 <= c.last10_hits <= c.last10_games <= 10):
        raise ValueError("Invalid historical hit counts")
    if c.native_probability is not None and not 0 <= c.native_probability <= 1:
        raise ValueError("Invalid model probability")
    rate5 = c.last5_hits / c.last5_games if c.last5_games else None
    rate10 = c.last10_hits / c.last10_games if c.last10_games else None
    defense_match = c.opponent_3pm_allowed_rank is not None and c.opponent_3pm_allowed_rank <= 10
    shooter_match = c.player_3pm_rank is not None and c.player_3pm_rank <= 10
    historical_90 = c.last10_games == 10 and c.last10_hits >= 9
    market_ready = c.odds_american is not None and bool(c.odds_timestamp) and bool(c.source)
    evidence_ready = defense_match and shooter_match and c.minutes_verified and c.injury_verified
    p = c.native_probability
    implied = implied_probability(c.odds_american) if market_ready else None
    ev = (p / implied - 1) if p is not None and implied is not None else None
    # Research filter only: independent certified model and data quality gates are required.
    decision = "HOLD"
    if market_ready and evidence_ready and p is not None and ev is not None:
        decision = "TAKE" if ev > 0 and historical_90 else "PASS"
    return dict(player=c.player, opponent=c.opponent, line=c.line,
                last5_rate=rate5, last10_rate=rate10, historical_90=historical_90,
                defense_top10=defense_match, shooter_top10=shooter_match,
                dfs_ownership_percent=c.dfs_ownership_percent,
                implied_probability=implied, native_probability=p,
                expected_roi=ev, decision=decision,
                certification="UNCERTIFIED_RESEARCH_ONLY")

def parlay_independent_probability(probabilities):
    """Illustrative only; correlated legs require joint distribution."""
    if any(p is None or p < 0 or p > 1 for p in probabilities):
        return None
    return prod(probabilities)
