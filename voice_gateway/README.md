# Freddy's Picks AI V9 — Protected live voice boardroom (deployment-ready source)

This is the next construction stage, separate from the public GitHub Pages boardroom. It includes voice-session client source and an ElevenLabs signing gateway, **but it is not deployed or live yet**.

The private app uses the existing six ElevenLabs voice agents. The CEO can start a microphone conversation with Bella, David, Cassidy, Roger, Sarah, or Adam Stone. During the call, the CEO can request an ElevenLabs **one-speaker-at-a-time handoff**. The avatars are still portraits; a speaking indicator responds to voice activity but does not animate mouths or independently verify the current employee after a handoff. The CEO's cloned Freddy voice is reserved; browser microphone audio is not converted to that voice.

## Why the private server is necessary

GitHub Pages is public and cannot safely hold ElevenLabs API keys. A publicly embedded, unauthenticated ElevenLabs voice widget could let unauthorized users spend the owner's voice credits. Official ElevenLabs documentation recommends temporary signed URLs from an authenticated backend.

This solution is prepared for a **Cloudflare Worker protected by Cloudflare Access**, with server-side verification of Access JWT signing key, RSA signature, issuer, audience, email and expiration, plus rate limiting.

Documentation:
- https://elevenlabs.io/docs/eleven-agents/customization/authentication
- https://elevenlabs.io/docs/eleven-agents/libraries/java-script
- https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/
- https://developers.cloudflare.com/workers/static-assets/binding/

## What the owner must configure before the private room works

1. Set up a **Cloudflare account and Access-protected Worker hostname**. Apply an Access policy authorizing only the CEO's verified email (MFA advised). Do not deploy an unauthenticated production endpoint. Cloudflare Access must supply a signed JWT in the Cf-Access-Jwt-Assertion header.
2. In the Worker secret store, configure ELEVENLABS_API_KEY, ACCESS_TEAM_DOMAIN (full https://team.cloudflareaccess.com URL, no trailing slash), ACCESS_AUD (Access application audience tag), CEO_EMAIL (approved email), and the six employee identifiers ELEVENLABS_BELLA_AGENT_ID, ELEVENLABS_DAVID_AGENT_ID, ELEVENLABS_CASSIDY_AGENT_ID, ELEVENLABS_ROGER_AGENT_ID, ELEVENLABS_SARAH_AGENT_ID, ELEVENLABS_ADAM_AGENT_ID. **Never paste keys or the CEO's email into public GitHub, chat or browser code.** Example command run locally inside the voice_gateway folder: npx wrangler secret put ELEVENLABS_API_KEY.
3. Locally run: cd voice_gateway && npm install && npm run check.
4. After Access and secrets are set up, deploy: npx wrangler deploy. The Worker requires JWT authentication for every static asset and the session endpoint. Rate limiting allows five signing attempts per minute per CEO identity and Cloudflare location; this is not a global spending cap. Enable ElevenLabs usage monitoring/alerts.
5. Only after protected signed sessions have been tested, change all six ElevenLabs agents to require authenticated/signed sessions; doing so early may break existing open voice test links and integrations.
6. Explicitly test a short mic conversation and staff handoff. Verify costs in the owner's ElevenLabs account. No test in this repository starts a real call.

An Access-protected hostname and private signing secrets have NOT been set up by this code, so the public GitHub boardroom currently uses only the signed-in ElevenLabs workspace.

## Security rules enforced in code

- Full Cloudflare RS256 JWT verification with remote team JWKS, issuer/AUD/exp and CEO email.
- Unsupported agent roles, missing or incorrect identity, cross-origin requests, missing rate limiter, invalid signatures and failed ElevenLabs responses are rejected.
- The ElevenLabs API key stays on the server. Signed URLs are ephemeral and delivered only by explicit owner-authenticated POST with no-store response.
- No provider keys in GitHub, browser markup or public JavaScript. No sportsbook wagers or Champion-001 modifications.
- Browser transcripts live only in the current session's DOM, rendered using safe textContent. They are not ballot signatures and are not saved by the page. ElevenLabs may retain and bill for actual calls separately.
- Unanimity is six independent approvals per exact reviewed pick followed by CEO approval, and missing model/odds evidence always forces HOLD. Neither the client nor voice gateway authenticates votes or certifies bets.

## Private CEO setup check (safe to run before paid voice)

After hosting under Cloudflare Access and entering your required Worker bindings,
sign into the protected private voice-room URL. Select
**Check private setup · no voice charges**. The server checks:

- Whether the ElevenLabs signing credential is present, without reading it back.
- Whether six syntactically valid employee agent IDs are configured, reporting only a count.
- Whether the Cloudflare rate-limiting and private static-asset bindings exist.
- Whether the owner's cryptographically validated Cloudflare Access identity is present.

The check is implemented as a CEO-only GET at `/api/readiness`. It
never contacts ElevenLabs, starts audio, signs a voice session, or stores a
transcript. It reports `CONFIGURATION_INCOMPLETE` or
`CONFIGURATION_READY_FOR_SHORT_VOICE_TEST`. Even the second status does
**not** mean a live voice conversation was completed, that ElevenLabs calls
are free, or that sportsbook/model evidence is valid.

For a failed readiness check, correct only the missing or invalid Worker
bindings using the Cloudflare Secrets UI. Do not paste their values into
ChatGPT or commit them into GitHub.

## Cloudflare Git-linked production redeployment

The Cloudflare production Build settings shown by the owner use the connected
`main` branch, root directory `voice_gateway`, build command
`npm install && npm run build`, and deploy command `npx wrangler deploy`.
A new commit changing this directory should request another Cloudflare build
**if those settings have been saved and Git deploys are enabled**.

After any redeployment, confirm in Cloudflare **Deployments / Builds** that the
new commit finished successfully. Then open the production URL behind the
existing **Freddy only** Access policy: the browser must show six employee
portraits rather than Cloudflare's "Hello World" starter. Use the protected
**Check private setup · no voice charges** button before ever starting a live
voice call. A GitHub CI success does not establish that Cloudflare deployed,
that Access authentication succeeded, or that the required Worker secrets exist.

## Offline test and build

- npm run test: synthetic JWT, origin, unauthorized user, unknown employee and provider safety tests; no API calls.
- npm run build: bundles the official @elevenlabs/client package into dist/ using esbuild.
- npm run check: test and build.
- GitHub Actions performs these checks, **but does not deploy the private Worker or start any paid voice call**.

The public docs/boardroom.html stays public, read-only and free of ElevenLabs agent IDs, keys, microphones or session tokens. The protected voice room will have a separate URL when hosting is configured.
