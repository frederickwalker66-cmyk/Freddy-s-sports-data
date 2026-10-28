# Freddy's Picks AI — SportsGameOdds integration (Challenger research only)

**Status:** Proposed on a separate review branch. Nothing on Champion-001 is changed. No live API response, credential presence, or sportsbook quote is certified merely by committing this code.

## Coverage
- SportsGameOdds API v2 `GET /events`, using `x-api-key` authentication. The key is NEVER placed in URL query strings, git history, output, or logs.
- NBA, MLB and NFL DraftKings-labeled moneylines, game spreads/run lines, full-game totals, and full-game over/under player props when SGO supplies valid player, market, line, and bookmaker timestamps.
- Configurable league order; one page of at most 8 events per league, or 24 total events per complete three-league run by default. Other leagues and period/alternate markets are not ingested into the current Challenger schema.
- Quotes older than 120 seconds, future timestamped, missing available DraftKings prices, invalid formats, live/in-play events, or unknown identities are discarded before snapshot creation.
- Provider IDs are **namespaced** `sgo:<eventID>`; SGO player IDs are not official NBA/MLB/NFL or SharpAPI IDs, and names are not sufficient for crosswalk verification.
- `includeAltLines=false` is requested. However the feed cannot independently establish primary-line status, so `is_main_line=false` remains fail-closed pending reviewed reconciliation.
- The workflow produces a daily quality report from collected odds and validation results. This is **daily evidence accumulation and auditing**, not continual retraining: actual learning requires independent settled results, calibrated pregame Champion-001 probabilities, and out-of-sample checks.
- No sportsbook account is queried directly. A SportsGameOdds `draftkings` quote is not independently verified at DraftKings itself and is **not** a model prediction or positive-EV candidate.

## GitHub Actions secret
In **Settings → Secrets and variables → Actions → Repository secrets**, use **`SPORTSGAMEODDS_API_KEY`**. The workflow also recognizes `SPORTSGAMEODDS_KEY`, `SPORTS_GAME_ODDS_API_KEY`, `SPORTSGAMEODDS`, or `SPORTS_GAME_ODDS`. The exact secret name cannot be determined from a pull request; the enabled workflow checks whether a supported name is present without revealing its value.

## Run safely
1. Review and merge the draft PR only after tests and requested review; do not merge the prior player-ID audit PR without separate approval.
2. After the PR is approved and merged into the default branch, the push triggers one controlled three-league run. On subsequent days the workflow runs automatically at 01:00 and 13:00 UTC (21:00 and 09:00 EDT, or 20:00 and 08:00 EST). Manual dispatch is also available. A full run makes one capped request per NBA, MLB and NFL, up to 8 returned events each. Provider object credits and rate limits depend on account plan; verify usage periodically. A missing or invalid secret causes a clear failed collection rather than pretending data was downloaded.
3. Read the workflow artifact `sgo-draftkings-research-<run_id>` for `snapshots/sportsgameodds_dk_*.jsonl`, `validation_sgo/report.json`, and `validation_sgo/daily_research_report.json`. The QA report summarizes observed leagues, market families, duplicate keys and quarantine causes, but **does not train models**. All artifacts have 30-day retention; permanent learning requires separate durable, private storage.
4. Scheduled research collection is enabled twice daily after merge, with a default cap of 24 returned event objects per run (roughly 1,440 returned-event objects per 30 days for two completed daily runs, plus manual runs and any API-specific minimums). If your account's object quota is lower, stop or reduce the schedule. The three-league implementation does not collect every sport in the provider catalog.

## Data contracts and remaining blockers
SportsGameOdds results are a **second research observation source**, not a replacement for the original SharpAPI odds collector. The present Challenger audit reads each source snapshot separately. An independent event-ID / participant-ID crosswalk, official rosters, up-to-date injury/lineup confirmation, direct current DraftKings prices, validated standalone Champion-001 forecasts, and outcomes/closing line evidence are still absent. All quotes fail closed on unreviewed schedule and primary-line status. No automatic join with SharpAPI is permitted without deterministic event/market/line reconciliation and independent source provenance.

A match between two odds aggregators is **not** direct verification of DraftKings, and neither provider's implied probability is an independent model probability. No production promotion, betting automation, wagering, or Champion-001 parameter change is included.

## Local fixture test (no network or credits)
```sh
python -m unittest discover -s tests -v
```

## Source references
- https://sportsgameodds.com/docs/basics/cheat-sheet
- https://sportsgameodds.com/docs/basics/quickstart
- https://sportsgameodds.com/docs/data-types/odds
- https://sportsgameodds.com/docs/faq
