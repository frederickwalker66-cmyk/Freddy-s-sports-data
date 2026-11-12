# V8 all-sports arbitrage — one-command research guide

**Purpose:** scan already acquired, timestamped prices across bookmakers for a *theoretical* two-way or three-way price mismatch. This is independent of Champion-001, Challenger-001, model probability, EV calibration and CLV. It does **not** verify real sportsbook checkout prices, stake capacity, market rules, or guarantee a profit. It never bets.

## Run from Android or Windows

1. Open [V8 One Command](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/v8-one-command.yml).
2. Select **Run workflow** on **main**; select **run_arbitrage** and submit.
3. Inspect **Summary**, then download the \`v8-one-command-run_arbitrage-...\` artifact for \`ARBITRAGE_RESEARCH.json\`.

**Current data limitation:** the five saved SharpAPI research archives contain **DraftKings-labeled observations only**. They cannot establish an actual cross-book arbitrage. The command reads those archives without paid-provider requests and must return **HOLD/zero** until a second independent bookmaker feed with the same authenticated event and settlement identity is supplied.

## Manual local input for researching multi-book odds

Pass an explicitly sourced JSONL file (one quote per line). Fields required for each record:

- \`source\` = \`manual_research\` or \`sharpapi_rest\`; \`record_type\` = \`pregame_odds_observation\`.
- \`league\`, \`event_id\`, \`home_team\`, \`away_team\`, \`event_start_utc\` must match **exactly** across the candidate's books.
- \`sportsbook\` is the distinct bookmaker, \`market_type\` is \`moneyline\`, \`point_spread\`, \`total_points\`, \`player_prop\`, or \`three_way_90_minute\`.
- \`selection_type\`: home/away, over/under or home/draw/away as appropriate. \`settlement_scope\` is a claimed, explicit exact-match settlement definition such as \`full_game_including_overtime\`. Same name does not prove same real bookmaker rule.
- \`odds_american\` integer, \`quote_at_utc\` and \`observed_at_utc\` actual UTC instants, \`line\` matching canonical spreads/totals/props, \`player_id\` and \`prop_stat\` for player props.
- \`is_main_line=true\`, \`is_alternate_line=false\`, \`is_live=false\`, \`certified_prediction=false\`, \`model_probability=null\`. For soccer 3-way use \`settlement_scope="regulation_90_minutes"\` and \`draw_included_in_outcome_partition=true\`.

The machine uses at most 120-second-old observed quotes, refuses old provider timestamps, permits at most 30 seconds of crossbook quote skew, chooses each book's **latest** offering, and requires at least two bookmakers and a complete identical-outcome partition. NFL two-way moneylines are excluded because a tie can void tickets.

Illustrative JSONL records (synthetic prices, **not** a current betting opportunity):

\`\`\`jsonl
{"source":"manual_research","record_type":"pregame_odds_observation","league":"nba","event_id":"DEMO-1","home_team":"Demo Home","away_team":"Demo Away","event_start_utc":"2026-11-13T01:00:00Z","quote_at_utc":"2026-11-12T23:58:00Z","observed_at_utc":"2026-11-12T23:58:20Z","sportsbook":"book_a","market_type":"moneyline","selection_type":"home","settlement_scope":"full_game_including_overtime","odds_american":110,"line":null,"is_main_line":true,"is_alternate_line":false,"is_live":false,"certified_prediction":false,"model_probability":null}
{"source":"manual_research","record_type":"pregame_odds_observation","league":"nba","event_id":"DEMO-1","home_team":"Demo Home","away_team":"Demo Away","event_start_utc":"2026-11-13T01:00:00Z","quote_at_utc":"2026-11-12T23:58:00Z","observed_at_utc":"2026-11-12T23:58:20Z","sportsbook":"book_b","market_type":"moneyline","selection_type":"away","settlement_scope":"full_game_including_overtime","odds_american":110,"line":null,"is_main_line":true,"is_alternate_line":false,"is_live":false,"certified_prediction":false,"model_probability":null}
\`\`\`

These sample timestamps expire; replace them only with genuinely observed quotes before running.

\`\`\`powershell
python v8_one_command.py --command run_arbitrage --arbitrage-input my_crossbook_quotes.jsonl --output-dir v8_results/arb
\`\`\`

The output reports \`inverse_decimal_odds_sum\`, theoretical ROI, cent-rounded **illustrative** stake split, worst modeled payout/profit, book names, odds, timestamps and exclusions. Any positive result has decision \`HOLD_THEORETICAL_ARBITRAGE_NOT_EXECUTABLE\`, **zero verified payouts**, **zero independently verified settlement equivalence**, and **zero wagers**. Never confuse the research bankroll with deposited or committed money.

## What is required before trusting a live opportunity

Independent point-in-time quote capture from at least two legally available sportsbooks; exact same event/player/line and market settlement; independent checks for voids, pushes, quarter/period, overtime, three-way draw, player availability, staking limits and currency/fees; confirmed simultaneous prices and complete legs. In particular, website screenshots or aggregator labels alone do not authenticate checkout quotes. Any change to implement real bet placement requires an entirely separate review and explicit authorization. No automatic wagering is provided here.
