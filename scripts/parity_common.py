"""Shared helpers for MP3Gain parity scripts."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from mp3gain_gui_py._tags.formats import ALL_MP3GAIN_KEYS  # noqa: E402

MP3GAIN_EXE = Path("c:/bin/mp3gain-win-1_2_5/mp3gain.exe")
ORIGINAL_DIR = Path("c:/tmp/mp3/original")
REFERENCE_89DB_DIR = Path("c:/tmp/mp3/89db")
CODEX_89DB_DIR = Path("c:/tmp/mp3/89dbcodex")
SNAPSHOT_DIR = Path("c:/tmp/pycompa")
DEFAULT_PARITY_JOBS = 4


def list_mp3_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.mp3"), key=lambda p: p.name.lower())


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def file_hashes(files: list[Path]) -> dict[str, str]:
    return {path.name: sha256_file(path) for path in files}


def has_id3v1_tag(path: Path) -> bool:
    if path.stat().st_size < 128:
        return False
    with path.open("rb") as handle:
        handle.seek(-128, 2)
        return handle.read(3) == b"TAG"


def read_id3v1_tail(path: Path) -> bytes | None:
    if path.stat().st_size < 128:
        return None
    with path.open("rb") as handle:
        handle.seek(-128, 2)
        tail = handle.read(128)
    if tail[:3] == b"TAG":
        return tail
    return None


def preserve_id3v1_tail(path: Path, tail: bytes | None) -> None:
    if tail is None:
        return
    with path.open("rb+") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        if size >= 128:
            handle.seek(-128, 2)
            existing = handle.read(128)
            if existing[:3] == b"TAG":
                handle.seek(-128, 2)
                handle.truncate()
    with path.open("ab") as handle:
        handle.write(tail)


def default_parity_jobs() -> int:
    raw = os.environ.get("MP3GAIN_PARITY_JOBS")
    if raw is None:
        return DEFAULT_PARITY_JOBS
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_PARITY_JOBS
    return max(1, parsed)


def run_mp3gain_table(
    files: list[Path],
    exe: Path = MP3GAIN_EXE,
    *,
    read_tag_only: bool = False,
) -> dict[str, dict[str, str]]:
    if not files:
        return {}
    command = [str(exe), "-q", "-o"]
    if read_tag_only:
        command.extend(["-s", "c"])
    command.extend(str(path) for path in files)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"mp3gain.exe failed with code {result.returncode}: {result.stderr or result.stdout}"
        )
    return parse_mp3gain_output(result.stdout)


def parse_mp3gain_output(text: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("File\t"):
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        file_token = parts[0].strip()
        key = "Album" if file_token.strip('"') == "Album" else Path(file_token).name
        rows[key] = {
            "mp3_gain": parts[1].strip(),
            "db_gain": parts[2].strip(),
            "max_amplitude": parts[3].strip(),
            "max_global_gain": parts[4].strip(),
            "min_global_gain": parts[5].strip(),
        }
        if len(parts) >= 11:
            rows[key].update(
                {
                    "album_gain": parts[6].strip(),
                    "album_db_gain": parts[7].strip(),
                    "album_max_amplitude": parts[8].strip(),
                    "album_max_global_gain": parts[9].strip(),
                    "album_min_global_gain": parts[10].strip(),
                }
            )
    return rows


def read_raw_mp3gain_tags(path: Path) -> dict[str, str]:
    tags: dict[str, str] = {}

    try:
        import mutagen.apev2 as _apev2  # type: ignore[import-untyped]

        ape = _apev2.APEv2(str(path))
        for key, value in ape.items():
            upper = key.upper()
            if upper in ALL_MP3GAIN_KEYS:
                tags[upper] = str(value)
    except Exception:
        pass

    if tags:
        return {k: tags[k] for k in sorted(tags)}

    try:
        import mutagen.id3 as _id3  # type: ignore[import-untyped]

        id3 = _id3.ID3(str(path))
        for key, frame in id3.items():
            if not key.startswith("TXXX:"):
                continue
            desc = key[5:].upper()
            if desc in ALL_MP3GAIN_KEYS:
                text = frame.text[0] if frame.text else ""
                tags[desc] = str(text)
    except Exception:
        pass

    return {k: tags[k] for k in sorted(tags)}
