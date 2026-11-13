# Freddy's Picks AI — All-Markets Game + Props Research

**New phone/laptop workflow command:** `run_mixed_market` (NBA and NFL only).

This is the unified **moneyline, full-game spread, full-game points Over/Under, and exact player-prop Over/Under** research view. The previous `run_nfl_props_edge` remains available. All other league commands remain unchanged. The workflow uses already saved SharpAPI research archives: **no paid API requests** and **no bets placed**.

## On the phone

Open **GitHub → Freddy-s-sports-data → Actions → Freddy's Picks AI V8 — One Command → Run workflow**, select `run_mixed_market`, then read the job summary or download `MIXED_MARKET_GAME_PROP_RESEARCH.json` from the run's artifact.

The report shows archive-supported market categories and two-sided source-labeled quotes if recent pregame pairs exist. A missing or stale quotation appears as missing, never as `0% probability`, `0 EV`, or a guessed market. NFL/NBA game markets and player props are *side-by-side*, not a fabricated five-leg betting ticket.

## Market classification

| Category | Selections | Required to claim an indicative native research edge |
|---|---|---|
| Moneyline | Home / Away | Exact event and settlement, independently reviewed native win probability |
| Point spread | Home / Away with **exact selected handicap** | Original native cover probability **for that handicap**; half-point non-alternate line, independent exact-line and settlement review |
| Game total | Over / Under with **exact full-game point line** | Original native total-over/under probability **for that threshold**; half-point non-alternate line, independent exact-line and settlement review |
| Player prop | Over / Under of named player's exact stat/line | Original native stat-specific probability, player active and identity evidence, independent market settlement review |

`run_edge` can rank research-only positive indicative EV candidates across these market types **only when** the required independently reviewed original time-stamped model probability and contemporaneous quoted sportsbook price are present. Both remain unverified as executable checkout receipts. It cannot convert a moneyline win probability into a spread-cover probability or a price-derived implied percentage into a model prediction.

## Parlay and model integrity

- Rank single-leg *indicative* EV before researching parlays. Do not force five qualifying legs when there are fewer.
- Multiple legs from the same game or player can be correlated; never multiply them into a parlay probability without a validated joint model.
- Market movement is not certified sharp bettor activity, and a pregame reprice is not closing-line value without matching independently authenticated entry and close receipts.
- Actual odds and lineup updates must be confirmed in the user's sportsbook. User screenshots remain private; never commit tickets, account details, or personal receipts.
- **Champion-001 remains frozen.** All current research is **HOLD** for independently certified positive-EV claims, and shadow stake remains $0.

## Tests

```bash
python -m unittest tests.test_v8_mixed_market_board -v
python -m unittest discover -s tests -p 'test_v8_*.py' -v
```

Successful CI only verifies code behavior. It does not certify betting profitability or guarantee any forecast.
