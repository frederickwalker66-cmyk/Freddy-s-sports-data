# V8 One Command — Phone, Windows Laptop and Eight-Sport Research

**One GitHub Actions screen** runs one sport, eight sports, model status, or Edge Value research.
It is NOT a certified prediction engine; historical results do not prove point-in-time
pregame feature availability or profitable bets.

## Phone (Android/iPhone) or Windows browser
1. Sign in to the GitHub account that can run this repository's Actions.
2. Open [V8 One Command](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/v8-one-command.yml).
3. Select **Run workflow**, branch **main**, and choose:
   - **run_nba** — download capped NBA historical public-score evidence.
   - **run_sports** — collect public historical scores for all eight configured sports.
   - **run_nfl**, **run_nhl**, **run_mlb**, **run_ncaaf**, **run_ncaab**, **run_mls**, **run_uefa** — one league.
   - **run_edge** — show existing research-edge count; without a separately provided forecast and price file it truthfully returns zero.
   - **model_status** — check actual NBA/eight-sport native training gates; no valid supplied evidence currently means blocked.
4. Choose a **days** budget (1, 7, 14, or 35). Optionally supply a past **end_date** as YYYY-MM-DD. Leave blank for yesterday (U.S. Eastern).
5. Click green **Run workflow**. Open its run page and read **Summary**. Download the **v8-one-command** artifact for game-level results and JSON status.

This executes on GitHub's cloud infrastructure, not your phone/laptop. Weekly Sunday public research capture is configured (best-effort GitHub schedule) when the workflow exists on main. Backfill artifacts are retained for 90 days: they are **not** a permanent historical warehouse; archive copies externally before retention expiry.

## Edge Value math

For a *hypothetical* independently generated NBA home moneyline probability p=0.58
at -110 American odds:

- Break-even probability = 110 / (110+100) = 52.38095%.
- Indicative probability edge = 58% - 52.38095% = 5.61905 percentage points.
- Indicative EV ROI = 0.58 * (1+100/110) - 1 = 10.72727%.

This example is **not today's model prediction or a verified available bet**.

The module `v8_edge_value.py` rejects market-implied probability substitutions,
nonpregame prices and forecasts, price/forecast timestamps >15 minutes apart,
missing source-review attestations, invalid American odds and wrong sport/market
settlement definitions. These self-reported flags still require independent
external verification; every result remains `certified_prediction=false`.

With genuine separately obtained JSONL candidate rows on your Windows laptop,
you can run:
```powershell
python v8_one_command.py --command run_edge --edge-input path\to\research_quotes.jsonl --output-dir v8_results/one_command
```
No actual sportsbook credentials are stored here. The GitHub UI **run_edge**
choice does not upload a file or invent prices; without an evidence file it
returns **0** research edges. In particular, a research price is not a verified
DraftKings checkout quote.

## Long-term historical collection

- Each run uses **at most 35 days per league** from public ESPN-published scores.
- Use different historical end dates to gather older windows. Do not assume
  sources have complete coverage back to 1950; report failed dates.
- The existing `challenger-historical-backfill.yml` workflow can consolidate
  multiple downloaded public archives into a research SQLite artifact.
- Original forecast timestamps, injuries, rosters, published stats, authentic
  model versions, independently adjudicated outcomes, and actual sportsbook
  odds need their own protected storage and independent review.
- Do not promote corrupted/trial SportsDataIO numerical stats to model training.
- Soccer three-way outcomes and NBA/NHL overtime market settlement must be
  correctly matched to the market definition before any certified evaluation.

## Existing model and betting status

Champion-001 remains frozen; its original executable is not authenticated.
Challenger-001 and V8 have research infrastructure but no independently
certified predictive edge. No real-money bet, automated wager or guaranteed
winner is created by any command.

The user-facing goal is **one control interface**. The important remaining
engineering work is a durable archive, authentic training/holdout data,
trained calibrated models and independently verified executable bookmaker
prices; only then can a qualifying EV leaderboard be published.
