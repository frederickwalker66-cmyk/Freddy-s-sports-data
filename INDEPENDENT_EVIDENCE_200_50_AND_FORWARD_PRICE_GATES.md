# Independent chronological model evidence + original forward/price validation

**Current release status: HOLD.** These changes implement strict evidence handling;
they do **not** create 250 actual authenticated games, a fitted certified
Challenger model, verified live bookmaker checkout, or any +EV betting pick.

## Existing archives are preserved

- NBA original V8 forward research: branch `research/forward-ledger`, durable
  original-first receipts, separate preliminary outcome grading.
- NFL/NHL original-first V8 forward research: branch
  `research/nfl-nhl-forward-ledger`, waiting for later mature results.
- Champion-001 is frozen and remains unauthenticated by an independent
  executable/model-version review. No code here modifies it.
- The existing SharpAPI feed remains **aggregator research**, not direct
  DraftKings sportsbook checkout.

## NBA dedicated original-source admission (200 + 50)

The NBA home-moneyline research engine now has its own original-source
admission path: `challenger_nba_independent_source_admission.py`. This
**is not** the seven-league non-NBA validator, and it preserves the NBA
engine's binary home-win outcome schema.

A candidate record must have `record_type:
nba_original_pregame_and_outcome_witness_v1`, the existing NBA historical
schema, `settlement_scope: including_overtime`,
`champion_001_modified: false`, a numeric official-compatible game ID,
and two separate attached proofs: `pregame_proof` and `outcome_proof`.

The NBA pregame Ed25519-signed attestation must bind `role:
independent_nba_pregame_custodian`, `league`, `event_id`, `market_type`,
`selection_type`, `settlement_scope`, `event_source_url`, `source_url`,
`original_sha256`, `features_sha256`, `features_asof_utc`,
`captured_at_utc`, `start_utc`. The final-result signed attestation
binds `role: independent_nba_final_custodian`, the same event and
market identity, original outcome bytes SHA256 and numeric `home_won`
label, result observation time and start time. Both original evidence
files must be retained under `--evidence-root`, and both keys must be
vetted by outside custodians rather than generated in the repository.

```bash
python -m pip install -r requirements-calibration.txt "cryptography>=42,<49"
python challenger_nba_independent_source_admission.py \
  --candidates independently_witnessed_nba_games.jsonl \
  --evidence-root nba_preserved_original_bytes \
  --pregame-public-key original_pregame_witness.pem \
  --final-public-key original_final_witness.pem \
  --outdir challenger_results/nba_authenticated_admission
```

This outputs a research-only signed-evidence inventory. Only after
**200 earlier admissible NBA games plus at least 50 later games on distinct
UTC game dates** are available does it create two separate train/holdout
JSONL files and a local holdout digest lock. Earlier game final outcomes
must have been observed before the first holdout pregame snapshot.

The **NBA training CLI now enforces this gate**, requires distinct
externally supplied public keys when historical rows are present, and
refuses to train from URL+hash+Boolean self-attestation alone:

```bash
python challenger_nba_probability.py \
  --history independently_witnessed_nba_games.jsonl \
  --original-evidence-root nba_preserved_original_bytes \
  --pregame-witness-public-key original_pregame_witness.pem \
  --final-witness-public-key original_final_witness.pem \
  --output-dir challenger_results/nba_probability
```

The admitted holdout IDs are passed into the trainer explicitly, to
avoid silently replacing the exact audited split with a default percentage
split. The fitted model uses **training outcomes only**. The holdout may
be used once for research evaluation and is not refit into the persisted
model artifact. An externally vetted primary publisher, trusted
independent as-of timestamps, and externally immutable holdout custody
are still needed before treating these as genuinely qualified source rows.

Unit tests are synthetic, and the source-authentication scripts
explicitly report the gap rather than claiming 250 real NBA records.

## Evidence admission contract (seven non-NBA leagues)

Entry point: `challenger_authenticated_chronological_dataset.py`.

The candidate JSONL records use the existing
`challenger_reviewed_pregame_game_evidence_v1` schema from
`CHALLENGER_MULTISPORT_NATIVE_TRAINING.md`, with two extra objects:

- `pregame_proof`: `{"attestation": {...}, "signature_b64": "...", "original_path": "relative/source.json"}`
- `outcome_proof`: same structure, with an independent outcome custodian.

Pregame exact **Ed25519-signed** JSON payload:
```json
{
  "role": "independent_pregame_custodian",
  "league": "nfl",
  "event_id": "123456789",
  "market_type": "moneyline",
  "settlement_scope": "including_overtime",
  "event_source_url": "https://...",
  "source_url": "https://...",
  "original_sha256": "64-hex",
  "features_sha256": "64-hex",
  "captured_at_utc": "ISO8601 UTC",
  "features_asof_utc": "ISO8601 UTC",
  "start_utc": "ISO8601 UTC"
}
```
Outcome payload keys: `role=independent_outcome_custodian`, `league`,
`event_id`, `market_type`, `settlement_scope`, `event_source_url`,
`source_url`, `original_sha256`, `outcome`,
`captured_at_utc`, `start_utc`.

