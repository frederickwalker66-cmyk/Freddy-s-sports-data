"""Authenticated HTTPS collection for sportsbook, roster/injury and frozen model.

Configured URLs must be trusted provider endpoints. HTTPS transport plus an
API key establishes a provider request, NOT cryptographic attestation or a
certified wager. No user-supplied JSON can promote TAKE.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import ssl
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MAX_BYTES = 2_000_000
SOURCE_CONFIG = {
    "sportsbook": ("FREDDY_ODDS_URL", "FREDDY_ODDS_API_KEY"),
    "roster_injury": ("FREDDY_ROSTER_INJURY_URL", "FREDDY_ROSTER_API_KEY"),
}
MODEL_ID = "Champion-001"


def _allowed_url(value):
    if not isinstance(value, str):
        return False
    parts = urlsplit(value)
    return (parts.scheme == "https" and bool(parts.hostname)
            and not parts.username and not parts.password
            and not parts.fragment and parts.port in (None, 443)
            and parts.hostname.lower() not in ("localhost", "127.0.0.1", "::1")
            and not parts.hostname.lower().endswith((".local", ".internal")))


def collect_one(kind, *, env=None, opener=urlopen, now=None):
    env = os.environ if env is None else env
    now = now or datetime.now(timezone.utc)
    url_key, secret_key = SOURCE_CONFIG[kind]
    url, token = env.get(url_key), env.get(secret_key)
    if not url or not token:
        return {"status": "HOLD_NOT_CONFIGURED", "kind": kind,
                "configured": False, "authenticated": False}
    if not _allowed_url(url):
        return {"status": "HOLD_INVALID_ENDPOINT", "kind": kind,
                "configured": True, "authenticated": False}
    try:
        req = Request(url, headers={"Ocp-Apim-Subscription-Key": token,
                                    "Accept": "application/json",
                                    "User-Agent": "FreddysPicksAI/1.0"})
        with opener(req, timeout=12, context=ssl.create_default_context()) as response:
            if response.status != 200:
                raise ValueError("unexpected_http_status")
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("response_too_large")
        parsed = json.loads(body)
        if not isinstance(parsed, (dict, list)):
            raise ValueError("invalid_json_shape")
        return {
            "status": "RECEIVED_AUTHENTICATED_HTTPS_UNVERIFIED_CONTENT",
            "kind": kind, "configured": True, "authenticated": False,
            "transport": "HTTPS_WITH_PROVIDER_API_KEY",
            "received_at": now.isoformat(),
            "source_host": urlsplit(url).hostname,
            "payload_sha256": hashlib.sha256(body).hexdigest(),
            "record_count": len(parsed),
            "data": parsed,
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"status": "HOLD_SOURCE_ERROR", "kind": kind,
                "configured": True, "authenticated": False,
                "error_type": type(exc).__name__}


def collect(*, env=None, opener=urlopen, now=None):
    sources = {kind: collect_one(kind, env=env, opener=opener, now=now)
               for kind in SOURCE_CONFIG}
    artifact = (env or os.environ).get("FREDDY_CHAMPION_ARTIFACT_SHA256")
    # An environment hash is only a reference, never proof of model execution.
    model = {"model_id": MODEL_ID,
             "status": "HOLD_NO_INDEPENDENT_NATIVE_INFERENCE",
             "artifact_reference_present": bool(artifact),
             "verified_predictions": 0}
    return {"status": "HOLD_CERTIFICATION_NOT_COMPLETE",
            "sources": sources, "native_champion_001": model,
            "certified_take_count": 0, "money_wagered_usd": 0}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = collect()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output),
                      "certified_take_count": 0}))


if __name__ == "__main__":
    main()
