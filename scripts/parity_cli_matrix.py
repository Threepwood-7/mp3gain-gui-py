"""Run a legacy CLI behavioral parity matrix against oracle and Python port."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from parity_common import (
    CODEX_89DB_DIR,
    LEGACY_ORACLE_EXE,
    ORIGINAL_DIR,
    SNAPSHOT_DIR,
    SRC_DIR,
    default_parity_jobs,
    list_mp3_files,
    sha256_file,
)

if TYPE_CHECKING:
    from argparse import Namespace


@dataclass(frozen=True)
class _Case:
    name: str
    oracle_args: tuple[str, ...]
    python_args: tuple[str, ...]
    mutates: bool


CASES: tuple[_Case, ...] = (
    _Case(
        name="analyze_table",
        oracle_args=("-q", "-o"),
        python_args=("-q", "-o"),
        mutates=False,
    ),
    _Case(
        name="check_tag_only",
        oracle_args=("-q", "-o", "-s", "c"),
        python_args=("-q", "-o", "-s", "c"),
        mutates=False,
    ),
    _Case(
        name="apply_track",
        oracle_args=("-q", "-r"),
        python_args=("-q", "-r"),
        mutates=True,
    ),
)


def _parse_args() -> Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=ORIGINAL_DIR,
        help="Source directory with original MP3 files.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=CODEX_89DB_DIR,
        help="Working root for temporary command-matrix copies.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=default_parity_jobs(),
        help="Parallel worker count.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="If > 0, limit to first N files.",
    )
    return parser.parse_args()


def _run_cmd(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> int:
    completed = subprocess.run(command, cwd=cwd, env=env, check=False, capture_output=True, text=True)
    return completed.returncode


def _run_case(repo_root: Path, source_file: Path, case: _Case, work_root: Path) -> dict[str, object]:
    oracle_dir = work_root / "oracle" / case.name
    python_dir = work_root / "python" / case.name
    oracle_dir.mkdir(parents=True, exist_ok=True)
    python_dir.mkdir(parents=True, exist_ok=True)

    oracle_file = oracle_dir / source_file.name
    python_file = python_dir / source_file.name
    shutil.copyfile(source_file, oracle_file)
    shutil.copyfile(source_file, python_file)

    oracle_cmd = [str(LEGACY_ORACLE_EXE), *case.oracle_args, str(oracle_file)]
    python_cmd = [sys.executable, "-m", "mp3gain_gui_py.legacy_cli", *case.python_args, str(python_file)]

    py_env = os.environ.copy()
    py_env["PYTHONPATH"] = str(SRC_DIR) + os.pathsep + py_env.get("PYTHONPATH", "")

    oracle_rc = _run_cmd(oracle_cmd, cwd=repo_root)
    python_rc = _run_cmd(python_cmd, cwd=repo_root, env=py_env)

    source_hash = sha256_file(source_file)
    oracle_hash = sha256_file(oracle_file)
    python_hash = sha256_file(python_file)

    return {
        "file": source_file.name,
        "case": case.name,
        "mutates": case.mutates,
        "oracle_exit_code": oracle_rc,
        "python_exit_code": python_rc,
        "exit_code_match": oracle_rc == python_rc,
        "oracle_sha256": oracle_hash,
        "python_sha256": python_hash,
        "byte_identity": oracle_hash == python_hash,
        "source_sha256": source_hash,
        "non_mutating_ok": (not case.mutates and oracle_hash == source_hash and python_hash == source_hash),
    }


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    files = list_mp3_files(args.source_dir)
    if args.sample > 0:
        files = files[: args.sample]

    jobs = max(1, min(args.jobs, max(1, len(files))))
    work_root = args.work_dir / "_cli_matrix"
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True, exist_ok=True)

    futures = []
    results: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        for source_file in files:
            for case in CASES:
                futures.append(executor.submit(_run_case, repo_root, source_file, case, work_root))
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: (str(item["file"]), str(item["case"])))
    exit_code_fail = sum(1 for item in results if not item["exit_code_match"])
    byte_fail = sum(1 for item in results if not item["byte_identity"])
    non_mutating_fail = sum(1 for item in results if item["mutates"] is False and item["non_mutating_ok"] is False)

    report = {
        "legacy_oracle_exe": str(LEGACY_ORACLE_EXE),
        "source_dir": str(args.source_dir),
        "jobs_used": jobs,
        "cases": [case.name for case in CASES],
        "summary": {
            "files": len(files),
            "runs": len(results),
            "exit_code_fail": exit_code_fail,
            "byte_identity_fail": byte_fail,
            "non_mutating_fail": non_mutating_fail,
            "status": "PASS" if exit_code_fail == 0 and byte_fail == 0 and non_mutating_fail == 0 else "FAIL",
        },
        "results": results,
    }

    report_path = SNAPSHOT_DIR / "parity_cli_matrix_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"CLI matrix report written: {report_path}")
    return 0 if report["summary"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
