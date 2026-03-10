from __future__ import annotations

from pathlib import Path

import mp3gain_gui_py.legacy_cli as legacy_cli
import pytest
from mp3gain_gui_py._legacy_exact.processor import LegacyCommandResult, LegacyCompatOptions
from mp3gain_gui_py._tags.reader import TagData


class _BranchFakeProcessor:
    def __init__(self) -> None:
        self.analyze_track_paths: list[Path] = []
        self.analyze_max_paths: list[Path] = []
        self.analyze_minmax_paths: list[Path] = []
        self.analyze_album_paths: list[list[Path]] = []
        self.analyze_album_minmax_paths: list[list[Path]] = []
        self.apply_steps_calls: list[tuple[Path, int, int | None]] = []
        self.apply_direct_calls: list[tuple[Path, int]] = []
        self.apply_single_calls: list[tuple[Path, int, int]] = []
        self.undo_paths: list[Path] = []
        self.delete_tag_calls: list[tuple[Path, str | None]] = []

    def analyze_track_gain_db(self, path: Path) -> float:
        self.analyze_track_paths.append(path)
        return -9.2

    def analyze_max_amplitude(self, path: Path) -> float:
        self.analyze_max_paths.append(path)
        return 32768.0

    def analyze_minmax_gain(self, path: Path) -> tuple[int, int]:
        self.analyze_minmax_paths.append(path)
        return 82, 210

    def analyze_album_gain_db(self, paths: list[Path]) -> float:
        self.analyze_album_paths.append(list(paths))
        return -9.35

    def analyze_album_minmax_gain(self, paths: list[Path]) -> tuple[int, int]:
        self.analyze_album_minmax_paths.append(list(paths))
        return 38, 210

    def compute_autoclip_steps(self, requested_steps: int, *, min_gain: int, max_gain: int) -> int:
        _ = min_gain
        _ = max_gain
        return requested_steps

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

    def apply_direct_gain_steps(
        self,
        path: Path,
        *,
        steps: int,
        options: LegacyCompatOptions,
    ) -> LegacyCommandResult:
        _ = options
        self.apply_direct_calls.append((path, steps))
        return LegacyCommandResult(exit_code=0, changed=True)

    def apply_single_channel_steps(
        self,
        path: Path,
        *,
        channel_index: int,
        steps: int,
        options: LegacyCompatOptions,
    ) -> LegacyCommandResult:
        _ = options
        self.apply_single_calls.append((path, channel_index, steps))
        return LegacyCommandResult(exit_code=0, changed=True)

    def undo(self, path: Path, *, options: LegacyCompatOptions) -> LegacyCommandResult:
        _ = options
        self.undo_paths.append(path)
        return LegacyCommandResult(exit_code=0, changed=True)

    def delete_mp3gain_tags(
        self,
        path: Path,
        *,
        tag_format: str | None = None,
    ) -> LegacyCommandResult:
        self.delete_tag_calls.append((path, tag_format))
        return LegacyCommandResult(exit_code=0, changed=True)


def _install_fake_processor(monkeypatch: pytest.MonkeyPatch) -> _BranchFakeProcessor:
    fake = _BranchFakeProcessor()
    monkeypatch.setattr(legacy_cli, "LegacyExactProcessor", lambda: fake)
    monkeypatch.setattr(
        legacy_cli,
        "_write_runtime_tags",
        lambda _path, _tags, *, tag_format, preserve_timestamp: None,
    )
    return fake


def test_check_only_branch_uses_tag_metrics_and_skips_processor_analysis(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"x")
    fake = _install_fake_processor(monkeypatch)
    monkeypatch.setattr(
        legacy_cli,
        "read_tags",
        lambda _path: TagData(
            tag_format="apev2",
            track_gain_db=-9.21,
            track_peak=1.036789,
            min_gain=82,
            max_gain=210,
        ),
    )

    code = legacy_cli.main(["/q", "/o", "/s", "c", str(target)])
    out = capsys.readouterr().out

    assert code == 0
    assert str(target) in out
    assert fake.analyze_track_paths == []
    assert fake.apply_steps_calls == []


@pytest.mark.parametrize(
    ("argv", "expected_format"),
    [
        (["/q", "/s", "d"], "apev2"),
    ],
)
def test_delete_tag_branch_calls_processor_with_expected_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    argv: list[str],
    expected_format: str,
) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"x")
    fake = _install_fake_processor(monkeypatch)

    code = legacy_cli.main([*argv, str(target)])

    assert code == 0
    assert fake.delete_tag_calls == [(target, expected_format)]


def test_direct_gain_branch_calls_apply_direct_gain_steps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"x")
    fake = _install_fake_processor(monkeypatch)

    code = legacy_cli.main(["/q", "/g", "4", str(target)])

    assert code == 0
    assert fake.apply_direct_calls == [(target, 4)]
    assert fake.analyze_minmax_paths == []


def test_single_channel_branch_calls_apply_single_channel_steps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"x")
    fake = _install_fake_processor(monkeypatch)

    code = legacy_cli.main(["/q", "/l", "1", "-3", str(target)])

    assert code == 0
    assert fake.apply_single_calls == [(target, 1, -3)]
    assert fake.analyze_minmax_paths == []


def test_track_apply_branch_uses_auto_tag_data_without_reanalysis(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"x")
    fake = _install_fake_processor(monkeypatch)
    monkeypatch.setattr(
        legacy_cli,
        "read_tags",
        lambda _path: TagData(
            tag_format="apev2",
            track_gain_db=-9.21,
            track_peak=1.036789,
            min_gain=82,
            max_gain=210,
        ),
    )

    code = legacy_cli.main(["/q", "/r", "/c", str(target)])

    assert code == 0
    assert len(fake.apply_steps_calls) == 1
    assert fake.apply_steps_calls[0][0] == target
    assert fake.analyze_track_paths == []


def test_album_apply_branch_uses_shared_album_steps_for_all_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    left = tmp_path / "a.mp3"
    right = tmp_path / "b.mp3"
    left.write_bytes(b"a")
    right.write_bytes(b"b")
    fake = _install_fake_processor(monkeypatch)
    monkeypatch.setattr(legacy_cli, "read_tags", lambda _path: TagData(tag_format="none"))

    code = legacy_cli.main(["/q", "/a", "/c", str(left), str(right)])

    assert code == 0
    assert fake.analyze_album_paths == [[left, right]]
    assert fake.analyze_album_minmax_paths == [[left, right]]
    assert len(fake.apply_steps_calls) == 2
    applied_steps = {call[1] for call in fake.apply_steps_calls}
    assert len(applied_steps) == 1


def test_undo_branch_calls_processor_undo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"x")
    fake = _install_fake_processor(monkeypatch)
    monkeypatch.setattr(
        legacy_cli,
        "read_tags",
        lambda _path: TagData(tag_format="apev2", undo_left=2, undo_right=2, undo_mode="N"),
    )

    code = legacy_cli.main(["/q", "/u", str(target)])

    assert code == 0
    assert fake.apply_steps_calls == [(target, 2, 2)]


def test_clip_guard_blocks_apply_without_c_or_k_or_f(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "sample.mp3"
    target.write_bytes(b"x")
    fake = _install_fake_processor(monkeypatch)
    monkeypatch.setattr(legacy_cli, "read_tags", lambda _path: TagData(tag_format="none"))
    monkeypatch.setattr(legacy_cli, "db_to_legacy_steps", lambda _gain, mp3_gain_mod=0: 10 + mp3_gain_mod)
    code = legacy_cli.main(["/q", "/r", str(target)])

    assert code == 1
    assert fake.apply_steps_calls == []
