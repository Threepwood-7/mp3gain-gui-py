"""WorkerBridge — Qt signal relay between background threads and the UI.

Workers run in daemon threads with no Qt access.  They call relay methods
on the bridge.  Qt signals are thread-safe: emitting from a non-owner thread
uses AutoConnection which queues to the receiver's thread automatically.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from .types import FileResult, WorkerRequest, WorkerResult


class WorkerBridge(QObject):
    """Qt signal hub for background MP3Gain workers."""

    file_started = Signal(object)   # Path
    file_done = Signal(object)      # FileResult
    all_done = Signal(object)       # WorkerResult
    progress = Signal(int, int)     # completed, total
    error = Signal(str)             # error message

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("worker_bridge")
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()
        self._active = False

    # ── Public control ────────────────────────────────────────────────────────

    def start_worker(self, request: WorkerRequest) -> None:
        """Spawn a background thread for *request*; cancel any running worker first."""
        with self._lock:
            if self._active:
                self._cancel_event.set()
            self._cancel_event.clear()
            self._active = True

        kind = request.kind
        if kind in ("track_analyze", "album_analyze"):
            from .analyze_worker import AnalyzeWorker  # noqa: PLC0415

            worker: Any = AnalyzeWorker(request, self)
        elif kind in ("apply_track", "apply_album", "apply_constant", "undo"):
            from .gain_worker import GainWorker  # noqa: PLC0415

            worker = GainWorker(request, self)
        else:
            from .tag_worker import TagWorker  # noqa: PLC0415

            worker = TagWorker(request, self)

        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()

    def cancel(self) -> None:
        """Signal the current worker to stop after the current file."""
        self._cancel_event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    # ── Relay methods called from worker threads ───────────────────────────────
    # Qt AutoConnection queues to the bridge's (main) thread automatically.

    def _relay_file_started(self, path: Path) -> None:
        self.file_started.emit(path)

    def _relay_file_done(self, result: FileResult) -> None:
        self.file_done.emit(result)

    def _relay_progress(self, completed: int, total: int) -> None:
        self.progress.emit(completed, total)

    def _relay_all_done(self, result: WorkerResult) -> None:
        with self._lock:
            self._active = False
        self.all_done.emit(result)

    def _relay_error(self, msg: str) -> None:
        self.error.emit(msg)
