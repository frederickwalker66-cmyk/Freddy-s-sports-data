# Live Sharp Edge certification feed repair — November 21, 2026

## What was repaired

The scheduled \`live-sharp-edge-certification.yml\` previously ran
\`scripts.live_certified_predictions\` without obtaining a candidate input.
When \`certification_input/candidates.json\` was absent, the program returned
an empty list and zero TAKE without explaining that no inputs had been obtained.

The new \`scripts.fetch_certification_candidates\` step can retrieve an
independently produced, **signed**, time-sensitive candidate batch from an
authenticated HTTPS endpoint. The workflow then runs the existing HMAC,
model-version, market-identity, time and expected-value checks. It publishes
both the decision report and a safe feed-readiness report, never the raw
candidate feed or its authentication token.

No original Champion-001 model, odds, predictions, or credentials are supplied
by this change. It does not certify any bets by itself.

## Required independently controlled configuration

Set GitHub **Actions secrets** (not tracked repository files):

- \`SHARP_CERTIFICATION_FEED_URL\`: HTTPS URL of an externally controlled
  signed-candidate source.
- \`SHARP_CERTIFICATION_FEED_TOKEN\`: independently provisioned long bearer
  token (32+ characters). Rotate/revoke outside this repo.
- \`SHARP_MODEL_ATTESTATION_KEY\`: model-evidence custodian's HMAC key.
- \`SHARP_ODDS_ATTESTATION_KEY\`: *different* sportsbook quote custodian's key.

Set GitHub **Actions variable**:

- \`SHARP_APPROVED_MODEL_VERSIONS\`: independently approved model release IDs.
  An entry in this variable is not itself independent model approval.

These values cannot be invented in this repository or entered into chat.
A single person generating two HMAC keys cannot establish independence.
Model originality, immutable version provenance, independently reproduced
reference outputs, prospective calibration, exact market/settlement and
player status, and executable DraftKings checkout receipts still need independent
validation before any bet can be described as certified.

## Feed contract

The private HTTPS endpoint returns UTF-8 JSON:

\`\`\`json
{
  "schema": "signed-certification-candidates-v1",
  "candidates": []
}
\`\`\`

The array is limited to 500 objects and 1 MB. Every nonempty row must include
the **real** \`model_attestation\` and \`odds_attestation\` objects accepted by
\`scripts/certify_sharp_edge.py\`. Both are HMAC-signed records with
\`payload\` and \`signature\` fields. They must reference the exact same event,
market, selection and line. The odds receipt must be fresh, independently
authenticated and still pregame. An unsigned, expired, inconsistent, or
unapproved candidate remains **HOLD**, never TAKE.

Do not expose or commit these candidate payloads, sportsbook authentication
tokens, or original model assets.

## Interpreting output

Download the latest workflow artifact \`live-sharp-edge-certification\`:

- \`certification_feed_status.json\`:
  \`FEED_NOT_CONFIGURED\`, \`FEED_AUTH_NOT_CONFIGURED\`,
  \`FEED_UNAVAILABLE_OR_INVALID\`, \`FEED_EMPTY\`, or \`FEED_RECEIVED\`.
  A received batch does **not** indicate a certified prediction.
- \`live_certified_predictions.json\`: TAKE / PASS / HOLD, exact blocker codes
  and count. \`NO_SIGNED_CANDIDATES\` confirms no active certified input;
  \`NO_CANDIDATE_PASSED_CERTIFICATION_GATES\` means the candidate batch
  contained no qualified TAKE selections.

The source and gate run every 15 minutes by schedule; **quotes older than 120
seconds at evaluation are rejected**. Scheduled execution does not guarantee
quotes will be present or fresh. This workflow does not itself procure original
sportsbook checkout quotes or produce native-model probabilities.

## Privacy / integrity

- HTTPS only, no cross-URL redirects, bounded responses, strict schema.
- Feed authentication token is not printed; raw input is never uploaded.
- Old local candidate inputs are deleted before every feed attempt.
- Pull requests run only offline tests, without live feed secrets.
- The original Champion-001 remains frozen.
- No automated wager is placed.

**Readiness is HOLD until the upstream independent evidence suppliers are
connected, model authenticity and release are validated, and actual signed
candidates pass the separate certification gate.**
