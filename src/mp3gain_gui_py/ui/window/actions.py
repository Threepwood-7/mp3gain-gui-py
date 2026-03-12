"""WindowActionsCoordinator — toolbar, menus, and keyboard shortcuts."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMenu, QToolBar
from threep_commons.qt.slots import safe_slot

from ..._workers.types import WorkerRequest

if TYPE_CHECKING:
    from ..._settings.manager import SettingsManager
    from ..._workers.worker_bridge import WorkerBridge
    from .._main_window import MainWindow


class WindowActionsCoordinator:
    """Creates and manages toolbar actions and menus for *window*."""

    def __init__(
        self,
        window: MainWindow,
        settings: SettingsManager,
        bridge: WorkerBridge,
    ) -> None:
        self._window = window
        self._settings = settings
        self._bridge = bridge

        self._build_actions()
        self._build_toolbar()
        self._build_menus()

    # ── Action construction ───────────────────────────────────────────────────

    def _build_actions(self) -> None:
        w = self._window

        self.act_add_files = QAction("Add Files...", w)
        self.act_add_files.setShortcut(QKeySequence("Ctrl+O"))

        self.act_add_folder = QAction("Add Folder...", w)
        self.act_add_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))

        self.act_remove = QAction("Remove Selected", w)
        self.act_remove.setShortcut(QKeySequence.StandardKey.Delete)

        self.act_clear = QAction("Clear List", w)

        self.act_track_analyze = QAction("Track Analysis", w)
        self.act_album_analyze = QAction("Album Analysis", w)

        self.act_apply_track = QAction("Apply Track Gain", w)
        self.act_apply_album = QAction("Apply Album Gain", w)
        self.act_apply_constant = QAction("Apply Constant Gain...", w)
        self.act_undo = QAction("Undo Gain Change", w)
        self.act_delete_tags = QAction("Delete Tags", w)

        self.act_cancel = QAction("Cancel", w)
        self.act_cancel.setEnabled(False)

        self.act_options = QAction("Options...", w)
        self.act_about = QAction("About...", w)

        # Connect
        self.act_add_files.triggered.connect(self._on_add_files)
        self.act_add_folder.triggered.connect(self._on_add_folder)
        self.act_remove.triggered.connect(self._on_remove)
        self.act_clear.triggered.connect(self._on_clear)
        self.act_track_analyze.triggered.connect(self._on_track_analyze)
        self.act_album_analyze.triggered.connect(self._on_album_analyze)
        self.act_apply_track.triggered.connect(self._on_apply_track)
        self.act_apply_album.triggered.connect(self._on_apply_album)
        self.act_apply_constant.triggered.connect(self._on_apply_constant)
        self.act_undo.triggered.connect(self._on_undo)
        self.act_delete_tags.triggered.connect(self._on_delete_tags)
        self.act_cancel.triggered.connect(self._on_cancel)
        self.act_options.triggered.connect(self._on_options)
        self.act_about.triggered.connect(self._on_about)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main", self._window)
        tb.setObjectName("main_toolbar")
        self._window.addToolBar(tb)

        tb.addAction(self.act_add_files)
        tb.addAction(self.act_add_folder)
        tb.addSeparator()
        tb.addAction(self.act_track_analyze)
        tb.addAction(self.act_album_analyze)
        tb.addSeparator()
        tb.addAction(self.act_apply_track)
        tb.addAction(self.act_apply_album)
        tb.addAction(self.act_apply_constant)
        tb.addSeparator()
        tb.addAction(self.act_undo)
        tb.addAction(self.act_delete_tags)
        tb.addSeparator()
        tb.addAction(self.act_cancel)
        tb.addSeparator()
        tb.addAction(self.act_options)

    def _build_menus(self) -> None:
        mb = self._window.menuBar()
        if mb is None:
            return

        # File menu
        file_menu: QMenu = mb.addMenu("&File")  # type: ignore[assignment]
        file_menu.addAction(self.act_add_files)
        file_menu.addAction(self.act_add_folder)
        file_menu.addSeparator()
        file_menu.addAction(self.act_remove)
        file_menu.addAction(self.act_clear)
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self._window.close)

        # Analysis menu
        analysis_menu: QMenu = mb.addMenu("&Analysis")  # type: ignore[assignment]
        analysis_menu.addAction(self.act_track_analyze)
        analysis_menu.addAction(self.act_album_analyze)

        # Gain menu
        gain_menu: QMenu = mb.addMenu("&Gain")  # type: ignore[assignment]
        gain_menu.addAction(self.act_apply_track)
        gain_menu.addAction(self.act_apply_album)
        gain_menu.addAction(self.act_apply_constant)
        gain_menu.addSeparator()
        gain_menu.addAction(self.act_undo)
        gain_menu.addAction(self.act_delete_tags)

        # Options menu
        options_menu: QMenu = mb.addMenu("&Options")  # type: ignore[assignment]
        options_menu.addAction(self.act_options)

        # Help menu
        help_menu: QMenu = mb.addMenu("&Help")  # type: ignore[assignment]
        help_menu.addAction(self.act_about)

    # ── Slot implementations ─────────────────────────────────────────────────

    @safe_slot
    def _on_add_files(self) -> None:
        last_dir = self._settings.last_add_files_dir
        paths, _ = QFileDialog.getOpenFileNames(
            self._window,
            "Add MP3 Files",
            last_dir or "",
            "MP3 Files (*.mp3);;All Files (*)",
        )
        if not paths:
            return
        file_paths = [Path(p) for p in paths]
        self._settings.last_add_files_dir = str(file_paths[0].parent)
        self._window.model.add_files(file_paths)

    @safe_slot
    def _on_add_folder(self) -> None:
        last_dir = self._settings.last_add_folder_dir
        folder = QFileDialog.getExistingDirectory(
            self._window, "Add Folder", last_dir or ""
        )
        if not folder:
            return
        self._settings.last_add_folder_dir = folder

        folder_path = Path(folder)
        if self._settings.add_subfolders:
            mp3s = sorted(folder_path.rglob("*.mp3"))
        else:
            mp3s = sorted(folder_path.glob("*.mp3"))
        self._window.model.add_files(mp3s)

    @safe_slot
    def _on_remove(self) -> None:
        rows = self._window.layout_coord.selected_rows()
        paths = [
            e.path for i in rows if (e := self._window.model.entry_at(i)) is not None
        ]
        if paths:
            self._window.model.remove_files(paths)

    @safe_slot
    def _on_clear(self) -> None:
        self._window.model.clear()

    @safe_slot
    def _on_track_analyze(self) -> None:
        paths = self._window.model.all_paths()
        if not paths:
            return
        req = WorkerRequest(
            kind="track_analyze",
            paths=paths,
            target_db=self._settings.target_volume_db,
            tag_mode=self._settings.tag_mode,
            stored_tag_policy=self._settings.stored_tag_policy,
        )
        self._start_worker(req)

    @safe_slot
    def _on_album_analyze(self) -> None:
        paths = self._window.model.all_paths()
        if not paths:
            return
        req = WorkerRequest(
            kind="album_analyze",
            paths=paths,
            album_groups=self._window.model.album_groups(),
            target_db=self._settings.target_volume_db,
            tag_mode=self._settings.tag_mode,
            stored_tag_policy=self._settings.stored_tag_policy,
        )
        self._start_worker(req)

    @safe_slot
    def _on_apply_track(self) -> None:
        paths = self._window.model.all_paths()
        if not paths:
            return
        req = WorkerRequest(
            kind="apply_track",
            paths=paths,
            target_db=self._settings.target_volume_db,
            tag_mode=self._settings.tag_mode,
            stored_tag_policy=self._settings.stored_tag_policy,
            wrap_gain=self._settings.wrap_gain,
            preserve_dates=self._settings.preserve_dates,
            force_apply_normalization=self._settings.force_apply_normalization,
            apply_zero_step=self._settings.apply_zero_step,
        )
        self._start_worker(req)

    @safe_slot
    def _on_apply_album(self) -> None:
        paths = self._window.model.all_paths()
        if not paths:
            return
        req = WorkerRequest(
            kind="apply_album",
            paths=paths,
            album_groups=self._window.model.album_groups(),
            target_db=self._settings.target_volume_db,
            tag_mode=self._settings.tag_mode,
            stored_tag_policy=self._settings.stored_tag_policy,
            wrap_gain=self._settings.wrap_gain,
            preserve_dates=self._settings.preserve_dates,
            force_apply_normalization=self._settings.force_apply_normalization,
            apply_zero_step=self._settings.apply_zero_step,
        )
        self._start_worker(req)

    @safe_slot
    def _on_apply_constant(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        paths = self._window.model.all_paths()
        if not paths:
            return
        db, ok = QInputDialog.getDouble(
            self._window,
            "Apply Constant Gain",
            "Gain (dB):",
            0.0,
            -60.0,
            60.0,
            1,
        )
        if not ok:
            return
        req = WorkerRequest(
            kind="apply_constant",
            paths=paths,
            constant_db=db,
            tag_mode=self._settings.tag_mode,
            stored_tag_policy=self._settings.stored_tag_policy,
            wrap_gain=self._settings.wrap_gain,
            preserve_dates=self._settings.preserve_dates,
        )
        self._start_worker(req)

    @safe_slot
    def _on_undo(self) -> None:
        paths = self._window.model.all_paths()
        if not paths:
            return
        req = WorkerRequest(
            kind="undo",
            paths=paths,
            tag_mode=self._settings.tag_mode,
            stored_tag_policy=self._settings.stored_tag_policy,
            wrap_gain=self._settings.wrap_gain,
            preserve_dates=self._settings.preserve_dates,
        )
        self._start_worker(req)

    @safe_slot
    def _on_delete_tags(self) -> None:
        paths = self._window.model.all_paths()
        if not paths:
            return
        req = WorkerRequest(kind="delete_tags", paths=paths)
        self._start_worker(req)

    @safe_slot
    def _on_cancel(self) -> None:
        self._bridge.cancel()

    @safe_slot
    def _on_options(self) -> None:
        from ..dialogs.options_dialog import OptionsDialog

        dlg = OptionsDialog(self._settings, self._window)
        dlg.exec()

    @safe_slot
    def _on_about(self) -> None:
        from ..dialogs.about_dialog import AboutDialog

        dlg = AboutDialog(self._window)
        dlg.exec()

    def _start_worker(self, req: WorkerRequest) -> None:
        self.act_cancel.setEnabled(True)
        self._bridge.start_worker(req)

    def set_worker_active(self, active: bool) -> None:
        self.act_cancel.setEnabled(active)
        for act in (
            self.act_track_analyze,
            self.act_album_analyze,
            self.act_apply_track,
            self.act_apply_album,
            self.act_apply_constant,
            self.act_undo,
            self.act_delete_tags,
        ):
            act.setEnabled(not active)
