# Freddy's Picks AI — SportsGameOdds source integration

**Status: manual-only research integration, designed to keep Champion-001 frozen.**

The separate `sportsgameodds_collector.py` source collector obtains **SportsGameOdds v2** (`GET /events`) DraftKings-labeled pregame source quotes using a secret sent as the `x-api-key` header. The token is never in a URL, output artifact, or git commit. Odds observations are **not** direct DraftKings checkout receipts or native model forecasts.

## How to run a controlled capture

Open GitHub Actions → **SportsGameOdds NBA NFL MLB research — manual capped intake** → Run workflow. The defaults are `NBA`, `5` maximum returned events, **1 page**, **1 league**, **1 API request**. Optional single-league settings: NBA, NFL, or MLB; request limit 2, 5, or 8 objects. The actual SportsGameOdds account may have response minimums, restrictions or quotas; inspect usage.

This integration deliberately has **no scheduled or push-triggered paid collection**. Pull requests run **offline tests only**, and even a successful test job makes zero API requests. Manual collection will fail before any network access if the repository secret is absent.

The collector accepts the original October 2026 GitHub Actions secret aliases: `SPORTSGAMEODDS_API_KEY`, `SPORTSGAMEODDS_KEY`, `SPORTS_GAME_ODDS_API_KEY`, `SPORTSGAMEODDS`, `SPORTS_GAME_ODDS`, `SPORTSGAMESODD`, `SPORTSGAMESODDS`, `SPORTS_GAMES_ODD`, `SPORTS_GAMES_ODDS`, `SPORTSGAMEODD`, and `SPORTS_GAME_ODD`. **If the secret already exists, do not create a duplicate or change the key.** The earlier collector accepted all these names. A manual run with an empty secret across all aliases still indicates a scope/name/accessibility problem, not necessarily that no credential was ever saved. If a manual run moves past the secret check but fails with HTTP 401, the provider rejected the stored credential. Never paste the token into a GitHub issue or chat.

The source reports appear in artifact `sgo-draftkings-research-<run_id>`:
- `snapshots/sportsgameodds_dk_*.jsonl`: provider-labeled observations and timestamps
- `snapshots/sportsgameodds_dk_*.summary.json`: source request and exclusion counts
- `validation_sgo/report.json`: separate, no-EV research reference screen

Each artifact is kept for 30 days. Source data is not a replacement for independent original pregame model probability records, authenticated league results, or actual sportsbook acceptance receipts.

## View SportsGameOdds alongside SharpAPI on the phone

Open GitHub Actions → **Freddy's Picks AI V8 — One Command (phone + laptop)** → Run workflow, leave the command at `run_mixed_market`. It will download the **latest existing successful** manual SGO archive, if present, with no additional SGO API request.

After every successful **manual** SportsGameOdds collection, GitHub automatically refreshes the existing **no-cost** `run_mixed_market` phone report from saved artifacts. This does not make any additional SportsGameOdds API requests or enable scheduled provider collection. An unsuccessful provider run produces no automatic report.

The regular mixed-market report remains a separate **SharpAPI-only** research board for moneylines, spreads, totals and props. `SGO_SEPARATE_SOURCE_RESEARCH.json` shows SportsGameOdds observations and an age-limited watchlist **separately** with source label, event, quote time and line. The GitHub Actions summary also shows the latest SGO archive coverage. No automatic cross-provider event/player join is performed, and SGO quotes are never used as Champion-001 probabilities or certified sharp edges.

## Safety and availability restrictions

- The collector retrieves **pregame** events, `includeAltLines=false`, with only DraftKings-labeled prices. Its research window can include quotes up to 15 minutes old; the phone watchlist only shows quotes captured within the preceding **120 seconds**.
- `is_main_line=false`, `cross_provider_identity_verified=false`, and `draftkings_price_independently_verified=false` are retained. A source's own event/player ID does not authenticate the same identity in NBA rosters or SharpAPI.
- Even when two aggregators' prices match, it is not direct checkout price verification, independent sharp-flow proof, or independently calibrated EV.
- No automatic bets. No changes to Champion-001. Challenger calibrations are still blocked until authentic pregame native model probabilities and settled outcomes are available.
- To avoid overuse, review plan limits and quota before enabling any recurring capture. The official docs state **Amateur 2,500 objects/month**, with per-request minimum object counts possible depending on plan. See <https://sportsgameodds.com/docs/info/rate-limiting>.

### Offline tests

```bash
python -m unittest discover -s tests -p 'test_sportsgameodds_collector.py' -v
python -m unittest discover -s tests -p 'test_v8_sgo_research.py' -v
python -m unittest discover -s tests -p 'test_v8_*.py' -v
```

API references: <https://sportsgameodds.com/docs/basics/cheat-sheet> and <https://sportsgameodds.com/docs/endpoints/getEvents>.
