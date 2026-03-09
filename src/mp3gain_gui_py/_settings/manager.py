"""SettingsManager — facade over UI, Ops and Session settings domains."""

from __future__ import annotations

from typing import Any

from .domains import OpsSettingsDomain, SessionSettingsDomain, UiSettingsDomain
from .registry import SettingsRegistry
from .storage import SettingsStorage


def _delegate_property(domain_attr: str, name: str) -> property:
    return property(
        lambda self: getattr(getattr(self, domain_attr), name),
        lambda self, value: setattr(getattr(self, domain_attr), name, value),
    )


class SettingsManager(SettingsRegistry):
    """Settings facade composed from UI, operations and session domains."""

    def __init__(self) -> None:
        self._storage = SettingsStorage()
        self.ui = UiSettingsDomain(self._storage)
        self.ops = OpsSettingsDomain(self._storage)
        self.session = SessionSettingsDomain(self._storage)
        self.settings_path = self._storage.settings_path

    def sync(self) -> None:
        self._storage.sync()

    def value(self, key: str, default: Any = None) -> Any:
        return self._storage.value(key, default)

    def set_value(self, key: str, value: Any) -> None:
        self._storage.set_value(key, value)

    def remove(self, key: str) -> None:
        self._storage.remove(key)

    def set_json(self, key: str, value: Any) -> None:
        self._storage.set_json(key, value)

    def get_json(self, key: str, default: Any) -> Any:
        return self._storage.get_json(key, default)

    # ── UI domain delegates ────────────────────────────────────────────────
    target_volume_db = _delegate_property("ui", "target_volume_db")
    tag_mode = _delegate_property("ui", "tag_mode")
    stored_tag_policy = _delegate_property("ui", "stored_tag_policy")
    folder_is_album = _delegate_property("ui", "folder_is_album")
    add_subfolders = _delegate_property("ui", "add_subfolders")
    preserve_dates = _delegate_property("ui", "preserve_dates")
    use_temp_files = _delegate_property("ui", "use_temp_files")
    show_file_progress = _delegate_property("ui", "show_file_progress")
    warn_on_clip = _delegate_property("ui", "warn_on_clip")

    # ── Ops domain delegates ───────────────────────────────────────────────
    wrap_gain = _delegate_property("ops", "wrap_gain")
    reckless_mode = _delegate_property("ops", "reckless_mode")

    # ── Session domain delegates ───────────────────────────────────────────
    last_add_files_dir = _delegate_property("session", "last_add_files_dir")
    last_add_folder_dir = _delegate_property("session", "last_add_folder_dir")
    window_geometry = _delegate_property("session", "window_geometry")
    column_widths = _delegate_property("session", "column_widths")
