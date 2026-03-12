"""FileListModel — QAbstractTableModel backing the main file list view.

Columns (matching VB6 GUI: Path\\File | Volume | clipping | Track Gain |
clip(Track) | Album Volume | Album Gain | clip(Album)):
  0  Path\\File
  1  Volume
  2  clipping
  3  Track Gain
  4  clip(Track)
  5  Album Volume
  6  Album Gain
  7  clip(Album)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QColor

from .file_entry import FileEntry

if TYPE_CHECKING:
    from pathlib import Path

_HEADERS = [
    "Path\\File",
    "Volume",
    "clipping",
    "Track Gain",
    "clip(Track)",
    "Album Volume",
    "Album Gain",
    "clip(Album)",
]

_COL_PATH = 0
_COL_VOLUME = 1
_COL_CLIPPING = 2
_COL_TRACK_GAIN = 3
_COL_CLIP_TRACK = 4
_COL_ALBUM_VOLUME = 5
_COL_ALBUM_GAIN = 6
_COL_CLIP_ALBUM = 7

_CLIP_YES = "Y"
_RED = QColor(200, 0, 0)
_DEFAULT_MODEL_INDEX = QModelIndex()


class FileListModel(QAbstractTableModel):
    """Table model for the MP3 file list."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setObjectName("file_list_model")
        self._entries: list[FileEntry] = []
        self._path_index: dict[Path, int] = {}

    # ── Qt overrides ───────────────────────────────────────────────────────

    def rowCount(
        self, parent: QModelIndex | QPersistentModelIndex = _DEFAULT_MODEL_INDEX
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(
        self, parent: QModelIndex | QPersistentModelIndex = _DEFAULT_MODEL_INDEX
    ) -> int:
        if parent.isValid():
            return 0
        return len(_HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(_HEADERS)
        ):
            return _HEADERS[section]
        return None

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or index.row() >= len(self._entries):
            return None

        entry = self._entries[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(entry, col)

        if role == Qt.ItemDataRole.ForegroundRole:
            return self._foreground(entry, col)

        return None

    # ── Public API ─────────────────────────────────────────────────────────

    def add_files(self, paths: list[Path]) -> None:
        """Append *paths*, skipping duplicates already in the model."""
        new_paths = [p for p in paths if p not in self._path_index]
        if not new_paths:
            return
        first = len(self._entries)
        last = first + len(new_paths) - 1
        self.beginInsertRows(QModelIndex(), first, last)
        for p in new_paths:
            self._path_index[p] = len(self._entries)
            self._entries.append(FileEntry(path=p))
        self.endInsertRows()

    def remove_files(self, paths: list[Path]) -> None:
        """Remove *paths* from the model."""
        remove_set = set(paths)
        new_entries = [e for e in self._entries if e.path not in remove_set]
        if len(new_entries) == len(self._entries):
            return
        self.beginResetModel()
        self._entries = new_entries
        self._rebuild_index()
        self.endResetModel()

    def clear(self) -> None:
        if not self._entries:
            return
        self.beginResetModel()
        self._entries.clear()
        self._path_index.clear()
        self.endResetModel()

    def update_entry(self, path: Path, **kwargs: Any) -> None:
        """Update fields of the entry at *path* and emit dataChanged."""
        idx = self._path_index.get(path)
        if idx is None:
            return
        entry = self._entries[idx]
        for k, v in kwargs.items():
            setattr(entry, k, v)
        top_left = self.index(idx, 0)
        bot_right = self.index(idx, len(_HEADERS) - 1)
        self.dataChanged.emit(top_left, bot_right, [Qt.ItemDataRole.DisplayRole])

    def all_paths(self) -> list[Path]:
        return [e.path for e in self._entries]

    def album_groups(self) -> dict[str, list[Path]]:
        """Group file paths by their parent directory (album group key)."""
        groups: dict[str, list[Path]] = {}
        for e in self._entries:
            groups.setdefault(e.group_key, []).append(e.path)
        return groups

    def entry_at(self, row: int) -> FileEntry | None:
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    # ── Internal ───────────────────────────────────────────────────────────

    def _rebuild_index(self) -> None:
        self._path_index = {e.path: i for i, e in enumerate(self._entries)}

    def _display_value(self, entry: FileEntry, col: int) -> str:
        if col == _COL_PATH:
            return entry.path_and_file
        if col == _COL_VOLUME:
            return f"{entry.volume_db:.1f}" if entry.volume_db is not None else ""
        if col == _COL_CLIPPING:
            return _CLIP_YES if entry.clipping else ""
        if col == _COL_TRACK_GAIN:
            return (
                f"{entry.track_gain_db:.1f}" if entry.track_gain_db is not None else ""
            )
        if col == _COL_CLIP_TRACK:
            if entry.clip_track is None:
                return ""
            return f"{entry.clip_track:.1f}"
        if col == _COL_ALBUM_VOLUME:
            return (
                f"{entry.album_volume_db:.1f}"
                if entry.album_volume_db is not None
                else ""
            )
        if col == _COL_ALBUM_GAIN:
            return (
                f"{entry.album_gain_db:.1f}" if entry.album_gain_db is not None else ""
            )
        if col == _COL_CLIP_ALBUM:
            if entry.clip_album is None:
                return ""
            return f"{entry.clip_album:.1f}"
        return ""

    def _foreground(self, entry: FileEntry, col: int) -> QColor | None:
        if col == _COL_CLIPPING and entry.clipping:
            return _RED
        if (
            col == _COL_CLIP_TRACK
            and entry.clip_track is not None
            and entry.clip_track > 1.0
        ):
            return _RED
        if (
            col == _COL_CLIP_ALBUM
            and entry.clip_album is not None
            and entry.clip_album > 1.0
        ):
            return _RED
        return None
