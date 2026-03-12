"""Frozen dataclasses representing settings snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class UiSettings:
    """User-visible preferences shown in the Options dialog."""

    target_volume_db: float = 89.0
    tag_mode: str = "apev2"  # "apev2" | "id3"
    stored_tag_policy: str = "auto"  # "auto" | "skip" | "recalc" | "check_only"
    folder_is_album: bool = True
    add_subfolders: bool = False
    preserve_dates: bool = False
    use_temp_files: bool = True
    show_file_progress: bool = True
    warn_on_clip: bool = True


@dataclass(frozen=True, slots=True)
class OpsSettings:
    """Low-level gain-writing operation flags."""

    wrap_gain: bool = False
    reckless_mode: bool = False
    force_apply_normalization: bool = True
    apply_zero_step: bool = False


@dataclass(frozen=True, slots=True)
class SessionSettings:
    """Per-session / window state persisted between runs."""

    last_add_files_dir: str = ""
    last_add_folder_dir: str = ""
    window_geometry: bytes = b""
    column_widths: tuple[int, ...] = field(default_factory=tuple)
