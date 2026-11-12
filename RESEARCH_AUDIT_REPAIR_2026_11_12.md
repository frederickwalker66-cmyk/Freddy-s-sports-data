# November 12, 2026 — Fail-closed research-audit repairs

**Scope:** V8 NFL/NHL forward outcome grading and SharpAPI/ESPN crosswalk diagnostics.
This is **not** a model calibration, certified forecast, positive-EV recommendation,
sportsbook checkout verification, automated bet, or production Champion-001 change.

## 1. Genuine ESPN source receipt occurs after grading starts

Run [43138348816](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/runs/43138348816)
failed at `published_score_is_not_verified_source_shape`. The source grader captured
its `current` cutoff *before* calling `historical_outcomes.collect`, whose
`retrieved_at_utc` is intentionally stamped **after** the HTTP response. The old
condition `retrieved_at_utc <= current` could reject any honest live retrieval.

The corrected grader checks the receipt against an observation clock read *after*
collection, without changing the 48-hour game-maturity cutoff, frozen first forecast,
or independent certification policy. A future-dated receipt, malformed row, wrong
source URL, non-regular season row, or duplicated event ID is quarantined and
reported, not treated as a graded win/loss. The artifact still describes ESPN-
**published research** and not official settlement.

## 2. Overnight SharpAPI rows do not equal future matched events

Run [43148647803](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/runs/43148647803)
had 1,618 aggregator odds rows (18 NBA main, 0 NBA props, 1,600 NFL) and zero
independently verified checkout prices or qualified model probabilities. No
independently matched future event was available; `run_sharp` reported zero
certified edges. This is not evidence that valid betting edges exist.

The crosswalk now explicitly records source-price timing categories (already
started, observed after tipoff, beyond the bounded seven-day horizon, malformed
time, untrusted identity, or eligible pregame) and actual queried ESPN Eastern
dates. It **does not** change the original requirement for an exact league,
home/away identity, and start within 60 seconds of ESPN, nor does it label an
unmatched quote as valid. If there are no eligible future sportsbook observations,
the correct output remains no source requests / no certified edge, not a
fabricated match.

## 3. Validation and release gates

Offline regression tests cover post-fetch clock ordering, future-dated receipts,
non-regular-season published scores, duplicated IDs, malformed records, source
errors, stale late-night quotes, bounded lookahead, and zero-certification
invariants.

Champion-001 remains frozen. Challenger-001 still requires independently
authenticated native pregame prediction evidence and eligible chronological
training/holdout games. V8 research scorecards retain their 48-hour result
maturity and 50-game minimum for provisional aggregate scoring. No files in
the Champion-001 model, production selection, betting, or model promotion paths
are changed. Do not merge to production without reviewing CI and downstream
source diagnostics.
