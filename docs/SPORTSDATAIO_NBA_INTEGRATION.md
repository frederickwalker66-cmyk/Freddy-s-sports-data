# SportsDataIO NBA endpoint integration

The authenticated probe uses documented NBA production endpoints:

- `/v3/nba/odds/json/GameOddsByDate/{date}`: pregame game odds.
- `/v3/nba/odds/json/BettingEventsByDate/{date}`: betting events for props discovery.
- `/v3/nba/scores/json/Players`: current NBA players.
- `/v3/nba/projections/json/InjuredPlayers`: injured players.

Official API documentation: https://sportsdata.io/developers/api-documentation/nba

Store `SPORTSDATAIO_ODDS_API_KEY` and `SPORTSDATAIO_NBA_API_KEY` in
your local environment (or GitHub Actions secrets when a workflow is wired
to consume them). These may be the same key if your plan covers both
products. Do not commit credentials.

Run: `python v8_one_command.py --command run_nba --sportsdataio-nba-probe`

The command writes `SPORTSDATAIO_NBA_READINESS.json` to the V8 output
directory. It makes real HTTPS calls only if credentials are available.
No response is interpreted as verified DraftKings odds unless the
sportsbook identity, available outcomes, timestamps, and exact lines
are mapped and independently checked. Player records require identity
matching and injury confirmation; this probe does not yet do so.

**Certified TAKE remains zero until original Champion-001 model artifact,
native inference, out-of-sample calibration, market-specific source
verification, and positive EV pass independently.**
