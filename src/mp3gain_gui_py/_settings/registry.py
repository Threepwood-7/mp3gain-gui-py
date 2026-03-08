"""Settings key constants and default values."""

from __future__ import annotations


class SettingsRegistry:
    """Base class carrying all QSettings key strings and default values."""

    # ── UI / display ───────────────────────────────────────────────────────
    TARGET_VOLUME_DB_KEY = "ui/target_volume_db"
    TAG_MODE_KEY = "ui/tag_mode"
    FOLDER_IS_ALBUM_KEY = "ui/folder_is_album"
    ADD_SUBFOLDERS_KEY = "ui/add_subfolders"
    PRESERVE_DATES_KEY = "ui/preserve_dates"
    USE_TEMP_FILES_KEY = "ui/use_temp_files"
    SHOW_FILE_PROGRESS_KEY = "ui/show_file_progress"
    WARN_ON_CLIP_KEY = "ui/warn_on_clip"

    # ── Operations ─────────────────────────────────────────────────────────
    WRAP_GAIN_KEY = "ops/wrap_gain"
    RECKLESS_MODE_KEY = "ops/reckless_mode"

    # ── Session ────────────────────────────────────────────────────────────
    LAST_ADD_FILES_DIR_KEY = "session/last_add_files_dir"
    LAST_ADD_FOLDER_DIR_KEY = "session/last_add_folder_dir"
    WINDOW_GEOMETRY_KEY = "session/window_geometry"
    COLUMN_WIDTHS_KEY = "session/column_widths"

    # ── Defaults ───────────────────────────────────────────────────────────
    DEFAULT_TARGET_VOLUME_DB: float = 89.0
    DEFAULT_TAG_MODE: str = "apev2"
    DEFAULT_FOLDER_IS_ALBUM: bool = True
    DEFAULT_ADD_SUBFOLDERS: bool = False
    DEFAULT_PRESERVE_DATES: bool = False
    DEFAULT_USE_TEMP_FILES: bool = True
    DEFAULT_SHOW_FILE_PROGRESS: bool = True
    DEFAULT_WARN_ON_CLIP: bool = True

    DEFAULT_WRAP_GAIN: bool = False
    DEFAULT_RECKLESS_MODE: bool = False

    DEFAULT_LAST_ADD_FILES_DIR: str = ""
    DEFAULT_LAST_ADD_FOLDER_DIR: str = ""
    DEFAULT_WINDOW_GEOMETRY: bytes = b""
    DEFAULT_COLUMN_WIDTHS: list[int] = []

    ALLOWED_TAG_MODES: frozenset[str] = frozenset({"apev2", "id3"})
