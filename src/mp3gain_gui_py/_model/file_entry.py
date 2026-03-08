"""FileEntry — mutable dataclass representing one row in the file list."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from mp3gain_gui_py._tags.reader import TagData

FileStatus = Literal["idle", "analyzing", "done", "error"]


@dataclass
class FileEntry:
    """All analysis results and metadata for a single MP3 file.

    Mutable so that the model can update individual fields after background
    analysis completes.
    """

    path: Path

    # ── ReplayGain analysis results ────────────────────────────────────────
    volume_db: float | None = None          # current perceived volume (dB)
    track_gain_db: float | None = None      # recommended track gain change (dB)
    album_gain_db: float | None = None      # recommended album gain change (dB)
    max_amplitude: float | None = None      # max decoded sample (0-32768 scale)

    # ── Frame scan results ─────────────────────────────────────────────────
    min_gain_field: int | None = None       # min global_gain byte across all frames
    max_gain_field: int | None = None       # max global_gain byte across all frames

    # ── Clipping indicators ────────────────────────────────────────────────
    clipping: bool = False                  # would clip at current gain
    clip_track: float | None = None         # amplitude after track gain applied
    album_volume_db: float | None = None    # album-level volume
    clip_album: float | None = None         # amplitude after album gain applied

    # ── Tag data read from file ────────────────────────────────────────────
    tag_data: TagData | None = None

    # ── Status / error ─────────────────────────────────────────────────────
    status: FileStatus = "idle"
    error_msg: str = ""

    # ── Derived properties ─────────────────────────────────────────────────

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def folder(self) -> str:
        return str(self.path.parent)

    @property
    def group_key(self) -> str:
        """Album group key — parent directory path used for album analysis."""
        return str(self.path.parent)

    @property
    def path_and_file(self) -> str:
        """Combined path\\filename display string matching VB6 GUI column."""
        return str(self.path)

    def reset_analysis(self) -> None:
        """Clear all analysis results, keeping path and tag data."""
        self.volume_db = None
        self.track_gain_db = None
        self.album_gain_db = None
        self.max_amplitude = None
        self.min_gain_field = None
        self.max_gain_field = None
        self.clipping = False
        self.clip_track = None
        self.album_volume_db = None
        self.clip_album = None
        self.status = "idle"
        self.error_msg = ""
