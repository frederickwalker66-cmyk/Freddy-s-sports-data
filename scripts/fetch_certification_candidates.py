"""Retrieve externally produced, signed candidate attestations; never synthesize picks.

The endpoint is private, HTTPS only, and must be controlled by an independent
evidence supplier. A fetched record is NOT certified until the separate
certification gate validates signatures, release approval, market and timing.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener


MAX_FEED_BYTES = 1_000_000
MAX_CANDIDATES = 500
SCHEMA = "signed-certification-candidates-v1"


class _RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirected evidence source is not allowed")


def fetch(endpoint, bearer_token, *, open_request=None):
    """Return attested candidate rows. Only a strict HTTPS feed is accepted."""
    url = urlsplit(endpoint)
    if (url.scheme != "https" or not url.hostname or url.username or
            url.password or url.fragment or not url.netloc):
        raise ValueError("invalid https feed url")
    if not isinstance(bearer_token, str) or len(bearer_token) < 32:
        raise ValueError("missing source authentication token")
    request = Request(endpoint, headers={
        "Authorization": "Bearer " + bearer_token,
        "Accept": "application/json",
        "Cache-Control": "no-store",
    })
    opener = open_request or build_opener(_RejectRedirect()).open
    with opener(request, timeout=12) as response:
        if response.geturl() != endpoint:
            raise ValueError("unexpected feed redirect")
        raw = response.read(MAX_FEED_BYTES + 1)
    if len(raw) > MAX_FEED_BYTES:
        raise ValueError("feed is oversized")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError("invalid feed schema")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        raise ValueError("invalid candidate batch")
    if any(not isinstance(c, dict) for c in candidates):
        raise ValueError("invalid candidate row")
    return candidates


def collect(endpoint, token, *, out, status_out, open_request=None):
    status = "FEED_NOT_CONFIGURED"
    candidates = []
    if endpoint:
        if not isinstance(token, str) or len(token) < 32:
            status = "FEED_AUTH_NOT_CONFIGURED"
        else:
            try:
                candidates = fetch(endpoint, token, open_request=open_request)
                status = "FEED_RECEIVED" if candidates else "FEED_EMPTY"
            except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
                status = "FEED_UNAVAILABLE_OR_INVALID"
    out = Path(out)
    if out.exists():
        out.unlink()  # fail-closed: never reuse older candidate records
    if candidates:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(candidates), encoding="utf-8")
        out.chmod(0o600)
    summary = {
        "status": status,
        "candidate_count": len(candidates),
        "certification_performed": False,
        "model_probability_generated": False,
        "checkout_quote_authenticated": False,
    }
    path = Path(status_out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="certification_input/candidates.json")
    parser.add_argument("--status", default="validation_output/certification_feed_status.json")
    args = parser.parse_args()
    report = collect(
        os.getenv("SHARP_CERTIFICATION_FEED_URL", ""),
        os.getenv("SHARP_CERTIFICATION_FEED_TOKEN", ""),
        out=args.input,
        status_out=args.status,
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
