"""MainWindow — top-level coordinator of coordinators."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QMainWindow, QMessageBox
from threep_commons.qt.slots import safe_slot

from .._model.file_list_model import FileListModel
from .._workers.types import FileResult, WorkerResult
from .window.actions import WindowActionsCoordinator
from .window.layout import WindowLayoutCoordinator
from .window.persistence import WindowPersistenceCoordinator
from .window.status import WindowStatusCoordinator

if TYPE_CHECKING:
    from .._settings.manager import SettingsManager
    from .._workers.worker_bridge import WorkerBridge
    from ..app_controller import AppController


class MainWindow(QMainWindow):
    """Main application window — delegates to four coordinator objects."""

    def __init__(
        self,
        controller: AppController,
        settings: SettingsManager,
        bridge: WorkerBridge,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("main_window")
        self.setWindowTitle("MP3Gain")
        self.resize(900, 500)

        self._controller = controller
        self._settings = settings
        self._bridge = bridge

        # Model
        self.model: FileListModel = FileListModel(parent=self)

        # Coordinators
        self.layout_coord: WindowLayoutCoordinator = WindowLayoutCoordinator(
            self, self.model
        )
        self.status_coord: WindowStatusCoordinator = WindowStatusCoordinator(self)
        self._actions = WindowActionsCoordinator(self, settings, bridge)
        self._persistence = WindowPersistenceCoordinator(
            self, settings, self.layout_coord
        )

        # Apply saved target volume
        self.layout_coord.target_volume_spin.setValue(settings.target_volume_db)
        self.layout_coord.target_volume_spin.valueChanged.connect(
            self._on_target_volume_changed
        )

        # Bridge signals
        bridge.file_started.connect(self._on_file_started)
        bridge.file_done.connect(self._on_file_done)
        bridge.all_done.connect(self._on_all_done)
        bridge.progress.connect(self._on_progress)
        bridge.error.connect(self._on_bridge_error)

        # Accept file drops on window
        self.setAcceptDrops(True)

    # ── Session ───────────────────────────────────────────────────────────────

    def restore_session(self) -> None:
        self._persistence.restore()

    def save_session(self) -> None:
        self._persistence.save()

    # ── Close event ───────────────────────────────────────────────────────────

    def closeEvent(self, event: Any) -> None:
        self.save_session()
        super().closeEvent(event)

    # ── Drag-and-drop ─────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: Any) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: Any) -> None:
        urls = event.mimeData().urls()
        paths: list[Path] = []
        for url in urls:
            p = Path(url.toLocalFile())
            if p.is_file() and p.suffix.lower() == ".mp3":
                paths.append(p)
            elif p.is_dir():
                if self._settings.add_subfolders:
                    paths.extend(sorted(p.rglob("*.mp3")))
                else:
                    paths.extend(sorted(p.glob("*.mp3")))
        if paths:
            self.model.add_files(paths)

    # ── Bridge signal handlers ────────────────────────────────────────────────

    @safe_slot
    def _on_file_started(self, path: object) -> None:
        if isinstance(path, Path):
            self.status_coord.set_current_file(str(path.name))

    @safe_slot
    def _on_file_done(self, result: Any) -> None:
        if not isinstance(result, FileResult):
            return
        kwargs: dict[str, Any] = {}
        if result.volume_db is not None:
            kwargs["volume_db"] = result.volume_db
        if result.track_gain_db is not None:
            kwargs["track_gain_db"] = result.track_gain_db
        if result.album_gain_db is not None:
            kwargs["album_gain_db"] = result.album_gain_db
        if result.max_amplitude is not None:
            kwargs["max_amplitude"] = result.max_amplitude
        if result.min_gain_field is not None:
            kwargs["min_gain_field"] = result.min_gain_field
        if result.max_gain_field is not None:
            kwargs["max_gain_field"] = result.max_gain_field
        kwargs["clipping"] = result.clipping
        if result.clip_track is not None:
            kwargs["clip_track"] = result.clip_track
        if result.album_volume_db is not None:
            kwargs["album_volume_db"] = result.album_volume_db
        if result.clip_album is not None:
            kwargs["clip_album"] = result.clip_album
        if not result.ok:
            kwargs["status"] = "error"
            kwargs["error_msg"] = result.error_msg
        else:
            kwargs["status"] = "done"
        self.model.update_entry(result.path, **kwargs)

    @safe_slot
    def _on_all_done(self, result: Any) -> None:
        if not isinstance(result, WorkerResult):
            return
        self._actions.set_worker_active(False)
        self.layout_coord.show_progress(False)
        self.status_coord.clear()
        msg = (
            f"{result.kind}: {result.succeeded} OK"
            + (f", {result.failed} failed" if result.failed else "")
            + (" (cancelled)" if result.cancelled else "")
        )
        self.status_coord.set_message(msg)

    @safe_slot
    def _on_progress(self, completed: int, total: int) -> None:
        self.layout_coord.show_progress(True)
        self.layout_coord.set_progress(completed, 1, completed, total)

    @safe_slot
    def _on_bridge_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Error", msg)

    @safe_slot
    def _on_target_volume_changed(self, value: float) -> None:
        self._settings.target_volume_db = value
