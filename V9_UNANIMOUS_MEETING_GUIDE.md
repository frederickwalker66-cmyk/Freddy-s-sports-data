# Freddy's Picks AI V9 — Unanimous per-pick pregame meeting

**CEO rule:** Evaluate only the exact picks the staff and CEO actually review. Each pick is its own decision. A single employee's REJECT, HOLD, ABSTAIN or missing vote blocks that exact pick, not all other picks in the meeting. For an eligible pick, require six independently attributable staff APPROVE votes on the identical game, market, side, line, bookmaker and quote, **plus CEO final approval**.

## Named boardroom role cards (expert responsibilities, not claims of real-world credentials)

| Employee | Voice | Job / expertise |
|---|---|---|
| Bella | Female | Command Center Manager: agendas, time windows, data freshness, consensus coordination |
| David | Male | Sports Data Analyst: source data, matchups, injuries, player L5/L10, schedule and event IDs |
| Cassidy | Female | Sharp Edge Analyst: frozen native Champion forecasts, forward calibration, executable odds, market-level EV |
| Roger | Male | Parlay Builder: market settlement, 4/6/8-leg proposals, conditional dependencies and correlation |
| Sarah | Female | Risk Manager: counterarguments, bankroll discipline, price/line sensitivity, kill criteria |
| Adam Stone | Male | Audit Engineer: GitHub run IDs, source hashes, timestamps, data integrity and independent authentication |

CEO's own ElevenLabs **Freddy voice** remains reserved for CEO. The voice agents can *hand off* a conversation in ElevenLabs (one speaking at a time). They are not yet wired to authenticated GitHub tool feeds or a synchronously lip-synced seven-person animated boardroom. Do not describe this as a fully deployed simultaneous live meeting.

## GitHub reporting

The V9 pregame meeting automatically writes two additional reports:

* V9_UNANIMOUS_PER_PICK.json — machine-readable per-pick vote status, specialist role cards, independent verification HOLD reasons.
* V9_UNANIMOUS_PER_PICK.md — named staff roster and per-reviewed-pick decision table in the GitHub Actions Summary.

Without an independently authenticated candidate-and-ballot integration, the automated report **does not manufacture candidates or votes**. It shows zero reviewed picks when no source-controlled exact-market candidates exist. All certified bets and shadow bets stay at zero.

## Optional offline / manual research rehearsal

For research rehearsal only, run:

    python v9_unanimous_per_pick.py --certification-json v9_results/V9_PREDICTION_CERTIFICATION_GAPS.json --meeting-json v9_results/V9_PREGAME_MEETING.json --candidates-json local_candidates.json --ballots-json local_ballots.json --output-dir v9_results

Example local_candidates.json:

    {"candidates":[{"league":"NBA","event_id":"1234","market":"moneyline","market_id":"book-market-1234","selection":"Home team","line":null,"american_odds":-120,"sportsbook":"DraftKings","quote_utc":"2026-11-18T13:00:00Z"}]}

The pick's review_id is computed from all exact market and price identity fields. A changed line, odds, timestamp or selection creates a **new pick** with no inherited votes. Use the returned review_id for local_ballots.json:

    {"ballots":[{"review_id":"pick_<20 hexadecimal chars>","employee_role":"Risk Manager","choice":"REJECT"}]}

Other valid choices: APPROVE, HOLD, ABSTAIN. One vote per unique employee and review ID. Unknown, duplicate or conflicting ballots fail closed; all missing ballots remain pending. REJECT on pick A never vetoes pick B. The example above uses fictional sample data, not actual sports evidence.

This JSON is **untrusted manual context**, not an independently verified ElevenLabs transcript or a cryptographically authenticated vote. Even a *reported* six-for-six vote cannot certify a bet while original frozen Champion-001 provenance, per-market calibrated probabilities, current injuries, exact market identity, executable DraftKings prices, and CEO signoff remain unavailable. The final status remains HOLD_NOT_CERTIFIED, without wagers, paid API calls, forced picks, or changes to frozen Champion-001.

## Future independent release prerequisites

1. Obtain authentically versioned native Champion-001 predictions and feature snapshots.
2. Capture point-in-time executable sportsbook checkout price + settlement rules.
3. Authenticate each employee's individual vote using independently controlled signer credentials or trusted live-call attestations. Consent and retention should be configured appropriately for voice transcripts.
4. Bind all six staff votes to the exact immutable pick identity, then record the CEO's separate decision.
5. Recheck injuries, quote freshness, risk and calibration just before kickoff; invalidate changed selections and re-vote.
6. Rank only candidates that actually pass all evidence and governance gates, and keep all others as HOLD/PASS.

No provider credentials, model files or sensitive transcripts are embedded in this repository.
