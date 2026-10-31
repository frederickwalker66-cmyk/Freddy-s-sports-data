"""Champion-001 authenticity gate. Never execute or modify model bytes.

The proof manifest must already exist in independently controlled custody.
A self-created checksum proves file integrity but NOT origin/version/authenticity.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

SHA = re.compile(r"^[0-9a-f]{64}$")


def inspect(model_path=None, proof_path=None):
    report = {
        "stage": "champion_001_artifact_authentication",
        "original_executable_verified": False,
        "immutable_model_version_authenticated": False,
        "reproducible_reference_outputs_verified": False,
        "certified_champion_001_predictions": 0,
        "champion_001_modified": False,
        "result": "blocked_missing_original_champion_artifact_or_independent_proof",
    }
    if not model_path or not proof_path:
        return report
    model, proof = Path(model_path), Path(proof_path)
    if not model.is_file() or not proof.is_file():
        return report
    data = model.read_bytes()
    try:
        manifest = json.loads(proof.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        report["result"] = "blocked_invalid_proof_manifest"
        return report
    actual = hashlib.sha256(data).hexdigest()
    expected = manifest.get("model_sha256")
    if not SHA.fullmatch(str(expected)) or expected != actual:
        report["result"] = "blocked_model_sha256_mismatch"
        return report
    report["sha256_matches_supplied_manifest"] = True
    report["artifact_size_bytes"] = len(data)
    report["result"] = "blocked_independent_original_provenance_and_reproducibility_not_verified"
    # Never set these to true from a self-authored JSON manifest.
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-path")
    p.add_argument("--independent-proof")
    p.add_argument("--output", default="validation_output/champion_authentication.json")
    args = p.parse_args(argv)
    report = inspect(args.model_path, args.independent_proof)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
