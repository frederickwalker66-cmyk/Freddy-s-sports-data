# Challenger-002 — NBA research prediction lane

Status: **development only; not fitted; not wager-ready**.

## Migration
- Retire Challenger-001 from **future active prediction routing only after** the new lane has been tested and explicitly switched over. Preserve all Challenger-001 audit evidence and artifacts.
- Never modify Champion-001, its frozen artifacts, or certified-mode gates.
- Do not relabel existing Challenger-001 outputs as Challenger-002.
- Do not substitute market-implied odds for native model probabilities.

## Required before any model probabilities
1. Independently sourced, timestamped pregame features and outcome labels with immutable provenance.
2. Chronological training split and untouched forward holdout; no leakage from postgame features.
3. A versioned, hashed fitted model artifact with reproducible training script and data manifest.
4. An isolated NBA moneyline scorer emitting original event IDs, UTC capture time, source references, model version, model probability, and uncertainty.
5. Backtest log loss, Brier score, calibration, and baseline comparison on untouched data.
6. Current sportsbook price with timestamp and market ID before computing EV; abstain on stale or missing prices.

## Release states
- `HOLD`: missing model, inputs, freshness, or validation.
- `RESEARCH`: genuine fitted forecast with traceable evidence but no independent certification; no claim of betting readiness.
- `CERTIFIED`: controlled by existing independent Sharp Edge certification, never by this lane.

## Current limitation
The existing Challenger-001 NBA research scorer requires a fitted artifact at `challenger_results/nba_probability/research_model.json`; that file was not present on main at inspection. This document does not claim the model is restored or predictions are available.
