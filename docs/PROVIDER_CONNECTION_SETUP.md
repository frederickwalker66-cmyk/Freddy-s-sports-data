# V8 provider connection and certification setup

The gateway is available in `research/trusted_provider_gateway.py` and is opt-in.
It **does not** ship with licensed API endpoints, secrets, source-specific parsing,
a trained Champion-001 artifact, or certified betting decisions.

## Configuration (environment variables; never commit real secrets)

| Variable | Required purpose |
| --- | --- |
| `FREDDY_ODDS_URL` | Full licensed provider HTTPS odds endpoint (including league and market parameters) |
| `FREDDY_ODDS_HOST` | Exact hostname matching the URL (no scheme or path) |
| `FREDDY_ODDS_API_KEY` | Odds provider credential |
| `FREDDY_ROSTER_INJURY_URL` | Full licensed provider HTTPS roster/injury endpoint |
| `FREDDY_ROSTER_INJURY_HOST` | Exact hostname matching the roster URL |
| `FREDDY_ROSTER_INJURY_API_KEY` | Roster/injury provider credential |
| `FREDDY_CHAMPION_ARTIFACT` | Existing frozen Champion-001 artifact path |
| `FREDDY_CHAMPION_SHA256` | Independently established SHA-256 of original model |
| `FREDDY_CHAMPION_RUNNER` | Reviewed Python adapter implementing frozen model inference |

For GitHub Actions, store credentials in **Actions secrets**, not in workflow YAML,
commits, issues, or chat. A configured provider must support the header
`Ocp-Apim-Subscription-Key`; providers with other authentication schemes
need an explicit, tested adapter before connection. The gateway currently
does not automatically map raw provider payloads into exact-market selections.
It does not persist raw licensed data to public artifacts.

Run locally after configuring environment variables:

```sh
python v8_one_command.py --command run_nba --trusted-source-readiness
```

Outputs `v8_results/one_command/TRUSTED_SOURCE_READINESS.json` and
`ONE_COMMAND_REPORT.json`. The gateway does not make network requests
unless the readiness flag is present. An unconfigured endpoint returns HOLD.

## Certification gates (NOT YET IMPLEMENTED END TO END)

1. Confirm licensed provider quote authenticity, market identity, pregame
   freshness, and executable sportsbook availability.
2. Independently confirm event ID, team, roster, player eligibility, and
   timestamped injury/starting status against trustworthy primary sources.
3. Reproduce frozen Champion-001 inference from original artifact and original
   feature pipeline, verify provenance and out-of-sample calibration.
4. Join exact selection/line/odds to model probability and compute EV only
   after all prior gates pass.
5. Recheck all inputs immediately before game start and write immutable
   timestamped receipts; otherwise HOLD/PASS.

A valid HTTPS API response **is not** independently authenticated market
content. A pinned model hash **is not** independent forecast certification.
No TAKE should be issued until these gates are implemented and tested.