Each detached signature covers the canonical JSON representation
(sort keys, compact separators). The witness's `original_path` points to
the actual preserved original bytes under `--evidence-root`; their SHA256
must agree with the payload and row. The pregame signature also binds the
canonical `features` hash so the numerical features cannot be swapped after
the fact. Source URLs, settlement scope, exact event identity and observed
timestamps must agree across signed evidence and model rows.

**Never create the signing private keys inside this repository or GitHub
Actions.** Public keys must be provided separately, and the independent
custodians and original publisher timestamps must be externally verified.
Two different keys are required for independent pregame and outcome roles.
A valid Ed25519 signature proves control of a private key and byte integrity:
it does **not** itself prove that the source was genuinely published before
the game or that the custodian did not backdate a timestamp. Independent
point-in-time publication / trusted timestamp evidence is still mandatory
for final qualification and any model release.

## Chronology / holdout lock

The software sorts events by UTC game start and **never splits one date**
between training and holdout. It chooses a holdout from the latest 50 or more
observations, excludes prior training results not actually observed by the
earliest holdout snapshot, and requires **200 earlier + 50 later games per
league**. It rejects duplicate identities, wrong markets, altered raw bytes,
invalid signatures, unavailable-before-game features, future outcomes and
feature schema drift.

Separate train/holdout JSONL files and a local holdout digest lock are written
only when thresholds pass. The local lock refuses changed split records on
repeat runs but is **not immutable external storage**. Before using any
holdout for a release decision, custody must be secured by an independent
write-once archive or trusted third-party snapshot and reviewed externally.
The original held-out outcomes must never be exposed to feature selection.

Command (with independent vetted public keys and real original files):
```bash
python -m pip install -r requirements-calibration.txt "cryptography>=42,<49"
python challenger_authenticated_chronological_dataset.py \
  --candidates reviewed_games_with_external_proofs.jsonl \
  --evidence-root preserved_original_bytes \
  --pregame-public-key witness_pregame_public.pem \
  --outcome-public-key witness_outcome_public.pem \
  --outdir challenger_results/authenticated_admission
```

The native seven-league training **CLI now checks the same admission gate**
and will not use records solely because they self-declare qualified:
```bash
python challenger_multisport_native_training.py \
  --evidence reviewed_games_with_external_proofs.jsonl \
  --original-evidence-root preserved_original_bytes \
  --pregame-witness-public-key witness_pregame_public.pem \
  --outcome-witness-public-key witness_outcome_public.pem \
  --output-dir challenger_results/native_model_training
```

This training CLI continues to produce **research-only** models. A model is
not released automatically on reaching 200+50, even with verified signatures.
NBA retains its separate specialized training path and is NOT admitted by this
seven-league gate.

## Original forward forecasts + sportsbook audit

Entry point: `v8_external_price_receipt_audit.py` consumes first-before-start
research forecasts and purported original sportsbook checkout captures.

It preserves the earliest forecast for each exact
(league, event, market, selection, line, settlement) and rejects later
revisions. It only matches externally witnessed **original** checkout
observations tied to the same event, exact market, selection, settlement
scope and clock, made **0–120 seconds after** the first forecast and before
the event. A detached Ed25519 signature from an independent checkout
custodian must cover the original bytes SHA256 and matching quote fields.
The quote must explicitly be labeled a direct original DraftKings checkout
capture; SharpAPI or other aggregator rows never qualify for this stage.

Command:
```bash
python v8_external_price_receipt_audit.py \
  --forecasts first_original_forward_research.jsonl \
  --quotes direct_checkout_external_witnesses.jsonl \
  --original-root preserved_checkout_original_bytes \
  --checkout-witness-public-key checkout_witness_public.pem \
  --out challenger_results/forward_price_witness_audit.json
```

**Critical:** An external witness's signed statement is **not** a cryptographic
signature from DraftKings or proof of an executable, current sportsbook price.
Source origin, market openness and actual user-visible checkout availability
still need separate primary-source verification. Consequently this module
returns **zero certified model probabilities, zero verified executable
sportsbook prices, zero certified positive EV and no bets**, even if it can
produce a witnessed *research-only* EV calculation.

## Automated regression checks and practical next dependencies

The new workflow `independent-evidence-gates.yml` performs offline unit
tests, daily/manual missing-evidence reports, and uploads only the gate reports.
It uses **no sportsbook credits** and never creates fabricated training
rows. Test fixtures with signed synthetic records are intentionally not
exported as real game evidence.

To reach the requested release-research dataset, an independent source
custodian must provide actual pregame original bytes with authentic
point-in-time evidence for at least 250 distinct qualifying games **in one
league**; an independent outcome/market-settlement custodian must provide
corresponding outcomes. An external assessor must verify source authenticity,
timing and holdout custody. For true EV certification there must additionally
be a trained pregame model with prospective calibration, verified and
available exact bookmaker checkout odds, and independent review.

Never silently turn ESPN retrospective scores, SportsDataIO unverified
numerics, SharpAPI aggregate quotes, or synthetic unit-test fixtures into
qualified games or betting recommendations.
