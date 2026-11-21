# Sharp Edge Pro — operational acceptance checklist

## Implemented in GitHub
- Five-minute offline readiness checks (best-effort GitHub cron).
- Reused original repository collector dry-run and integrity tests.
- Hourly bounded NBA SharpAPI live collection (maximum 2 requests per run; up to 48 per day) and ESPN schedule corroboration.
- Research-only staging and quarantine; no wagers or certification.
- GitHub Actions artifacts containing timestamped odds and validation reports.

## Not yet proven or implemented
- A successful end-to-end execution of the new hourly live workflow.
- Authenticated SportsDataIO roster and injury data ingestion, verified player ID crosswalk and availability.
- Independent Sharp Edge Pro predictive probability model and out-of-sample calibration.
- Independent DraftKings executable checkout price verification.
- Outcome settlement, calibration, closing-line value and prospective paper-trading audit.
- Public dashboard deployment and separate GitHub repository.
- Certified TAKE selections: **0**.

## Safety and costs
- Champion-001 remains frozen; no predictions copied from it.
- Live odds workflow uses SHARPAPI_KEY repository secret; missing key fails closed.
- API costs/quotas not established; up to 48 SharpAPI calls/day if scheduled runs succeed.
- No automatic wagering; shadow stake $0.
- All recommendations remain HOLD until evidence clears every required gate.
