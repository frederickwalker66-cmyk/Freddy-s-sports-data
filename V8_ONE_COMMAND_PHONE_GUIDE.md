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
   - **run_sharp** — read the five most recent successfully completed SharpAPI research archives (if available), report eligible DraftKings-labeled main-moneyline prices and historical line movement. **No new provider API calls, no added API credit use.**
   - **run_health** — inspect actual eight-sport source collection runs and their most recent completed success. This is read-only; it cannot force or certify a source.
   - **run_certify** — read the most recent already completed eight-sport source gate and SharpAPI moneyline archive, reconcile source counts, and list per-league blockers. **Evidence audit only, never fake certified predictions.**
   - **run_nba_train** — download recent original NBA prospective review receipts, report real independently unqualified training gaps and produce a downloadable manual-review worklist. It deliberately does not train on unverified review packets.
   - **run_nba_oos** — fetch up to 35 real NBA historical regular-season score days (public ESPN only), replay a fixed Elo benchmark using a 48-hour result embargo, and report retrospective Brier/log loss. **This is not a real pregame logged forecast, certified calibration, executable EV, or a betting recommendation.**
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

## SharpAPI: what `run_sharp` means

- The existing [SharpAPI DraftKings collector](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/collect-sharpapi.yml) already captures pregame NBA, NFL and MLB main/prop research odds on its own schedule.
- **run_sharp** downloads recent existing successful collector artifacts and analyzes *historical main moneyline quotes* using the established timestamp and market-identity guards. It reports available capture date, counts by sport, change in no-vig home win probability, and excluded/invalid rows.
- A single price snapshot is not evidence of line movement. A change in a DraftKings-labeled price is not proof of **sharp money**, a winning wager or a model edge.
- The report intentionally does not infer professional betting handle, public versus sharp ticket splits, current availability, or DraftKings checkout verification.
- `run_sharp` does NOT call the paid SharpAPI service. For a separate **fresh** provider capture, use its existing workflow's *Run workflow* control, mindful of provider quotas/credit charges and the configured API secret. The original scheduled SharpAPI collection remains unchanged.
- Archived SharpAPI quote artifacts expire after 30 days; preserve the records separately before that expiration if a long-term line movement warehouse is needed.

## Source-reliability watchdog (research-only)

- The `v8-source-cadence-watchdog.yml` workflow is a separate automatic
  safety mechanism for missed or delayed GitHub Actions source runs.
- It checks only real GitHub metadata from the existing eight-sport original-source
  preflight. Its own hourly schedule and two upstream triggers are best-effort.
- If there is no active preflight run, the last completed success is more than
  150 minutes old, and fewer than four workflow dispatches were created in the
  last 24 hours, the watchdog requests **one** manual GitHub Actions dispatch
  of the existing FREE public-source preflight workflow on `main`.
- Missing GitHub API metadata blocks recovery, rather than declaring a source
  missing or successful. A dispatch acknowledgment is not a successful source run.
- Neither `run_health` nor the watchdog can authenticate NBA schedule bytes,
  circumvent official NBA 403 access restrictions, verify bookmaker checkout
  odds, train models, certify predicted probabilities, or place wagers.
- The watchdog does **not** invoke the paid SharpAPI or SportsDataIO collectors.

## Certification evidence inspection: `run_certify`

- Select **run_certify** and read the GitHub run Summary. It downloads the
  most recent completed source-preflight research audit and SharpAPI archived
  market baseline, if those GitHub artifacts still exist.
- Inspect the **CERTIFICATION_AUDIT.json** artifact for the actual source-run IDs,
  saved event counts, same-run release/identity reconciliation, original frozen
  Champion-001 status, seven-league research models, and league-specific gaps.
- This is not model retraining or proof of accuracy. Source timestamps, partial
  original provider responses, local checksums, successful GitHub tests,
  reviewer booleans, SharpAPI-labeled odds or positive research EV are **not**
  independent certificates.
