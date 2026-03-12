"""SettingsManager facade over UI, Ops and Session settings domains."""

from __future__ import annotations

from threep_commons.settings import (
    QSettingsJsonStorage,
    SettingsManagerBase,
    delegate_domain_property,
)

from mp3gain_gui_py.constants import APP_IDENTITY

from .domains import OpsSettingsDomain, SessionSettingsDomain, UiSettingsDomain
from .registry import SettingsRegistry


class SettingsManager(SettingsManagerBase, SettingsRegistry):
    """Settings facade composed from UI, operations and session domains."""

    def __init__(self) -> None:
        super().__init__(QSettingsJsonStorage(APP_IDENTITY))
        self.ui = UiSettingsDomain(self._storage)
        self.ops = OpsSettingsDomain(self._storage)
        self.session = SessionSettingsDomain(self._storage)

    # UI domain delegates
    target_volume_db = delegate_domain_property("ui", "target_volume_db")
    tag_mode = delegate_domain_property("ui", "tag_mode")
    stored_tag_policy = delegate_domain_property("ui", "stored_tag_policy")
    folder_is_album = delegate_domain_property("ui", "folder_is_album")
    add_subfolders = delegate_domain_property("ui", "add_subfolders")
    preserve_dates = delegate_domain_property("ui", "preserve_dates")
    use_temp_files = delegate_domain_property("ui", "use_temp_files")
    show_file_progress = delegate_domain_property("ui", "show_file_progress")
    warn_on_clip = delegate_domain_property("ui", "warn_on_clip")

    # Ops domain delegates
    wrap_gain = delegate_domain_property("ops", "wrap_gain")
    reckless_mode = delegate_domain_property("ops", "reckless_mode")
    force_apply_normalization = delegate_domain_property("ops", "force_apply_normalization")
    apply_zero_step = delegate_domain_property("ops", "apply_zero_step")

    # Session domain delegates
    last_add_files_dir = delegate_domain_property("session", "last_add_files_dir")
    last_add_folder_dir = delegate_domain_property("session", "last_add_folder_dir")
    window_geometry = delegate_domain_property("session", "window_geometry")
    column_widths = delegate_domain_property("session", "column_widths")
