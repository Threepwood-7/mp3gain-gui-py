from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mp3gain_gui_py.ui.dialogs.options_dialog import OptionsDialog

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


@dataclass
class _DummySettings:
    target_volume_db: float = 89.0
    tag_mode: str = "apev2"
    stored_tag_policy: str = "auto"
    folder_is_album: bool = True
    add_subfolders: bool = False
    preserve_dates: bool = False
    use_temp_files: bool = True
    show_file_progress: bool = True
    warn_on_clip: bool = True
    wrap_gain: bool = False
    reckless_mode: bool = False
    force_apply_normalization: bool = True
    apply_zero_step: bool = False
    sync_called: bool = False

    def sync(self) -> None:
        self.sync_called = True


def test_options_dialog_force_apply_controls_load_from_settings(qtbot: QtBot) -> None:
    settings = _DummySettings(force_apply_normalization=True, apply_zero_step=False)
    dialog = OptionsDialog(settings)
    qtbot.addWidget(dialog)

    assert dialog._force_apply_normalization.isChecked() is True
    assert dialog._apply_zero_step.isChecked() is False


def test_options_dialog_force_apply_controls_persist_to_settings(qtbot: QtBot) -> None:
    settings = _DummySettings(force_apply_normalization=True, apply_zero_step=False)
    dialog = OptionsDialog(settings)
    qtbot.addWidget(dialog)

    dialog._force_apply_normalization.setChecked(False)
    dialog._apply_zero_step.setChecked(True)
    dialog._apply_and_accept()

    assert settings.force_apply_normalization is False
    assert settings.apply_zero_step is True
    assert settings.sync_called is True
