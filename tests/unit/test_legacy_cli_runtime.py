from __future__ import annotations

from typing import TYPE_CHECKING

import mp3gain_gui_py.legacy_cli as legacy_cli
from mp3gain_gui_py._legacy_exact.processor import (
    LegacyCommandResult,
    LegacyCompatOptions,
)
from mp3gain_gui_py._tags.reader import TagData

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class _FakeProcessor:
    def __init__(self) -> None:
        self.analyze_track_paths: list[Path] = []
        self.analyze_max_paths: list[Path] = []
        self.analyze_minmax_paths: list[Path] = []
        self.direct_steps: list[int] = []
        self.undo_paths: list[Path] = []
        self.apply_steps_calls: list[tuple[Path, int, int | None]] = []

    def analyze_track_gain_db(self, path: Path) -> float:
        self.analyze_track_paths.append(path)
        return -9.0

    def analyze_max_amplitude(self, path: Path) -> float:
        self.analyze_max_paths.append(path)
        return 24576.0

    def analyze_minmax_gain(self, path: Path) -> tuple[int, int]:
        self.analyze_minmax_paths.append(path)
        return 80, 180

    def analyze_album_gain_db(self, paths: list[Path]) -> float:
        _ = paths
        return -9.0

    def analyze_album_minmax_gain(self, paths: list[Path]) -> tuple[int, int]:
        _ = paths
        return 80, 180

    def apply_direct_gain_steps(
        self,
        path: Path,
        *,
        steps: int,
        options: LegacyCompatOptions,
    ) -> LegacyCommandResult:
        _ = path
        _ = options
        self.direct_steps.append(steps)
        return LegacyCommandResult(exit_code=0, changed=True)

    def apply_steps(
        self,
        path: Path,
        *,
        left_steps: int,
        right_steps: int | None = None,
        options: LegacyCompatOptions,
    ) -> LegacyCommandResult:
        _ = options
        self.apply_steps_calls.append((path, left_steps, right_steps))
        return LegacyCommandResult(exit_code=0, changed=True)

    def undo(self, path: Path, *, options: LegacyCompatOptions) -> LegacyCommandResult:
        _ = options
        self.undo_paths.append(path)
        return LegacyCommandResult(exit_code=0, changed=True)

    def read_replaygain_tags(self, path: Path) -> TagData:
        _ = path
        return TagData(tag_format="none")


def _install_fake_processor(monkeypatch: pytest.MonkeyPatch) -> _FakeProcessor:
    fake = _FakeProcessor()
    monkeypatch.setattr(legacy_cli, "LegacyExactProcessor", lambda: fake)
    monkeypatch.setattr(
        legacy_cli,
        "_write_runtime_tags",
        lambda _processor, _path, _tags, *, tag_format, preserve_timestamp: None,
    )
    return fake


def test_runtime_analysis_recalc_table_uses_python_processor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"x")
    fake = _install_fake_processor(monkeypatch)

    code = legacy_cli.main(["/q", "/o", "/s", "r", str(target)])
    out = capsys.readouterr().out

    assert code == 0
    assert fake.analyze_track_paths == [target]
    assert fake.analyze_max_paths == [target, target]
    assert fake.analyze_minmax_paths == [target]
    assert str(target) in out


def test_runtime_direct_gain_uses_python_processor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"x")
    fake = _install_fake_processor(monkeypatch)

    code = legacy_cli.main(["/q", "/g", "4", str(target)])

    assert code == 0
    assert fake.direct_steps == [4]
    assert fake.analyze_minmax_paths == []


def test_runtime_modifiers_m_and_d_execute_python_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"x")
    fake = _install_fake_processor(monkeypatch)
    monkeypatch.setattr(
        legacy_cli,
        "_load_runtime_tags",
        lambda _processor, _path, *, tag_format: TagData(tag_format="none"),
    )

    code = legacy_cli.main(["/m", "1", "/d", "1.5", str(target)])
    out = capsys.readouterr().out

    assert code == 0
    assert fake.analyze_track_paths == [target]
    assert 'Recommended "Track" dB change' in out


def test_runtime_undo_uses_python_processor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"x")
    fake = _install_fake_processor(monkeypatch)
    monkeypatch.setattr(
        legacy_cli,
        "_load_runtime_tags",
        lambda _processor, _path, *, tag_format: TagData(
            tag_format="apev2",
            undo_left=2,
            undo_right=2,
            undo_mode="N",
        ),
    )

    code = legacy_cli.main(["/q", "/u", str(target)])

    assert code == 0
    assert fake.apply_steps_calls == [(target, 2, 2)]


def test_no_oracle_passthrough_symbols_remain() -> None:
    assert not hasattr(legacy_cli, "_LEGACY_ORACLE_EXE")
    assert not hasattr(legacy_cli, "_should_oracle_passthrough")
    assert not hasattr(legacy_cli, "_run_oracle_passthrough")


def test_help_qmark_without_files_returns_one(capsys: pytest.CaptureFixture[str]) -> None:
    code = legacy_cli.main(["/?"])
    _ = capsys.readouterr()
    assert code == 1


def test_unrecognized_e_option_reports_stderr_and_continues(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"x")
    _install_fake_processor(monkeypatch)

    code = legacy_cli.main(["/q", "/o", "/e", str(target)])
    captured = capsys.readouterr()

    assert code == 0
    assert "I don't recognize option /e" in captured.err
