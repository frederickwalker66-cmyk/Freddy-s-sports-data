# Freddy's Picks AI — roster verification contract

**Current status (October 28, 2026):** A scheduled official evidence fetcher is installed, but there is still no independently verified provider-to-league player-ID crosswalk or complete live NBA/NFL/MLB roster feed. No player props are eligible for research staging without an external, independently reviewed roster manifest. Current collection remains research-only, not bet-ready. Champion-001 is unchanged.

## What is checked
- Provider player ID exists and maps to an **independent official player ID**; never presume SharpAPI's IDs are league IDs.
- Player name and league match that mapping, and the verified team is a home or away participant in the event.
- Player's verified roster status is `active` (other states are quarantined).
- The source is a league-owned NBA.com, NFL.com, or MLB.com HTTPS URL.
- The roster entry's `verified_at_utc` is within 24 hours before quote collection (not in the future).
- Missing, stale, duplicate, or conflicting mappings are quarantined.
- Roster presence DOES NOT imply game availability: lineup participation, injury reports, minutes restrictions, starting status, and individual prop listing require separate bet-time verification.
- A separate game-day status manifest must independently confirm injury clearance and active/lineup status with a current official source. Out, questionable, probable, doubtful, missing or stale statuses all fail closed.

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

## Added October 28 — game-day injury and lineup layer

`availability_validation.py` requires a separately reviewed JSON file with `players` entries containing `league`, `provider_player_id`, `event_id`, `player_name`, `team`, `source_url`, `verified_at_utc`, `injury_status` and `lineup_status`. A player's entry can pass only if:

- `injury_status = "available"`;
- `lineup_status = "confirmed_active"` for NBA/NFL, or `"confirmed_lineup"` for MLB;
- league, player ID, name, event and team all match the quote;
- the verified report timestamp is at most **2 hours old** at the odds timestamp and not in the future;
- the cited source is an official NBA.com/NFL.com/MLB.com HTTPS domain.

This file is a **manual independently reviewed manifest**, not a magically validated source. A URL string alone is not proof of source correctness. Missing independent status evidence quarantines all player props. Never infer healthy/available simply because a player is absent from an NBA or NFL injury report.

Run the full gate (still research only):
```bash
python challenger_audit.py --input snapshots/<snapshot>.jsonl \
  --schedule reviewed_events.json --rosters reviewed_rosters.json \
  --availability reviewed_game_day.json --output-dir validation_output
```

## Official-source evidence retrieval

`official_source_refresh.py` is invoked by the existing GitHub workflow. It attempts to save, in the private workflow artifact:
- the **latest same-day NBA injury report PDF**, selected from [official.nba.com](https://official.nba.com/nba-injury-report-2026-27-season/);
- active MLB rosters from `statsapi.mlb.com` for the current date;
- MLB pregame game/box-score evidence including available batting orders;
- a machine-readable `source_refresh_report.json`, including explicit partial/unavailable source statuses.

**This does not parse NBA per-player injury statuses, create NBA/NFL roster syncs, or independently verify cross-provider player IDs or game-day active players.** The NFL source remains `not_connected`. MLB rosters and batting-order snapshots are official **evidence** but are not automatically reconciled to SharpAPI IDs or cleared for wagering. The pipeline preserves zero certified picks and zero automated bets.

Official reports change during the day. A 2-hour freshness requirement for manually checked status does not replace an immediate before-bet recheck, particularly in the minutes before tipoff, kickoff or first pitch. No live betting readiness or automated bet placement is implied.

## NBA/MLB priority integration — October 28, 2026

GitHub now includes a *separate official-data collection workflow* at [Refresh official NBA and MLB source evidence](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/refresh-nba-mlb-evidence.yml). This is independent of SharpAPI quotas and does not run the odds collector. It runs on manual dispatch or a scheduled three-times-daily UTC cadence, and archives evidence for seven days.

NBA: The official injury report PDF is captured. The script also attempts the explicit 2026-27 season `stats.nba.com/stats/commonallplayers` index to obtain NBA-native player IDs and official team assignments. Network blocks or missing/incomplete data yield `nba_player_index.status = unavailable`; never treat the mere presence of a URL as a verified roster. NBA injury reports do not include all healthy players and cannot, by themselves, clear participation.

MLB: The 2026 official 30-team active roster data and available game box-score/lineup evidence are captured through `statsapi.mlb.com`. The October 28 live run 40772850855 confirmed 30/30 team rosters and one game's box-score evidence. A complete *download* does not establish a confirmed starting lineup or source-to-odds ID mapping.

Independent research audits require a reviewed player-ID crosswalk from SharpAPI to official NBA/MLB player IDs. Each per-player game-day participation check must also be explicitly reviewed, and late scratches can override older reports. Odds remain research-only; **zero qualified selections and zero automated bets**.
