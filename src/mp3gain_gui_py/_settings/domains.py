"""QSettings domain objects: UI, Ops, Session."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import normalize as _norm
from .registry import SettingsRegistry

if TYPE_CHECKING:
    from .storage import SettingsStorage


class UiSettingsDomain(SettingsRegistry):
    def __init__(self, storage: SettingsStorage) -> None:
        self._storage = storage

    @property
    def target_volume_db(self) -> float:
        return _norm.normalize_float(
            self._storage.value(self.TARGET_VOLUME_DB_KEY, self.DEFAULT_TARGET_VOLUME_DB),
            self.DEFAULT_TARGET_VOLUME_DB,
        )

    @target_volume_db.setter
    def target_volume_db(self, value: float) -> None:
        self._storage.set_value(self.TARGET_VOLUME_DB_KEY, float(value))

    @property
    def tag_mode(self) -> str:
        raw = _norm.normalize_str(
            self._storage.value(self.TAG_MODE_KEY, self.DEFAULT_TAG_MODE),
            self.DEFAULT_TAG_MODE,
        )
        return raw if raw in self.ALLOWED_TAG_MODES else self.DEFAULT_TAG_MODE

    @tag_mode.setter
    def tag_mode(self, value: str) -> None:
        v = value if value in self.ALLOWED_TAG_MODES else self.DEFAULT_TAG_MODE
        self._storage.set_value(self.TAG_MODE_KEY, v)

    @property
    def stored_tag_policy(self) -> str:
        raw = _norm.normalize_str(
            self._storage.value(self.STORED_TAG_POLICY_KEY, self.DEFAULT_STORED_TAG_POLICY),
            self.DEFAULT_STORED_TAG_POLICY,
        )
        if raw in self.ALLOWED_STORED_TAG_POLICIES:
            return raw
        return self.DEFAULT_STORED_TAG_POLICY

    @stored_tag_policy.setter
    def stored_tag_policy(self, value: str) -> None:
        if value in self.ALLOWED_STORED_TAG_POLICIES:
            v = value
        else:
            v = self.DEFAULT_STORED_TAG_POLICY
        self._storage.set_value(self.STORED_TAG_POLICY_KEY, v)

    @property
    def folder_is_album(self) -> bool:
        return _norm.normalize_bool(
            self._storage.value(self.FOLDER_IS_ALBUM_KEY, self.DEFAULT_FOLDER_IS_ALBUM)
        )

    @folder_is_album.setter
    def folder_is_album(self, value: bool) -> None:
        self._storage.set_value(self.FOLDER_IS_ALBUM_KEY, bool(value))

    @property
    def add_subfolders(self) -> bool:
        return _norm.normalize_bool(
            self._storage.value(self.ADD_SUBFOLDERS_KEY, self.DEFAULT_ADD_SUBFOLDERS)
        )

    @add_subfolders.setter
    def add_subfolders(self, value: bool) -> None:
        self._storage.set_value(self.ADD_SUBFOLDERS_KEY, bool(value))

    @property
    def preserve_dates(self) -> bool:
        return _norm.normalize_bool(
            self._storage.value(self.PRESERVE_DATES_KEY, self.DEFAULT_PRESERVE_DATES)
        )

    @preserve_dates.setter
    def preserve_dates(self, value: bool) -> None:
        self._storage.set_value(self.PRESERVE_DATES_KEY, bool(value))

    @property
    def use_temp_files(self) -> bool:
        return _norm.normalize_bool(
            self._storage.value(self.USE_TEMP_FILES_KEY, self.DEFAULT_USE_TEMP_FILES)
        )

    @use_temp_files.setter
    def use_temp_files(self, value: bool) -> None:
        self._storage.set_value(self.USE_TEMP_FILES_KEY, bool(value))

    @property
    def show_file_progress(self) -> bool:
        return _norm.normalize_bool(
            self._storage.value(self.SHOW_FILE_PROGRESS_KEY, self.DEFAULT_SHOW_FILE_PROGRESS)
        )

    @show_file_progress.setter
    def show_file_progress(self, value: bool) -> None:
        self._storage.set_value(self.SHOW_FILE_PROGRESS_KEY, bool(value))

    @property
    def warn_on_clip(self) -> bool:
        return _norm.normalize_bool(
            self._storage.value(self.WARN_ON_CLIP_KEY, self.DEFAULT_WARN_ON_CLIP)
        )

    @warn_on_clip.setter
    def warn_on_clip(self, value: bool) -> None:
        self._storage.set_value(self.WARN_ON_CLIP_KEY, bool(value))


class OpsSettingsDomain(SettingsRegistry):
    def __init__(self, storage: SettingsStorage) -> None:
        self._storage = storage

    @property
    def wrap_gain(self) -> bool:
        return _norm.normalize_bool(
            self._storage.value(self.WRAP_GAIN_KEY, self.DEFAULT_WRAP_GAIN)
        )

    @wrap_gain.setter
    def wrap_gain(self, value: bool) -> None:
        self._storage.set_value(self.WRAP_GAIN_KEY, bool(value))

    @property
    def reckless_mode(self) -> bool:
        return _norm.normalize_bool(
            self._storage.value(self.RECKLESS_MODE_KEY, self.DEFAULT_RECKLESS_MODE)
        )

    @reckless_mode.setter
    def reckless_mode(self, value: bool) -> None:
        self._storage.set_value(self.RECKLESS_MODE_KEY, bool(value))


class SessionSettingsDomain(SettingsRegistry):
    def __init__(self, storage: SettingsStorage) -> None:
        self._storage = storage

    @property
    def last_add_files_dir(self) -> str:
        return _norm.normalize_str(
            self._storage.value(self.LAST_ADD_FILES_DIR_KEY, "")
        )

    @last_add_files_dir.setter
    def last_add_files_dir(self, value: str) -> None:
        self._storage.set_value(self.LAST_ADD_FILES_DIR_KEY, str(value))

    @property
    def last_add_folder_dir(self) -> str:
        return _norm.normalize_str(
            self._storage.value(self.LAST_ADD_FOLDER_DIR_KEY, "")
        )

    @last_add_folder_dir.setter
    def last_add_folder_dir(self, value: str) -> None:
        self._storage.set_value(self.LAST_ADD_FOLDER_DIR_KEY, str(value))

    @property
    def window_geometry(self) -> bytes:
        return _norm.normalize_bytes(
            self._storage.value(self.WINDOW_GEOMETRY_KEY, b"")
        )

    @window_geometry.setter
    def window_geometry(self, value: bytes) -> None:
        self._storage.set_value(self.WINDOW_GEOMETRY_KEY, bytes(value))

    @property
    def column_widths(self) -> list[int]:
        return _norm.normalize_int_list(
            self._storage.get_json(self.COLUMN_WIDTHS_KEY, [])
        )

    @column_widths.setter
    def column_widths(self, value: list[int]) -> None:
        self._storage.set_json(self.COLUMN_WIDTHS_KEY, list(value))
