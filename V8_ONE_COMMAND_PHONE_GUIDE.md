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
   - **run_nba_forward** — capture original NBA future schedule bytes and score-history receipts right now; record actual timestamped before-tipoff Elo research probabilities if 80+ sufficiently matured prior games and all 35 source days are available. This is a separate V8 research lane, NOT the frozen Champion-001 certification quota.
   - **run_nfl_forward** — capture original ESPN NFL pre-start event bytes with a 7-day outlook and prior 35 days of published results. Record fixed Elo v0 research P(home wins | no tie), explicitly NOT an actionable moneyline probability.
   - **run_nhl_forward** — capture original ESPN NHL pre-start event bytes with a 2-day outlook and prior 35 days of published results. Record fixed Elo v0 NHL full-game home-win research probabilities; OT/SO and sportsbook settlement are unverified.
   - **run_sport_board** — read the persistent NFL/NHL first-forecast research history and separately published outcomes from `research/nfl-nhl-forward-ledger`. This is read-only; it does not generate or place bets.
   - **run_nba_grade** — read the saved genuine pretipoff V8 research forecasts, check their original schedule-byte hashes and GitHub run timestamps, then grade only games with ESPN final results observed at least 48 hours after their original scheduled tipoff. Never backfill or change an original prediction.
   - **run_leaderboard** — read your stored forward research records from the separate `research/forward-ledger` Git branch, show original forecasts, pending games, Brier/log loss and any models with at least 50 real graded forward games. No current game bets or fabricated edge.
   - **run_calibration** — read the saved research reliability report from the same durable Git branch. It shows five fixed probability buckets; empirical win frequencies are withheld for buckets with fewer than 20 graded games, aggregate Brier/log-loss require 50+ games, and exploratory calibration error requires 100+ games and ten per occupied bucket.
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

## LIVE forward NBA research: `run_nba_forward`

Use this from GitHub Actions on your Android/iPhone or Windows laptop. Choose
`run_nba_forward` and **leave the historical end-date blank**. The phone
workflow automatically chooses the 35-day public history budget, and scans
ESPN NBA original future schedule bytes for today and tomorrow. It uses no
paid sportsbook APIs and places no bets.

On successful capture, download `nba_forward/NBA_FORWARD_FORECASTS.jsonl`,
`nba_forward/NBA_FORWARD_RESEARCH_STATUS.json` and
`nba_forward/nba_original_future_schedule_YYYYMMDD.json`.

Each **actually pre-tipoff recorded** research row includes source event ID,
home/away ESPN IDs, captured schedule SHA-256, model/version, specific home
moneyline research probability, captured UTC forecast time and future tipoff
time. Later settlements are **not** incorporated at forecast time, and no
outcomes are filled in ahead of a later result review.

The base algorithm is a **new fixed Elo v0 research benchmark** (K20, home
advantage 60; 1500 initial ratings) replaying 35 days of *already completed*
ESPN-published NBA regular-season games. Prior results are used only if
their start was at least 48 hours before the current forecast and their
score was actually retrieved before the forecast. This is an assumed
conservative result-availability rule, not authenticated publisher timing.

The workflow is also scheduled best-effort daily around **3:37 pm Eastern
during standard time / 4:37 pm during daylight time**, as well as an initial
main-branch install run. GitHub scheduled events are best-effort and may be
late or missed; games already started are excluded.

**Do not merge this lane into Champion-001.** The original frozen Champion-001
has 0 certified shadows until original executable and probabilities are
authenticated. V8 research rows are NOT a sportsbook quote, an independently
calibrated probability, a certified pick, guaranteed return or an actionable
+EV recommendation. To grade it, independently retrieve later final results
and compare with the **unchanged, timestamped forecast**; retain missing
forecasts, losses and voids.

## NBA prospective research grading: `run_nba_grade`

Choose **Run workflow → run_nba_grade → Run workflow** in the GitHub phone
command center, with the historical end-date **blank**. It requires no paid
sportsbook API and creates no bets. The same read-only grading workflow is
scheduled at approximately **8:53 a.m. EST / 9:53 a.m. EDT**, best effort.

The grader looks through up to 35 recent successful One Command GitHub runs,
and downloads only available archived forward-forecast artifacts. The first
successful November 9, 2026 run has a **legacy artifact name**
`v8-one-command-run_nba_oos-42699985963`; the grader recognizes that label
but checks the actual report must say `run_nba_forward` before accepting it.

