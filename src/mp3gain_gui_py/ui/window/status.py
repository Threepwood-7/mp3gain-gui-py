"""WindowStatusCoordinator — status bar management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QStatusBar

if TYPE_CHECKING:
    from .._main_window import MainWindow


class WindowStatusCoordinator:
    """Manages a 3-panel status bar: message | current file | ETA."""

    def __init__(self, window: MainWindow) -> None:
        bar: QStatusBar = window.statusBar()  # type: ignore[assignment]
        bar.setSizeGripEnabled(True)

        self._msg_label = QLabel("Ready")
        self._file_label = QLabel()
        self._eta_label = QLabel()

        bar.addWidget(self._msg_label, 2)
        bar.addWidget(self._file_label, 3)
        bar.addPermanentWidget(self._eta_label, 1)

    def set_message(self, text: str) -> None:
        self._msg_label.setText(text)

    def set_current_file(self, text: str) -> None:
        self._file_label.setText(text)

    def set_eta(self, text: str) -> None:
        self._eta_label.setText(text)

    def clear(self) -> None:
        self._msg_label.setText("Ready")
        self._file_label.setText("")
        self._eta_label.setText("")
