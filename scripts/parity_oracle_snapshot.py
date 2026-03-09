"""Capture oracle snapshots from mp3gain.exe and MP3Gain tags."""

from __future__ import annotations

import json
from datetime import UTC, datetime
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
    from pathlib import Path


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


def main() -> int:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = SNAPSHOT_DIR / "parity_oracle_snapshot.json"

    snapshot = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "original": _snapshot_for(ORIGINAL_DIR),
        "reference_89db": _snapshot_for(REFERENCE_89DB_DIR),
    }
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    original_count = len(snapshot["original"]["files"])  # type: ignore[index]
    reference_count = len(snapshot["reference_89db"]["files"])  # type: ignore[index]
    print(
        f"Oracle snapshot written: {output_path} "
        f"(original={original_count}, reference_89db={reference_count})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
