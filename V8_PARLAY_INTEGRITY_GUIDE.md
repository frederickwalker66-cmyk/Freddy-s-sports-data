# Freddy's Picks AI — Placed Parlay Integrity Gate (research only)

This upgrade prevents the November 12 failure mode: treating external-model
"high confidence" picks, sportsbook implied probabilities, or a winning-leg
count as proof of sharp edge. **It never changes Champion-001.**

## Five rules (enforced by `v8_parlay_risk_audit.py`)

1. **Separate user-reported accepted tickets from research:** a `placed` record
   must have an accepted timestamp, stake, accepted *combined* American odds,
   and the bookmaker. A `research` record cannot contain those fields.
   Reported wagers are not independently authenticated sportsbook receipts.
2. **Never substitute history for calibration:** no model probability, joint
   win rate, or certified EV is inferred from recent hit counts or market odds.
   Exact-market native forward calibration is governed by existing separate
   forward-calibration files. A user-supplied probability is not certification.
3. **Flag parlay correlation:** each leg carries an event ID; two or more
   selections on one game are grouped. Two props for the same player in the
   same game receive an additional warning. Multiplying independent leg
   probabilities is prohibited.
4. **Demand actual CLV:** early repricing and user-entered closing quotes are
   not independently authenticated closing receipts. Verified CLV remains
   `null` until external exact-settlement entry/close evidence can be audited.
   Never claim realized CLV for an unaccepted research ticket.
5. **Fail closed:** unverifiable outcomes, prices, athlete identities, or
   probabilities stay `HOLD`. User-reported wins/losses are not independently
   graded. No auto-betting, no Champion-001 modification, zero certified bets.

## Private local example

Create `private_ticket.json` **outside the repository**. The following is
fictional; it contains no personal bet receipt or live recommendation.

```json
{
  "schema_version": 1,
  "ticket_kind": "placed",
  "bookmaker": "Example Sportsbook",
  "accepted_at": "2026-11-12T17:25:00-05:00",
  "stake_usd": "5.00",
  "accepted_american_odds": 8104,
  "displayed_total_payout_usd": "410.20",
  "legs": [
    {
      "league": "nba",
      "event_id": "nba:EXAMPLE-A-EXAMPLE-B:2026-11-12",
      "event_start": "2026-11-12T19:00:00-05:00",
      "market": "moneyline",
      "selection": "example_team_a",
      "line": null
    },
    {
      "league": "nba",
      "event_id": "nba:EXAMPLE-A-EXAMPLE-B:2026-11-12",
      "event_start": "2026-11-12T19:00:00-05:00",
      "market": "player_prop",
      "selection": "under",
      "line": 5.5,
      "player_name": "Example Athlete",
      "prop_stat": "assists"
    }
  ]
}
```

```bash
python v8_parlay_risk_audit.py --ticket-file private_ticket.json --output private_ticket_audit.json
python -m unittest tests.test_v8_parlay_risk_audit -v
```

Only upload generalized report snippets for troubleshooting. Never commit
actual receipts, transaction numbers, gambling account details, or personally
identifying wager data to a public GitHub repository.

The auditor checks payout **math** using the *combined* accepted odds; it does
not invent individual odds or add 30% boosts a second time. Example +8104 at
$5 corresponds to $410.20 total return (not a probability forecast).

## How the result is used

- `ticket_kind=placed` records that the user reports an accepted wager; it
  is separate from `ticket_kind=research` and never counts as a certified model pick.
- `same_event_groups`, `same_player_groups` and `warning_codes` help diagnose
  over-correlation and price/provenance gaps.
- `parlay_settlement`, `actual_winnings_usd`, `joint_model_win_probability_percent`,
  `certified_parlay_expected_value_percent` and
  `verified_realized_clv_percent` are intentionally `null`, not zero.
- True external score grading and authenticated CLV require dedicated future
  evidence-ingestion and independent source verification. This audit does not
  mislabel user claims as externally verified facts.
- The existing `run_nfl_props_edge`, `run_readiness`, and native forward
  calibration workflows remain research-only and unchanged.
