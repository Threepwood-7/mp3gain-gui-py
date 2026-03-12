"""Capture oracle snapshots from mp3gain.exe and MP3Gain tags."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from parity_common import (
    ORIGINAL_DIR,
    REFERENCE_89DB_DIR,
    SNAPSHOT_DIR,
    file_hashes,
    list_mp3_files,
    read_raw_mp3gain_tags,
    run_mp3gain_table,
)

if TYPE_CHECKING:
    from argparse import Namespace


def _snapshot_for(directory: Path) -> dict[str, object]:
    files = list_mp3_files(directory)
    return {
        "directory": str(directory),
        "files": [path.name for path in files],
        "hashes_sha256": file_hashes(files),
        # Read stored MP3Gain fields only to avoid mutating fixture files.
        "mp3gain_table": run_mp3gain_table(files, read_tag_only=True),
        "tags": {path.name: read_raw_mp3gain_tags(path) for path in files},
    }


def _parse_args() -> Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--original-dir",
        type=Path,
        default=ORIGINAL_DIR,
        help="Directory containing original MP3 files.",
    )
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=REFERENCE_89DB_DIR,
        help="Directory containing legacy 89 dB MP3 files.",
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=SNAPSHOT_DIR,
        help="Directory where snapshot JSON will be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    snapshot_dir = args.snapshot_dir
    original_dir = args.original_dir
    reference_dir = args.reference_dir

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    output_path = snapshot_dir / "parity_oracle_snapshot.json"

    snapshot = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "original": _snapshot_for(original_dir),
        "reference_89db": _snapshot_for(reference_dir),
    }
    output_path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8"
    )

    original_count = len(snapshot["original"]["files"])  # type: ignore[index]
    reference_count = len(snapshot["reference_89db"]["files"])  # type: ignore[index]
    print(
        f"Oracle snapshot written: {output_path} "
        f"(original={original_count}, reference_89db={reference_count})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
