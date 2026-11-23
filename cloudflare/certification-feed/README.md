# Independent certification feed — Cloudflare transport

This component transports externally signed candidate records; it does **not** create model predictions, authenticate Champion-001, independently verify odds, sign records, or approve releases. The Python certification gate retains final authority and HOLD behavior.

## Deploy
1. Deploy `cloudflare/certification-feed/worker.js` as a separate Cloudflare Worker controlled by the independent evidence custodian.
2. Create a Cloudflare KV namespace and bind it to the Worker as `CERTIFICATION_EVIDENCE`.
3. Create two different random secrets (minimum 32 characters) in Cloudflare Worker secrets: `FEED_READ_TOKEN` and `FEED_WRITE_TOKEN`. Do not store them in git or logs. Keep the write token with the independent evidence custodian only.
4. The independent custodian POSTs `{"schema":"signed-certification-candidates-v1","candidates":[...]}` to `https://<worker-host>/v1/candidates` with `Authorization: Bearer <FEED_WRITE_TOKEN>`. All candidate rows must contain original model, odds, and release attestations. The worker stores them for 15 minutes only.
5. In GitHub Actions repository secrets set `SHARP_CERTIFICATION_FEED_URL` to the **GET** endpoint and `SHARP_CERTIFICATION_FEED_TOKEN` to the **read** token. Set independent, distinct `SHARP_MODEL_ATTESTATION_KEY`, `SHARP_ODDS_ATTESTATION_KEY`, `SHARP_RELEASE_ATTESTATION_KEY` held by their respective custodians, and `SHARP_APPROVED_MODEL_VERSIONS` as a GitHub Actions variable after authenticating the original model.
6. Run `live-sharp-edge-certification.yml`. Inspect its summary and artifact. A green workflow check does not imply any certified TAKE.

## Security boundaries
The prediction engine must not possess the odds or release signing secrets. The worker must not possess the model, odds, or release signing keys. The writer token is **not** a certification signature. Deploying this worker alone cannot produce genuine certified predictions.

Cloudflare KV is eventually consistent; allow propagation and use a single independent writer. For higher-assurance intake, use an authenticated database or Durable Object and independent audit logging. Do not upload placeholder, backfilled, or fabricated predictions.
