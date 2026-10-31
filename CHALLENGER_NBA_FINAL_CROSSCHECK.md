# Challenger-001 NBA official final-score comparison (research only)

This stage follows the existing eight-sport evidence bridge and NBA historical
review intake. It compares previously archived ESPN-published NBA final scores
to a **separate league-owned** NBA CDN season schedule where available.

Source:
`https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json`

Run on pre-existing NBA historical review candidates:

```bash
python challenger_nba_official_final_crosscheck.py \
  --candidates prospective_validation/nba_history_review_candidates.jsonl \
  --output-dir prospective_validation
```

Outputs:
- `nba_official_final_crosscheck.jsonl` — match/score status per candidate,
  source retrieval time, original ESPN label, and official NBA game ID when
  exactly one same-teams/time match exists.
- `nba_official_final_crosscheck_report.json` — counts of agreeing, conflicting,
  missing, ambiguous, unfinished or unavailable results.

A matching candidate MUST have the same home/away teams, a unique game within
30 minutes of its observed tip time, NBA final status, and the same final
points for both teams. A fallback based on just matchup names or a fabricated
final outcome is forbidden. If NBA's schedule is blocked, unavailable or no
longer covers the historical season, the report records source unavailability
and **zero score agreements**; the workflow must not invent a result.

**Trust boundary:** score agreement establishes only that two different
published feeds currently display matching results. It does NOT authenticate
the original NBA source publication timestamp, the historical feature
availability at the original pregame cutoff, ESPN's same-provider feature
history, NBA team's player/injury context, original receipt signatures,
the relevant bookmaker's moneyline settlement, or a calibrated model
probability. Passing a score comparison does not make a training example
eligible.

No market prices are fetched. No SportsGameOdds calls or dependencies.
No `historical_results.jsonl` or trained model is emitted. All candidate
training eligibility flags remain false. Original Champion-001 frozen.
