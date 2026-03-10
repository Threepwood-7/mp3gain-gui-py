"""Build helpers for the vendored legacy C backend DLL."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def legacy_source_dir() -> Path:
    return repo_root() / "src" / "c" / "legacy" / "mp3gain-1_5_2-src"


def backend_bin_dir() -> Path:
    return Path(__file__).resolve().parent / "bin"


def backend_dll_path() -> Path:
    return backend_bin_dir() / "mp3gain_legacy_backend.dll"


def _source_files() -> list[Path]:
    source_root = legacy_source_dir()
    mpglib = source_root / "mpglibDBL"
    files = [
        source_root / "c_api_shim.c",
        source_root / "gain_analysis.c",
        source_root / "mp3gain.c",
        source_root / "rg_error.c",
        source_root / "apetag.c",
        source_root / "id3tag.c",
    ]
    files.extend(sorted(mpglib.glob("*.c")))
    return files


def _toolchain_ok() -> tuple[str | None, str]:
    gcc = shutil.which("gcc")
    if gcc is None:
        return None, "gcc is not available on PATH (MinGW toolchain required)"
    return gcc, ""


def build_backend(*, force: bool = False) -> Path:
    gcc, reason = _toolchain_ok()
    if gcc is None:
        raise RuntimeError(reason)

    source_root = legacy_source_dir()
    dll_path = backend_dll_path()
    dll_path.parent.mkdir(parents=True, exist_ok=True)

    sources = _source_files()
    if not force and dll_path.exists():
        dll_mtime = dll_path.stat().st_mtime
        newest_src = max(path.stat().st_mtime for path in sources)
        if dll_mtime >= newest_src:
            return dll_path

    cmd = [
        gcc,
        "-shared",
        "-O2",
        "-std=gnu89",
        "-fcommon",
        "-DWIN32",
        "-DasWIN32DLL",
        "-DHAVE_MEMCPY",
        "-Wl,--exclude-all-symbols",
        "-o",
        str(dll_path),
    ]
    cmd.extend(str(path) for path in sources)
    cmd.extend(
        [
            "-I",
            str(source_root),
            "-I",
            str(source_root / "mpglibDBL"),
            "-luser32",
            "-lwinmm",
            "-lm",
        ]
    )

    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            "Failed to build C backend DLL.\n"
            f"Command: {' '.join(cmd)}\n"
            f"STDOUT:\n{completed.stdout}\n"
            f"STDERR:\n{completed.stderr}"
        )
    return dll_path
