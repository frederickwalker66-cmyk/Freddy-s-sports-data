# Freddy's Picks AI — SharpAPI DraftKings collector

Installed on `main` in `frederickwalker66-cmyk/Freddy-s-sports-data` on October 28, 2026.

## Purpose

Collect timestamped **research-only** pregame DraftKings odds for NBA, NFL, and MLB moneyline, other full-game main markets, and `player_*` props. Filter out in-play, stale, incomplete, and non-DraftKings quotes. **This collector does not make bets or generate Champion-001 predictions. The frozen Champion-001 model remains unchanged.**

## One-time GitHub secret

Open the repository's [Actions secrets settings](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/settings/secrets/actions).

Create a repository secret named exactly `SHARPAPI_KEY` using your private SharpAPI key. If it already exists, do not duplicate it. The key is read only at run time from GitHub Actions secrets; never paste its value into source code, chat messages, screenshots, or logs.

## Run and inspect

Open [the workflow](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/collect-sharpapi.yml). Choose **Run workflow** on `main` if it is not already running.

The workflow runs the 10 offline unit tests, checks whether `SHARPAPI_KEY` is present without printing its value, and calls SharpAPI. It uploads a `sharpapi-pregame-<run-id>` artifact containing a JSONL dataset and a JSON summary, when generated. The summary field `pregame_odds_quotes` counts accepted quotes. A green run and accepted odds must be independently checked; **offline tests alone do not establish live collection**.

A schedule also requests runs at 16:00, 20:00, and 23:00 UTC. GitHub may delay scheduled jobs. The workflow has a `push` trigger scoped to changes to its own workflow file to support initial deployment verification.

## Local verification

```sh
python -m unittest discover -s tests -v
python -m py_compile collector.py
```

## Safety and limits

- API documentation: https://docs.sharpapi.io/en/api-reference/odds/
- Uses `GET /api/v1/odds`, header `X-API-Key`, and cursor pagination.
- Caps each league/market group at 4 pages × 200 observations, respecting a 5.5-second pause between calls. Counts are not exhaustive when capped.
- Rejects odds whose source timestamp is older than 15 minutes and games that began before collection.
- Retains GitHub Actions artifacts for 30 days; this is a public repository, so do not include any confidential content in artifacts.
- Market quotes are **not** Champion-001 model probabilities, certified selections, or defensible positive-EV predictions.
- No wagering; model remains frozen. Certified prediction count is **0** until independently demonstrated otherwise.

## Live status

Installation is confirmed by the presence of `collector.py`, `tests/test_collector.py`, and `.github/workflows/collect-sharpapi.yml` on `main`. The Actions run history and the secret availability must be checked separately before describing ingestion as operational.