- Genuine certification requires qualified pregame features and settled
  outcomes, a reproducible untouched holdout and calibrated model,
  externally authenticated original model custody and a qualified independent
  release review. Executable bookmaker prices are needed for an actionable EV
  betting claim. None can be auto-created from missing historical files.
- The command **never places bets** or changes Champion-001. It reports zero
  certified predictions until those requirements are satisfied and checked
  outside the self-asserted reporting pipeline.

## NBA original-data training stage: `run_nba_train`

The phone action downloads up to four recent successful **prospective outcome-validation** archives, rechecks their saved original-capture NBA review packets, and produces:
- `NBA_RESEARCH_INTAKE.json`: real packet counts, pregame features/final-result review readiness, 200-train/50-holdout independent-evidence shortfall, and unresolved source/settlement requirements.
- `NBA_ORIGINAL_REVIEW_WORKLIST.jsonl`: deduplicated NBA event references with original line hashes, unverified source run numbers and blockers. Its contents **must not be fed into the native trainer**.

The phone button does not automatically qualify research data; original review packets explicitly contain `qualified_for_challenger_training=false`. When a genuinely externally reviewed separate history dataset becomes available on a Windows machine, the existing native research trainer can be invoked through the CLI without changing Champion-001:

```powershell
python v8_one_command.py --command run_nba_train --nba-review-dir path\to\downloaded_outcome_artifacts --nba-qualified-history path\to\externally_reviewed_nba_history.jsonl
```

That separate file must satisfy the original `challenger_nba_probability.train_engine` schema and its 200/50 chronological training/holdout gates. Even a successful research model remains **unverified**, because source-review flags and original receipts cannot independently authenticate themselves. A subsequent external audit of publisher time, outcome and exact bookmaker settlement, model calibration, and executable sportsbook quotes is required before any certified positive-EV recommendation.

## NBA research probability benchmark: `run_nba_oos`

Select **run_nba_oos**, choose **35** days, and select an **in-season past**
date such as `2026-02-15`. The command fetches only the original public ESPN
scoreboard dates in that 35-day window; no odds API or subscription credits.

Its JSON artifact records each game ID and a simulated home-win probability
from a fixed Elo update rule. Prior games are applied only after a **48-hour
assumed outcome-publication embargo**, with simultaneous events scored before
either result is incorporated.

After 80 warmup games and at least 30 later games, it reports exploratory
Brier score, log loss and an **untrained neutral 50/50** reference. The data
are historical results fetched after the games; the forecasts are **not**
authentic pre-tipoff recorded shadow predictions. Neither an assumed 48-hour
publication lag nor a good retrospective Brier score proves actual forecast
skill, independent NBA source authenticity, bet ROI or current market edge.

If there are fewer than 110 usable regular-season results or the public source
fails, the command reports HOLD and does not fabricate metrics. Every output
remains uncertified, and Champion-001 is not modified.

For actual certification, first accumulate separately authenticated pregame
team/injury data and model versions captured *before* start times, then
evaluate reproducible probabilities against independently adjudicated
outcomes on untouched later games and independently verified executable
bookmaker prices.

## Interpretation of NBA retrospective skill: compare with an evolving baseline

The `run_nba_oos` report also measures a **rolling home-win-rate
baseline**, computed entirely from previously presumed-matured results. This
reference uses Beta(1,1) smoothing and the same 48-hour assumed result
availability embargo as the fixed Elo replay. The comparison includes:

- Retrospective Elo versus rolling-prior Brier and log loss on the same later games.
- Paired Brier improvement = **rolling-prior Brier minus Elo Brier**. Positive
  numbers indicate Elo outperformed that benchmark over this historical sample.
- An approximate 95% *game-day-cluster bootstrap* interval for the Brier
  difference, which is only exploratory (1000 deterministic resamples).
- The existing 50/50 neutral reference, which is **not** a sportsbook baseline.

An Elo Brier score slightly below 0.25 is **not enough** by itself to show
skill. Compare against the rolling home prior and examine uncertainty first.
Neither comparison repairs unverified original result-publication timestamps,
establishes actual pregame forecast receipts, demonstrates profitable bets,
or permits promotion to certified betting predictions.
