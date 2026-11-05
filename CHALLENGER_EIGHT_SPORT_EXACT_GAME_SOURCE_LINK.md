# Challenger-001 — Exact per-game original ESPN evidence reconciliation

## Verified problem

After #73, the eight-sport coverage audit verified original response file SHA-256, and that the parsed schedule events match the original ESPN HTTP source. However the *subsequent per-game prospective_event_evidence.jsonl archive* was joined using only ESPN league/event ID and general timestamp bounds. A modified archived team, kickoff, observed time or source URL could still pass the event-ID join. This is a dangerous source-to-training provenance gap, even while all currently qualified training counts remain zero.

## Source-to-game evidence chain

Every archived research game must now match the corresponding original schedule event on ALL these independent dimensions:

1. Exact ESPN league + numeric event ID (uniqueness preserved).
2. Exact ESPN home and away full team names.
3. Exact actual UTC kickoff instant (timezone-offset-equivalent representations allowed).
4. Exact source URL including the original league and Eastern requested calendar date.
5. Exact source response completion timestamp (not merely a time within the scan's interval).
6. Exact SHA-256 of the original response bytes linked through the parsed event and archived pregame game record, required when live original-byte capture is enabled.
7. Exact game archive completion timestamp equal to the prospective capture report, with the observed schedule response and completed archive both strictly before kickoff.
8. Actual number of archived per-game rows equals the reported scheduled game count. Legitimately discovered games that began before archive completion remain explicitly unarchived, not historical forecasts.

The independent original-response stage continues to open, hash and reparse each raw ESPN response byte-for-byte and requires parsed-source equality. That earlier check plus this game-level join closes the full chain original response -> discovered event -> archived pregame row. The response cannot be promoted to independent ESPN publication-time attestation or an official league schedule just because it has a self-computed hash.

## Production gating and testing

The live GitHub all-sports workflow now asserts that the number of exact fully reconciled per-game rows is identical to the number of archived pregame event records, before uploading source evidence. Ten additional synthetic negative/positive tests cover forged teams, kickoff, URL, observation time, missing/forged SHA, altered report count, completion clock and zero certification. All earlier original-byte, response clock and non-bet regression tests remain in force.

## What remains unresolved

- First actual seven-day ESPN capture is still needed to quantify live event coverage by league; a successful push safety suite does not count as a live scan.
- Independent official schedule corroboration, genuine historical source-publisher publication timestamps, athlete active lists, legitimate sportsbook checkout quotes, market-specific settlement and calibrated pregame native model probabilities are still missing.
- **Champion-001 remains frozen, qualified new training games=0, certified predictions=0, verified positive-EV bets=0, automated wagers=0.**
