from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import mp3gain_gui_py._workers.process_tasks as process_tasks_mod
from mp3gain_gui_py._legacy_exact.math import db_to_legacy_steps

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


class _DummyProcessor:
    def __init__(self, *, analyzed_gain_db: float) -> None:
        self._analyzed_gain_db = analyzed_gain_db
        self.apply_steps_calls: list[int] = []

    def analyze_track_metrics(
        self,
        path: Path,
        *,
        include_gain: bool = True,
    ) -> tuple[float, float, int, int]:
        _ = path
        _ = include_gain
        return self._analyzed_gain_db, 0.0, 0, 255

    def apply_steps(
        self,
        path: Path,
        *,
        left_steps: int,
        options: object,
    ) -> object:
        _ = path
        _ = options
        self.apply_steps_calls.append(left_steps)
        return SimpleNamespace(exit_code=0, message="")

    def undo(self, path: Path, *, options: object) -> object:
        _ = path
        _ = options
        return SimpleNamespace(exit_code=0, message="")


def test_gain_file_task_forced_track_normalize_uses_analysis_not_tags(
    monkeypatch: MonkeyPatch,
) -> None:
    dummy = _DummyProcessor(analyzed_gain_db=3.010299956639812)
    monkeypatch.setattr(process_tasks_mod, "_get_processor", lambda: dummy)
    monkeypatch.setattr(
        process_tasks_mod,
        "read_tags",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("read_tags should not be called")
        ),
    )

    result = process_tasks_mod.gain_file_task(
        "apply_track",
        str(Path("sample.mp3")),
        constant_db=0.0,
        wrap_gain=False,
        preserve_dates=False,
        target_db=87.0,
        force_apply_normalization=True,
        apply_zero_step=False,
    )

    assert result.ok is True
    assert dummy.apply_steps_calls == [1]


def test_gain_file_task_forced_track_zero_step_can_skip_apply(
    monkeypatch: MonkeyPatch,
) -> None:
    dummy = _DummyProcessor(analyzed_gain_db=0.0)
    monkeypatch.setattr(process_tasks_mod, "_get_processor", lambda: dummy)

    result = process_tasks_mod.gain_file_task(
        "apply_track",
        str(Path("sample.mp3")),
        constant_db=0.0,
        wrap_gain=False,
        preserve_dates=False,
        target_db=89.0,
        force_apply_normalization=True,
        apply_zero_step=False,
    )

    assert result.ok is True
    assert dummy.apply_steps_calls == []


def test_gain_file_task_forced_track_zero_step_can_apply(
    monkeypatch: MonkeyPatch,
) -> None:
    dummy = _DummyProcessor(analyzed_gain_db=0.0)
    monkeypatch.setattr(process_tasks_mod, "_get_processor", lambda: dummy)

    result = process_tasks_mod.gain_file_task(
        "apply_track",
        str(Path("sample.mp3")),
        constant_db=0.0,
        wrap_gain=False,
        preserve_dates=False,
        target_db=89.0,
        force_apply_normalization=True,
        apply_zero_step=True,
    )

    assert result.ok is True
    assert dummy.apply_steps_calls == [0]


def test_gain_file_task_force_disabled_apply_track_uses_tags(
    monkeypatch: MonkeyPatch,
) -> None:
    track_gain = 3.010299956639812
    dummy = _DummyProcessor(analyzed_gain_db=0.0)
    monkeypatch.setattr(process_tasks_mod, "_get_processor", lambda: dummy)
    monkeypatch.setattr(
        process_tasks_mod,
        "read_tags",
        lambda _path: SimpleNamespace(track_gain_db=track_gain, album_gain_db=None),
    )

    result = process_tasks_mod.gain_file_task(
        "apply_track",
        str(Path("sample.mp3")),
        constant_db=0.0,
        wrap_gain=False,
        preserve_dates=False,
        target_db=89.0,
        force_apply_normalization=False,
        apply_zero_step=False,
    )

    assert result.ok is True
    assert dummy.apply_steps_calls == [db_to_legacy_steps(track_gain)]


def test_gain_file_task_forced_album_requires_group_steps(
    monkeypatch: MonkeyPatch,
) -> None:
    dummy = _DummyProcessor(analyzed_gain_db=0.0)
    monkeypatch.setattr(process_tasks_mod, "_get_processor", lambda: dummy)

    missing = process_tasks_mod.gain_file_task(
        "apply_album",
        str(Path("sample.mp3")),
        constant_db=0.0,
        wrap_gain=False,
        preserve_dates=False,
        target_db=89.0,
        force_apply_normalization=True,
        apply_zero_step=False,
        forced_steps=None,
    )
    present = process_tasks_mod.gain_file_task(
        "apply_album",
        str(Path("sample.mp3")),
        constant_db=0.0,
        wrap_gain=False,
        preserve_dates=False,
        target_db=89.0,
        force_apply_normalization=True,
        apply_zero_step=False,
        forced_steps=2,
    )

    assert missing.ok is False
    assert "Album analysis failed" in missing.error_msg
    assert present.ok is True
    assert dummy.apply_steps_calls == [2]
