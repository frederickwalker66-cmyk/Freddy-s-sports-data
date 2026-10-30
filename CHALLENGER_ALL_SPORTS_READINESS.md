# Challenger-001 — all eight configured sports linked (research only)

This stage **links existing evidence** by ESPN game ID without re-fetching scores or
using SharpAPI, Sports Game Odds, DraftKings, paid API credits, or Champion-001.
It is **not** a training dataset, certified model, or betting prediction system.

## Leagues

| League | Existing historical source | Secondary results corroboration |
|---|---|---|
| NBA | Capped 35-day ESPN backfill | Existing NBA.com/third-party season archive score audit |
| MLB | Capped 35-day ESPN backfill | Existing MLB StatsAPI score audit |
| NFL | Capped 35-day ESPN backfill | **Not independently checked by this stage** |
| NHL | Capped 35-day ESPN backfill | **Not independently checked by this stage** |
| NCAAF | Capped 35-day ESPN backfill | **Not independently checked by this stage** |
| NCAAB | Capped 35-day ESPN backfill | **Not independently checked by this stage** |
| MLS | Existing 21-day eight-league ESPN archive | **Not independently checked by this stage** |
| UEFA Champions League | Existing 21-day eight-league ESPN archive | **Not independently checked by this stage** |

The workflow retrieves the **latest successful archived run** for each
configured pipeline. The six-league backfill and eight-league archival runs
have different dates and collection coverage. **Do not add their counts as if
they were distinct games**, and do not claim MLB/NBA independent checks match
another run merely because both runs succeeded. Secondary results are
joined by the actual ESPN event ID and reject missing/duplicate source IDs.

## Inputs / outputs

`.github/workflows/challenger-multisport-readiness.yml` runs eight parallel
league evaluations on main and offline tests on pull requests. It reuses
existing GitHub Actions artifacts saved for 30 days:

- Six-league `challenger-backfill-<league>-<run_id>` files.
- MLS / UEFA `challenger-001-history-<run_id>` files.
- The existing `challenger-secondary-nba-<run_id>` and
  `challenger-secondary-mlb-<run_id>` published result comparisons.

For each league the script emits `linked_evidence.jsonl` for existing
**research candidates only** and `readiness_report.json` documenting
original results, research candidates, score agreements, source-day coverage,
missing pregame evidence and blocked training status. An aggregate artifact
reports all eight sports only if every league job succeeded.

To use a local archived backfill:

```bash
python challenger_multisport_evidence_link.py \
  --league nba \
  --results source/published_results.jsonl \
  --candidates source/research_candidates.jsonl \
  --checks secondary/secondary_result_checks.jsonl \
  --coverage source/backfill_coverage.json
```

For MLS / UEFA, pass archived `results.jsonl`, `retrospective_candidates.jsonl`
and `coverage.json`, without unverified secondary checks.

## Meaning of the new linkage

- A matching result from a **separately published source** is useful
  retrospective score corroboration, not proof of historical feature
  publication time.
- Research features derived from final scores using a 48-hour embargo **do not
  prove** that the source data was actually public before tipoff.
- Timestamped lineups, injuries, pregame team metrics, available sportsbook
  odds, official adjudication, and independent as-of evidence remain missing.
- MLS and UEFA three-way markets require their own outcome, draw and settlement
  model. This binary moneyline stage does not train them.
- Additional leagues (WNBA, tennis, etc.) require separate ingestion,
  normalization and settlement logic. They are **not** silently treated as linked.
- An absent historical source, inaccessible artifact, mismatched event ID,
  unverified pregame field, or duplicate game fails closed.
- `qualified_training_examples=0`, certified predictions and betting-ready
  selections remain `0`; `champion_001_modified=false`.

**Next legitimate training milestone:** document pregame data publication and
event-specific timestamps with immutable prospective snapshots (or trustworthy
historical as-of archives), independent final results, larger seasonal samples,
and out-of-sample probability calibration. Preserve Champion-001 frozen.

## October 30 integrity repair — research-only