Each downloaded forecast must match (1) its original saved schedule HTTP
bytes SHA-256, (2) its exact ESPN event ID, team IDs, and scheduled kickoff,
(3) its GitHub run-created/completed timestamps surrounding the original
forecast capture, (4) the fixed model version and its original probability,
and (5) its explicit research-only and $0 stake flags. Later reforecasts
cannot revise the **first** accepted probability for the same event. A
conflicting event identity is quarantined.

Game outcomes stay **PENDING** until the ORIGINAL kickoff time is at least
48 hours old and a separate public ESPN completed-score record is available.
Source outages, postponed or shifted games, unresolved official settlement,
and changing team IDs are reported as **HOLD**, never silently scored as
losses. Even scored outcomes are ESPN-published *research* results, not
independent league adjudication.

The downloadable `NBA_FORWARD_GRADING_REPORT.json` and
`NBA_FORWARD_GRADING_LEDGER.jsonl` provide:
- True sample counts, pending and excluded records.
- Per-game original forecast probability, timestamp, source GitHub run ID,
  later published score, source URL, and each game's Brier/log-loss.
- Aggregate research Brier, log loss, direction accuracy and an explicit
  50+ forward-graded-game readiness flag.

A sample below 50 games is **preliminary**; even at 50+, research grading
does not independently certify calibration, model authenticity, or
actionable positive EV. **Champion-001 original certified shadows remain 0**
and no odds or wagers are generated. GitHub artifacts expire after 90 days,
so a durable externally archived forecast ledger is still needed.

## Long-lived forecast archive and forward-performance dashboard

The separate GitHub Actions workflow
`v8-durable-forward-ledger.yml` collects previously completed original NBA
research forecast captures after each One Command workflow success and once
daily (best-effort). It preserves the original GitHub run JSON, before-tipoff
probability JSONL, model version, full schedule response bytes and local
SHA-256 digests under the dedicated Git branch:

`research/forward-ledger` → `data/v8_forward/`

It builds `NBA_FORWARD_RESEARCH.sqlite`, `FORECAST_HISTORY.jsonl`, and
`LEADERBOARD.json`. Git branch storage outlives GitHub's normal 90-day
workflow artifact period, but **is not externally immutable** or a guarantee
of independent event/source custody. Keep separate off-repository backups.

A timestamped original forecast cannot be overwritten by a later forecast.
Duplicate or conflicting event identities are quarantined. ESPN published
final outcomes are added separately only after a minimum 48-hour waiting
period; missing scores do not count as losses. Existing recorded grades are
not silently replaced on each refresh.

For a quick status from Android/iPhone or Windows choose:
**Run workflow → run_leaderboard → Run workflow**.
This is a READ-ONLY lookup and does not trigger the data collector or place
a bet. The separate durable writer owns archival updates.

Only research models with at least **50 forward-graded games** enter the
ranked scoreboard, sorted by lower Brier score. This minimum allows
**preliminary comparison**, not independent calibration or betting
certification. Original Champion-001 model and shadow quota remain frozen
and separate; certified bets and certified positive EV remain zero until
independent model/source and sportsbook verification exists.

## Forward-research calibration without inflated accuracy claims

Open **V8 One Command → Run workflow → run_calibration → Run workflow**.
This read-only command loads `data/v8_forward/CALIBRATION.json` from the
separate `research/forward-ledger` branch. The daily archival/grading writer
produces this file from SQLite using ONLY first-retained, actually timestamped
before-tipoff V8 NBA research predictions and later ESPN-published outcomes.
It makes no provider API calls and does not modify original probabilities.

- **Fewer than 50 forward-graded games:** Withhold Brier and log loss.
- **50 or more graded games:** Report descriptive Brier/log loss, including a
  neutral 50/50 Brier reference (not a sportsbook).
- **Five FIXED buckets:** P(home) in [0,20%), [20,40%), [40,60%), [60,80%),
  [80,100%). Display mean forecast and number of games. Empirical home-win
  frequency and Wilson 95% descriptive interval require **20 games in a bin**.
- **Calibration error (ECE):** Withhold until **at least 100 forward-graded
  games** and at least **10 in every occupied bin**. This is an exploratory
  statistic, not an independently validated calibration certificate.
- **Uncertainty:** A 1000-resample paired game-day-cluster Brier interval
  becomes available at >=50 graded games and >=10 distinct game dates.

Games still pending 48h or missing published final results remain UNGRADED.
Malformed, timestamp-inconsistent or contradictory records cause an explicit
HOLD/error rather than altered forecasts or inflated performance. Bins
and threshold rules were fixed BEFORE observing the outcomes of these
first forward-game forecasts.

This measures only **research probability quality**; it does not establish
profitable betting, real executable bookmaker prices, verified independent
publisher custody, the original frozen Champion-001 model or ANY certified
positive-EV selections. **Champion-001 shadows and certified bets remain 0.**

