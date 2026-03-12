from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMainWindow

from mp3gain_gui_py.ui.window.actions import WindowActionsCoordinator

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


class _DummyModel:
    def __init__(self, paths: list[Path], groups: dict[str, list[Path]]) -> None:
        self._paths = paths
        self._groups = groups

    def all_paths(self) -> list[Path]:
        return list(self._paths)

    def album_groups(self) -> dict[str, list[Path]]:
        return dict(self._groups)

    def add_files(self, _paths: list[Path]) -> None:
        return None

    def remove_files(self, _paths: list[Path]) -> None:
        return None

    def clear(self) -> None:
        return None


@dataclass
class _DummySettings:
    target_volume_db: float = 87.0
    tag_mode: str = "apev2"
    stored_tag_policy: str = "auto"
    wrap_gain: bool = False
    preserve_dates: bool = False
    force_apply_normalization: bool = True
    apply_zero_step: bool = True
    last_add_files_dir: str = ""
    last_add_folder_dir: str = ""
    add_subfolders: bool = False


def test_apply_track_request_carries_force_normalize_fields(qtbot: QtBot) -> None:
    paths = [Path(r"C:\tmp\a.mp3")]
    groups = {str(paths[0].parent): [paths[0]]}
    window = QMainWindow()
    window.model = _DummyModel(paths, groups)  # type: ignore[attr-defined]
    qtbot.addWidget(window)
    settings = _DummySettings()
    bridge = SimpleNamespace(start_worker=lambda _req: None, cancel=lambda: None)
    coord = WindowActionsCoordinator(window, settings, bridge)  # type: ignore[arg-type]

    captured = []
    coord._start_worker = captured.append  # type: ignore[method-assign]
    coord._on_apply_track()

    assert len(captured) == 1
    req = captured[0]
    assert req.kind == "apply_track"
    assert req.target_db == settings.target_volume_db
    assert req.force_apply_normalization is True
    assert req.apply_zero_step is True


def test_apply_album_request_carries_target_and_force_flags(qtbot: QtBot) -> None:
    paths = [Path(r"C:\tmp\a\one.mp3"), Path(r"C:\tmp\a\two.mp3")]
    groups = {str(paths[0].parent): list(paths)}
    window = QMainWindow()
    window.model = _DummyModel(paths, groups)  # type: ignore[attr-defined]
    qtbot.addWidget(window)
    settings = _DummySettings(target_volume_db=81.0, apply_zero_step=False)
    bridge = SimpleNamespace(start_worker=lambda _req: None, cancel=lambda: None)
    coord = WindowActionsCoordinator(window, settings, bridge)  # type: ignore[arg-type]

    captured = []
    coord._start_worker = captured.append  # type: ignore[method-assign]
    coord._on_apply_album()

    assert len(captured) == 1
    req = captured[0]
    assert req.kind == "apply_album"
    assert req.target_db == 81.0
    assert req.force_apply_normalization is True
    assert req.apply_zero_step is False
    assert req.album_groups == groups
