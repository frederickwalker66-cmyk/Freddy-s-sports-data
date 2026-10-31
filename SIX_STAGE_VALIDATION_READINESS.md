# Freddy's Picks AI six-stage independent validation gate

**Scope:** staged implementation in requested order. **No change to Champion-001**, no SportsGameOdds source, and no wagers.

## 1. Live SharpAPI alignment

The prospective capture workflow listens for `workflow_run.completed` from the exact successful SharpAPI odds collector on main and downloads that **specific run's** artifact, rather than selecting an arbitrary older one. The existing per-quote safeguards still require bookmaker label, correct market/selection, an event in the future, quote age less than 15 minutes relative to receipt, and receipt age less than 15 minutes relative to prospective snapshot. If GitHub queues the workflow for too long, **quotes correctly fail again**; never relax safeguards to inflate availability. Direct DraftKings checkout verification remains unconnected, so accepted observations stay research-only. A scheduled/manual run may still encounter stale quotes; the new event trigger improves synchronization but does **not prove that any fresh quotes have passed**.

## 2. Original Champion-001 authentication

`champion_001_authentication.py` inventories provided model bytes and compares to a supplied hash manifest but NEVER executes/retrains/changes the frozen model. Original independent custody, model provenance, and reference-probability reproduction cannot be proven by a newly generated local manifest. The actual frozen executable and independently attested proof are **not found in the current repository**, so the result is BLOCKED. They must be recovered from an owner-controlled external source before certification.

## 3. NBA historical training qualification

`challenger_nba_history_qualification.py` reviews the NBA candidate queue and the independent published NBA score comparison. It reports genuine second-source score matches separately from independent original pregame-feature proof, independently authenticated receipts, independent game adjudication, and bookmaker settlement rules. It produces **zero automatically qualified training examples**; collecting 250 ESPN-published final scores does not establish 200 independently qualified chronological training games and 50 later holdouts. Never infer available-at-tipoff features from retrospective scores.

## 4. Historical player boxes separated from moneyline

`challenger_nba_player_boxes.py` samples up to **five actually archived NBA event IDs** from the existing research SQLite, requests ESPN's NBA summary and accepts only completed, exactly identified events with two teams, parseable player minutes, DNP markers, points, rebounds, assists and independent raw labels. Unavailable/partial rows fail closed. It does not invent shots, three-pointers, player usage or missing players. Such boxes are one-provider **historical participation research**, not independently verified prop settlement and NEVER pregame moneyline features. Each record has `qualified_for_player_prop_training=false` and `qualified_for_game_winner_training=false`. Other sports' player boxes need **league-specific parsers and official corroboration**; this stage only begins with NBA.

## 5. Actual out-of-sample metrics

`challenger_oos_calibration.py` has independent `league/market/model_version` partitions and requires independently adjudicated outcomes, independently verified pregame features, a separately captured pre-event model output, and true chronological holdout flags. Brier, log loss, 50% threshold hit rate and five-bin expected calibration error are suppressed until a 50+ qualified holdout exists. A no-vig closing market baseline is calculated only for complete same-book, simultaneously verified two-sided lines; closing-line value requires independently verified entry and closing prices; **real betting ROI requires actual independently verified wager receipts and settlements**, not invented $0 hypothetical bets. Missing metrics remain NULL, not zero; no model is promoted merely for passing software tests. The current workflow runs on **empty qualified evidence** and correctly emits a blocked status, not a backfilled probability.

## 6. Artifacts, retention and branch protection

`challenger_artifact_manifest.py` emits SHA-256 hashes of research SQLite, coverage and gate reports and refuses to overwrite an existing manifest. These are **self-issued integrity fingerprints**, not external signatures or WORM/immutable storage. The SQLite artifact still has a 90-day GitHub Actions retention period; its current storage is **NOT durable**.

**Requires repository owner administration (NOT carried out by this workflow):**
- Enable main branch protection / ruleset: require pull request, require a successfully completed offline test workflow, prevent force pushes and branch deletion, restrict bypass, and require at least one independent reviewer. GitHub's connected actions available here do not expose a branch-protection write; main currently reports unprotected.
- Provide a versioned, access-controlled archival destination (e.g., externally configured object-store versioning plus retention/Object Lock), separate write/read roles and external signed artifact manifest. Uploading to an unconfigured cloud bucket or creating one without approved credentials is NOT claimed.
- Retain original Champion binary under independent immutable custody; attach verified reproducibility tests before any production promotion.

**Operational test:** Python fixture suite `tests/test_six_stage_validation.py`; historical backfill also emits blocked Champion authentication, null-qualified calibration and research artifact hashes; post-consolidation job samples at most 5 real NBA box scores.

**Stop/ship decision:** Continue $0 research and validation; do not claim authenticated win probabilities, verified +EV, certified Champion shadows, calibrated Challenger, profit or betting readiness without independently verifiable source evidence.
