# Challenger #93–96 — NBA pregame research selection ledger

## Purpose

Continue Freddy's Picks AI with a genuinely **prospective, testable, $0-stake**
NBA moneyline **research selection**, without manufacturing a qualified trained
Challenger-001 model or silently using unqualified historical research packets
as independent training evidence.

The existing collector already records ESPN future schedules, actual pregame
snapshots, previously observed team form, and timestamped untrained baseline
home-win probabilities. This change makes its selections explicit and
reproducible from the exact pregame snapshot: not a training bypass.

## #93: Immutable first valid snapshot-based forecast per game

For each NBA event, use the earliest genuinely archived fixed-rule forecast,
verify a corresponding EXACT captured event snapshot, and recompute the
untrained 0.5 + 0.3 * (prior home win rate - prior away win rate) from that
original snapshot.

- Actual source snapshot timestamp <= forecast timestamp < event start.
- Previously observed prior team history required; no fabricated missing form.
- Each probability is independent of sportsbooks, market prices, or result data.
- Home if research P(home) > 50%; away if P(home) < 50%; neutral 50% has no pick.
- Preserve both side probabilities, actual forecast UTC, exact event ID,
  source snapshot checksum, baseline version, and permanent self-issued receipt.
- Reject after-tipoff forecasts, changed baseline values, mismatched fixture IDs,
  conflicting same-time original bytes, and identity revisions.
- Duplicate snapshots/forecasts across runs count ONCE per NBA event.
- A self-issued receipt proves only **local consistency**, not publication
  authenticity, original model provenance or immutable external custody.

## #94: Regression suite

13 separate synthetic-only tests cover live chronology, home/away polarity,
neutral no-pick, exact-probability recomputation, future score exclusion,
duplicate source rows, team revision quarantine, result ambiguity,
source-byte divergence, frozen Champion and no betting.

## #95: Prospective first-capture integration

Runs directly after the existing untrained baseline forecast step in
challenger-prospective-pregame.yml; writes:

- prospective_pregame/nba_untrained_moneyline_shadow_ledger.jsonl
- prospective_pregame/nba_untrained_moneyline_shadow_ledger_report.json

Records actual selections for future NBA events only when the contemporaneous
source is valid. It does not create a certified trained model.

## #96: Later outcome reconciliation

The existing twice-daily outcome-validation workflow downloads actual previous
prospective captures; it now regenerates the earliest selection per event and
links to later published ESPN finals for **descriptive research-only** grading.

- prospective_validation/nba_untrained_moneyline_shadow_ledger.jsonl
- prospective_validation/nba_untrained_moneyline_shadow_ledger_report.json

No odds are appended. Unverified, revised, duplicate, future or inconsistent
final outcomes stay ungraded/quarantined. Training is NOT performed.

## Hard boundaries and current model status

- Champion-001 **frozen and unauthenticated**: zero certified predictions.
- The archived 53 NBA feature/outcome review candidates lack independent
  training qualification; they are **not used to fit a model**.
- The fixed-rule baseline is UNTRAINED; research side probabilities are not
  certified Challenger-001 probabilities, verified +EV or sportsbook offers.
- These research selections do **not** count toward Champion-001's 25–50
  daily certified-shadow target. Research stake and wager stake stay $0.
- Qualified training = 0, certified Challenger = 0, real-money authorization = 0.
- Before a native probability model can be released, authenticate original
  historical pregame feature availability and actual independent outcome
  adjudication; train on distinct qualified games with 200 chronological
  training and 50 later holdout; evaluate genuine Brier/log loss and calibration.

## Reproduce

From a source capture:

    python challenger_nba_prospective_shadow_ledger.py \
      --snapshot-root prospective_pregame \
      --forecast-root prospective_pregame \
      --output-dir prospective_pregame

From archived past capture runs with a separate ESPN published-final link:

    python challenger_nba_prospective_shadow_ledger.py \
      --snapshot-root snapshots \
      --forecast-root snapshots \
      --linked-results prospective_validation/linked_pregame_outcomes.jsonl \
      --output-dir prospective_validation

The existing scheduled workflows automatically execute these steps on their
normal cadence; no additional cron or automation is introduced.
