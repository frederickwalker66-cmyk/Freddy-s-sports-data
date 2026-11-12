# Freddy's Picks AI — Requested NBA/NFL Sharp Edge rerun

- Requested research date (America/New_York): **2026-11-12**
- Request: NBA and NFL games, spreads, totals, NBA/NFL player props, Sharp Edge, native probabilities, calibration, certified model expected value, and CLV evidence
- Input policy: only already captured SharpAPI DraftKings-labeled archives; **zero additional paid API requests**
- Command executed by triggered workflow: `run_nfl_props_edge`
- Quality policy: compare like-for-like exact event, market, line and athlete identity; distinguish price-implied/no-vig market percentages from native predictive probability
- Model policy: Champion-001 frozen; Challenger research unpromoted; no synthetic model forecasts, fake EV, or calibration numbers
- CLV policy: no CLV without timestamped original entry plus independently authenticated closing price of the identical settlement outcome
- Output: downloadable `NBA_NFL_FULL_GAME_MARKETS_RESEARCH.json`, `NBA_NFL_SHARP_EDGE_PROBABILITIES.json`, `NBA_NFL_SHARP_EDGE_CALIBRATION.json`, and `NBA_NFL_SHARP_EDGE_CLV.json`
- Bet policy: certified positive-EV best bets only if independent evidence qualifies; otherwise **PASS/HOLD**, **$0 shadow stake**, **no automated wagers**

Edit this request file via a reviewed GitHub change whenever another on-demand archive-only Sharp Edge scan is needed. A successful workflow execution does not certify sports betting profitability.
