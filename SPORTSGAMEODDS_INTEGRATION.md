# Freddy's Picks AI — SportsGameOdds integration (Challenger research only)

**Status:** Proposed on a separate review branch. Nothing on Champion-001 is changed. No live API response, credential presence, or sportsbook quote is certified merely by committing this code.

## Coverage
- SportsGameOdds API v2 `GET /events`, using `x-api-key` authentication. The key is NEVER placed in URL query strings, git history, output, or logs.
- NBA, MLB and NFL DraftKings-labeled moneylines, game spreads/run lines, full-game totals, and full-game over/under player props when SGO supplies valid player, market, line, and bookmaker timestamps.
- Configurable league order; one page of at most 25 events per run by default. Other leagues and period/alternate markets are not ingested into the current Challenger schema.
- Quotes older than 120 seconds, future timestamped, missing available DraftKings prices, invalid formats, live/in-play events, or unknown identities are discarded before snapshot creation.
- Provider IDs are **namespaced** `sgo:<eventID>`; SGO player IDs are not official NBA/MLB/NFL or SharpAPI IDs, and names are not sufficient for crosswalk verification.
- `includeAltLines=false` is requested. However the feed cannot independently establish primary-line status, so `is_main_line=false` remains fail-closed pending reviewed reconciliation.
- No sportsbook account is queried directly. A SportsGameOdds `draftkings` quote is not independently verified at DraftKings itself and is **not** a model prediction or positive-EV candidate.

## GitHub Actions secret
In **Settings → Secrets and variables → Actions → Repository secrets**, use **`SPORTSGAMEODDS_API_KEY`**. The workflow also recognizes `SPORTSGAMEODDS_KEY`, `SPORTS_GAME_ODDS_API_KEY`, `SPORTSGAMEODDS`, or `SPORTS_GAME_ODDS`. The exact secret name cannot be determined from a pull request; the enabled workflow checks whether a supported name is present without revealing its value.

## Run safely
1. Review and merge the draft PR only after tests and requested review; do not merge the prior player-ID audit PR without separate approval.
2. On the default branch, select **Actions → SportsGameOdds DraftKings research feed → Run workflow** to run the single-page limited collector. The workflow consumes API credits (up to 25 returned events in the current configuration). A failed credential or API check does not imply that a secret value is valid.
3. Read the workflow's artifact `sgo-draftkings-research-<run_id>` for `snapshots/sportsgameodds_dk_*.jsonl` and `validation_sgo/report.json`. The validation report must show **zero staged observations** and **zero certified/bet-ready picks** while no independently verified schedule is provided.
4. For scheduled runs, first check SportsGameOdds quota/costs and explicitly set repository **Actions variable `ENABLE_SGO_SCHEDULE=true`**. The daily cron is otherwise disabled. Workflow dispatch is independent of that variable.

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
