# Freddy's Picks AI V9 — Sharp Edge Board + Pregame Staff Meeting

This V9 milestone attaches the six virtual staff roles to **saved GitHub Actions evidence**, then convenes a **read-only meeting for games scheduled to begin within 90 minutes**. Every published meeting includes an individual six-role summary, original source-run reference, source age, upcoming games, market categories, evidence gates, and the final team decision.

## How often it runs

- Original eight-sport ESPN schedule capture already attempts at **:27 and :53 UTC each hour**, 24 hours a day (GitHub cron is best effort). A separate source watchdog runs at **:17 each hour** and can request bounded recovery if stale.
- The pregame review starts after successful source workflow completions, at **:45 UTC every hour** as a fallback, or manually. It **does not** start another paid or free sports-provider collector. It only downloads already archived GitHub research artifacts.
- Existing 8 AM/5 PM Eastern ChatGPT reporting schedules, Champion-001 freeze and separate daily audit remain unchanged.
- A GitHub schedule does not guarantee exact pre-tipoff execution. It is a timed research review, not a meeting of six continuously autonomous ChatGPT sessions.

## What the employees discuss

The Command Center Manager identifies fixtures and workflow health. The Sports Data Analyst checks the timestamped eight-sport schedule archive. The Sharp Edge Analyst summarizes stored moneyline, spread, over/under, player prop and combo evidence without treating research probabilities as Champion-001. The Parlay Builder examines why four-, six-, and eight-leg proposals lack independently verified joint probability. The Risk Manager vetoes uncertified selections. The Audit Engineer retains archive pointers, timestamps, and reasons for HOLD.

**Every game remains HOLD until** native Champion-001 output, game-and-market-specific calibration, official player availability, identical offered sportsbook market and executable quote, legitimate timing, and correlated joint probability (if parlay) are independently established. The current board merely indexes archived receipts and **cannot claim real-time DraftKings prices, live sharp action, independently certified EV or a validated prediction**. Six-role consensus alone never creates data.

## Mobile access

After the PR is merged and Actions passes, open [V9 Pregame Meeting](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/v9-pregame-meeting.yml). The run Summary displays the final six-role review. The artifact called `v9-pregame-research-meeting-<run id>` contains:

- `V9_SHARP_EDGE_EVIDENCE_BOARD.json` and `.md`: source-hashed research rows, historical observations, and gate status.
- `V9_PREGAME_MEETING.json` and `.md`: per-game time window, six-person findings, and final team decision.

A completed green workflow says the audit software ran; it does not certify any picks. No wagers, paid provider requests, model changes or nonzero shadow stakes are created by this workflow.
