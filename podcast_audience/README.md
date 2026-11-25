# Public viewer-question service — separate from CEO private Worker
Do **not** deploy this inside freddys-v9-private-voice. It accepts public viewer questions on a separate Workers domain without exposing the host studio.

## Provisioning
1. Create Cloudflare Turnstile widget for your chosen *public* question-page domain and copy SITE KEY.
2. Create D1 database with `npx wrangler d1 create freddys-podcast-questions` and copy actual database UUID into a new local `wrangler.jsonc` copied from `wrangler.jsonc.example`. Never commit secrets.
3. Apply remote migration with `npx wrangler d1 migrations apply freddys-podcast-questions --remote`.
4. Add Worker secrets `TURNSTILE_SECRET_KEY` and `PODCAST_QUESTIONS_ADMIN_KEY` (random >=24 characters) with `npx wrangler secret put NAME`; set non-secret `TURNSTILE_SITE_KEY`.
5. Deploy using `npx wrangler deploy` from `podcast_audience`.
6. Configure separate private voice gateway secrets `PODCAST_QUESTIONS_ADMIN_KEY` with the matching value and `PODCAST_QUESTIONS_SERVICE_URL` with this service's verified https address; optionally `PUBLIC_PODCAST_QUESTIONS_URL` for the safe user-facing form link.
7. Confirm Turnstile rejects invalid tokens, legitimate viewers can submit, and only the CEO's authenticated private gateway can read pending questions.
Do not publish the public question link until the protections above are validated.

**Privacy:** Submission captures a display name and question only, stores pending rows in D1, and does not show answers publicly. Cloudflare platform logs may still handle request metadata/IP. Establish a retention policy and delete old questions periodically. No automatic audience-question publishing or AI prompt ingestion.
**Security:** Turnstile server-side verification, per-IP rate limit (per Cloudflare location), input cap and allowlisted database fields. Admin list uses bearer key, never put the key in browser code. No audience service can access your CEO session or billing credentials.
