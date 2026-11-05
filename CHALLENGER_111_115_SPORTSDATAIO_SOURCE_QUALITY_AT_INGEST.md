# Freddy's Picks AI — #111–115 SportsDataIO ingestion source-quality quarantine

## Why this work matters

Official SportsDataIO documentation says **Free Trial and Dev Key** API
responses can intentionally scramble game scores, player and team statistics,
and odds while keeping team/schedule structures usable for development:

- https://sportsdata.io/help/scrambled-data
- https://sportsdata.io/developers

Our November 5, 2026 live audit found **38 exact-match NBA games with score
disagreements versus ESPN**; their winners aligned while point totals had
near-constant date-specific ratios. The November 5 #107–110 integrity
upgrade detected all **four** suspicious dates.

**We cannot authenticate the user's specific API key entitlement from
the presence of an Actions secret, HTTP 200, or this pattern alone.**

## #111: Classify source trust at intake, not only after comparisons

New source: \`challenger_sportsdataio_ingestion_trust.py\`.

The classifier inventories provider field names and numeric value counts.
These are **research-only metadata**; no raw scores/points/odds are copied
into the published quality summary.

- Team IDs and game IDs are candidates for identity crosswalks only.
- Schedule/time/team fields still require exact independent game matching.
- Scores, stats, box scores, spreads, lines, moneylines and prices are
  **unverified and cannot be native trained features or +EV inputs**.
- No "score correction" ratios, implied probabilities as model predictions,
  upgraded source entitlement assertions, bets, or trained model artifacts.

## #112–113: Original collector and validator both enforce provenance

\`sportsdataio_collector.py\` preserves the original provider payload for
research debug but now labels every response:
\`provider_scores_stats_odds_authenticated=false\`,
\`numeric_values_eligible_for_training=false\`,
\`schedule_metadata_only_research=true\`, \`bet_ready=false\`.

\`challenger_sportsdataio_validation.py\` refuses a record marked as
verified, bet-ready, model-probability-bearing or otherwise promoted.
The report includes an independent \`provider_source_quality\` object:
number of records with unverified numerical data, per-league counts,
recorded source status, and explicit zero training/forecast/betting gates.

No trained model is fitted by this collector.

## #114: Test the actual collector/validator data path

Synthetic offline regression tests cover all six scheduled leagues, a mocked
JSON-returning collector, raw payload preservation, score/odds field
detection, missing/invalid timestamps, source-trust promotion rejection,
oversized/malformed JSON, duplicate data and no model/bet writes.

## #115: Existing scheduled intake with an immediate quality check

\`.github/workflows/sportsdataio-research-intake.yml\` now verifies
the completed quality report after each successful collection.

The workflow retains its existing morning/evening cadence. On the
next merge touching this intake code, it also runs its existing six-league
matrix once to ensure the real credential is available and live collection
labels are truthful. Manual runs can still test MLS entitlement separately;
do not infer MLS support from NBA account success.

No new scheduled recurring task or extra model instance is created.

## Release gates that still require external data

1. Confirm **real, unscrambled** SportsDataIO source entitlement for each
   intended product: NBA scores, team/player stats and odds are separately
   licensed capabilities. View the subscription within SportsDataIO account
   rather than trying to guess a secret's plan from code.
2. Independently compare exact published final scores and box stats with a
   reliable league-operated or other original-source audit. Successful API
   transport, matched winners or consistent scaling do NOT establish fidelity.
3. Authenticate real original pregame feature bytes and their publication
   times, and secure a true chronological 200+ qualified NBA training and
   50+ later holdout dataset.
4. Fit the native Challenger-001 NBA moneyline engine only after the
   independent training gate passes. Then evaluate proper calibration,
   Brier/log loss on the untouched holdout, and follow a versioned release.
5. Treat actual executable DraftKings quotes/prop settlement as separate
   evidence; no aggregator label alone authorizes +EV ranking.

**Current**: Champion-001 frozen; certified Champion/Challenger predictions 0,
native qualified training 0, verified executable DraftKings prices 0,
real-money wagers 0. The untrained $0 NBA research ledger remains separate.