## NFL and NHL original forward research (new V8 lanes)

Choose **Run workflow → run_nfl_forward** or **run_nhl_forward** from your
phone or Windows computer in **V8 One Command**. Leave `end_date` empty.
The workflow selects 35 source days automatically for either forward lane.

There is also a dedicated scheduled GitHub workflow,
`v8-nfl-nhl-forward.yml`, which captures both lanes separately around
**3:41 p.m. Eastern (standard time) / 4:41 p.m. (daylight time)** daily.
GitHub schedule runs are best-effort: they can start late or be missed.
The two separate downloadable artifacts are:
- `NFL_FORWARD_RESEARCH_FORECASTS.jsonl` and original
  `nfl_original_future_schedule_YYYYMMDD.json` responses.
- `NHL_FORWARD_RESEARCH_FORECASTS.jsonl` and original
  `nhl_original_future_schedule_YYYYMMDD.json` responses.

Both use a fixed initial Elo rule that has NOT been trained or calibrated:
NFL K=18, home advantage=45 Elo points, >=35 prior 48h-matured
**non-tie** published regular-season games; NHL K=16, home advantage=35,
>=50 prior 48h-matured non-tie regular-season published games. They fetch
at most 35 historical days and save the future schedule **wire bytes** and
local SHA-256. NFL scans 7 upcoming Eastern dates, NHL 2. All original
outcomes and odds stay blank until independently reviewed later. Failed
source days prevent probability creation and remain recorded as explicit
HOLDs instead of invented history.

**Critical NFL market-definition warning:** a two-outcome NFL Elo result
with ties omitted is conditional on no tie and is **not equivalent to an
executable NFL sportsbook moneyline price**. NHL overtime/shootout
grading and exact house settlement are also not validated. No bankroll,
bet slip, bookmaker checkout price or verified positive-EV computation
is generated from these research probabilities.

These newly recorded sports are still **V8 separate forward research**;
they DO NOT inherit the NBA SQLite database, grading or 50-game
calibration results. Those require separate sport-specific verified outcome
grading and durable archiving. Original Champion-001 stays frozen;
**certified picks: 0, automated wagers: 0**.

## NFL + NHL original forward prediction grading and durable archive

The NFL/NHL first actual main-branch capture ran on **November 9, 2026**
(GitHub run `42711310554`), recording **14 NFL** conditional non-tie
research probabilities and **10 NHL** full-game ESPN-win research
probabilities before their scheduled starts.

The separate workflow `v8-nfl-nhl-forward-grade-ledger.yml` runs after
a successful source-capture workflow, best-effort daily, and can be
manually dispatched from GitHub Actions. It downloads actual completed
GitHub run metadata + the matching `v8-nfl-forward-RUNID` and
`v8-nhl-forward-RUNID` artifacts and verifies:

- Original complete successful GitHub run, initial event and model version.
- Original ESPN response JSON bytes and SHA-256, event ID, matchup and UTC tipoff.
- Original model probability and GitHub run capture **before** the game starts.
- No self-promoted Champion-001, betting odds or certified model results.

The writer then preserves raw original source files in a distinct Git branch
`research/nfl-nhl-forward-ledger`, under
`data/v8_forward/nfl/` and `data/v8_forward/nhl/`.
Each sport has its own `FIRST_FORECASTS.sqlite`,
`FIRST_FORECAST_HISTORY.jsonl` and
`FORWARD_RESEARCH_LEADERBOARD.json`.

Only the **first validated forecast** is ever graded. A later forecast
does NOT overwrite the original. Conflicting identities are quarantined.
Published results are fetched **no earlier than 48 hours after the
original scheduled start**. Missing or delayed games stay pending/HOLD.

**NFL published ties** are recorded as excluded from the conditional
no-tie binary target: they are **not** wins or losses. NHL scores are
published full-game results, but overtime/shootout sportsbook grading
has NOT been independently adjudicated; a tied published NHL score
is held rather than inventing a winner.

A research leaderboard requires **50 genuinely forward-graded binary
games for each sport and model** before showing Brier/log loss and
direction accuracy. Even then this is research only, not calibrated
bookmaker odds or independent model certification.

Use **Run workflow → run_sport_board → Run workflow** from the main
V8 One Command screen for a read-only NFL/NHL report. Use the separate
durable grading workflow to refresh archived originals and scorecards.
Git branch persistence is useful after temporary GitHub artifacts expire,
but **is not externally immutable, third-party signed custody**. Back up
the branch separately. Frozen Champion-001 remains unchanged;
**certified Champion-001 shadows 0, certified positive EV 0, wagers $0**.
