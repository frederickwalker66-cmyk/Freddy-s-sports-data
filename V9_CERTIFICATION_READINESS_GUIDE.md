# Freddy's Picks AI V9 - Per-Game Prediction Certification Audit

This milestone adds an individual evidence checklist for each game appearing in the six-employee pregame meeting. It runs immediately after the existing V9 schedule review and archives:

- V9_PREDICTION_CERTIFICATION_GAPS.json (structured reasons and source pointers)
- V9_PREDICTION_CERTIFICATION_GAPS.md (one-display, phone-readable staff meeting summary)

The existing two daily ChatGPT scans, two hourly original ESPN source-capture attempts, watchdog recovery, pregame meeting schedule and frozen Champion-001 remain unchanged. This new audit **only reads already downloaded GitHub artifacts** and never calls any paid API, schedules additional collectors, alters the model or places bets.

## Eight required proof categories

1. Independently authenticated original Champion-001 executable/weights and immutable provenance.
2. Native Champion-001 probability from a reproducible point-in-time feature snapshot.
3. Forward/out-of-sample calibration for the exact league and market.
4. Independent exact-game identity linked to source and league event IDs.
5. Exact bookmaker market, rules/settlement, line, player and selection identity.
6. Fresh, executable DraftKings checkout price at the actual review time.
7. Confirmed current injury/roster/active status for markets involving players.
8. Separately controlled model-release authorization and review.

Existing saved ESPN records and research-market rows provide **context**, not this entire evidence set. A game-name match is not an exact event-ID or market-ID match. A checksum of a user-created manifest does not authenticate Champion-001. A DraftKings-labeled odds-aggregator row does not guarantee an executable DraftKings checkout quote. Retrospective hit rates cannot substitute for prospective forecast calibration or true CLV.

**Until independent evidence custody and a separate release verifier exist, every gate stays blocked and the final decision remains HOLD, even if an untrusted archived report says a bet is certified.** This explicit fail-closed boundary protects your frozen production model.

This milestone does **not** implement production certification, select a winning bet, or count any shadow prediction as certified. Its purpose is to make the missing evidence visible for each proposed market and identify what must be built or independently supplied next.

## Access

Open the GitHub workflow **Freddy's Picks AI V9 - Six Staff Pregame Meeting (read-only)** and inspect the most recent successful run's Actions Summary. Download the run's artifact bundle for full per-game gate details. A green workflow means the audit ran; it does not mean a positive-EV pick was certified.
