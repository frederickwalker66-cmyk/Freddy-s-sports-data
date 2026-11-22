"""Safe configuration preflight: report presence only, never secret values.

Configuration readiness is NOT candidate authenticity or model certification.
"""
import json
import os

REQUIRED_SECRETS = (
    "SHARP_CERTIFICATION_FEED_URL",
    "SHARP_CERTIFICATION_FEED_TOKEN",
    "SHARP_MODEL_ATTESTATION_KEY",
    "SHARP_ODDS_ATTESTATION_KEY",
    "SHARP_RELEASE_ATTESTATION_KEY",
)
REQUIRED_VARIABLES = ("SHARP_APPROVED_MODEL_VERSIONS",)


def assess(env):
    configured = {name: bool(env.get(name, "").strip()) for name in REQUIRED_SECRETS + REQUIRED_VARIABLES}
    missing = [name for name, present in configured.items() if not present]
    endpoint = env.get("SHARP_CERTIFICATION_FEED_URL", "")
    if configured["SHARP_CERTIFICATION_FEED_URL"] and not endpoint.startswith("https://"):
        missing.append("SHARP_CERTIFICATION_FEED_URL_REQUIRES_HTTPS")
    keys = [env.get(name, "") for name in REQUIRED_SECRETS if name.endswith("_KEY")]
    if all(keys) and len(set(keys)) != len(keys):
        missing.append("INDEPENDENT_SIGNING_KEYS_NOT_DISTINCT")
    if any(configured[name] and len(env.get(name, "")) < 32 for name in REQUIRED_SECRETS if name.endswith("_KEY") or name.endswith("_TOKEN")):
        missing.append("SIGNING_KEY_OR_TOKEN_TOO_SHORT")
    return {
        "configuration_ready_for_live_fetch": not missing,
        "missing_or_invalid_configuration_names": sorted(set(missing)),
        "candidate_feed_authenticated": False,
        "model_calibration_certified": False,
        "direct_checkout_verified": False,
        "certified_take_count": 0,
        "decision": "HOLD",
    }


if __name__ == "__main__":
    print(json.dumps(assess(os.environ), sort_keys=True))
