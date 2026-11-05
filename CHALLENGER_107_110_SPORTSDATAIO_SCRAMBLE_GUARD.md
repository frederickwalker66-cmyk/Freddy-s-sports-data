# Challenger #107–110 — real licensed-provider score integrity and scramble safety

## Evidence recovered on November 5, 2026

After #101–106 was merged, the live NBA source-validation run
[42110497882](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/runs/42110497882)
successfully fetched four dates of original SportsDataIO NBA source bytes.
No API source request error was reported. However, exact final scores did not
agree with ESPN for any of the 53 historical research candidates:

- **38** exact fixture/date/team matches had different NBA scores.
- **2** additional source finals failed the valid-score check.
- **13** candidate games fell outside the four most recent requested dates.
- All 38 score-conflicted matches showed **the same winning team**,
  but the exact points were demonstrably inconsistent.
- Within each represented date, provider scores had almost constant
  multiplicative ratios relative to ESPN:

| Eastern date | Conflicting matches | Median provider/ESPN point ratio |
|---|---:|---:|
| Oct 31 | 7 | approximately 1.661 |
| Nov 1 | 4 | approximately 1.297 |
| Nov 2 | 14 | approximately 0.646 |
| Nov 4 | 13 | approximately 0.714 |

**Important external documentation:** SportsDataIO's official help center
explains that its Free Trial and Dev Key API responses can contain intentionally
scrambled scores, statistics and odds. Team identities and schedules can remain
accurate even when quantitative sports data is not usable for actual analysis:

https://sportsdata.io/help/scrambled-data

https://sportsdata.io/developers

The pattern above is consistent with transformed provider values, but it does
**not** prove the user's exact account plan, license level, or the specific
cause. Don't infer premium access from an API request returning HTTP 200.
Do not use apparent agreement on winner side to claim exact-score
authenticity. Never multiply, divide or otherwise reverse-engineer altered
scores to manufacture accurate game results.

## #107–110 actual pipeline repair

New file \`challenger_sportsdataio_score_scramble_guard.py\` audits the real
original-score comparison rows and checks their source file hashes against
the report. It calculates ratios **only as a diagnostic** of potential
same-day systematic transformation and reports by-date sample size,
range, median and published-score winner agreement.

The script never outputs reconstructed scores, qualified historical training
files, native probabilities, odds or betting picks.

The twice-daily outcome workflow now runs the scrubber immediately after
the licensed NBA final-score check, preserving its report under:

\`prospective_validation/nba_provider_score_integrity_diagnostic.json\`

The combined NBA master release diagnostic reads that report, verifies its
row counts and existing third-party statuses, and elevates
**VERIFY_SPORTSDATAIO_REAL_UNSCRAMBLED_DATA_ENTITLEMENT** to the first
unresolved operational priority. It still runs zero-data native NBA fit
qualification and holds certified deployment.

The existing all-eight-sport pregame research, NBA injury source review,
independent outcome comparison, model-source custody, exact odds-match,
historical training and Champion freeze requirements remain intact.

## Exact external next step

Check SportsDataIO account entitlement outside the source code. Verify that
the key has **real**, non-scrambled data access for NBA scores and stats (and,
separately, the historical/live odds and prop products needed). Re-run exact
same-game published score comparisons after entitlement validation. The code
cannot upgrade or authenticate a provider subscription on behalf of the user.

If a paid real-data entitlement is available, the subsequent independent
source and model training gates still must pass. A provider upgrade does not
retroactively authenticate source publication timing from older archives,
produce the original Champion-001 model or prove any sportsbook checkout price.

**Current certified counts must remain 0 and Champion-001 frozen.**
