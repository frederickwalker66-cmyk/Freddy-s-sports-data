# Challenger-001 All-Sports Prospective Evidence Bridge

Status: **research-only and fail-closed**. Original Champion-001 frozen.

## Scope

This module is named `challenger_multisport_evidence_bridge.py` and processes
all eight **currently configured** competition feeds (not literally every
sports competition in the world):

| League | Research-only result type | Training status |
|---|---|---|
| NBA | Published score winner, binary | Blocked |
| NFL | Published score winner, binary | Blocked |
| MLB | Published score winner, binary | Blocked |
| NHL | Published score winner, binary; market overtime rules unverified | Blocked |
| NCAAF | Published score winner, binary | Blocked |
| NCAAB | Published score winner, binary | Blocked |
| MLS | Home/draw/away three-way published score | Blocked |
| UEFA Champions League | Home/draw/away three-way published score; knockout/extra-time rules unverified | Blocked |

"Binary" and "three-way" above describe **published result research only**,
not validated sportsbook market settlement. Markets must be checked separately
for regulation, overtime, extra time, penalty shootouts, pushes and voids.

WNBA, tennis, MMA/UFC, golf, Formula 1 and other competitions are **not yet**
in the connected eight-league feed. They must be added only after a verified
schedule feed, participant identity and explicit market/result/settlement rules
are implemented. This bridge does not fake additional coverage.

## Pipeline

`.github/workflows/challenger-prospective-outcome-validation.yml` already
retrieves archived prospective snapshots and links later published ESPN finals.
This branch adds another step after that linkage:

```bash
python challenger_multisport_evidence_bridge.py \
  --snapshot-root snapshots \
  --linked-results prospective_validation/linked_pregame_outcomes.jsonl \
  --output-dir prospective_validation
```

The module selects the **earliest** real prospective snapshot for each event,
blocks same-time conflicting snapshots, checks exact event/league/team/time
identity against the outcome linkage, and rejects missing/duplicate/ambiguous
published finals. It also checks whether each team's 3–5 prior-game
form evidence had valid saved timestamps at the snapshot cutoff. Missing
historical form is not filled with fake zeroes.

It writes only:
- `all_sports_evidence_review_queue.jsonl`
- `all_sports_evidence_report.json`

These are inspection artifacts, **not** `historical_results.jsonl`, **not**
qualified model training input, and **not** independently verified outcomes.
On-the-fly SHA-256 fingerprints of JSON objects are change-detection metadata,
not third-party source authentication.

## What remains for real model training

1. Independently authenticate original stored snapshot receipts, collection
   times, source publication times and season/market definitions.
2. Independently adjudicate final results, especially overtime and soccer
   three-way settlement. Confirm team/participant IDs.
3. Maintain durable archives beyond the current GitHub Actions retention window.
4. Accumulate enough point-in-time examples **per sport**. Do not combine
   cross-sport observations into a single purported calibrated model.
5. Train separate sport/market predictors using chronologically untouched
   holdouts. Player points, assists, strikeouts, shots and other props need
   entirely separate outcome and minutes/exposure models.
6. Verify actual sportsbook quotes and calculate out-of-sample calibration,
   Brier/log-loss, closing-line value and expected value where evidence exists.

The script intentionally creates **zero** trained models, certified
Champion-001/Challenger-001 predictions, betting-ready selections or wagers.

## Testing

```bash
python -m unittest discover -s tests -v
```

Synthetic tests cover all eight leagues, draws, invalid pregame timestamps,
future-derived features, conflicting archives, incomplete results, unsupported
sports and CLI artifacts. A green test run validates software behavior only.
