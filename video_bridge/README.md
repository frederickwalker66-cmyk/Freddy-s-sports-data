# Freddy's Picks AI V9 — Six-person live video conference integration

## What this project does, and does NOT do

This directory implements the offline **six-identity Zoom meeting coordinator**
and security preflight with automatic partial-join rollback. It DOES NOT
contain a deployable Zoom SDK bot, Zoom server, live audio/video streams, TTS
video avatar renderer, Meeting SDK credentials, or a native WhatsApp group
video call. Do not claim that actual meeting participants have joined merely
because the offline tests pass.

**Goal:** The CEO joins a native Zoom meeting and sees six distinct AI
participant tiles (Bella, David, Cassidy, Roger, Sarah and Adam Stone) who
can speak and send their own real-time video media. A separate, authorized
Linux Meeting SDK process per participant is needed to publish six independent
Zoom identities. Each bot requires a virtual video camera/stream for the
assigned portrait/avatar and a virtual microphone linked to the appropriate
ElevenLabs voice-agent response; route incoming CEO audio through explicit
speaker-turn management to prevent six simultaneous overlapping answers.

Zoom's Meeting SDK can support bots in accordance with current app
authorization, OBF rules for external meetings, host consent, and Zoom's
automated-participant policies. A live Linux bot runtime and virtual
audio/video sources will need to be implemented, integrated and hosted
outside the Cloudflare Worker. **The Cloudflare Worker cannot execute a
Linux Zoom Meeting SDK binary or publish six native Zoom media streams.**

Official Zoom SDK resources (verify requirements before implementation):
- https://developers.zoom.us/docs/meeting-sdk/auth/obf/
- https://github.com/zoom/skills/blob/main/skills/meeting-sdk/linux/linux.md
- https://github.com/zoom/skills/blob/main/skills/meeting-sdk/linux/meeting-sdk-bot.md
- https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0088381

### Platform compatibility

| Platform | Native six-agent AI video conference | Status |
|---|---|---|
| Zoom Meetings | Technically feasible with six SDK bots, separate runtime, authorization and virtual A/V streams | **Not yet integrated or running** |
| Zoom Video SDK custom app | Feasible separately as a custom video chat app, not a normal Zoom Meeting | Not built |
| WhatsApp group video calls | No supported Business Calling API for six programmatic AI video participants | **Not supported** |
| Google Meet | A separate bot/media integration would be needed, with API constraints | Not built |
| Private V9 Cloudflare website | Six selectable fictional portraits with one ElevenLabs audio conversation at a time | Existing independent product, not Zoom participants |

### Minimum real Zoom deployment prerequisites

1. Connect the owner's Zoom account and register the appropriate Zoom Meeting SDK app.
2. Obtain the necessary Zoom app permissions/OBF approvals, host permission and an authorized private meeting.
3. Set up secure server-hosted Zoom SDK keys; never store them in GitHub or frontend code.
4. Provision an appropriate Linux native SDK runtime for **six independent bot processes** with real Zoom participant receipts. Cloudflare Workers alone is insufficient.
5. Provide 6 legally usable generated portrait/avatar video feeds via virtual cameras, plus 6 virtual microphones carrying authenticated agent output from ElevenLabs. Requires a separately implemented bidirectional speech/video media pipeline, synchronization, and consent disclosure.
6. Wire the bot runtime to the backend using authenticated actions and verified Zoom participant-state events. No unauthenticated public API endpoints.
7. Before costs or external operations, require the verified CEO to explicitly approve meeting join and voice/media usage, with limits and teardown.
8. Live-test with **one bot first**, then scale to six and inspect Zoom participant list and video feeds. This project deliberately never initiates that test.

### Offline controls

`node --test video_bridge/test/*.test.mjs` checks that:
- All six identities are distinct.
- A malformed or off-domain Zoom URL is rejected.
- No bot is allowed to start without CEO authorization, manual start and explicit cost approval.
- Six participant receipts and rollback behavior are enforced by a simulated SDK adapter.
- WhatsApp video is never misreported as available.

These tests use in-memory stubs only; no ElevenLabs, Zoom, WhatsApp,
Cloudflare, sportsbook, camera or microphone API calls.

No part of this source code modifies frozen Champion-001, authenticates
sportsbook expert ballots, or places bets.
