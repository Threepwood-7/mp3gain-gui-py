"""Normalize MP3 files to the default 89 dB track target via legacy CLI switches.

Usage examples:
    python scripts/normalize_89db.py "C:/music"
    python scripts/normalize_89db.py "C:/music" --recurse
    python scripts/normalize_89db.py "C:/music" --dst-dir "C:/tmp/normalized"
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace


def _parse_args() -> Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "src_dir",
        type=Path,
        help="Source directory containing MP3 files.",
    )
    parser.add_argument(
        "--recurse",
        action="store_true",
        help="Recurse into subdirectories while discovering MP3 files.",
    )
    parser.add_argument(
        "--dst-dir",
        type=Path,
        default=None,
        help="Optional destination directory. If omitted, files are normalized in place.",
    )
    return parser.parse_args()


def _is_mp3(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".mp3"


def _discover_mp3_files(src_dir: Path, *, recurse: bool) -> list[Path]:
    if recurse:
        candidates = (path for path in src_dir.rglob("*") if _is_mp3(path))
    else:
        candidates = (path for path in src_dir.iterdir() if _is_mp3(path))
    return sorted(candidates)


def _make_writable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IWRITE)


def _prepare_destination(src_file: Path, *, src_root: Path, dst_root: Path) -> Path:
    relative_path = src_file.relative_to(src_root)
    dst_file = dst_root / relative_path
    dst_file.parent.mkdir(parents=True, exist_ok=True)

    if src_file.resolve() != dst_file.resolve():
        shutil.copyfile(src_file, dst_file)
    _make_writable(dst_file)
    return dst_file


def _build_pythonpath(repo_root: Path) -> str:
    src_dir = repo_root / "src"
    existing = os.environ.get("PYTHONPATH", "")
    if existing:
        return f"{src_dir}{os.pathsep}{existing}"
    return str(src_dir)


def _normalize_file(target_file: Path, *, repo_root: Path) -> tuple[int, list[str], str, str]:
    command = [
        sys.executable,
        "-m",
        "mp3gain_gui_py.legacy_cli",
        "/r",
        "/c",
        "/s",
        "r",
        str(target_file),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = _build_pythonpath(repo_root)
    completed = subprocess.run(
        command,
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode, command, completed.stdout, completed.stderr


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = args.src_dir.resolve()
    dst_dir = args.dst_dir.resolve() if args.dst_dir is not None else None

    if not src_dir.exists() or not src_dir.is_dir():
        print(f"Source directory not found: {src_dir}", file=sys.stderr)
        return 2

    src_files = _discover_mp3_files(src_dir, recurse=args.recurse)
    if not src_files:
        print(f"No MP3 files found in: {src_dir}")
        return 0

    targets: list[Path] = []
    if dst_dir is None:
        targets = src_files
    else:
        dst_dir.mkdir(parents=True, exist_ok=True)
        for src_file in src_files:
            targets.append(_prepare_destination(src_file, src_root=src_dir, dst_root=dst_dir))

    total = len(targets)
    for index, target in enumerate(targets, start=1):
        exit_code, command, stdout, stderr = _normalize_file(target, repo_root=repo_root)
        rendered = subprocess.list2cmdline(command)
        print(f"[{index}/{total}] {rendered}")
        if stdout.strip():
            print(stdout.rstrip())
        if stderr.strip():
            print(stderr.rstrip(), file=sys.stderr)
        if exit_code != 0:
            print(
                f"Normalization failed for {target} (exit code {exit_code}).",
                file=sys.stderr,
            )
            return exit_code

    print(f"Normalization complete: {total} file(s) processed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
