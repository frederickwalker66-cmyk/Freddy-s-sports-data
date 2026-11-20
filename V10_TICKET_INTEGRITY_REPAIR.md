# V10 Ticket Integrity Repair — November 20, 2026

This patch repairs **ticket construction and evidence gating**, not the
mathematical accuracy of a predictive model. It does not create new certified
bets, infer a win rate from losing tickets, make wagers, or change Champion-001.

## Joint winning-margin check

If a same-event ticket includes a team moneyline and a point spread, specify
which team is the home or away side **using the explicit \`team_side\` field**.
Do not infer team identity from a free-text selection or a team nickname.

Use the signed handicap for the selected team: away +6.5 is \`line: 6.5\`;
home -6.5 is \`line: -6.5\`. The input represents exact market **win**
conditions, not pushes. The audit outputs lower and upper integer home-score
minus away-score margins and whether those conditions can both win.

Example fictional **research** ticket snippet:

\`\`\`json
{
  "legs": [
    {"league": "nba", "event_id": "synthetic:home-away",
     "market": "moneyline", "selection": "Example Home",
     "team_side": "home", "line": null},
    {"league": "nba", "event_id": "synthetic:home-away",
     "market": "point_spread", "selection": "Example Away",
     "team_side": "away", "line": 6.5}
  ]
}
\`\`\`

When these two selections must *both* win, the home team must win by **1–6
points**. That restriction is **not** a model probability or a claim that the
combination is automatically bad value. It requires a separately validated
joint-outcome model and an independently checked combined checkout price.

If \`team_side\` is missing on a moneyline/spread pair, the result is
\`UNRESOLVED_TEAM_SIDE\`, not a guessed margin or a certified edge.

## Player prop evidence checks

The Challenger preflight now requires explicit evidence fields for prop
research, in addition to a verified quote, active status, and a genuinely
independent model probability:

- \`workload_evidence_verified\`: evidence for minutes/snaps/touches/routes or
  a documented expected-workload projection.
- \`game_script_review_verified\`: check the effect of leads, blowouts,
  offensive pace, injuries, and role substitutions on opportunities.
- \`exact_stat_line_calibration_verified\`: future/out-of-sample performance
  for the exact player-stat-and-line probability model.

All three remain **unverified** when absent, which produces blockers. Boolean
flags alone are not independent evidence; the analyst must retain source
records and timestamps. Prior 5/10 game hit rates and published analyst picks
must never be substituted for a calibrated win probability.

## Regression checks

Run the repo's offline suite after this patch:

\`\`\`bash
python -m unittest tests.test_ticket_outcome_geometry -v
python -m unittest tests.test_challenger_ticket_preflight -v
python -m unittest tests.test_v8_parlay_risk_audit -v
python -m unittest discover -s tests -v
\`\`\`

These are **synthetic tests** and prove logical behavior of the gates only.
They do not certify real live odds, athlete availability, positive expected
value, model calibration, or historical settled tickets.

Never commit a personally identifying sportsbook receipt to the public repo.
Preserve the original pregame ledger unchanged and store real receipt
information privately.
