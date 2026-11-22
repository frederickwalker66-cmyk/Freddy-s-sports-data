# SharpAPI connection repair — November 22, 2026

## Verified failure
The `sharpapi-connection-check.yml` run failed in its first step with:
`Add SHARP_API_KEY under Settings > Secrets and variables > Actions.`
The odds request was **not executed**. Provider status-page uptime does not establish account authentication.

## Required one-time secure account action
Open https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/settings/secrets/actions and create a **repository secret** named exactly `SHARP_API_KEY` with the complete SharpAPI key as its value. Do not use a repository variable, README, issue, commit, or chat message. If the complete key was not saved when issued, rotate it in SharpAPI; this invalidates the old key and may affect other integrations.

## Verification
Run https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/sharpapi-connection-check.yml on `main`.
A passing secret-presence check only establishes that GitHub supplied a nonempty secret. API authentication, endpoint support, plan entitlement, response schema, and sportsbook/market freshness must each be independently tested. Do not certify model probabilities or bets based on a green workflow alone.

## Research safety
Keep Champion-001 frozen and isolated from Sharp Edge Pro staging. Retain research-only HOLD/PASS until independently timestamped DraftKings prices, team/roster/injury evidence, original pregame Champion probabilities, calibration, and correlation checks pass. Never print tokens, place wagers, or trigger paid polling automatically.
