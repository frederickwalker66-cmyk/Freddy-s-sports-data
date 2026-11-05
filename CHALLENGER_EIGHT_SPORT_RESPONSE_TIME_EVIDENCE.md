# Challenger-001 — Eight-Sport Per-Response Pregame Observation Clock

## Failure mode eliminated

Previously, the seven-day eight-sport ESPN collector attached the SCAN START timestamp to every returned schedule event. A collection that took multiple minutes could therefore label a response obtained AFTER an event's kickoff as having been observed before it. Such false as-of evidence must not enter prospective research or chronological training.

## Implemented

1. A seven-day prospective scan now requires a real timezone-aware observation clock. The live CLI supplies actual UTC wall-clock time; synthetic tests inject a fixed deterministic clock. Single-day legacy report callers remain compatible without the new multi-day rule.
2. Each of the at most 64 ESPN date requests records its own UTC request start and response finish (or failed attempt end) in the source audit. Clocks must be timezone aware, non-regressing, no earlier than the scan start. If an attempted scan crosses the Eastern calendar day boundary, the response is not accepted as part of the previous day's dated scan.
3. A pregame event receives its ACTUAL schedule response completion timestamp, not the start of the scan. A game that starts while a slow response is fetched is rejected as not a pregame observation.
4. The requested YYYY-MM-DD must equal the game's scheduled Eastern calendar date, not just its approximate UTC day. A returned game from a different date is quarantined with an explicit wrong-date count instead of terminating the date lookup early.
5. The coverage audit now checks the ordered request/response timestamps, and requires every discovered and subsequently archived ESPN event to correspond to the exact response receipt URL, requested Eastern date and observed UTC time. Fabricated, edited, missing or inconsistent as-of timestamps fail closed.
6. The scheduled 8:15 AM / 6:15 PM EST scans and existing SharpAPI-triggered scans use the same clock guard. A passing offline test does not establish live source availability; live count verification still requires the next actual capture artifact.
7. Six additional deterministic tests cover a response after tipoff, clock regression, receipt tampering, wrong date, mandatory live clock and normal multiple-request reconciliation. Existing 20 seven-day tests and the full repository safety suite are retained.

## No betting promotion

ESPN is a public third-party source, not an independently authenticated official league source. An original same-run event and receipt do not certify the upstream publisher's historical publication timestamp, player eligibility, actual DraftKings checkout prices, trained probabilities, calibrated EV or sportsbook settlement.

Champion-001 remains frozen. New independently qualified training rows, certified Champion/Challenger predictions, verified positive-EV bets and automated wagers all remain ZERO.
