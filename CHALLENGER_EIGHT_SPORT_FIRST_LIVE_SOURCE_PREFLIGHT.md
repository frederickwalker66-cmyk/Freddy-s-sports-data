# Challenger-001 — First live seven-day eight-sport source preflight

## Why this step matters

November 5, 2026 post-merge GitHub Actions runs after PR #74 validated code only and intentionally skipped actual external source capture. The first scheduled complete seven-day scan had not executed. Offline success does not prove ESPN source access or new per-league game coverage.

This lightweight, read-only GitHub Actions workflow makes one genuine as-observed seven-day source-only run on its first merge to main. It also supports manual dispatch. The existing twice-daily scheduled all-sports collector remains unchanged. No new duplicate recurring scan is added.

## Source and timing evidence

At most eight ESPN calendar-date requests for each of NBA, NFL, MLB, NHL, NCAAF, NCAAB, MLS, and UEFA Champions League, stopping for each sport at the first eligible future slate. Source failures, empty days and finished/unusable games remain separate diagnoses. The original HTTP response bytes are saved per league and Eastern date with source URL, SHA-256, byte length, exact request/response UTC time and game identity. The independent existing audit rereads every original response and reconciles every archived game with its source URL, exact kickoff, teams and observation time.

## Artifacts

The 45-day GitHub Actions artifact contains these files under seven_day_source_preflight/:

- espn_schedule_capture.json: actual source URLs, dates, game listings, responses and failures.
- espn_original_schedule_bytes/*.json: original response bytes, not reconstructed JSON.
- prospective_event_evidence.jsonl: research-only pregame events, no training or betting promotion.
- prospective_report.json: prospective counts and no-bet flags.
- eight_sport_schedule_coverage.json: original-byte and per-game source verification.
- preflight_summary.json: compact eight-league counts, source errors, first upcoming slate dates.

## Use

    python -m unittest discover -s tests -p 'test_challenger_eight_sport_source_preflight.py' -v

    python challenger_eight_sport_source_preflight.py --lookahead-days 7 --output-dir seven_day_source_preflight

Workflow: .github/workflows/challenger-eight-sport-source-preflight.yml

GitHub workflow first checks all synthetic safety tests, then makes live public ESPN requests only on main push or explicit manual dispatch. The first merge creates a one-time live opportunity. Any source failure remains visible; no games are invented. A self-computed hash cannot authenticate an upstream publisher's historical publication time or independent league scheduling.

Even successful source coverage does not certify Champion-001 or Challenger-001 probabilities, verified bookmaker odds, player eligibility, settlement, positive EV, or automated wagering. All corresponding certifications remain zero. Champion-001 remains frozen.

After a successful live run, inspect each sport's future_games_archived and source_days_failed values before deciding which source to repair next.
