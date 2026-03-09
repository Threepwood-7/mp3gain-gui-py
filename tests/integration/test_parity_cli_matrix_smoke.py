"""Optional parity-cli matrix smoke test against external local fixtures."""

from __future__ import annotations

import os
import subprocess
from hashlib import sha256
from pathlib import Path

import pytest


@pytest.mark.integration
def test_parity_cli_matrix_smoke_external() -> None:
    if os.environ.get("MP3GAIN_CLI_MATRIX_SMOKE") != "1":
        pytest.skip("Set MP3GAIN_CLI_MATRIX_SMOKE=1 to run parity_cli_matrix smoke.")

    repo_root = Path(__file__).resolve().parents[2]
    oracle = Path("c:/bin/mp3gain-win-1_2_5/mp3gain.exe")
    source = Path("c:/tmp/mp3/original")
    snapshot = Path("c:/tmp/pycompa")
    if not oracle.exists():
        pytest.skip(f"Missing oracle binary: {oracle}")
    if not source.exists():
        pytest.skip(f"Missing source directory: {source}")

    before = sorted(source.glob("*.mp3"))
    before_hashes = {path.name: sha256(path.read_bytes()).hexdigest() for path in before}

    command = [
        "hatch",
        "run",
        "python",
        "scripts/parity_cli_matrix.py",
        "--sample",
        "2",
        "--jobs",
        "2",
        "--snapshot-dir",
        str(snapshot),
    ]
    completed = subprocess.run(command, cwd=repo_root, check=False, text=True, capture_output=True)
    assert completed.returncode in {0, 1}

    after = sorted(source.glob("*.mp3"))
    after_hashes = {path.name: sha256(path.read_bytes()).hexdigest() for path in after}
    assert before_hashes == after_hashes
