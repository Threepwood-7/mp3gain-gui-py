from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
from ctypes import c_double, c_int
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
C_ORACLE_SOURCE: Final[Path] = (
    REPO_ROOT / "tests" / "unit" / "c_oracle" / "legacy_math_oracle.c"
)
BUILD_ROOT: Final[Path] = Path(r"c:\tmp\pycompa\mp3gain_c_oracle")
DLL_PATH: Final[Path] = BUILD_ROOT / "legacy_math_oracle.dll"


class CTagState(ctypes.Structure):
    _fields_ = [
        ("dirty", c_int),
        ("have_undo", c_int),
        ("undo_left", c_int),
        ("undo_right", c_int),
        ("undo_wrap", c_int),
        ("have_track_gain", c_int),
        ("track_gain", c_double),
        ("have_track_peak", c_int),
        ("track_peak", c_double),
        ("have_album_gain", c_int),
        ("album_gain", c_double),
        ("have_album_peak", c_int),
        ("album_peak", c_double),
        ("have_minmax_gain", c_int),
        ("min_gain", c_int),
        ("max_gain", c_int),
        ("have_album_minmax_gain", c_int),
        ("album_min_gain", c_int),
        ("album_max_gain", c_int),
    ]


def _gcc_path() -> str | None:
    return shutil.which("gcc")


def c_oracle_available() -> bool:
    return _gcc_path() is not None and C_ORACLE_SOURCE.exists()


def build_c_oracle(force_rebuild: bool = False) -> Path:
    gcc = _gcc_path()
    if gcc is None:
        raise RuntimeError("gcc is not available in PATH")
    if not C_ORACLE_SOURCE.exists():
        raise RuntimeError(f"C oracle source not found: {C_ORACLE_SOURCE}")

    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    needs_rebuild = force_rebuild or (not DLL_PATH.exists())
    if DLL_PATH.exists() and not needs_rebuild:
        needs_rebuild = C_ORACLE_SOURCE.stat().st_mtime > DLL_PATH.stat().st_mtime

    if needs_rebuild:
        command = [
            gcc,
            "-shared",
            "-std=c99",
            "-O2",
            "-o",
            str(DLL_PATH),
            str(C_ORACLE_SOURCE),
            "-lm",
        ]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(
                "Failed to build C oracle DLL.\n"
                f"Command: {' '.join(command)}\n"
                f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
    return DLL_PATH


def load_c_oracle(force_rebuild: bool = False) -> ctypes.CDLL:
    dll_path = build_c_oracle(force_rebuild=force_rebuild)
    os.environ.setdefault("PATH", "")
    dll = ctypes.CDLL(str(dll_path))

    dll.mp3gain_c_legacy_round.argtypes = [c_double]
    dll.mp3gain_c_legacy_round.restype = c_int

    dll.mp3gain_c_db_to_steps.argtypes = [c_double, c_int]
    dll.mp3gain_c_db_to_steps.restype = c_int

    dll.mp3gain_c_steps_to_db_exact.argtypes = [c_int]
    dll.mp3gain_c_steps_to_db_exact.restype = c_double

    dll.mp3gain_c_steps_to_db_approx.argtypes = [c_int]
    dll.mp3gain_c_steps_to_db_approx.restype = c_double

    dll.mp3gain_c_autoclip_track_gain.argtypes = [c_int, c_double]
    dll.mp3gain_c_autoclip_track_gain.restype = c_int

    dll.mp3gain_c_autoclip_album_gain.argtypes = [c_int, c_double]
    dll.mp3gain_c_autoclip_album_gain.restype = c_int

    dll.mp3gain_c_update_tag_state.argtypes = [
        ctypes.POINTER(CTagState),
        c_int,
        c_int,
        c_int,
    ]
    dll.mp3gain_c_update_tag_state.restype = None

    return dll
