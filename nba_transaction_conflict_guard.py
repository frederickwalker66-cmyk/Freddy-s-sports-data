"""Evidence-backed minimum NBA transaction conflicts, NOT a complete live roster.

These assertions are a conservative last-line quarantine for stale source-labeled
game/prop associations. They do not confirm any other player, availability, or
a complete roster. Refresh/change these assertions only after league evidence.
"""
from datetime import datetime, timezone

# NBA official July 10, 2026 trade and current team roster.
# https://www.nba.com/hornets/news/charlotte-hornets-acquire-naz-reid-multiple-draft-picks-from-minnesota-for-lamelo-ball-and-josh-green
# https://www.nba.com/team/1610612750/roster
# Trades may change again. This is a historical transaction guard, not a
# current-roster grant of eligibility.
KNOWN_TRANSACTION_AFTER = datetime(2026, 7, 10, tzinfo=timezone.utc)
KNOWN_TEAMS = {
    "lamelo ball": "minnesota timberwolves",
    "josh green": "minnesota timberwolves",
    "naz reid": "charlotte hornets",
    "julius randle": "brooklyn nets",
}
TEAM_ALIASES = {
    "min": "minnesota timberwolves",
    "cha": "charlotte hornets",
    "bkn": "brooklyn nets",
    "brooklyn": "brooklyn nets",
    "minnesota": "minnesota timberwolves",
    "charlotte": "charlotte hornets",
}

def normalized(value):
    if not isinstance(value, str):
        return ""
    name = " ".join(value.strip().casefold().split())
    return TEAM_ALIASES.get(name, name)

def known_transaction_conflict(player_name, home_team, away_team, start_utc):
    """Only detect definite conflicts for an observed post-trade matchup.

    Unknown player names always remain UNVERIFIED, never promoted to active.
    """
    name = normalized(player_name)
    expected = KNOWN_TEAMS.get(name)
    if not expected:
        return False
    try:
        start = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
        if start.tzinfo is None:
            return True  # Cannot establish as-of eligibility.
        if start.astimezone(timezone.utc) < KNOWN_TRANSACTION_AFTER:
            return False
    except (AttributeError, TypeError, ValueError):
        return True
    return expected not in {normalized(home_team), normalized(away_team)}