Two odds-collector GitHub Actions workflows now call `challenger_schedule_crosswalk.py`
before `challenger_audit.py`. A successful ESPN retrieval is only an
**independent public-schedule corroboration**, not an officially verified
DraftKings checkout quote, an injury/roster crosswalk, or a model probability.
The manifest maps each provider event ID to a single ESPN event only when
league, normalized *full* team names and scheduled tipoff (within 60 seconds)
agree. Unknown, conflicting, duplicate or unavailable source matches remain
quarantined. Passing this schedule check can stage research observations but
cannot certify betting value, player props, model predictions or wagers.

NBA historical outcome ingestion now requires **ESPN season.type = 2**
(regular season). Prospective NBA prior-form features and retrospective
research/Elo evaluators also reject untyped or preseason NBA evidence.
This fail-closed behavior may reduce the eligible NBA sample, and prior
research-only descriptive scorecards that used untyped history must **not**
be treated as unbiased regular-season validation or credited to Champion-001.

The collector and daily research audit accept `staged_for_research_only > 0`
only when a matching schedule is present; they still require zero certified
predictions, zero independently verified checkout prices and zero wagers.
Player status and league-operated settlement verification remain unsolved,
and the model backtest is still blocked on absent qualified training data.
Do not claim a B+ grade from passing engineering tests.

## October 30 gate diagnostics — no relaxed certification

`challenger_schedule_crosswalk.py` now records *near-time* public-schedule
matches **separately**, when full normalized home/away names and league agree
but the provider's scheduled start differs from ESPN by **more than 60 seconds
and no more than 15 minutes**. The signed time offset is recorded in seconds
(provider start minus ESPN start), grouped by sport. These near matches are
NOT appended to the schedule manifest's accepted `events` and never bypass
`challenger_audit.py`'s 60-second cutoff. Missing, conflicting, or multiple
possible matches stay quarantined. A 10-minute difference may be the provider's
tipoff convention or inaccurate metadata; the report **does not decide which**.

Both odds-collector jobs now save `quality_diagnostics.json`, which checks
that every original odds observation is accounted for exactly once in the
research-only or quarantine partition. It summarizes by sport the exact
quarantine reason counts, observation freshness buckets (<=120 sec, 121–900
sec, >900 sec, or invalid/future timestamps), and market families. Its test
suite rejects missing or swapped quotes, inadequate schedule provenance,
and any attempted certification. It records **zero** verified sportsbook
checkout prices, qualified historical training examples, certified forecasts,
positive-EV bets, and placed wagers, regardless of stage counts.

At the October 30 pre-repair-to-diagnostics boundary, the SharpAPI run had
22 **NFL** research-stage observations and 0 NBA staged quotes; the
SportsGameOdds run had 0 staged observations because all were unconfirmed
primary lines and too old for strict 120-second validation. These are
one-run observations, not performance claims. This change improves the
explanation and targeting of the data-quality gates; it does not claim to
repair unknown NBA schedule-time differences or generate certified bets.

## October 30 — NBA schedule clock triangulation

The official NBA CDN (`https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json`)
publishes `leagueSchedule.gameDates[].games[]` with NBA game IDs,
scheduled UTC starts and home/away team identities. The new
`challenger_nba_schedule_clock.py` reads that source only to audit NBA
events which were **already rejected** for 61–900-second differences between
ESPN and provider-listed starts. It requires one unique NBA game (same
full home/away names and start within 24 hours) to classify whether the NBA
clock matches ESPN, provider time, or neither. An unavailable official NBA
schedule is recorded as unavailable rather than guessed. The script does
not accept an event, change provider odds, override the existing 60-second
audit threshold, recalculate any probabilities, or certify a bet.

Both odds-collector workflows archive `nba_clock_diagnostic.json` beside
their original independent schedule crosswalk, raw odds, quarantine and
per-league quality report. Any NBA agreement remains **diagnostic-only**;
manual/source verification and a tested policy decision are required before
changing acceptance rules. This source covers the current NBA season and is
not an as-of archive for historical model training.
