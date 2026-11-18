# Freddy's Picks AI V9 — Protected live voice boardroom (deployment-ready source)

This directory holds the private Cloudflare Worker source, separate from the public GitHub Pages boardroom. Check Cloudflare Deployments for the current live version: a successful GitHub build or commit does not independently confirm Cloudflare production rollout or credential readiness.

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

## Zoom Video SDK — private browser video room (custom app, not Zoom Meetings)

A second private page, `/video.html`, has been added under the **same Cloudflare
Access-protected Worker**. It is a mobile-friendly Zoom Video SDK browser client:
- Six named fictional employee **portrait previews**, all clearly labeled
  *Awaiting video bridge*; these are **not** authenticated remote participants
  and are not video streams. Do not misrepresent them as live.
- CEO-only **Check Zoom setup · no charge** button. The protected
  `GET /api/zoom-video-readiness` reports presence of Zoom SDK credentials
  without returning credentials or contacting Zoom.
- After CEO explicitly selects the potential Zoom billing checkbox and clicks
  **Join private Zoom video room**, the protected
  `POST /api/zoom-video-token` issues a one-hour HS256
  Zoom Video SDK JWT server-side using Cloudflare Web Crypto.
  The Zoom key/secret never appear in GitHub or browser source. The endpoint
  requires the existing verified Cloudflare Access JWT, a strict same-origin
  POST, explicit `approved:true`, and rate limiting. It makes **no** Zoom
  API calls. The browser loads the pinned Zoom Web SDK from Zoom's CDN and
  asks Zoom to start or join a session only when the CEO clicks Join.
- After joining, separate explicit **Start camera** and **Connect microphone**
  buttons control permissions and media. Only actually connected Zoom SDK
  participants can appear as live remote video tiles. The app can mute and
  leave. Neither the setup check nor GitHub CI initiates paid calls.
- The Zoom-specific Content Security Policy is limited to `/video.html`,
  not the regular private ElevenLabs voice boardroom. Cloudflare Access
  remains mandatory even when the Zoom Video SDK credentials are absent.

### Owner setup in Zoom Platform Studio and Cloudflare

1. In **Zoom Platform Studio → Video SDK → Credentials**, locate your Video
   SDK **SDK Key** and **SDK Secret**. These are different from Zoom API
   credentials. Do not send them to ChatGPT or commit them to your repository.
2. In Cloudflare **Workers & Pages → freddys-v9-private-voice →
   Settings → Variables and Secrets**, add `ZOOM_VIDEO_SDK_KEY` and
   `ZOOM_VIDEO_SDK_SECRET` as **encrypted Secret** values. Retain existing
   Access policy `Freddy only` and the Access JWT configuration.
3. Wait for Cloudflare to apply the secret binding if necessary. Confirm
   deployment of the latest `main` commit. Sign into the protected
   `https://freddys-v9-private-voice.frederickwalker66.workers.dev/video.html`.
4. Tap **Check Zoom setup · no charge**. This checks configuration locally
   without a provider request. If it says missing, verify the Worker
   secret names (not the secret values). Do not click Join until ready to
   incur Zoom SDK charges and explicitly approve any required Zoom account
   plan/credit enrollment.

### What is not built yet

The Zoom Video SDK session is a **custom browser application**, not a session
inside the Zoom Meetings client. No six autonomous avatar bots currently
connect. The separate `video_bridge/` package contains only an offline
six-participant coordinator; actual video SDK bot clients, credentials,
avatar video rendering and bidirectional ElevenLabs media transport
still require separate authorized runtime hosting, cost approval and integration.
The page clearly distinguishes portraits from actual Zoom SDK participants.
Neither the static portraits nor the V9 voice browser handoff are six native
video participants. Native WhatsApp six-AI group video calls are not offered
by the current supported business API.

Official references:
- https://developers.zoom.us/docs/video-sdk/web/get-started/
- https://developers.zoom.us/docs/video-sdk/web/sessions/
- https://developers.zoom.us/docs/video-sdk/web/video/
- https://developers.zoom.us/docs/video-sdk/web/audio/
- https://developers.zoom.us/docs/video-sdk/auth/

## Optional Zoom + WhatsApp entry points (no automated or paid calls)

This feature adds a section in the **Access-protected private Worker** for
manual Zoom and WhatsApp access. It does not add Zoom/WhatsApp bot participants,
native group calls, scheduling, sending messages, or a bridge from ElevenLabs
into Zoom or WhatsApp. The existing one-speaker-at-a-time voice room is separate
and live ElevenLabs sessions can incur charges only after explicit Start.

**Zoom:**

1. Sign in to your own Zoom account and create or schedule a human meeting.
2. Copy only the Zoom join URL (format `https://us02web.zoom.us/j/12345678901?pwd=...`).
   In Cloudflare **Worker → Settings → Variables and Secrets** add an optional
   **Secret** named `ZOOM_JOIN_URL` containing the actual join link. Keep the
   invite/password out of public GitHub, WhatsApp shares, and screenshots.
3. Redeploy only if Cloudflare indicates the secret change needs it. Sign in to
   the protected Worker and press **Check my Zoom link · no call**. This
   calls only the same-origin, CEO-authenticated `GET /api/integrations`
   endpoint and does not call Zoom or ElevenLabs. If a strict
   `https://zoom.us/j/` or `https://*.zoom.us/j/` meeting link is configured,
   the button **Open my Zoom meeting** appears. It opens Zoom only on click.
   If no valid link is set, the user is told how to configure it.

**WhatsApp:**

- **Share via WhatsApp** prepares a user-selected chat message containing only
  the private room's origin and root path. It does not transmit meeting
  passwords, signed session URLs, identities, access JWTs, provider keys, picks,
  transcripts or any agent configuration. The message is not sent automatically.
- Sharing the room URL does NOT bypass Cloudflare Access: only accounts
  authorized by the private Access policy can enter, even if they receive the
  link. WhatsApp previews could see the URL but cannot enter the room.
- **Copy room link** copies the protected URL on explicit user action. If the
  clipboard isn't available, use the browser's Copy Link action.

**Security behavior:** Static room and setup controls are available to a
cryptographically authenticated CEO even when the ElevenLabs API key is
missing, so the user can diagnose/setup both access options. The
`POST /api/session` voice-signing route still denies calls without the key,
limiter and agent ID. `GET /api/integrations` uses the same JWT verification;
Zoom meeting URLs are validated as strict HTTPS `zoom.us` subdomain and
meeting path, returned only to the authorized CEO and never logged/stored by
this code. A meeting invite with an embedded passcode is a sensitive URL;
protect it as a Worker Secret. WhatsApp share text is derived from the
currently authenticated room origin and excludes all query strings or tokens.

## Offline test and build

- npm run test: synthetic JWT, origin, unauthorized user, unknown employee and provider safety tests; no API calls.
- npm run build: bundles the official @elevenlabs/client package into dist/ using esbuild.
- npm run check: test and build.
- GitHub Actions performs these checks, **but does not deploy the private Worker or start any paid voice call**.

The public docs/boardroom.html stays public, read-only and free of ElevenLabs agent IDs, keys, microphones or session tokens. The protected voice room will have a separate URL when hosting is configured.
