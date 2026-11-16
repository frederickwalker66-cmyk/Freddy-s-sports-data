"""Normalize a downloaded upstream prospective artifact to the strict run-ID layout.

The source workflow uploads several paths, so GitHub stores the prospective
files under prospective_pregame/ inside the artifact ZIP. The outcome linker
historically expected these files directly under snapshots/<run_id>/.
Never fill in missing files, forge receipts, or promote records to training.
"""
from __future__ import annotations

import argparse
from pathlib import Path

REQUIRED = (
    "prospective_event_evidence.jsonl",
    "historical_published_results.jsonl",
    "point_in_time_receipt.json",
)
NESTED = "prospective_pregame"


def normalize_archive(folder: Path, run_id: str) -> str:
    """Require exactly one unambiguous layout and the original receipt.

    Return 'flattened' or 'already_flat'. Raise ValueError for any missing,
    mixed, conflicting, symlinked or unrelated layout. This verifies layout
    only; subsequent receipt and point-in-time audits still gate all rows.
    """
    folder = Path(folder)
    if not run_id.isdecimal() or folder.name != run_id:
        raise ValueError("expected_numeric_github_run_directory")
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("missing_or_untrusted_download_directory")
    nested = folder / NESTED
    if nested.is_symlink():
        raise ValueError("symlinked_prospective_source_directory")
    if nested.is_dir():
        if any((folder / name).exists() for name in REQUIRED):
            raise ValueError("ambiguous_mixed_flat_and_nested_archive")
        if any(not (nested / name).is_file() or
               (nested / name).is_symlink() for name in REQUIRED):
            raise ValueError("incomplete_nested_original_evidence_or_receipt")
        items = sorted(nested.iterdir())
        if any(item.is_symlink() or (folder / item.name).exists()
               for item in items):
            raise ValueError("conflicting_or_symlinked_original_archive_entry")
        # Preserve the *same bytes*, not a synthesized or reconstructed run.
        for item in items:
            item.rename(folder / item.name)
        nested.rmdir()
        status = "flattened"
    else:
        status = "already_flat"
    if any(not (folder / name).is_file() or
           (folder / name).is_symlink() for name in REQUIRED):
        raise ValueError("incomplete_original_evidence_or_receipt")
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        status = normalize_archive(args.directory, args.run_id)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"prospective archive held: {exc}\n")
    print(f"Original pregame archive layout: {status}; run {args.run_id}. "
          "Receipt not yet validated; no model or bet certification.")


if __name__ == "__main__":
    main()
