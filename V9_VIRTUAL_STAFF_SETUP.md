# Freddy's Picks AI V9 — Virtual Staff Command Center

Six specialist **read-only software roles** report to one GitHub Actions Summary and JSON/Markdown board. They are *not* independent ChatGPT accounts or authenticated native sports prediction engines. They use actual execution metadata from the existing repository.

| Virtual employee | Responsibility | Fail-closed requirement |
| --- | --- | --- |
| Command Center Manager | Combine workflow health, failed runs and dashboard status | Job success never equals data accuracy |
| Sports Data Analyst | Track official-source, SharpAPI, injury and player L5/L10 source workflows | Unknown odds/lineups marked unverified |
| Sharp Edge Analyst | Assess readiness for calibrated probability and independent price evidence | All unauthenticated EV marked HOLD |
| Parlay Builder | Assess mixed-market parlay readiness, risk and correlations | No invented 4/6/8-leg tickets or joint probabilities |
| Risk Manager | Enforce original model, settlement, quote and wagering gates | Frozen Champion-001, no wagers or paid calls |
| Audit Engineer | Identify failed/stale workflows and inspect evidence provenance | Green Actions jobs do not release the model |

## How it runs

The existing **all-sports ChatGPT automation** is already scheduled at **8 AM and 5 PM America/New_York**. A separate Champion audit also runs every morning. Do not create redundant automations.

This new GitHub Actions workflow starts when the existing **Phone Command Center** or **V8 One Command** workflow completes, and on explicit manual dispatch. After merge into `main` it also runs upon its own initial push. It does not dispatch a second sports scan or invoke any sportsbook API. GitHub events and scheduled tasks can be delayed; the virtual-staff board records status snapshots, not guaranteed real-time quotes.

To review manually on mobile, open [V9 Six Virtual Staff](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/v9-virtual-staff.yml), tap **Run workflow**, then open the run Summary or download `v9-six-staff-dashboard-<run-id>`.

Generated outputs: `V9_VIRTUAL_STAFF_BOARD.md` (one-display six-role dashboard) and `V9_VIRTUAL_STAFF_BOARD.json` (machine-readable role statuses).

## Limits and security

- Retain frozen Champion-001 and unpromoted Challenger-001. No code path trains or replaces either.
- Do not run SportsGameOdds or use its archived odds as current quotes.
- Do not infer DraftKings checkout availability, authenticated player eligibility, calibrated probability, market expected value or certification from job status.
- No automated wagers, no paid API calls, and shadow stakes are $0.
- Review and merge the pull request before claiming unattended GitHub execution is live.
- For a genuinely autonomous prediction-and-qualification workforce later, add secure evidence artifacts, sport/market-specific independently calibrated model predictions, verified odds and original outcomes before changing the release gate.
