from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


def _load_script_module(module_name: str, script_name: str) -> ModuleType:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(script_path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_build_one_skip_tags_does_not_rewrite_tags(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    mod = _load_script_module("test_parity_build", "parity_build_codex_89db.py")

    src = tmp_path / "source.mp3"
    src_bytes = b"audio-data-APETAGEX-meta-TAG-tail"
    src.write_bytes(src_bytes)
    dst = tmp_path / "dest.mp3"

    class DummyProcessor:
        def analyze_track_gain_db_with_fallback(self, path: Path) -> tuple[float, bool]:
            _ = path
            return -3.5, False

        def apply_steps(
            self,
            path: Path,
            *,
            left_steps: int,
            options: object,
        ) -> None:
            _ = (path, left_steps, options)

    def fail_call(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("tag/scan helpers must not be called in skip_tags profile")

    monkeypatch.setattr(mod, "LegacyExactProcessor", DummyProcessor)
    monkeypatch.setattr(mod, "scan_file", fail_call)
    monkeypatch.setattr(mod, "scan_max_amplitude", fail_call)
    monkeypatch.setattr(mod, "delete_tags", fail_call)
    monkeypatch.setattr(mod, "write_tags", fail_call)
    monkeypatch.setattr(mod, "read_id3v1_tail", fail_call)
    monkeypatch.setattr(mod, "preserve_id3v1_tail", fail_call)

    result = mod._build_one(src, dst, legacy_profile="skip_tags")
    assert dst.read_bytes() == src_bytes
    assert result["legacy_profile"] == "skip_tags"
    assert result["track_peak"] is None
    assert result["used_ascii_alias"] is False


def test_select_sample_names_is_seeded_and_sorted() -> None:
    mod = _load_script_module("test_parity_external", "parity_external_sample_report.py")
    names = [
        "zeta.mp3",
        "Alpha.mp3",
        "bravo.mp3",
        "Echo.mp3",
        "delta.mp3",
        "charlie.mp3",
    ]

    sample_a = mod._select_sample_names(names, sample_size=4, seed=42)
    sample_b = mod._select_sample_names(names, sample_size=4, seed=42)
    sample_c = mod._select_sample_names(names, sample_size=4, seed=99)

    assert sample_a == sample_b
    assert sample_a == sorted(sample_a, key=str.lower)
    assert sample_c != sample_a
