"""Optional parity smoke test against external local fixtures."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_parity_smoke_external() -> None:
    if os.environ.get("MP3GAIN_PARITY_SMOKE") != "1":
        pytest.skip("Set MP3GAIN_PARITY_SMOKE=1 to run external parity smoke test.")

    repo_root = Path(__file__).resolve().parents[2]
    exe = Path("c:/bin/mp3gain-win-1_2_5/mp3gain.exe")
    original = Path("c:/tmp/mp3/original")
    reference = Path("c:/tmp/mp3/89db")

    if not exe.exists():
        pytest.skip(f"Missing oracle binary: {exe}")
    if not original.exists() or not reference.exists():
        pytest.skip("Missing external fixture directories for parity smoke test.")

    mode = os.environ.get("MP3GAIN_PARITY_MODE", "quick").strip().lower()
    if mode not in {"quick", "full"}:
        pytest.fail(
            f"Invalid MP3GAIN_PARITY_MODE={mode!r}; expected 'quick' or 'full'."
        )

    command = [sys.executable, "scripts/parity_compare.py", "--mode", mode]

    jobs_raw = os.environ.get("MP3GAIN_PARITY_JOBS")
    if jobs_raw:
        command.extend(["--jobs", jobs_raw])

    if os.environ.get("MP3GAIN_PARITY_STRICT") == "1":
        command.append("--strict")
    if mode == "full" and os.environ.get("MP3GAIN_PARITY_FORCE_REBUILD") == "1":
        command.append("--force-rebuild")

    legacy_profile = os.environ.get("MP3GAIN_PARITY_LEGACY_PROFILE")
    if legacy_profile:
        command.extend(["--legacy-profile", legacy_profile])

    completed = subprocess.run(command, cwd=repo_root, check=False, text=True)
    assert completed.returncode == 0, f"Parity command failed: {' '.join(command)}"
