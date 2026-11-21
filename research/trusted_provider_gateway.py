"""Explicit authenticated feed transport and frozen Champion-001 execution boundary.

No endpoint or artifact is invented. Configuration is mandatory; failures HOLD.
Transport authentication is not provider-signed data authenticity.
"""
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


class SourceUnavailable(RuntimeError):
    pass


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def fetch_provider_json(url, *, api_key, allowed_host, timeout=10, max_bytes=2_000_000):
    """Retrieve HTTPS JSON from a specifically pinned provider hostname."""
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != allowed_host
            or parsed.username or parsed.password or parsed.fragment
            or parsed.port not in (None, 443) or not api_key):
        raise SourceUnavailable("provider_configuration_invalid")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise SourceUnavailable("provider_redirect_not_allowed")
    request = urllib.request.Request(
        url, headers={"Ocp-Apim-Subscription-Key": api_key,
                      "Accept": "application/json", "User-Agent": "FreddysPicksResearch/1"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise SourceUnavailable("provider_payload_too_large")
            payload = json.loads(raw)
    except (OSError, ValueError, TimeoutError) as exc:
        raise SourceUnavailable("provider_request_failed") from exc
    return {"payload": payload, "retrieved_at": _utc_now(),
            "provider_host": allowed_host, "transport_authenticated": True,
            "provider_signature_verified": False}


def collect_configured_sources(env=None):
    """Require independently configured odds and player/injury endpoints.

    Provider responses are preserved as raw data; no fabricated market mapping.
    """
    env = os.environ if env is None else env
    outputs = {}
    for category in ("ODDS", "ROSTER_INJURY"):
        url = env.get("FREDDY_" + category + "_URL")
        key = env.get("FREDDY_" + category + "_API_KEY")
        host = env.get("FREDDY_" + category + "_HOST")
        if not all((url, key, host)):
            outputs[category.lower()] = {"status": "HOLD_NOT_CONFIGURED"}
            continue
        try:
            result = fetch_provider_json(url, api_key=key, allowed_host=host)
            # Never publish raw licensed payload or credentials into CI logs.
            outputs[category.lower()] = {
                "status": "RECEIVED_UNVERIFIED_CONTENT",
                "retrieved_at": result["retrieved_at"],
                "provider_host": result["provider_host"],
                "transport_authenticated": True,
                "provider_signature_verified": False,
                "payload_sha256": hashlib.sha256(
                    json.dumps(result["payload"], sort_keys=True).encode()).hexdigest(),
                "market_or_roster_normalization_verified": False,
            }
        except SourceUnavailable as exc:
            outputs[category.lower()] = {"status": "HOLD_SOURCE_ERROR", "reason": str(exc)}
    return outputs


def execute_frozen_champion(input_record, *, artifact_path, expected_sha256,
                            runner_path, timeout=15):
    """Run a pinned local model adapter, never substitute market probabilities.

    The adapter must already exist and be independently audited; hash pinning
    alone cannot establish calibration or trustworthy model lineage.
    """
    artifact = Path(artifact_path)
    runner = Path(runner_path)
    if (not artifact.is_file() or artifact.is_symlink() or not runner.is_file()
            or runner.is_symlink() or len(expected_sha256) != 64):
        raise SourceUnavailable("champion_artifact_or_runner_missing")
    actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if actual != expected_sha256.lower():
        raise SourceUnavailable("champion_artifact_hash_mismatch")
    try:
        result = subprocess.run([sys.executable, str(runner), str(artifact)],
                                input=json.dumps(input_record), text=True,
                                capture_output=True, timeout=timeout, check=True)
        output = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SourceUnavailable("champion_execution_failed") from exc
    p = output.get("model_probability") if isinstance(output, dict) else None
    if (not isinstance(output, dict) or output.get("model_id") != "Champion-001" or type(p) not in (float, int)
            or not 0 < p < 1 or not output.get("forecast_run_id")):
        raise SourceUnavailable("champion_output_invalid")
    return {"model_id": "Champion-001", "model_probability": p,
            "forecast_run_id": output["forecast_run_id"],
            "model_artifact_sha256": actual, "predicted_at": _utc_now(),
            "independently_validated": False, "certified": False}


def readiness(env=None):
    env = os.environ if env is None else env
    sources = collect_configured_sources(env)
    model = {"status": "HOLD_MODEL_NOT_CONFIGURED"}
    artifact = env.get("FREDDY_CHAMPION_ARTIFACT")
    runner = env.get("FREDDY_CHAMPION_RUNNER")
    sha = env.get("FREDDY_CHAMPION_SHA256")
    if all((artifact, runner, sha)):
        model = {"status": "CONFIGURED_NOT_INDEPENDENTLY_VERIFIED",
                 "artifact_hash_pinned": True}
    return {"sources": sources, "champion_001": model,
            "certified_predictions": 0, "decision": "HOLD",
            "warning": "Transport credentials, pinned artifacts, and user-supplied data do not independently certify betting EV."}
