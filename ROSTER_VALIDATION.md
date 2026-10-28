# Freddy's Picks AI — roster verification contract

**Current status (October 28, 2026):** The repository does not yet contain an automatically refreshed NBA/NFL/MLB roster feed or a verified provider-ID crosswalk. No player props are eligible for research staging without an external, independently reviewed roster manifest. Current collection remains research-only, not bet-ready. Champion-001 is unchanged.

## What is checked
- Provider player ID exists and maps to an **independent official player ID**; never presume SharpAPI's IDs are league IDs.
- Player name and league match that mapping, and the verified team is a home or away participant in the event.
- Player's verified roster status is `active` (other states are quarantined).
- The source is a league-owned NBA.com, NFL.com, or MLB.com HTTPS URL.
- The roster entry's `verified_at_utc` is within 24 hours before quote collection (not in the future).
- Missing, stale, duplicate, or conflicting mappings are quarantined.
- Roster presence DOES NOT imply game availability: lineup participation, injury reports, minutes restrictions, starting status, and individual prop listing require separate bet-time verification.

## Independent sources
- NBA: NBA.com team roster and official transaction pages, for 2026–27 season.
- NFL: NFL.com 2026 team rosters and official team transaction/injury reports.
- MLB: MLB.com active roster and official MLB Stats API `https://statsapi.mlb.com/api/v1/teams/{teamId}/roster?rosterType=active`, plus game-day lineups.

## Roster manifest input

For each independently reviewed matching player, put an item in a JSON file:
```json
{
  "players": [
    {
      "league": "nba",
      "provider_player_id": "<SharpAPI ID from an observed quote>",
      "official_player_id": "<verified NBA ID>",
      "player_name": "<verified player name>",
      "team": "<exact collector home_team or away_team name>",
      "status": "active",
      "source_url": "https://www.nba.com/<official-roster-page>",
      "verified_at_utc": "2026-10-28T20:00:00Z"
    }
  ]
}
```
This is a **schema example only**, not real roster evidence. A URL in a manifest is not proof the page was checked. Have a trusted roster ingestion/reconciliation step verify the source and ID crosswalk before creating this file.

Run research-only validation:

```sh
python challenger_audit.py --input snapshots/sharpapi_dk_<timestamp>.jsonl --schedule reviewed_events.json --rosters reviewed_rosters.json
```

No `--rosters` file? All props are quarantined. No `--schedule` file? All odds are quarantined. The scheduled GitHub workflow intentionally supplies neither file until independent ingestion exists, and asserts zero bet-ready picks.

**Still required before usable bets:** automated authoritative daily/event-time roster refresh with stable cross-provider ID reconciliation, current injury/lineup verification, independent DraftKings price verification immediately before selection, and independently generated calibrated Challenger model probabilities. The collector does not place bets.
