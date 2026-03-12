"""Normalize MP3 files to a target dB using legacy two-step CLI flow.

Per file flow:
1) analyze with `/q /o /s r`
2) apply with `/q /g <steps> /t` (only when final steps != 0)

Usage examples:
    python scripts/run_normalize.py "C:/music"
    python scripts/run_normalize.py "C:/music" --db 87
    python scripts/run_normalize.py "C:/music" --recurse --jobs 8
    python scripts/run_normalize.py "C:/music" --dst-dir "C:/tmp/normalized"
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _load_db_to_legacy_steps():
    from mp3gain_gui_py._legacy_exact.math import db_to_legacy_steps

    return db_to_legacy_steps


db_to_legacy_steps = _load_db_to_legacy_steps()

DEFAULT_TARGET_DB = 89.0


@dataclass(frozen=True)
class NormalizeResult:
    index: int
    total: int
    target_file: Path
    analyze_command: list[str]
    analyze_returncode: int
    analyze_stdout: str
    analyze_stderr: str
    analyzed_steps: int | None
    final_steps: int | None
    apply_command: list[str] | None
    apply_returncode: int | None
    apply_stdout: str
    apply_stderr: str
    error: str | None


def _parse_args() -> Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "src_dir",
        type=Path,
        help="Source directory containing MP3 files.",
    )
    parser.add_argument(
        "--db",
        type=float,
        default=DEFAULT_TARGET_DB,
        help=f"Target track loudness in dB (default: {DEFAULT_TARGET_DB}).",
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
    parser.add_argument(
        "--jobs",
        type=int,
        default=(os.cpu_count() or 1),
        help="Parallel workers to use (default: number of processors).",
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


def _build_analysis_command(target_file: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "mp3gain_gui_py.legacy_cli",
        "/q",
        "/o",
        "/s",
        "r",
        str(target_file),
    ]


def _build_apply_command(target_file: Path, *, final_steps: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "mp3gain_gui_py.legacy_cli",
        "/q",
        "/g",
        str(final_steps),
        "/t",
        str(target_file),
    ]


def _normalize_path_text(path_text: str) -> str:
    return os.path.normcase(os.path.normpath(path_text.strip()))


def _parse_analysis_mp3_gain(stdout_text: str, *, target_file: Path) -> int:
    target_norm = _normalize_path_text(str(target_file))
    fallback_steps: int | None = None
    for line in stdout_text.splitlines():
        cols = line.split("\t")
        if len(cols) < 2:
            continue
        file_col = cols[0].strip()
        if not file_col:
            continue
        if file_col.lower() == "file":
            continue
        if file_col.strip('"').lower() == "album":
            continue
        step_text = cols[1].strip()
        try:
            steps = int(step_text)
        except ValueError:
            continue
        if fallback_steps is None:
            fallback_steps = steps
        if _normalize_path_text(file_col) == target_norm:
            return steps
    if fallback_steps is not None:
        return fallback_steps
    raise ValueError("Could not parse MP3 gain steps from analysis output.")


def _run_command(
    command: list[str], *, repo_root: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _process_file(
    *,
    index: int,
    total: int,
    target_file: Path,
    repo_root: Path,
    env: dict[str, str],
    step_offset: int,
) -> NormalizeResult:
    analyze_command = _build_analysis_command(target_file)
    analyze_completed = _run_command(analyze_command, repo_root=repo_root, env=env)
    if analyze_completed.returncode != 0:
        return NormalizeResult(
            index=index,
            total=total,
            target_file=target_file,
            analyze_command=analyze_command,
            analyze_returncode=int(analyze_completed.returncode),
            analyze_stdout=analyze_completed.stdout,
            analyze_stderr=analyze_completed.stderr,
            analyzed_steps=None,
            final_steps=None,
            apply_command=None,
            apply_returncode=None,
            apply_stdout="",
            apply_stderr="",
            error="analysis command failed",
        )

    try:
        analyzed_steps = _parse_analysis_mp3_gain(
            analyze_completed.stdout, target_file=target_file
        )
    except ValueError as exc:
        return NormalizeResult(
            index=index,
            total=total,
            target_file=target_file,
            analyze_command=analyze_command,
            analyze_returncode=int(analyze_completed.returncode),
            analyze_stdout=analyze_completed.stdout,
            analyze_stderr=analyze_completed.stderr,
            analyzed_steps=None,
            final_steps=None,
            apply_command=None,
            apply_returncode=None,
            apply_stdout="",
            apply_stderr="",
            error=str(exc),
        )

    final_steps = analyzed_steps + step_offset
    if final_steps == 0:
        return NormalizeResult(
            index=index,
            total=total,
            target_file=target_file,
            analyze_command=analyze_command,
            analyze_returncode=int(analyze_completed.returncode),
            analyze_stdout=analyze_completed.stdout,
            analyze_stderr=analyze_completed.stderr,
            analyzed_steps=analyzed_steps,
            final_steps=final_steps,
            apply_command=None,
            apply_returncode=None,
            apply_stdout="",
            apply_stderr="",
            error=None,
        )

    apply_command = _build_apply_command(target_file, final_steps=final_steps)
    apply_completed = _run_command(apply_command, repo_root=repo_root, env=env)
    err = None if apply_completed.returncode == 0 else "apply command failed"
    return NormalizeResult(
        index=index,
        total=total,
        target_file=target_file,
        analyze_command=analyze_command,
        analyze_returncode=int(analyze_completed.returncode),
        analyze_stdout=analyze_completed.stdout,
        analyze_stderr=analyze_completed.stderr,
        analyzed_steps=analyzed_steps,
        final_steps=final_steps,
        apply_command=apply_command,
        apply_returncode=int(apply_completed.returncode),
        apply_stdout=apply_completed.stdout,
        apply_stderr=apply_completed.stderr,
        error=err,
    )


def _print_result(result: NormalizeResult) -> None:
    analyze_rendered = subprocess.list2cmdline(result.analyze_command)
    print(f"[{result.index}/{result.total}] ANALYZE {analyze_rendered}")
    if result.analyze_stdout.strip():
        print(result.analyze_stdout.rstrip())
    if result.analyze_stderr.strip():
        print(result.analyze_stderr.rstrip(), file=sys.stderr)

    if result.error is not None:
        print(
            f"[{result.index}/{result.total}] ERROR {result.target_file}: {result.error}",
            file=sys.stderr,
        )
        return

    assert result.analyzed_steps is not None
    assert result.final_steps is not None
    print(
        f"[{result.index}/{result.total}] STEPS analyzed={result.analyzed_steps} "
        f"offset_applied={result.final_steps - result.analyzed_steps} final={result.final_steps}"
    )

    if result.apply_command is None:
        print(f"[{result.index}/{result.total}] APPLY skipped (final steps == 0)")
        return

    apply_rendered = subprocess.list2cmdline(result.apply_command)
    print(f"[{result.index}/{result.total}] APPLY {apply_rendered}")
    if result.apply_stdout.strip():
        print(result.apply_stdout.rstrip())
    if result.apply_stderr.strip():
        print(result.apply_stderr.rstrip(), file=sys.stderr)

    if result.apply_returncode not in {0, None}:
        print(
            f"[{result.index}/{result.total}] ERROR {result.target_file}: "
            f"apply exit code {result.apply_returncode}",
            file=sys.stderr,
        )


def main() -> int:
    args = _parse_args()
    repo_root = REPO_ROOT
    src_dir = args.src_dir.resolve()
    dst_dir = args.dst_dir.resolve() if args.dst_dir is not None else None
    target_db = float(args.db)
    jobs = int(args.jobs)

    if jobs <= 0:
        print("--jobs must be greater than 0.", file=sys.stderr)
        return 2

    if not src_dir.exists() or not src_dir.is_dir():
        print(f"Source directory not found: {src_dir}", file=sys.stderr)
        return 2

    src_files = _discover_mp3_files(src_dir, recurse=args.recurse)
    if not src_files:
        print(f"No MP3 files found in: {src_dir}")
        return 0

    targets: list[Path]
    if dst_dir is None:
        targets = src_files
        for target in targets:
            _make_writable(target)
    else:
        dst_dir.mkdir(parents=True, exist_ok=True)
        targets = [
            _prepare_destination(src_file, src_root=src_dir, dst_root=dst_dir)
            for src_file in src_files
        ]

    total = len(targets)
    step_offset = db_to_legacy_steps(target_db - DEFAULT_TARGET_DB)
    env = os.environ.copy()
    env["PYTHONPATH"] = _build_pythonpath(repo_root)

    print(
        f"Starting normalization: files={total}, target_db={target_db:g}, jobs={jobs}, "
        f"step_offset={step_offset}",
    )

    failures: list[NormalizeResult] = []
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        future_map = {
            executor.submit(
                _process_file,
                index=idx,
                total=total,
                target_file=target,
                repo_root=repo_root,
                env=env,
                step_offset=step_offset,
            ): (idx, target)
            for idx, target in enumerate(targets, start=1)
        }

        for future in as_completed(future_map):
            result = future.result()
            _print_result(result)
            if result.error is not None:
                failures.append(result)

    if failures:
        print(
            f"Normalization completed with failures: {len(failures)} file(s) failed.",
            file=sys.stderr,
        )
        first = failures[0]
        if first.apply_returncode not in {None, 0}:
            return int(first.apply_returncode)
        if first.analyze_returncode != 0:
            return int(first.analyze_returncode)
        return 1

    print(f"Normalization complete: {total} file(s) processed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
