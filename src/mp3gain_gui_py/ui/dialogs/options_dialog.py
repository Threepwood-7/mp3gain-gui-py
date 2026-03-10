"""OptionsDialog — mirrors frmOptions: all UiSettings + OpsSettings fields."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from ..._settings.manager import SettingsManager


class OptionsDialog(QDialog):
    """Options dialog for UI + operations settings."""

    def __init__(self, settings: SettingsManager, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._settings = settings
        self.setObjectName("options_dialog")
        self.setWindowTitle("Options")
        self.setMinimumWidth(340)

        # ── UI settings group ──────────────────────────────────────────────
        ui_group = QGroupBox("User Interface", self)
        ui_form = QFormLayout(ui_group)

        self._target_volume = QDoubleSpinBox(self)
        self._target_volume.setRange(0.0, 150.0)
        self._target_volume.setSingleStep(0.5)
        self._target_volume.setDecimals(1)
        self._target_volume.setValue(settings.target_volume_db)
        ui_form.addRow("Target volume (dB):", self._target_volume)

        self._tag_mode = QComboBox(self)
        self._tag_mode.addItems(["apev2", "id3"])
        self._tag_mode.setCurrentText(settings.tag_mode)
        ui_form.addRow("Tag format:", self._tag_mode)

        self._stored_tag_policy = QComboBox(self)
        self._stored_tag_policy.addItems(["auto", "skip", "recalc", "check_only"])
        self._stored_tag_policy.setCurrentText(settings.stored_tag_policy)
        ui_form.addRow("Stored tag policy:", self._stored_tag_policy)

        self._folder_is_album = QCheckBox("Treat folder as album", self)
        self._folder_is_album.setChecked(settings.folder_is_album)
        ui_form.addRow(self._folder_is_album)

        self._add_subfolders = QCheckBox("Include subfolders when adding folder", self)
        self._add_subfolders.setChecked(settings.add_subfolders)
        ui_form.addRow(self._add_subfolders)

        self._preserve_dates = QCheckBox("Preserve file timestamps", self)
        self._preserve_dates.setChecked(settings.preserve_dates)
        ui_form.addRow(self._preserve_dates)

        self._use_temp_files = QCheckBox("Use temporary files when writing", self)
        self._use_temp_files.setChecked(settings.use_temp_files)
        ui_form.addRow(self._use_temp_files)

        self._show_file_progress = QCheckBox("Show per-file progress", self)
        self._show_file_progress.setChecked(settings.show_file_progress)
        ui_form.addRow(self._show_file_progress)

        self._warn_on_clip = QCheckBox("Warn when clipping would occur", self)
        self._warn_on_clip.setChecked(settings.warn_on_clip)
        ui_form.addRow(self._warn_on_clip)

        # ── Ops settings group ─────────────────────────────────────────────
        ops_group = QGroupBox("Gain Writing", self)
        ops_form = QFormLayout(ops_group)

        self._wrap_gain = QCheckBox("Wrap global_gain (avoid frame skip)", self)
        self._wrap_gain.setChecked(settings.wrap_gain)
        ops_form.addRow(self._wrap_gain)

        self._reckless_mode = QCheckBox("Reckless mode (no CRC recalculation)", self)
        self._reckless_mode.setChecked(settings.reckless_mode)
        ops_form.addRow(self._reckless_mode)

        self._force_apply_normalization = QCheckBox(
            "Force analyze+normalize on apply (track+album)",
            self,
        )
        self._force_apply_normalization.setChecked(settings.force_apply_normalization)
        ops_form.addRow(self._force_apply_normalization)

        self._apply_zero_step = QCheckBox(
            "Apply even when computed step is 0",
            self,
        )
        self._apply_zero_step.setChecked(settings.apply_zero_step)
        ops_form.addRow(self._apply_zero_step)

        # ── Dialog buttons ─────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._apply_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(ui_group)
        layout.addWidget(ops_group)
        layout.addWidget(buttons)

    def _apply_and_accept(self) -> None:
        s = self._settings
        s.target_volume_db = self._target_volume.value()
        s.tag_mode = self._tag_mode.currentText()
        s.stored_tag_policy = self._stored_tag_policy.currentText()
        s.folder_is_album = self._folder_is_album.isChecked()
        s.add_subfolders = self._add_subfolders.isChecked()
        s.preserve_dates = self._preserve_dates.isChecked()
        s.use_temp_files = self._use_temp_files.isChecked()
        s.show_file_progress = self._show_file_progress.isChecked()
        s.warn_on_clip = self._warn_on_clip.isChecked()
        s.wrap_gain = self._wrap_gain.isChecked()
        s.reckless_mode = self._reckless_mode.isChecked()
        s.force_apply_normalization = self._force_apply_normalization.isChecked()
        s.apply_zero_step = self._apply_zero_step.isChecked()
        s.sync()
        self.accept()
